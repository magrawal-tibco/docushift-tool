"""Additive catalog manager backed by the CSV pair.

Storage is `config/products.csv` + `config/versions.csv`, normalized on
the docsite `slug` (docs/architecture.md §3), which is the only product identifier
the source system guarantees unique. Merging is a **snapshot-based 3-way
merge**: `state.db` holds what discovery wrote last (*base*), the CSV holds what
the user has since edited (*mine*), and a fetch supplies *theirs*. Any field where
`mine != base` is inferred to be a human edit and is preserved -- no protection
flag required, because expecting a user to tick one on each edited row of a
4,000-row sheet guarantees silent data loss.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from docushift.models import (
    CONVERTIBLE_ENGINES,
    Catalog,
    EngineSource,
    FamilySource,
    Product,
    ProductVersion,
    ScopeSource,
    SourceEngine,
    ZipSource,
)
from docushift.state import StateStore
from docushift.utils.csvio import (
    format_bool,
    format_optional_bool,
    format_optional_int,
    natural_version_key,
    normalize_date,
    parse_bool,
    parse_optional_bool,
    parse_optional_int,
    read_rows,
    write_rows,
)

if TYPE_CHECKING:  # pragma: no cover - import kept lazy to avoid a config <-> catalog cycle
    from docushift.config import ConfigManager

PRODUCT_COLUMNS = (
    # First because it is the key: the column `versions.csv` joins on and every
    # `state.db` table is keyed by. `product_code` follows it as a short label and
    # is explicitly **not** unique -- see `Product.slug`.
    "slug",
    "product_code",
    "display_name",
    "bu",
    "family",
    "family_source",
    # The outermost selection gate (architecture.md §3.10). Resolved from
    # `config/scope.yaml` at merge time and carried here so the sheet shows the
    # answer without anyone opening the YAML.
    "in_scope",
    "scope_source",
    "custom_override",
)

# `_bu` / `_family` are denormalized from products.csv so the sheet can be filtered
# by family without a VLOOKUP. They are regenerated on every write and edits to
# them are ignored -- see docs/architecture.md §3.2.
VERSION_COLUMNS = (
    "slug",
    "version",
    "is_archived",
    "convert_eligible",
    "convert_batch",
    "release_date",
    "engine",
    "engine_source",
    "zip_url",
    "zip_source",
    "custom_override",
    "_bu",
    "_family",
    # Stage 4 inventory (architecture.md §3.9). Underscored like `_bu`/`_family`
    # because they are tool-owned and edits are ignored, but unlike those two they
    # are *not* regenerated on every write -- they persist between extract runs,
    # the way `engine` does.
    "_has_csh",
    "_csh_names",
    "_has_api_ref",
    "_api_files",
    "_doc_files",
)

# The `versions.csv` column each inventory field round-trips through.
_INVENTORY_COLUMNS = (
    ("has_csh", "_has_csh"),
    ("csh_names", "_csh_names"),
    ("has_api_ref", "_has_api_ref"),
    ("api_files", "_api_files"),
    ("doc_files", "_doc_files"),
)

# Fields discovery owns and may therefore update. `family` is handled separately
# because `family_source=manual` outranks any fetch. `in_scope`/`scope_source` are
# absent structurally: they are a local policy call resolved from `scope.yaml`, and
# the docsite has no value to three-way-merge against -- so `product_snapshot`
# carries neither and there is no rule needed to stop a fetch overwriting them.
# `slug` is absent for a third reason again: it is the key, so a fetch that changed
# it would be describing a different product, not an edit to this one.
_MERGEABLE_PRODUCT_FIELDS = ("display_name", "product_code")
# Engine fields are absent by design: the detector writes them, not discovery.
# `convert_batch` is absent for the same structural reason from the other side --
# it is purely a human scheduling decision, so a fetch has nothing true to say
# about it and it is excluded from `version_snapshot` entirely. `zip_source` is
# excluded on the same grounds: it records a human's decision to supply the
# package by hand, which a fetch has no standing to revoke. Note `zip_url` *is*
# merged even on a manual row -- recording the endpoint discovery has since found
# is what makes "you can drop the pin now" a computable warning.
_MERGEABLE_VERSION_FIELDS = ("is_archived", "convert_eligible", "release_date", "zip_url")


class CatalogError(Exception):
    """Raised when an import would lose data, e.g. an unexplained missing row."""


@dataclass
class MergeStats:
    """What a fetch actually changed. Reported by `docushift catalog fetch`."""
    products_added: int = 0
    products_updated: int = 0
    versions_added: int = 0
    versions_updated: int = 0
    fields_preserved: int = 0
    products_out_of_scope: int = 0
    deletions_blocked: list[str] = field(default_factory=list)
    # Slugs in `scope.yaml` that matched no product this fetch touched. Almost
    # always an upstream rename, which is how an exclusion silently stops working.
    scope_rules_unmatched: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "products_added": self.products_added,
            "products_updated": self.products_updated,
            "versions_added": self.versions_added,
            "versions_updated": self.versions_updated,
            "fields_preserved": self.fields_preserved,
            "products_out_of_scope": self.products_out_of_scope,
            "deletions_blocked": list(self.deletions_blocked),
            "scope_rules_unmatched": list(self.scope_rules_unmatched),
        }


class CatalogManager:
    """Loads, merges, and writes the catalog CSV pair."""

    def __init__(
        self,
        products_path: Path,
        versions_path: Path,
        state: StateStore | None = None,
        config: "ConfigManager | None" = None,
    ):
        self.products_path = products_path
        self.versions_path = versions_path
        self.state = state
        # Only needed to check family names against taxonomy.yaml. Optional, because
        # an unknown family is a warning, not an error -- see `warnings()`.
        self.config = config
        self._catalog: Catalog | None = None
        # Slugs seen more than once in products.csv on the last `load()`. Only a
        # hand-edit can produce one -- discovery's keys are unique -- and it is
        # reported by `validate()` rather than raised, so the sheet stays openable.
        self._duplicate_slugs: list[str] = []

    # -- load / save ---------------------------------------------------------

    def load(self) -> Catalog:
        """Reads both CSVs. Missing files yield an empty catalog, not an error."""
        if self._catalog is not None:
            return self._catalog

        catalog = Catalog()
        self._duplicate_slugs = []
        for row in read_rows(self.products_path):
            slug = row.get("slug", "").strip().lower()
            if not slug:
                continue
            # Last row wins, and the loser is recorded rather than lost silently:
            # `validate()` reports it, so `catalog import` refuses the sheet before
            # a `save()` writes the collapsed version back over the original.
            if slug in catalog.products:
                self._duplicate_slugs.append(slug)
            catalog.products[slug] = Product(
                slug=slug,
                product_code=row.get("product_code", "").strip() or slug,
                display_name=row.get("display_name", "").strip() or slug,
                bu=row.get("bu", "").strip().lower() or "tibco",
                family=row.get("family", "").strip().lower() or "general",
                family_source=_coerce_enum(FamilySource, row.get("family_source"), FamilySource.UNCLASSIFIED),
                # Read through the *optional* parser, then defaulted to true: only
                # an explicit `false` excludes. `parse_bool` cannot express this --
                # it treats a blank cell as `false` outright, ignoring its own
                # default -- and a blank cell in a hand-added row must never
                # silently drop the product out of every stage of the pipeline.
                in_scope=parse_optional_bool(row.get("in_scope")) is not False,
                scope_source=_coerce_enum(ScopeSource, row.get("scope_source"), ScopeSource.DEFAULT),
                custom_override=parse_bool(row.get("custom_override")),
            )

        for row in read_rows(self.versions_path):
            slug = row.get("slug", "").strip().lower()
            version = row.get("version", "").strip()
            if not slug or not version:
                continue
            product = catalog.products.get(slug)
            if product is None:
                # A version row with no product row is a broken join, not a product.
                raise CatalogError(
                    f"versions.csv references unknown slug '{slug}' (version '{version}'). "
                    f"Add the product to products.csv or remove the orphaned version row."
                )
            is_archived = parse_bool(row.get("is_archived"))
            product.versions[version] = ProductVersion(
                slug=slug,
                version=version,
                is_archived=is_archived,
                convert_eligible=parse_bool(row.get("convert_eligible"), default=not is_archived),
                convert_batch=row.get("convert_batch", "").strip().lower(),
                release_date=normalize_date(row.get("release_date")) or None,
                engine=_coerce_enum(SourceEngine, row.get("engine"), SourceEngine.AUTO),
                engine_source=_coerce_enum(EngineSource, row.get("engine_source"), EngineSource.AUTO),
                zip_url=row.get("zip_url", "").strip() or None,
                zip_source=_coerce_enum(ZipSource, row.get("zip_source"), ZipSource.AUTO),
                custom_override=parse_bool(row.get("custom_override")),
                # Nullable on purpose -- a blank cell means "never extracted" and
                # must not read as `false`/`0` (architecture.md §3.9).
                has_csh=parse_optional_bool(row.get("_has_csh")),
                csh_names=parse_optional_int(row.get("_csh_names")),
                has_api_ref=parse_optional_bool(row.get("_has_api_ref")),
                api_files=parse_optional_int(row.get("_api_files")),
                doc_files=parse_optional_int(row.get("_doc_files")),
            )

        self._catalog = catalog
        return catalog

    def save(self) -> None:
        """Writes both CSVs with a fixed column order and a stable sort.

        The sort is what makes a no-op fetch produce a zero-line diff: products by
        `(bu, family, slug)`, versions by product then version descending
        using a natural sort, so `10.4.0` sits above `9.1.0`.
        """
        catalog = self.load()

        products = sorted(catalog.products.values(), key=lambda p: (p.bu, p.family, p.slug))
        write_rows(
            self.products_path,
            PRODUCT_COLUMNS,
            [
                {
                    "slug": p.slug,
                    "product_code": p.product_code,
                    "display_name": p.display_name,
                    "bu": p.bu,
                    "family": p.family,
                    "family_source": str(p.family_source),
                    "in_scope": format_bool(p.in_scope),
                    "scope_source": str(p.scope_source),
                    "custom_override": format_bool(p.custom_override),
                }
                for p in products
            ],
        )

        version_rows = []
        for product in products:
            for version in sorted(
                product.versions.values(), key=lambda v: natural_version_key(v.version), reverse=True
            ):
                version_rows.append(
                    {
                        "slug": product.slug,
                        "version": version.version,
                        "is_archived": format_bool(version.is_archived),
                        "convert_eligible": format_bool(version.convert_eligible),
                        "convert_batch": version.convert_batch,
                        "release_date": normalize_date(version.release_date),
                        "engine": str(version.engine),
                        "engine_source": str(version.engine_source),
                        "zip_url": version.zip_url or "",
                        "zip_source": str(version.zip_source),
                        "custom_override": format_bool(version.custom_override),
                        "_bu": product.bu,
                        "_family": product.family,
                        "_has_csh": format_optional_bool(version.has_csh),
                        "_csh_names": format_optional_int(version.csh_names),
                        "_has_api_ref": format_optional_bool(version.has_api_ref),
                        "_api_files": format_optional_int(version.api_files),
                        "_doc_files": format_optional_int(version.doc_files),
                    }
                )
        write_rows(self.versions_path, VERSION_COLUMNS, version_rows)

    # -- accessors -----------------------------------------------------------

    def get_product(self, slug: str) -> Product | None:
        return self.load().products.get(slug)

    def resolve_slug(self, selector: str) -> str:
        """Turns whatever a human typed at `--product` into a catalog key.

        A slug is returned as-is. A `product_code` is resolved to the slug of the
        product carrying it -- which is the whole reason this exists: `ems` is a
        code, `tibco-enterprise-message-service` is the key, and demanding the
        latter on the command line for the sake of an internal rename would be a
        poor trade.

        An **ambiguous** code raises rather than picking one. Ten codes are shared
        by twenty-one products and one of those pairs straddles the scope boundary,
        so silently resolving `stat-sts` to whichever product sorted first is
        exactly the class of bug this re-key was done to remove.

        An unknown selector is returned unchanged, so callers keep their own
        "no such product" message -- and `--product <slug>` still works before the
        first fetch, when the catalog is empty.
        """
        selector = selector.strip().lower()
        catalog = self.load()
        if selector in catalog.products:
            return selector
        matches = sorted(p.slug for p in catalog.products.values() if p.product_code == selector)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise CatalogError(
                f"'{selector}' is a product_code shared by {len(matches)} products, and product_code is not "
                f"unique. Pass one of these slugs instead: " + ", ".join(matches)
            )
        return selector

    def get_version(self, slug: str, version: str) -> ProductVersion | None:
        product = self.get_product(slug)
        return product.versions.get(version) if product else None

    def iter_versions(
        self,
        bu: str | None = None,
        family: str | None = None,
        slug: str | None = None,
        version: str | None = None,
        batch: str | None = None,
        eligible_only: bool = False,
    ) -> list[tuple[Product, ProductVersion]]:
        """Filtered `(product, version)` pairs, in catalog sort order.

        The three gates compose rather than override, outside in (§3.7): scope,
        then eligibility, then the batch. `batch="poc-1"` with `eligible_only=True`
        yields the versions that are both scheduled and permitted -- a row tagged
        into a batch but left `convert_eligible=false` is still excluded -- and no
        version of an out-of-scope product is yielded at all.

        The scope gate is deliberately conditioned on `eligible_only` rather than
        applied unconditionally, so that reporting and inventory callers (which
        pass `eligible_only=False`) still see excluded products. An out-of-scope
        product is absent from the *work*, never from the *books* (§3.10).
        """
        catalog = self.load()
        results = []
        for product in sorted(catalog.products.values(), key=lambda p: (p.bu, p.family, p.slug)):
            if bu and product.bu != bu.lower():
                continue
            if family and product.family != family.lower():
                continue
            if slug and product.slug != slug:
                continue
            if eligible_only and not product.in_scope:
                continue
            for ver in sorted(product.versions.values(), key=lambda v: natural_version_key(v.version), reverse=True):
                if version and ver.version != version:
                    continue
                if batch and ver.convert_batch != batch.strip().lower():
                    continue
                if eligible_only and not ver.convert_eligible:
                    continue
                results.append((product, ver))
        return results

    def batches(self) -> dict[str, int]:
        """Version counts per `convert_batch` label, so a run's scope is checkable.

        Unscheduled rows are omitted rather than grouped under `""` -- "how many
        versions are in wave-2" is the question this answers, and folding 3,900
        untagged rows into the same table would bury it.
        """
        counts: dict[str, int] = {}
        for _, ver in self.iter_versions():
            if ver.convert_batch:
                counts[ver.convert_batch] = counts.get(ver.convert_batch, 0) + 1
        return dict(sorted(counts.items()))

    # -- merge ---------------------------------------------------------------

    def merge_fetch_results(
        self,
        discovered: list[Product],
        allow_deletes: bool = False,
        dry_run: bool = False,
    ) -> MergeStats:
        """Snapshot-based 3-way merge of a discovery result into the catalog.

        Deletion is scoped to the products actually fetched, so a `--product ems`
        run can never remove anything belonging to another product.
        """
        catalog = self.load()
        stats = MergeStats()
        scope_rules = self._scope_rules()

        for incoming in discovered:
            slug = incoming.slug
            mine = catalog.products.get(slug)

            if mine is None:
                catalog.products[slug] = incoming
                stats.products_added += 1
                stats.versions_added += len(incoming.versions)
            else:
                stats.products_updated += 1
                stats.fields_preserved += self._merge_product(mine, incoming)
                added, updated, preserved = self._merge_versions(mine, incoming)
                stats.versions_added += added
                stats.versions_updated += updated
                stats.fields_preserved += preserved

            # Applied to new and existing products alike, so a product first seen
            # after the rule was written is excluded on arrival rather than
            # converted once and excluded afterwards.
            product = catalog.products[slug]
            _resolve_scope(product, scope_rules)
            if not product.in_scope:
                stats.products_out_of_scope += 1

            blocked = self._collect_deletions(catalog.products[slug], incoming)
            if blocked:
                if allow_deletes:
                    for gone in blocked:
                        del catalog.products[slug].versions[gone]
                        if self.state:
                            self.state.forget_version(slug, gone)
                else:
                    stats.deletions_blocked.extend(f"{slug}@{v}" for v in blocked)

        # Computed against the whole catalog, not just the products this fetch
        # touched: on a scoped fetch every other rule would look unmatched.
        stats.scope_rules_unmatched = self.unmatched_scope_rules()

        if stats.deletions_blocked and not allow_deletes:
            raise CatalogError(
                "Fetch would remove catalog rows that discovery no longer returns: "
                + ", ".join(sorted(stats.deletions_blocked))
                + ". This usually means a version key was mangled (Excel reads '1.10' as '1.1'). "
                + "Re-run with --allow-deletes if the removal is intended."
            )

        if not dry_run:
            self._record_snapshots(discovered)
            self.save()

        return stats

    def _scope_rules(self) -> dict[str, str]:
        """`{slug: reason}` from `config/scope.yaml`, or empty with no config."""
        return self.config.load_scope() if self.config is not None else {}

    def unmatched_scope_rules(self) -> list[str]:
        """Scope rules whose slug matches no product in the catalog -- §3.10.

        The day a rule stops matching is the day the exclusion stops working, and
        the usual cause is an upstream rename. Reported rather than ignored,
        because silence is indistinguishable from success here.

        Note this is only conclusive over a fully fetched catalog: before the first
        `catalog fetch --all`, a rule matches nothing simply because its product has
        not been discovered yet. Callers say so when they present the list.
        """
        known = set(self.load().products)
        return sorted(slug for slug in self._scope_rules() if slug not in known)

    def _merge_product(self, mine: Product, theirs: Product) -> int:
        """Merges discovery-owned product fields. Returns the count preserved."""
        if mine.custom_override:
            # Explicit whole-row pin: ignore every upstream change.
            return len(_MERGEABLE_PRODUCT_FIELDS) + 1

        base = self.state.get_product_snapshot(mine.slug) if self.state else None
        preserved = 0

        for name in _MERGEABLE_PRODUCT_FIELDS:
            if self._take_theirs(mine, theirs, base, name):
                setattr(mine, name, getattr(theirs, name))
            else:
                preserved += 1

        # `family` carries provenance, so precedence beats the snapshot: a manual
        # assignment is never overwritten, and a fetch may only improve on a source
        # of equal or lower confidence.
        if mine.family_source is FamilySource.MANUAL:
            preserved += 1
        elif _family_rank(theirs.family_source) <= _family_rank(mine.family_source):
            if self._take_theirs(mine, theirs, base, "family"):
                mine.family = theirs.family
                mine.family_source = theirs.family_source
                mine.bu = theirs.bu
            else:
                preserved += 1
        else:
            preserved += 1

        return preserved

    def _merge_versions(self, mine: Product, theirs: Product) -> tuple[int, int, int]:
        added = updated = preserved = 0

        for key, incoming in theirs.versions.items():
            existing = mine.versions.get(key)
            if existing is None:
                mine.versions[key] = incoming
                added += 1
                continue

            updated += 1
            if existing.custom_override:
                preserved += len(_MERGEABLE_VERSION_FIELDS)
                continue

            base = self.state.get_version_snapshot(mine.slug, key) if self.state else None
            for name in _MERGEABLE_VERSION_FIELDS:
                if self._take_theirs(existing, incoming, base, name):
                    setattr(existing, name, getattr(incoming, name))
                else:
                    preserved += 1

        return added, updated, preserved

    @staticmethod
    def _take_theirs(mine: object, theirs: object, base: dict | None, name: str) -> bool:
        """The 3-way decision for one field: `theirs` wins unless a human moved it.

        With no snapshot (first fetch after adopting the state DB) there is no base
        to compare against, so the conservative reading is that the CSV value is the
        user's and is kept.
        """
        mine_value = getattr(mine, name)
        if base is None:
            return mine_value in (None, "")
        return _as_text(mine_value) == _as_text(base.get(name))

    @staticmethod
    def _collect_deletions(mine: Product, theirs: Product) -> list[str]:
        """Version keys the catalog has that this fetch of the same product did not return."""
        return sorted(set(mine.versions) - set(theirs.versions))

    def _record_snapshots(self, discovered: list[Product]) -> None:
        """Writes the new merge base: what discovery said, this fetch.

        One transaction for the whole pass, which is both faster and more correct
        than one per row -- a half-written base would read as a set of unflagged
        manual edits on the next fetch.
        """
        if self.state is None:
            return
        with self.state.transaction():
            for product in discovered:
                self.state.record_product_snapshot(product)
                for version in product.versions.values():
                    self.state.record_version_snapshot(version)

    # -- edits ---------------------------------------------------------------

    def set_conversion_eligibility(self, slug: str, version: str, eligible: bool) -> bool:
        """Toggles `convert_eligible`. The snapshot makes this survive the next fetch."""
        target = self.get_version(slug, version)
        if target is None:
            return False
        target.convert_eligible = eligible
        self.save()
        return True

    def set_product_field(self, slug: str, name: str, value: str) -> bool:
        """Sets a product field. Setting `family` also pins its provenance to manual."""
        product = self.get_product(slug)
        if product is None:
            return False
        if name == "family":
            product.family = value.lower()
            product.family_source = FamilySource.MANUAL
        elif name == "bu":
            product.bu = value.lower()
        elif name == "display_name":
            product.display_name = value
        elif name == "slug":
            product.slug = value or None
        elif name == "in_scope":
            # Pinned to manual either way. Putting a product back in scope has to
            # outrank scope.yaml or the next fetch would undo it; taking one out by
            # hand records the same provenance so the two are read the same way.
            product.in_scope = parse_bool(value)
            product.scope_source = ScopeSource.MANUAL
        elif name == "custom_override":
            product.custom_override = parse_bool(value)
        else:
            raise CatalogError(f"'{name}' is not a settable products.csv field")
        self.save()
        return True

    def set_version_field(self, slug: str, version: str, name: str, value: str) -> bool:
        """Sets a version field. Setting `engine` pins `engine_source` to manual."""
        target = self.get_version(slug, version)
        if target is None:
            return False
        if name == "engine":
            target.engine = SourceEngine(value.lower())
            target.engine_source = EngineSource.MANUAL
        elif name == "zip_url":
            target.zip_url = value or None
        elif name == "zip_source":
            target.zip_source = ZipSource(value.strip().lower())
        elif name == "convert_eligible":
            target.convert_eligible = parse_bool(value)
        elif name == "convert_batch":
            # Normalized on the way in so `POC-1`, `poc-1 ` and `poc-1` are one batch.
            target.convert_batch = value.strip().lower()
        elif name == "custom_override":
            target.custom_override = parse_bool(value)
        else:
            raise CatalogError(f"'{name}' is not a settable versions.csv field")
        self.save()
        return True

    def record_detected_engine(self, slug: str, version: str, engine: SourceEngine) -> bool:
        """Writes back an engine resolved during extraction. Never overrides a manual value."""
        target = self.get_version(slug, version)
        if target is None or target.engine_source is EngineSource.MANUAL:
            return False
        target.engine = engine
        target.engine_source = EngineSource.DETECTED
        self.save()
        return True

    def record_extract_inventory(
        self,
        slug: str,
        version: str,
        csh_sources: int,
        csh_names: int,
        api_files: int,
        doc_files: int,
    ) -> bool:
        """Writes back the Stage 4 inventory for one version -- architecture.md §3.9.

        All five columns are set in one call so the two booleans cannot disagree
        with the counts they summarize: each is *derived here* from the measurement
        rather than passed in, which is why the signature takes `csh_sources` (how
        many CSH source files were located) and not `has_csh`.

        `has_csh` is deliberately not `csh_names > 0`. An empty `<CatapultAliasFile />`
        or zero-byte alias file is 55% of the observed corpus, so `has_csh=True` with
        `csh_names=0` is a real and distinct state -- the version ships a help map
        that yields nothing -- and it is worth seeing before conversion, not after.

        Callers must not invoke this for a failed or partial extract. Leaving the
        row blank is the honest answer there; writing zeros would make a failure
        indistinguishable from an empty package.
        """
        target = self.get_version(slug, version)
        if target is None:
            return False
        target.has_csh = csh_sources > 0
        target.csh_names = csh_names
        target.has_api_ref = api_files > 0
        target.api_files = api_files
        target.doc_files = doc_files
        self.save()
        return True

    def clear_extract_inventory(self, slug: str, version: str) -> bool:
        """Blanks the inventory columns, restoring "never extracted".

        Needed when a version's extracted tree is discarded: stale counts describing
        a directory that no longer exists are worse than no counts, because nothing
        about the row says they are stale.
        """
        target = self.get_version(slug, version)
        if target is None:
            return False
        for field_name, _ in _INVENTORY_COLUMNS:
            setattr(target, field_name, None)
        self.save()
        return True

    # -- reporting -----------------------------------------------------------

    def triage_summary(self) -> dict[str, object]:
        """Family classification progress, so triage has a reportable metric."""
        catalog = self.load()
        counts = dict.fromkeys((str(s) for s in FamilySource), 0)
        scope_counts = dict.fromkeys((str(s) for s in ScopeSource), 0)
        unclassified = []
        out_of_scope = []
        for product in catalog.products.values():
            counts[str(product.family_source)] += 1
            scope_counts[str(product.scope_source)] += 1
            if product.family_source is FamilySource.UNCLASSIFIED:
                unclassified.append(product.slug)
            if not product.in_scope:
                out_of_scope.append(product.slug)
        return {
            "total": len(catalog.products),
            "counts": counts,
            "unclassified": sorted(unclassified),
            "scope_counts": scope_counts,
            "out_of_scope": sorted(out_of_scope),
        }

    def validate(self) -> list[str]:
        """Re-reads the CSVs and reports anything that looks like spreadsheet damage."""
        problems: list[str] = []
        catalog = self.load()

        # The key. Two rows sharing a slug means one of them has already been lost
        # from the in-memory catalog, and letting a `save()` follow would write the
        # loss back to disk -- so this aborts the import while both rows still exist
        # in the file the user can fix.
        for duplicate in sorted(set(self._duplicate_slugs)):
            problems.append(
                f"products.csv has more than one row with slug '{duplicate}'. The slug is the catalog key; "
                f"give each product its own docs.tibco.com slug or delete the duplicate row."
            )

        for product in catalog.products.values():
            if self.state:
                known = self.state.known_versions(product.slug)
                missing = known - set(product.versions)
                if missing:
                    problems.append(
                        f"{product.slug}: version(s) {sorted(missing)} known to discovery are absent "
                        f"from versions.csv (Excel may have coerced e.g. '1.10' to '1.1')"
                    )
            for ver in product.versions.values():
                if ver.engine is SourceEngine.AUTO and ver.engine_source is not EngineSource.AUTO:
                    problems.append(f"{product.slug}@{ver.version}: engine 'auto' with a resolved source")
                # A `manual` row is exempt: its package is supplied by hand at the
                # canonical path, so there is no URL to be missing (architecture §3.8).
                if ver.convert_eligible and not ver.zip_url and ver.zip_source is not ZipSource.MANUAL:
                    problems.append(f"{product.slug}@{ver.version}: convert_eligible with no zip_url")
        return problems

    def warnings(self) -> list[str]:
        """Things worth saying out loud that must not block a write.

        Kept separate from `validate()` because the two have opposite consequences:
        a `validate()` problem aborts the import, whereas everything here is a
        legitimate state the user may have chosen deliberately.
        """
        notes: list[str] = []
        catalog = self.load()

        # One aggregated line rather than one per rule: with 61 exclusions and a
        # partially fetched catalog this is routinely dozens of entries, and sixty
        # near-identical warnings would bury the ones that matter.
        unmatched = self.unmatched_scope_rules()
        if unmatched and catalog.products:
            shown = ", ".join(unmatched[:8]) + (" ..." if len(unmatched) > 8 else "")
            notes.append(
                f"config/scope.yaml: {len(unmatched)} of {len(self._scope_rules())} out-of-scope rules match no "
                f"product in the catalog ({shown}). Expected until `catalog fetch --all` has run; afterwards it "
                f"means the product was renamed upstream and is no longer being excluded."
            )

        for product in sorted(catalog.products.values(), key=lambda p: p.slug):
            # A family typed straight into products.csv is accepted and its folder
            # auto-registered; the warning exists so a typo ('mesaging') is visible
            # before it silently becomes a third family folder holding one product.
            if self.config is not None and not self.config.is_known_family(product.bu, product.family):
                try:
                    folder = self.config.family_folder_name(product.bu, product.family)
                except ValueError as exc:
                    notes.append(f"{product.slug}: {exc}")
                    continue
                notes.append(
                    f"{product.slug}: family '{product.family}' is not declared in taxonomy.yaml "
                    f"for bu '{product.bu}'. Accepted; workspace folder -> families/{folder}. "
                    f"Add it to taxonomy.yaml to silence this."
                )
            for ver in sorted(product.versions.values(), key=lambda v: natural_version_key(v.version), reverse=True):
                # Scheduled, but the product it belongs to is excluded outright.
                # The row reads as scheduled and will never run. Which of the two
                # places the exclusion came from is named, because they are undone
                # differently: one is a YAML edit, the other a CSV edit.
                if ver.convert_batch and not product.in_scope:
                    origin = (
                        "config/scope.yaml"
                        if product.scope_source is ScopeSource.SCOPE_RULE
                        else f"a manual in_scope=false on {product.slug}"
                    )
                    notes.append(
                        f"{product.slug}@{ver.version}: in batch '{ver.convert_batch}' but the product "
                        f"is out of scope (via {origin}), so it will be skipped. Run "
                        f"`docushift catalog set --product {product.slug} --in-scope` to include it."
                    )
                # Scheduled but not permitted: the batch flag looks like it selected
                # this row, and nothing downstream will ever pick it up.
                if ver.convert_batch and not ver.convert_eligible:
                    notes.append(
                        f"{product.slug}@{ver.version}: in batch '{ver.convert_batch}' but "
                        f"convert_eligible=false, so it will be skipped. Run "
                        f"`docushift catalog enable --product {product.slug} --version {ver.version}`."
                    )
                # The pin still wins, but discovery has since produced an endpoint,
                # so the hand-supplied package may no longer be necessary.
                if ver.zip_source is ZipSource.MANUAL and ver.zip_url:
                    notes.append(
                        f"{product.slug}@{ver.version}: zip_source=manual, but discovery now has a "
                        f"zip_url for it. The manual package still wins. Run `docushift catalog set "
                        f"--product {product.slug} --version {ver.version} --zip-source auto` to "
                        f"download it instead."
                    )
                # Identified, eligible, and unconvertible. Worth saying out loud
                # because the sheet looks ready: the row has a real engine name
                # rather than `auto`, so nothing about it reads as unresolved --
                # yet Stage 5 has no handler and will skip it. Scoped to eligible
                # rows so this stays actionable; an ineligible row carrying
                # `r-help` is inventory, and sorting the column shows it.
                identified_no_handler = (
                    ver.engine is not SourceEngine.AUTO and ver.engine not in CONVERTIBLE_ENGINES
                )
                if ver.convert_eligible and identified_no_handler:
                    notes.append(
                        f"{product.slug}@{ver.version}: engine '{ver.engine}' is identified but has no "
                        f"Stage 5 handler, so conversion will skip it. Set convert_eligible=false to take it out "
                        f"of scope, or convert it by hand."
                    )
                notes.extend(self._inventory_notes(product.slug, ver))
        return notes

    @staticmethod
    def _inventory_notes(slug: str, ver: ProductVersion) -> list[str]:
        """Flags an inventory boolean that contradicts the count beside it (§3.9).

        `record_extract_inventory` derives both from one measurement, so this shape
        only arises from a hand-edit. It is a warning rather than a `validate()`
        problem on purpose: the columns are advisory, the next `docushift extract`
        overwrites them wholesale, and blocking an import over a stale summary cell
        would be out of proportion to the harm.

        `_has_csh=true` with `_csh_names=0` is **not** flagged -- that is the
        empty-alias-file case and a legitimate measurement.
        """
        notes = []
        if ver.has_api_ref is False and ver.api_files:
            notes.append(
                f"{slug}@{ver.version}: _has_api_ref=false but _api_files={ver.api_files}. "
                f"These are written together, so one has been hand-edited. The next "
                f"`docushift extract` of this version will overwrite both."
            )
        if ver.has_csh is False and ver.csh_names:
            notes.append(
                f"{slug}@{ver.version}: _has_csh=false but _csh_names={ver.csh_names}. "
                f"These are written together, so one has been hand-edited. The next "
                f"`docushift extract` of this version will overwrite both."
            )
        return notes


_FAMILY_PRECEDENCE = {
    FamilySource.MANUAL: 0,
    FamilySource.TAXONOMY_RULE: 1,
    FamilySource.DOCSITE_CATEGORY: 2,
    FamilySource.UNCLASSIFIED: 3,
}


def _family_rank(source: FamilySource) -> int:
    return _FAMILY_PRECEDENCE[source]


def _resolve_scope(product: Product, rules: dict[str, str]) -> None:
    """Applies `scope.yaml` to one product -- docs/design.md §3.3.1.

    Ranked `manual` > `scope_rule` > `default`, first match wins:

    1. `scope_source=manual` is a human's decision and is preserved unconditionally.
    2. A slug listed in the rules excludes the product.
    3. Anything else is in scope -- and this step **actively resets** a previous
       `scope_rule` exclusion, so deleting a slug from the YAML really does restore
       the product. That is safe only because step 1 short-circuits ahead of it: a
       reset can never undo a hand-set value.

    The lookup is a dict hit on the exact slug, never a substring test. Which rules
    are live is answered separately by `unmatched_scope_rules()`, over the whole
    catalog rather than one fetch -- a scoped fetch would otherwise report every
    rule it did not visit as dead.
    """
    if product.scope_source is ScopeSource.MANUAL:
        return

    if product.slug in rules:
        product.in_scope = False
        product.scope_source = ScopeSource.SCOPE_RULE
        return

    product.in_scope = True
    product.scope_source = ScopeSource.DEFAULT


def _as_text(value: object) -> str:
    """Normalizes a value for snapshot comparison; the snapshot stores everything as text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return format_bool(value)
    return str(value).strip()


def _coerce_enum(enum_cls, value: object, default):
    """Reads an enum column tolerantly -- an unrecognized token falls back to the default."""
    token = str(value or "").strip().lower()
    try:
        return enum_cls(token)
    except ValueError:
        return default
