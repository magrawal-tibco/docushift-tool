"""Stage 1: turn docsite API payloads into catalog-shaped `Product` records.

The output feeds `CatalogManager.merge_fetch_results()` unchanged -- the crawler
does no writing of its own. Everything it produces is what discovery *owns*
(display name, slug, versions, archive flags, release dates, ZIP URLs); it never
sets `engine` (the detector's, after extraction), `convert_batch` or `zip_source`
(the user's). See docs/architecture.md §3.5.

## The shape of the real payloads

Verified against the live API on 2026-09-03:

* Every response is wrapped: `{"result": {"success": ..., "product"|"products": ...}}`.
* `/api/products/{slug}` returns **the current version as the product object** --
  it carries `version_no` and `folder_path` itself -- with every *other* version
  in a `siblings` list. So the record set is `[product] + siblings`.
* ...but only for a slug the API flags `isChildProduct`. A slug flagged
  `isParentProduct` returns `version_no: null`, `folder_path: ""` and no
  `siblings` at all -- 34 products, 685 versions, and until 2026-09-23 every one
  of them was dropped. **`/api/products/{slug}-latest` turns any parent into a
  child**: it returns the ordinary child shape, and its `siblings` list is the
  version drop-down. Measured 2026-09-22 across all 34: it resolves for every
  one, with sibling counts matching A-to-Z's `versionCount` exactly, which is why
  one extra request per parent is the whole fix and no pagination is needed.
* A sibling's `isArchive` flag is what separates active from archived. Archived
  siblings often carry a stale `folder_path` (`enterprise_message_service` rather
  than `ems/8.2.1`), which is why an active ZIP URL is only ever built from a
  path that actually looks like `<code>/<version>`.
* `/api/products/archive/{slug}` supplies the archived versions' real `zipPath`
  and a human `GA_date` ("November 2022"). It overlaps `siblings` rather than
  replacing it, so the two are merged by version number.

## Why the key lookups are tolerant

Key spellings differ between endpoints (`version_no` here, `versionNumber`
there) and the API is undocumented. Matching a handful of candidate names costs
nothing and turns a whole-crawl failure into a non-event; being strict would mean
a release every time the docsite team renames a field.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from typing import Any

from docushift.config import ConfigManager
from docushift.discovery.client import DocsiteClient, DocsiteError
from docushift.models import Product, ProductVersion
from docushift.utils.csvio import normalize_date, parse_bool
from docushift.utils.slug import slugify

# Candidate key names, most specific first. See the module docstring.
_NAME_KEYS = ("display_name", "product_name", "name", "title")
_SLUG_KEYS = ("slug", "product_slug", "url_slug", "seo_url")
_ID_KEYS = ("id", "product_id", "productId")
_VERSION_KEYS = ("version_no", "versionNumber", "version_number", "version")
_FOLDER_KEYS = ("folder_path", "folderPath", "path")
# `published_date` is deliberately absent: it is when the docsite published the
# page, which for old releases is a bulk-migration timestamp (every EMS 5.x and
# 6.x record reads 2022-05-26). Leaving it out lets the archive index's `GA_date`
# supply the real release month instead.
_DATE_KEYS = ("releaseDate", "release_date", "GA_date", "ga_date", "date")
_ZIP_KEYS = ("zipPath", "zip_path", "zipUrl", "zip_url")
_ARCHIVED_KEYS = ("isArchive", "is_archive", "archived")
_ARCHIVE_EXISTS_KEYS = ("isArchiveExists", "is_archive_exists", "archive_exists", "hasArchive")
_SIBLING_KEYS = ("siblings", "versions", "sibling_versions", "other_versions", "product_versions")
_ARCHIVE_CHILD_KEYS = ("children", "archives", "archive_versions", "versions")
_PUBLIC_KEYS = ("isPublicLevel", "is_public_level", "isPublic")
_PRODUCT_LIST_KEYS = ("products", "results", "items", "data")
# How many versions A-to-Z claims a product has. Not used to build anything --
# it is the independent number the crawl's own output is checked against, which
# is what turns a parent product's silent drop into a reported defect.
_VERSION_COUNT_KEYS = ("versionCount", "version_count", "versionsCount", "versions_count")

# Appended to a slug to turn a parent product into a child one. See the module
# docstring. A slug suffix, never a URL suffix: the docsite page
# `/products/tibco-webfocus-client` is served by the slug `ibi-webfocus-client`,
# and `tibco-webfocus-client-latest` is not a thing. Always built from the slug
# A-to-Z returned.
_LATEST_SUFFIX = "-latest"

# Envelopes the docsite wraps responses in, peeled before anything is read.
_ENVELOPE_KEYS = ("result", "data", "response", "payload", "product")

# Stripped when deriving a product code from a slug. Only reached by products that
# publish no usable folder path -- the docsite prefixes most slugs with the vendor.
_SLUG_PREFIXES = ("tibco-", "ibi-", "spotfire-")


@dataclass
class CrawlResult:
    """What one crawl produced, plus what it could not reach.

    Errors are collected rather than raised so one unreachable product does not
    abandon a 250-product run. A product that errored is **absent from
    `products`** rather than present-but-empty: an empty version list would read
    to the merge as "every version was deleted upstream".
    """
    products: list[Product] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # Docsite entries with no published version at all (licence pages, connector
    # stubs). Counted rather than listed: none of them have anything to convert.
    # Skipped for the same reason errored products are.
    unversioned: int = 0
    # Entries A-to-Z advertises a `versionCount` for that still yielded nothing.
    # Split out of `unversioned` on 2026-09-23 and **named, not counted**, because
    # the two are not the same event: a licence page with no versions is the
    # docsite working as intended, while a product the index says has 22 is a
    # defect in this module. Both landed in one tally until `tibco-streaming`
    # surfaced twelve days later in a convert run -- the number was printed the
    # whole time, under a label that said the drop was expected.
    advertised_but_empty: list[str] = field(default_factory=list)
    # Entries the docsite marks as not publicly visible. Skipped before the
    # request, because fetching one just yields an SSO page.
    non_public: int = 0
    # Both keyed by docsite slug -- the catalog key -- so they land in `state.db`
    # under the same identifier the CSV rows use.
    product_metadata: dict[str, dict[str, str]] = field(default_factory=dict)
    version_metadata: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)


class DocsiteCrawler:
    """Walks the docsite API and builds catalog-shaped products."""

    def __init__(self, client: DocsiteClient, config: ConfigManager, include_archived: bool = True):
        self.client = client
        self.config = config
        self.include_archived = include_archived

        defaults = dict(config.load_docsite().get("defaults") or {})
        self.active_eligible = bool(defaults.get("active_convert_eligible", True))
        self.archived_eligible = bool(defaults.get("archived_convert_eligible", False))

    # -- entry point ----------------------------------------------------------

    def discover(
        self,
        bu: str | None = None,
        selectors: Collection[str] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> CrawlResult:
        """Crawls the docsite and returns catalog-shaped products.

        `selectors` are docsite slugs or product codes, matched against the A-to-Z
        list *before* the per-product request -- which is why `--product` and
        `--batch` are the cheap scopes: a three-product batch is three requests,
        not 700. `bu` can only be applied after the keyword rules have run, so it
        costs a full crawl.

        There is no `family` filter, and since Phase 32 there cannot be: discovery
        assigns no family, so there is nothing here to filter on. The CLI turns
        `--family` into `selectors` by reading the catalog instead.

        Note that a product's code (`ems`) is usually not derivable from its slug
        (`tibco-enterprise-message-service`); the caller is expected to pass the
        slug it already holds in the catalog alongside the code.
        """
        result = CrawlResult()

        try:
            entries = self._list_products(result)
        except DocsiteError as exc:
            result.errors.append(f"product list: {exc}")
            return result

        if selectors is not None:
            wanted = {str(s).strip().lower() for s in selectors if s}
            entries = [e for e in entries if wanted & {e["slug"], self._code_from_slug(e["slug"])}]

        total = len(entries)

        for index, entry in enumerate(entries, start=1):
            if on_progress:
                on_progress(index, total, entry["slug"])
            try:
                product = self._build_product(entry, result)
            except DocsiteError as exc:
                result.errors.append(f"{entry['slug']}: {exc}")
                continue
            if product is None:
                if _as_count(entry["version_count"]) > 0:
                    result.advertised_but_empty.append(entry["slug"])
                else:
                    result.unversioned += 1
                continue
            if bu and product.bu != bu.strip().lower():
                continue
            result.products.append(product)

        return result

    # -- product list ---------------------------------------------------------

    def _list_products(self, result: CrawlResult) -> list[dict[str, str]]:
        """Normalizes `/api/a_to_z` into `{slug, name, id}` records.

        Entries with no slug are dropped: the slug is the key every other endpoint
        is addressed by, so there is nothing that can be done with one.

        Entries flagged not publicly visible are dropped too. Requesting one
        returns an SSO interstitial served as HTTP 200 -- 70 of the docsite's 739
        entries, which would otherwise be 70 wasted requests and 70 errors in the
        report. A *missing* flag is treated as public, so a schema change cannot
        silently empty the crawl.

        **The visibility filter runs before the de-duplication, not after.** One
        slug can arrive twice with different visibility: `spotfire-application` is
        both id 8862 (`isPublicLevel: false`, `isOnlyForAdmin: true`, 1 version)
        and id 2452 (public, 99 versions). De-duplicating first meant the
        admin-only record claimed the slug and was then discarded as non-public,
        so the real product was never requested and was counted under
        `non_public` -- one duplicated slug in 739 records, and the reason a
        99-version product was invisible to the catalog until 2026-09-22.
        A slug therefore counts as non-public only when **every** record for it
        is. Among several visible records the first still wins: nothing in the
        payload ranks them, and inventing an order would be a guess.
        """
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in _as_records(self.client.a_to_z(), _PRODUCT_LIST_KEYS):
            slug = _first(record, _SLUG_KEYS)
            if slug:
                grouped.setdefault(slug, []).append(record)

        entries = []
        for slug, records in grouped.items():
            visible = [r for r in records if _is_public(r)]
            if not visible:
                result.non_public += 1
                continue
            record = visible[0]
            entries.append(
                {
                    "slug": slug,
                    "name": _first(record, _NAME_KEYS) or slug,
                    "id": _first(record, _ID_KEYS) or "",
                    # The most versions any visible record claims. Read from the
                    # whole group so a stub cannot understate a real product.
                    "version_count": str(max(_as_count(_first(r, _VERSION_COUNT_KEYS)) for r in visible)),
                }
            )
        return entries

    # The category endpoint was read here until Phase 32, to promote a product no
    # keyword rule had matched. Nothing assigns a family at discovery any more, so
    # the only consumer is gone and the per-crawl request with it. It had promoted
    # zero products in the catalog as it stood.

    # -- one product ----------------------------------------------------------

    def _build_product(self, entry: dict[str, str], result: CrawlResult) -> Product | None:
        """Builds one product, or `None` if the docsite publishes no versions for it."""
        slug = entry["slug"]
        detail = _unwrap(self.client.product(slug))
        if not isinstance(detail, dict):
            raise DocsiteError("product detail was not an object")

        records = _versioned_records(detail)
        if not records:
            # A parent product: no version, no folder path, no siblings. Its
            # releases are one slug away -- see the module docstring.
            latest = self._latest_detail(slug, result)
            if latest is not None:
                detail, records = latest, _versioned_records(latest)
        if not records:
            return None

        code = self._derive_code(slug, detail, records)
        product = self._product_shell(entry, detail, code)

        for record in records:
            version = self._version_from_record(slug, code, record, result)
            product.versions.setdefault(version.version, version)

        if self.include_archived and self._archive_may_exist(detail):
            self._apply_archive_index(product, slug, result)

        meta = result.product_metadata.setdefault(slug, {"docsite_slug": slug})
        if entry["id"]:
            meta["docsite_id"] = entry["id"]
        return product

    def _latest_detail(self, slug: str, result: CrawlResult) -> dict[str, Any] | None:
        """`/api/products/{slug}-latest`, or `None` if it does not resolve.

        Only reached by a product whose own detail carried no version, so the
        cost is one request per parent -- 34 on a full crawl -- and none at all
        for the ~600 products that already work.

        A failure here is **not** recorded as an error. The caller returns `None`
        and the product lands in `advertised_but_empty` or `unversioned`, which
        says the same thing in the place a reader is already looking; adding an
        error line as well would report one genuinely version-less licence page
        twice.
        """
        try:
            detail = _unwrap(self.client.product(f"{slug}{_LATEST_SUFFIX}"))
        except DocsiteError:
            return None
        return detail if isinstance(detail, dict) else None

    def _product_shell(self, entry: dict[str, str], detail: dict[str, Any], code: str) -> Product:
        # The detail name carries the version ("... 10.5.0"); the A-to-Z name does
        # not, and a version number baked into a product row would go stale.
        display_name = entry["name"] or _first(detail, _NAME_KEYS) or code

        # Phase 32: discovery resolves `bu` and stops. It assigns no family, from a
        # keyword rule or from anything else, so every new product lands in
        # `catalog triage` for a human. The docsite category used to be promoted
        # here when no rule matched -- it was automatic family assignment wearing a
        # different provenance, and removing it closes the same door. It was also
        # inert: zero products in the catalog carried `docsite_category`. The
        # argument for all of it is on `resolve_product_info`.
        info = self.config.resolve_product_info(code, display_name)

        return Product(
            slug=entry["slug"],
            product_code=code,
            display_name=display_name,
            bu=str(info["bu"]),
            family=str(info["family"]),
            family_source=info["family_source"],
        )

    def _version_from_record(
        self, slug: str, code: str, record: dict[str, Any], result: CrawlResult
    ) -> ProductVersion:
        """Builds one version row. Keyed on `slug`, pathed from `code`.

        Both identifiers are needed and they are not interchangeable: the catalog
        row is keyed on the slug, while the docsite's ZIP folder is named from the
        code, which is precisely what `_derive_code` was built to recover.
        """
        number = _first(record, _VERSION_KEYS)
        archived = parse_bool(record.get(_present(record, _ARCHIVED_KEYS)))
        declared, folder = _version_folder(record, code, number)
        # Only the path the docsite actually published is recorded; the
        # reconstructed one below is good enough to build a URL from but not
        # something to hand the download stage as fact.
        if declared:
            result.version_metadata.setdefault((slug, number), {})["folder_path"] = declared

        return ProductVersion(
            slug=slug,
            version=number,
            is_archived=archived,
            convert_eligible=self.archived_eligible if archived else self.active_eligible,
            release_date=normalize_date(_first(record, _DATE_KEYS)) or None,
            # Archived versions are not published under the active layout; their
            # real endpoint comes from the archive index below, and a templated
            # guess here would be a broken URL recorded as fact.
            zip_url=None if archived else self.client.active_zip_url(folder, slug, number),
        )

    def _derive_code(self, slug: str, detail: dict[str, Any], records: list[dict[str, Any]]) -> str:
        """The catalog's `product_code`, e.g. `ems` for `tibco-enterprise-message-service`.

        Read from a `<code>/<version>` folder path, which is what the ZIP URL is
        built from. The current version's own path is preferred because archived
        siblings carry stale ones. Products with no usable path at all fall back to
        the slug with its vendor prefix stripped.

        Unchanged by the 2026-09-10 re-key, and deliberately so: this always
        answered "what does the docsite call this product's folder?", which is a
        real and correct question. What was wrong was treating the answer as a
        unique key -- ten codes are shared by twenty-one products, and the fix was
        to key on the slug rather than to make this derivation guess harder.
        """
        for record in (detail, *records):
            folder = _first(record, _FOLDER_KEYS)
            head, _, tail = folder.strip("/").partition("/")
            if head and tail:
                return slugify(head)
        return self._code_from_slug(slug)

    @staticmethod
    def _code_from_slug(slug: str) -> str:
        code = slugify(slug)
        for prefix in _SLUG_PREFIXES:
            if code.startswith(prefix) and len(code) > len(prefix):
                return code[len(prefix) :]
        return code

    @staticmethod
    def _archive_may_exist(detail: dict[str, Any]) -> bool:
        """Whether to spend a request on the archive index.

        An explicit `false` is trusted and saves a request per product. A *missing*
        flag is not read as "no": the key is absent from some responses, and
        skipping on absence would silently lose every archived version.
        """
        key = _present(detail, _ARCHIVE_EXISTS_KEYS)
        return True if key is None else bool(detail[key])

    def _apply_archive_index(self, product: Product, slug: str, result: CrawlResult) -> None:
        """Fills in archived versions' real ZIP endpoints from the archive index.

        The index overlaps `siblings` rather than replacing it, so a version already
        known from the detail payload is topped up in place; only genuinely new ones
        are added.
        """
        try:
            payload = self.client.product_archive(slug)
        except DocsiteError as exc:
            # Non-fatal: the active versions are the ones that get converted, and
            # aborting the product over its history would be a poor trade.
            result.errors.append(f"{slug}: archive index unavailable ({exc})")
            return

        for record in _as_records(_unwrap(payload), _ARCHIVE_CHILD_KEYS):
            number = _first(record, _VERSION_KEYS)
            if not number:
                continue
            zip_path = _first(record, _ZIP_KEYS)
            released = normalize_date(_first(record, _DATE_KEYS)) or None
            existing = product.versions.get(number)

            if existing is None:
                product.versions[number] = ProductVersion(
                    slug=slug,
                    version=number,
                    is_archived=True,
                    convert_eligible=self.archived_eligible,
                    release_date=released,
                    zip_url=self.client.url(zip_path) if zip_path else None,
                )
                continue
            if not existing.is_archived:
                # Listed in both places: the active record is the current one, and
                # marking it archived would quietly make it ineligible.
                continue
            if zip_path:
                existing.zip_url = self.client.url(zip_path)
            if released and not existing.release_date:
                existing.release_date = released


# -- tolerant payload readers -------------------------------------------------


def _first(record: Any, keys: tuple[str, ...]) -> str:
    """First non-empty value among candidate key names, as trimmed text."""
    if not isinstance(record, dict):
        return ""
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return str(value).strip()
    return ""


def _is_public(record: dict[str, Any]) -> bool:
    """Whether A-to-Z says this record is publicly visible.

    A *missing* flag is public, for the reason `_list_products` gives: a schema
    change must not be able to empty the crawl.
    """
    key = _present(record, _PUBLIC_KEYS)
    return True if key is None else bool(record[key])


def _as_count(value: Any) -> int:
    """A count from a payload field that may be absent, blank, or a string.

    Anything unreadable is 0, which means "A-to-Z made no claim" -- so a product
    is only ever reported as a defect on a number the docsite actually published.
    """
    try:
        return int(str(value).strip() or 0)
    except ValueError:
        return 0


def _versioned_records(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """The detail object and its siblings, keeping only those carrying a version.

    `siblings` is looked up by name only -- the generic list search would happily
    return the product's `Documents` array instead.
    """
    siblings = detail.get(_present(detail, _SIBLING_KEYS) or "") or []
    records = [detail, *(s for s in siblings if isinstance(s, dict))]
    return [r for r in records if _first(r, _VERSION_KEYS)]


def _present(record: Any, keys: tuple[str, ...]) -> str | None:
    """The first candidate key the record actually declares, `None` if it declares none.

    Distinct from `_first` because a `false` flag and an absent one mean different
    things here -- see `_archive_may_exist`.
    """
    if not isinstance(record, dict):
        return None
    return next((key for key in keys if key in record), None)


def _unwrap(payload: Any) -> Any:
    """Peels the `{"result": {"product": ...}}` envelopes off a response."""
    seen = 0
    while isinstance(payload, dict) and seen < len(_ENVELOPE_KEYS):
        key = next((k for k in _ENVELOPE_KEYS if isinstance(payload.get(k), (dict, list))), None)
        if key is None:
            return payload
        payload = payload[key]
        seen += 1
    return payload


def _as_records(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Extracts a list of dicts from a payload that may or may not be wrapped.

    In order: a bare list; one of the named keys; inside an envelope; and finally
    any single list-of-dicts on the object, which covers a wrapper nobody has seen
    yet.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _as_records(value, keys)
            if nested:
                return nested

    for key in _ENVELOPE_KEYS:
        value = payload.get(key)
        if isinstance(value, (dict, list)):
            nested = _as_records(value, keys)
            if nested:
                return nested

    for value in payload.values():
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            return value
    return []


def _version_folder(record: dict[str, Any], code: str, version: str) -> tuple[str, str]:
    """Returns `(declared, usable)` paths for a version's files.

    Archived records carry stale folder paths (`enterprise_message_service`,
    `ems-zlinux`), so a path only counts as declared when it has both segments;
    otherwise the canonical `<code>/<version>` layout is reconstructed for URL
    building only. `usable` is `""` when there is no version to reconstruct from,
    which stops a malformed ZIP URL being built.
    """
    folder = _first(record, _FOLDER_KEYS).strip("/")
    head, _, tail = folder.partition("/")
    if head and tail:
        return folder, folder
    return "", f"{code}/{version}" if code and version else ""
