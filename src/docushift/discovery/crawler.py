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
from docushift.models import FamilySource, Product, ProductVersion
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
_CATEGORY_KEYS = ("category", "category_name", "categoryName", "suite", "suite_name")
_PUBLIC_KEYS = ("isPublicLevel", "is_public_level", "isPublic")
_PRODUCT_LIST_KEYS = ("products", "results", "items", "data")

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
    # Entries the docsite marks as not publicly visible. Skipped before the
    # request, because fetching one just yields an SSO page.
    non_public: int = 0
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
        family: str | None = None,
        selectors: Collection[str] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> CrawlResult:
        """Crawls the docsite and returns catalog-shaped products.

        `selectors` are docsite slugs or product codes, matched against the A-to-Z
        list *before* the per-product request -- which is why `--product` and
        `--batch` are the cheap scopes: a three-product batch is three requests,
        not 700. `bu` and `family` can only be applied after classification, so
        they cost a full crawl.

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
        categories = self._load_categories(result) if total else {}

        for index, entry in enumerate(entries, start=1):
            if on_progress:
                on_progress(index, total, entry["slug"])
            try:
                product = self._build_product(entry, categories, result)
            except DocsiteError as exc:
                result.errors.append(f"{entry['slug']}: {exc}")
                continue
            if product is None:
                result.unversioned += 1
                continue
            if bu and product.bu != bu.strip().lower():
                continue
            if family and product.family != family.strip().lower():
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
        """
        entries = []
        seen = set()
        for record in _as_records(self.client.a_to_z(), _PRODUCT_LIST_KEYS):
            slug = _first(record, _SLUG_KEYS)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            public = _present(record, _PUBLIC_KEYS)
            if public is not None and not record[public]:
                result.non_public += 1
                continue
            entries.append(
                {
                    "slug": slug,
                    "name": _first(record, _NAME_KEYS) or slug,
                    "id": _first(record, _ID_KEYS) or "",
                }
            )
        return entries

    def _load_categories(self, result: CrawlResult) -> dict[str, str]:
        """Slug -> family, from the category endpoint. Advisory only.

        A failure here is recorded and shrugged off: categories can only ever
        promote an `unclassified` product (architecture §3.3), so losing them
        degrades triage rather than the crawl.
        """
        if "bu_category_products" not in self.client.endpoints:
            return {}
        try:
            payload = self.client.bu_category_products()
        except DocsiteError as exc:
            result.errors.append(f"categories (advisory, skipped): {exc}")
            return {}

        mapping: dict[str, str] = {}
        for record in _as_records(payload, _PRODUCT_LIST_KEYS):
            slug = _first(record, _SLUG_KEYS)
            category = _first(record, _CATEGORY_KEYS)
            if not slug or not category:
                continue
            # taxonomy.yaml keys are underscored identifiers; the folder name gets
            # hyphenated later by utils/slug.py.
            mapping[slug] = slugify(category).replace("-", "_")
        return mapping

    # -- one product ----------------------------------------------------------

    def _build_product(
        self, entry: dict[str, str], categories: dict[str, str], result: CrawlResult
    ) -> Product | None:
        """Builds one product, or `None` if the docsite publishes no versions for it."""
        detail = _unwrap(self.client.product(entry["slug"]))
        if not isinstance(detail, dict):
            raise DocsiteError("product detail was not an object")

        # The detail object *is* the current version; `siblings` holds the rest.
        # Looked up by name only -- the generic list search would happily return
        # the product's `Documents` array instead.
        siblings = detail.get(_present(detail, _SIBLING_KEYS) or "") or []
        records = [detail, *(s for s in siblings if isinstance(s, dict))]
        records = [r for r in records if _first(r, _VERSION_KEYS)]
        if not records:
            return None

        code = self._derive_code(entry["slug"], detail, records)
        product = self._product_shell(entry, detail, code, categories)

        for record in records:
            version = self._version_from_record(code, record, result)
            product.versions.setdefault(version.version, version)

        if self.include_archived and self._archive_may_exist(detail):
            self._apply_archive_index(product, entry["slug"], code, result)

        meta = result.product_metadata.setdefault(code, {"docsite_slug": entry["slug"]})
        if entry["id"]:
            meta["docsite_id"] = entry["id"]
        return product

    def _product_shell(
        self, entry: dict[str, str], detail: dict[str, Any], code: str, categories: dict[str, str]
    ) -> Product:
        # The detail name carries the version ("... 10.5.0"); the A-to-Z name does
        # not, and a version number baked into a product row would go stale.
        display_name = entry["name"] or _first(detail, _NAME_KEYS) or code

        info = self.config.resolve_product_info(code, display_name)
        family = str(info["family"])
        family_source = info["family_source"]

        # Advisory promotion: only ever fills a gap, never overrides a rule match.
        if family_source is FamilySource.UNCLASSIFIED and categories.get(entry["slug"]):
            family = categories[entry["slug"]]
            family_source = FamilySource.DOCSITE_CATEGORY

        return Product(
            product_code=code,
            display_name=display_name,
            bu=str(info["bu"]),
            family=family,
            family_source=family_source,
            slug=entry["slug"],
        )

    def _version_from_record(self, code: str, record: dict[str, Any], result: CrawlResult) -> ProductVersion:
        number = _first(record, _VERSION_KEYS)
        archived = parse_bool(record.get(_present(record, _ARCHIVED_KEYS)))
        declared, folder = _version_folder(record, code, number)
        # Only the path the docsite actually published is recorded; the
        # reconstructed one below is good enough to build a URL from but not
        # something to hand the download stage as fact.
        if declared:
            result.version_metadata.setdefault((code, number), {})["folder_path"] = declared

        return ProductVersion(
            product_code=code,
            version=number,
            is_archived=archived,
            convert_eligible=self.archived_eligible if archived else self.active_eligible,
            release_date=normalize_date(_first(record, _DATE_KEYS)) or None,
            # Archived versions are not published under the active layout; their
            # real endpoint comes from the archive index below, and a templated
            # guess here would be a broken URL recorded as fact.
            zip_url=None if archived else self.client.active_zip_url(folder),
        )

    def _derive_code(self, slug: str, detail: dict[str, Any], records: list[dict[str, Any]]) -> str:
        """The catalog's `product_code`, e.g. `ems` for `tibco-enterprise-message-service`.

        Read from a `<code>/<version>` folder path -- what the catalog already uses
        and what the ZIP URL is built from. The current version's own path is
        preferred because archived siblings carry stale ones. Products with no
        usable path at all fall back to the slug with its vendor prefix stripped.
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

    def _apply_archive_index(self, product: Product, slug: str, code: str, result: CrawlResult) -> None:
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
                    product_code=code,
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
