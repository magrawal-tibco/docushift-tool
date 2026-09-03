"""Additive catalog manager backed by the CSV pair.

Storage is `config/products.csv` + `config/versions.csv`, normalized on
`product_code` (docs/architecture.md §3). Merging is a **snapshot-based 3-way
merge**: `state.db` holds what discovery wrote last (*base*), the CSV holds what
the user has since edited (*mine*), and a fetch supplies *theirs*. Any field where
`mine != base` is inferred to be a human edit and is preserved -- no protection
flag required, because expecting a user to tick one on each edited row of a
4,000-row sheet guarantees silent data loss.
"""

from dataclasses import dataclass, field
from pathlib import Path

from docushift.models import (
    Catalog,
    EngineSource,
    FamilySource,
    Product,
    ProductVersion,
    SourceEngine,
)
from docushift.state import StateStore
from docushift.utils.csvio import (
    format_bool,
    natural_version_key,
    normalize_date,
    parse_bool,
    read_rows,
    write_rows,
)

PRODUCT_COLUMNS = (
    "product_code",
    "display_name",
    "bu",
    "family",
    "family_source",
    "slug",
    "custom_override",
)

# `_bu` / `_family` are denormalized from products.csv so the sheet can be filtered
# by family without a VLOOKUP. They are regenerated on every write and edits to
# them are ignored -- see docs/architecture.md §3.2.
VERSION_COLUMNS = (
    "product_code",
    "version",
    "is_archived",
    "convert_eligible",
    "release_date",
    "engine",
    "engine_source",
    "zip_url",
    "custom_override",
    "_bu",
    "_family",
)

# Fields discovery owns and may therefore update. `family` is handled separately
# because `family_source=manual` outranks any fetch.
_MERGEABLE_PRODUCT_FIELDS = ("display_name", "slug")
# Engine fields are absent by design: the detector writes them, not discovery.
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
    deletions_blocked: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "products_added": self.products_added,
            "products_updated": self.products_updated,
            "versions_added": self.versions_added,
            "versions_updated": self.versions_updated,
            "fields_preserved": self.fields_preserved,
            "deletions_blocked": list(self.deletions_blocked),
        }


class CatalogManager:
    """Loads, merges, and writes the catalog CSV pair."""

    def __init__(self, products_path: Path, versions_path: Path, state: StateStore | None = None):
        self.products_path = products_path
        self.versions_path = versions_path
        self.state = state
        self._catalog: Catalog | None = None

    # -- load / save ---------------------------------------------------------

    def load(self) -> Catalog:
        """Reads both CSVs. Missing files yield an empty catalog, not an error."""
        if self._catalog is not None:
            return self._catalog

        catalog = Catalog()
        for row in read_rows(self.products_path):
            code = row.get("product_code", "").strip()
            if not code:
                continue
            catalog.products[code] = Product(
                product_code=code,
                display_name=row.get("display_name", "").strip() or code,
                bu=row.get("bu", "").strip().lower() or "tibco",
                family=row.get("family", "").strip().lower() or "general",
                family_source=_coerce_enum(FamilySource, row.get("family_source"), FamilySource.UNCLASSIFIED),
                slug=row.get("slug", "").strip() or None,
                custom_override=parse_bool(row.get("custom_override")),
            )

        for row in read_rows(self.versions_path):
            code = row.get("product_code", "").strip()
            version = row.get("version", "").strip()
            if not code or not version:
                continue
            product = catalog.products.get(code)
            if product is None:
                # A version row with no product row is a broken join, not a product.
                raise CatalogError(
                    f"versions.csv references unknown product_code '{code}' (version '{version}'). "
                    f"Add the product to products.csv or remove the orphaned version row."
                )
            is_archived = parse_bool(row.get("is_archived"))
            product.versions[version] = ProductVersion(
                product_code=code,
                version=version,
                is_archived=is_archived,
                convert_eligible=parse_bool(row.get("convert_eligible"), default=not is_archived),
                release_date=normalize_date(row.get("release_date")) or None,
                engine=_coerce_enum(SourceEngine, row.get("engine"), SourceEngine.AUTO),
                engine_source=_coerce_enum(EngineSource, row.get("engine_source"), EngineSource.AUTO),
                zip_url=row.get("zip_url", "").strip() or None,
                custom_override=parse_bool(row.get("custom_override")),
            )

        self._catalog = catalog
        return catalog

    def save(self) -> None:
        """Writes both CSVs with a fixed column order and a stable sort.

        The sort is what makes a no-op fetch produce a zero-line diff: products by
        `(bu, family, product_code)`, versions by product then version descending
        using a natural sort, so `10.4.0` sits above `9.1.0`.
        """
        catalog = self.load()

        products = sorted(catalog.products.values(), key=lambda p: (p.bu, p.family, p.product_code))
        write_rows(
            self.products_path,
            PRODUCT_COLUMNS,
            [
                {
                    "product_code": p.product_code,
                    "display_name": p.display_name,
                    "bu": p.bu,
                    "family": p.family,
                    "family_source": str(p.family_source),
                    "slug": p.slug or "",
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
                        "product_code": product.product_code,
                        "version": version.version,
                        "is_archived": format_bool(version.is_archived),
                        "convert_eligible": format_bool(version.convert_eligible),
                        "release_date": normalize_date(version.release_date),
                        "engine": str(version.engine),
                        "engine_source": str(version.engine_source),
                        "zip_url": version.zip_url or "",
                        "custom_override": format_bool(version.custom_override),
                        "_bu": product.bu,
                        "_family": product.family,
                    }
                )
        write_rows(self.versions_path, VERSION_COLUMNS, version_rows)

    # -- accessors -----------------------------------------------------------

    def get_product(self, product_code: str) -> Product | None:
        return self.load().products.get(product_code)

    def get_version(self, product_code: str, version: str) -> ProductVersion | None:
        product = self.get_product(product_code)
        return product.versions.get(version) if product else None

    def iter_versions(
        self,
        bu: str | None = None,
        family: str | None = None,
        product_code: str | None = None,
        version: str | None = None,
        eligible_only: bool = False,
    ) -> list[tuple[Product, ProductVersion]]:
        """Filtered `(product, version)` pairs, in catalog sort order."""
        catalog = self.load()
        results = []
        for product in sorted(catalog.products.values(), key=lambda p: (p.bu, p.family, p.product_code)):
            if bu and product.bu != bu.lower():
                continue
            if family and product.family != family.lower():
                continue
            if product_code and product.product_code != product_code:
                continue
            for ver in sorted(product.versions.values(), key=lambda v: natural_version_key(v.version), reverse=True):
                if version and ver.version != version:
                    continue
                if eligible_only and not ver.convert_eligible:
                    continue
                results.append((product, ver))
        return results

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

        for incoming in discovered:
            code = incoming.product_code
            mine = catalog.products.get(code)

            if mine is None:
                catalog.products[code] = incoming
                stats.products_added += 1
                stats.versions_added += len(incoming.versions)
            else:
                stats.products_updated += 1
                stats.fields_preserved += self._merge_product(mine, incoming)
                added, updated, preserved = self._merge_versions(mine, incoming)
                stats.versions_added += added
                stats.versions_updated += updated
                stats.fields_preserved += preserved

            blocked = self._collect_deletions(catalog.products[code], incoming)
            if blocked:
                if allow_deletes:
                    for gone in blocked:
                        del catalog.products[code].versions[gone]
                        if self.state:
                            self.state.forget_version(code, gone)
                else:
                    stats.deletions_blocked.extend(f"{code}@{v}" for v in blocked)

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

    def _merge_product(self, mine: Product, theirs: Product) -> int:
        """Merges discovery-owned product fields. Returns the count preserved."""
        if mine.custom_override:
            # Explicit whole-row pin: ignore every upstream change.
            return len(_MERGEABLE_PRODUCT_FIELDS) + 1

        base = self.state.get_product_snapshot(mine.product_code) if self.state else None
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

            base = self.state.get_version_snapshot(mine.product_code, key) if self.state else None
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
        if self.state is None:
            return
        for product in discovered:
            self.state.record_product_snapshot(product)
            for version in product.versions.values():
                self.state.record_version_snapshot(version)

    # -- edits ---------------------------------------------------------------

    def set_conversion_eligibility(self, product_code: str, version: str, eligible: bool) -> bool:
        """Toggles `convert_eligible`. The snapshot makes this survive the next fetch."""
        target = self.get_version(product_code, version)
        if target is None:
            return False
        target.convert_eligible = eligible
        self.save()
        return True

    def set_product_field(self, product_code: str, name: str, value: str) -> bool:
        """Sets a product field. Setting `family` also pins its provenance to manual."""
        product = self.get_product(product_code)
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
        elif name == "custom_override":
            product.custom_override = parse_bool(value)
        else:
            raise CatalogError(f"'{name}' is not a settable products.csv field")
        self.save()
        return True

    def set_version_field(self, product_code: str, version: str, name: str, value: str) -> bool:
        """Sets a version field. Setting `engine` pins `engine_source` to manual."""
        target = self.get_version(product_code, version)
        if target is None:
            return False
        if name == "engine":
            target.engine = SourceEngine(value.lower())
            target.engine_source = EngineSource.MANUAL
        elif name == "zip_url":
            target.zip_url = value or None
        elif name == "convert_eligible":
            target.convert_eligible = parse_bool(value)
        elif name == "custom_override":
            target.custom_override = parse_bool(value)
        else:
            raise CatalogError(f"'{name}' is not a settable versions.csv field")
        self.save()
        return True

    def record_detected_engine(self, product_code: str, version: str, engine: SourceEngine) -> bool:
        """Writes back an engine resolved during extraction. Never overrides a manual value."""
        target = self.get_version(product_code, version)
        if target is None or target.engine_source is EngineSource.MANUAL:
            return False
        target.engine = engine
        target.engine_source = EngineSource.DETECTED
        self.save()
        return True

    # -- reporting -----------------------------------------------------------

    def triage_summary(self) -> dict[str, object]:
        """Family classification progress, so triage has a reportable metric."""
        catalog = self.load()
        counts = dict.fromkeys((str(s) for s in FamilySource), 0)
        unclassified = []
        for product in catalog.products.values():
            counts[str(product.family_source)] += 1
            if product.family_source is FamilySource.UNCLASSIFIED:
                unclassified.append(product.product_code)
        return {
            "total": len(catalog.products),
            "counts": counts,
            "unclassified": sorted(unclassified),
        }

    def validate(self) -> list[str]:
        """Re-reads the CSVs and reports anything that looks like spreadsheet damage."""
        problems: list[str] = []
        catalog = self.load()

        for product in catalog.products.values():
            if self.state:
                known = self.state.known_versions(product.product_code)
                missing = known - set(product.versions)
                if missing:
                    problems.append(
                        f"{product.product_code}: version(s) {sorted(missing)} known to discovery are absent "
                        f"from versions.csv (Excel may have coerced e.g. '1.10' to '1.1')"
                    )
            for ver in product.versions.values():
                if ver.engine is SourceEngine.AUTO and ver.engine_source is not EngineSource.AUTO:
                    problems.append(f"{product.product_code}@{ver.version}: engine 'auto' with a resolved source")
                if ver.convert_eligible and not ver.zip_url:
                    problems.append(f"{product.product_code}@{ver.version}: convert_eligible with no zip_url")
        return problems


_FAMILY_PRECEDENCE = {
    FamilySource.MANUAL: 0,
    FamilySource.TAXONOMY_RULE: 1,
    FamilySource.DOCSITE_CATEGORY: 2,
    FamilySource.UNCLASSIFIED: 3,
}


def _family_rank(source: FamilySource) -> int:
    return _FAMILY_PRECEDENCE[source]


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
