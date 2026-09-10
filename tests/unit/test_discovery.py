"""Unit tests for the docsite client and crawler (Phase 3).

No network. A fake `requests.Session` serves canned payloads, so the real
`DocsiteClient` -- URL building, ZIP templating, JSON decoding, error mapping --
is under test alongside the crawler that consumes it.

The payloads mirror the live API's actual shape, verified against
`docs.tibco.com` on 2026-09-03 and trimmed to the fields the crawler reads:
a `{"result": {"product": ...}}` envelope, the detail object doubling as the
current version, `siblings` mixing active and archived releases with stale
folder paths on the old ones, and an archive index that overlaps `siblings`
rather than replacing it. A couple of records deliberately use different key
spellings, because tolerating that is the crawler's stated contract.
"""

import json

import pytest

from docushift.config import ConfigManager
from docushift.discovery import CrawlResult, DocsiteClient, DocsiteCrawler, DocsiteError
from docushift.models import FamilySource
from tests.conftest import TAXONOMY_YAML

DOCSITE = {
    "base_url": "https://docs.tibco.com",
    "endpoints": {
        "a_to_z": "/api/a_to_z",
        "product": "/api/products/{slug}",
        "product_archive": "/api/products/archive/{slug}",
        "bu_category_products": "/api/bu_category_products",
    },
    "zip_urls": {"active_template": "/pub/{folder_path}/doc/zip/tib_{folder_slug}_doc.zip"},
    # No rate limit: a throttled suite is a slow one, and the throttle is exercised
    # directly in test_client_throttles_between_requests.
    "crawl": {"timeout_seconds": 5, "rate_limit_per_second": 0},
    "defaults": {"active_convert_eligible": True, "archived_convert_eligible": False},
}


def _envelope(key: str, value):
    return {"result": {"success": True, "error": None, key: value}}


PAYLOADS = {
    "/api/a_to_z": _envelope(
        "products",
        [
            {
                "name": "TIBCO Enterprise Message Service™",
                "slug": "tibco-enterprise-message-service",
                "id": 644,
                "isPublicLevel": True,
            },
            {"name": "TIBCO EBX®", "slug": "tibco-ebx", "id": 2001, "isPublicLevel": True},
            # No visibility flag at all: treated as public rather than dropped.
            {"name": "Adapter Code for Joomla!", "slug": "adapter-code-for-joomla", "id": 8667},
            # Employee-only. Requesting it would return an SSO page as HTTP 200.
            {"name": "TIBCO Policy Manager", "slug": "tibco-policy-manager", "isPublicLevel": False},
        ],
    ),
    # The detail object *is* the current version: it carries version_no and
    # folder_path itself, with every other release under `siblings`.
    "/api/products/tibco-enterprise-message-service": _envelope(
        "product",
        {
            "id": 9159,
            "name": "TIBCO Enterprise Message Service™ 10.5.0",
            "slug": "tibco-enterprise-message-service-10-5-0",
            "version_no": "10.5.0",
            "folder_path": "ems/10.5.0",
            "releaseDate": "2026-01-29T00:00:00.000Z",
            "isArchive": False,
            "isArchiveExists": True,
            "siblings": [
                {
                    "version_no": "10.4.0",
                    "folder_path": "ems/10.4.0",
                    "releaseDate": "2025-02-06T09:21:53.000Z",
                    "isArchive": False,
                },
                # Archived, and carrying the stale folder path the live API returns.
                {"version_no": "8.2.1", "folder_path": "enterprise_message_service", "isArchive": True},
                {"version_no": "10.2.1", "folder_path": "ems/10.2.1", "isArchive": True},
            ],
        },
    ),
    "/api/products/archive/tibco-enterprise-message-service": _envelope(
        "product",
        {
            "id": 644,
            "slug": "tibco-enterprise-message-service",
            "children": [
                {
                    "version_no": "10.2.1",
                    "GA_date": "November 2022",
                    "zipPath": "/pub/ems/tibco-enterprise-message-service-10-2-1_documentation.zip",
                },
                {
                    "version_no": "6.0.1",
                    "GA_date": "June 2012",
                    "zipPath": "/pub/ems/tibco-enterprise-message-service-6-0-1_documentation.zip",
                },
            ],
        },
    ),
    # Deliberately a different dialect: camelCase keys, a `versions` list instead
    # of `siblings`, and no archive flag at all.
    "/api/products/tibco-ebx": _envelope(
        "product",
        {
            "name": "TIBCO EBX® 6.2.0",
            "versions": [{"versionNumber": "6.2.0", "folderPath": "ebx/6.2.0", "release_date": "2025-02-01"}],
        },
    ),
    "/api/products/archive/tibco-ebx": _envelope("product", {"children": []}),
    # An unversioned docsite entry: a licence page, nothing to convert.
    "/api/products/adapter-code-for-joomla": _envelope(
        "product", {"name": "Adapter Code for Joomla!", "isUnversionedProduct": True, "Documents": []}
    ),
    "/api/bu_category_products": _envelope("products", [{"slug": "tibco-ebx", "category": "Data Management"}]),
}


class FakeResponse:
    def __init__(self, payload, status_code: int = 200, text: str | None = None):
        self._payload = payload
        self.status_code = status_code
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


class FakeSession:
    """Routes by URL path. Records every call so request counts can be asserted."""

    def __init__(self, payloads: dict[str, object] | None = None):
        self.payloads = dict(PAYLOADS if payloads is None else payloads)
        self.calls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: float | None = None):
        path = url.replace("https://docs.tibco.com", "")
        self.calls.append(path)
        if path not in self.payloads:
            return FakeResponse(None, status_code=404, text="not found")
        return FakeResponse(self.payloads[path])


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(session: FakeSession) -> DocsiteClient:
    return DocsiteClient(DOCSITE, session=session)


@pytest.fixture
def crawl_config(project_root) -> ConfigManager:
    """A config whose taxonomy classifies EMS, so `family` is not all `unclassified`."""
    taxonomy = TAXONOMY_YAML.replace(
        "rules: []",
        "rules:\n  - match: [ems]\n    bu: tibco\n    family: messaging\n",
    )
    (project_root / "config" / "taxonomy.yaml").write_text(taxonomy, encoding="utf-8")
    (project_root / "config" / "docsite.yaml").write_text(json.dumps(DOCSITE), encoding="utf-8")
    return ConfigManager(root_dir=project_root)


@pytest.fixture
def crawler(client: DocsiteClient, crawl_config: ConfigManager) -> DocsiteCrawler:
    return DocsiteCrawler(client, crawl_config)


def _crawl(session: FakeSession, config: ConfigManager, **kwargs) -> CrawlResult:
    return DocsiteCrawler(DocsiteClient(DOCSITE, session=session), config).discover(**kwargs)


def _by_code(result: CrawlResult, code: str):
    return next(p for p in result.products if p.product_code == code)


# -- client -------------------------------------------------------------------


def test_client_absolutises_a_relative_path(client: DocsiteClient) -> None:
    assert client.url("/pub/ems.zip") == "https://docs.tibco.com/pub/ems.zip"


def test_client_passes_an_absolute_url_through(client: DocsiteClient) -> None:
    """The archive API returns `zipPath` in both forms, so both must survive."""
    assert client.url("https://elsewhere.example/ems.zip") == "https://elsewhere.example/ems.zip"


def test_active_zip_url_fills_both_template_slots(client: DocsiteClient) -> None:
    assert client.active_zip_url("ems/10.4.0") == (
        "https://docs.tibco.com/pub/ems/10.4.0/doc/zip/tib_ems_10.4.0_doc.zip"
    )


def test_active_zip_url_without_a_folder_path_is_none(client: DocsiteClient) -> None:
    """A guessed URL would be recorded in the catalog and only fail at download time."""
    assert client.active_zip_url("") is None


def test_get_json_raises_on_a_non_200(client: DocsiteClient) -> None:
    with pytest.raises(DocsiteError, match="404"):
        client.get_json("/api/products/nope")


def test_get_json_raises_on_html_served_with_a_200(session: FakeSession) -> None:
    """A login or error page answering 200 must not be mistaken for an empty product."""
    session.payloads["/api/a_to_z"] = None
    with pytest.raises(DocsiteError, match="did not return JSON"):
        DocsiteClient(DOCSITE, session=session).a_to_z()


def test_unknown_endpoint_names_the_config_file(client: DocsiteClient) -> None:
    with pytest.raises(DocsiteError, match="docsite.yaml"):
        client.product_list_by_suites()


def test_client_throttles_between_requests(session: FakeSession) -> None:
    import time

    throttled = DocsiteClient({**DOCSITE, "crawl": {"rate_limit_per_second": 20}}, session=session)
    started = time.monotonic()
    throttled.a_to_z()
    throttled.a_to_z()

    # Two requests at 20/s means at least one 50ms gap.
    assert time.monotonic() - started >= 0.04


# -- crawler: shape of the real payloads --------------------------------------


def test_discover_returns_catalog_shaped_products(crawler: DocsiteCrawler) -> None:
    result = crawler.discover()

    assert sorted(p.product_code for p in result.products) == ["ebx", "ems"]
    assert not result.errors


def test_product_code_comes_from_the_folder_path_not_the_slug(crawler: DocsiteCrawler) -> None:
    """`ems` is published as `tibco-enterprise-message-service`; the code is in the path."""
    ems = _by_code(crawler.discover(), "ems")

    assert ems.slug == "tibco-enterprise-message-service"


def test_the_detail_object_is_itself_the_current_version(crawler: DocsiteCrawler) -> None:
    """10.5.0 appears nowhere in `siblings` -- it is the product object's own version."""
    ems = _by_code(crawler.discover(), "ems")

    assert "10.5.0" in ems.versions
    assert ems.versions["10.5.0"].is_archived is False


def test_the_product_row_keeps_the_unversioned_display_name(crawler: DocsiteCrawler) -> None:
    """The detail name carries the version ('... 10.5.0'), which would go stale in a product row."""
    assert _by_code(crawler.discover(), "ems").display_name == "TIBCO Enterprise Message Service™"


def test_siblings_are_split_by_their_archive_flag(crawler: DocsiteCrawler) -> None:
    ems = _by_code(crawler.discover(), "ems").versions

    assert ems["10.4.0"].is_archived is False
    assert ems["10.2.1"].is_archived is True
    assert (ems["10.4.0"].convert_eligible, ems["10.2.1"].convert_eligible) == (True, False)


def test_active_versions_get_a_generated_zip_url(crawler: DocsiteCrawler) -> None:
    ems = _by_code(crawler.discover(), "ems")

    assert ems.versions["10.4.0"].zip_url.endswith("/pub/ems/10.4.0/doc/zip/tib_ems_10.4.0_doc.zip")


def test_iso_release_timestamps_are_trimmed_to_the_day(crawler: DocsiteCrawler) -> None:
    assert _by_code(crawler.discover(), "ems").versions["10.4.0"].release_date == "2025-02-06"


def test_a_stale_sibling_folder_path_is_not_turned_into_a_zip_url(crawler: DocsiteCrawler) -> None:
    """8.2.1 reports `folder_path: enterprise_message_service`; templating it would
    produce a confidently wrong URL recorded in the catalog as fact."""
    stale = _by_code(crawler.discover(), "ems").versions["8.2.1"]

    assert stale.is_archived is True
    assert stale.zip_url is None


def test_the_archive_index_supplies_archived_zip_endpoints(crawler: DocsiteCrawler) -> None:
    """10.2.1 is in both `siblings` and the archive index; the index has the real URL."""
    archived = _by_code(crawler.discover(), "ems").versions["10.2.1"]

    assert archived.zip_url == (
        "https://docs.tibco.com/pub/ems/tibco-enterprise-message-service-10-2-1_documentation.zip"
    )
    # normalize_date keeps a docsite month-year verbatim rather than dropping it.
    assert archived.release_date == "November 2022"


def test_the_archive_index_can_add_versions_siblings_omits(crawler: DocsiteCrawler) -> None:
    added = _by_code(crawler.discover(), "ems").versions["6.0.1"]

    assert added.is_archived is True
    assert added.convert_eligible is False
    assert added.zip_url.endswith("tibco-enterprise-message-service-6-0-1_documentation.zip")


def test_camelcase_and_alternate_list_keys_parse_the_same(crawler: DocsiteCrawler) -> None:
    ebx = _by_code(crawler.discover(), "ebx")

    assert "6.2.0" in ebx.versions
    assert ebx.versions["6.2.0"].release_date == "2025-02-01"
    assert ebx.versions["6.2.0"].zip_url.endswith("/pub/ebx/6.2.0/doc/zip/tib_ebx_6.2.0_doc.zip")


def test_unversioned_docsite_entries_are_skipped_and_counted(crawler: DocsiteCrawler) -> None:
    """Many A-to-Z entries are licence pages with nothing to convert."""
    result = crawler.discover()

    assert "adapter-code-for-joomla" not in [p.slug for p in result.products]
    assert result.unversioned == 1


def test_non_public_entries_are_skipped_before_the_request(
    crawler: DocsiteCrawler, session: FakeSession
) -> None:
    """Employee-only products answer with an SSO page as HTTP 200; asking is pure waste."""
    result = crawler.discover()

    assert result.non_public == 1
    assert "/api/products/tibco-policy-manager" not in session.calls
    assert not result.errors


def test_a_missing_visibility_flag_is_treated_as_public(crawler: DocsiteCrawler, session: FakeSession) -> None:
    """A schema change must not silently empty the crawl."""
    crawler.discover()

    assert "/api/products/adapter-code-for-joomla" in session.calls


def test_an_sso_page_served_as_200_says_so(session: FakeSession) -> None:
    session.payloads["/api/products/tibco-ebx"] = None
    session.get = _html_for(session, "/api/products/tibco-ebx", "<html><title>Redirecting to Pureauth</title>")

    with pytest.raises(DocsiteError, match="not public"):
        DocsiteClient(DOCSITE, session=session).product("tibco-ebx")


def _html_for(session: FakeSession, path: str, body: str):
    original = session.get

    def get(url: str, timeout: float | None = None):
        if url.endswith(path):
            session.calls.append(path)
            return FakeResponse(None, status_code=200, text=body)
        return original(url, timeout)

    return get


# -- crawler: classification --------------------------------------------------


def test_taxonomy_rules_classify_and_record_provenance(crawler: DocsiteCrawler) -> None:
    ems = _by_code(crawler.discover(), "ems")

    assert (ems.bu, ems.family) == ("tibco", "messaging")
    assert ems.family_source is FamilySource.TAXONOMY_RULE


def test_docsite_category_only_fills_an_unclassified_family(crawler: DocsiteCrawler) -> None:
    """EBX matches no rule, so the advisory category may promote it; EMS may not be touched."""
    result = crawler.discover()

    assert _by_code(result, "ebx").family == "data_management"
    assert _by_code(result, "ebx").family_source is FamilySource.DOCSITE_CATEGORY
    assert _by_code(result, "ems").family == "messaging"


def test_crawler_never_sets_engine_or_zip_source(crawler: DocsiteCrawler) -> None:
    """Discovery owns neither: the engine is detected after extraction, the ZIP source is the user's."""
    version = _by_code(crawler.discover(), "ems").versions["10.5.0"]

    assert str(version.engine) == "auto"
    assert str(version.engine_source) == "auto"
    assert str(version.zip_source) == "auto"
    assert version.convert_batch == ""


def test_folder_paths_and_ids_are_reported_for_the_state_db(crawler: DocsiteCrawler) -> None:
    result = crawler.discover()

    # Keyed by slug, matching the catalog and every `state.db` table. The value is
    # still the code-named folder -- that is what the ZIP URL is built from.
    slug = "tibco-enterprise-message-service"
    assert result.version_metadata[(slug, "10.4.0")]["folder_path"] == "ems/10.4.0"
    assert result.product_metadata[slug]["docsite_id"] == "644"
    assert result.product_metadata[slug]["docsite_slug"] == slug


# -- crawler: scoping ---------------------------------------------------------


def test_selectors_filter_before_the_per_product_request(crawler: DocsiteCrawler, session: FakeSession) -> None:
    """The point of --product/--batch is fewer requests, not just fewer rows."""
    result = crawler.discover(selectors=["tibco-enterprise-message-service"])

    assert [p.product_code for p in result.products] == ["ems"]
    assert "/api/products/tibco-ebx" not in session.calls


def test_a_selector_also_matches_a_slug_derived_code(crawler: DocsiteCrawler) -> None:
    """`--product ebx` must work even though the docsite slug is `tibco-ebx`."""
    assert [p.product_code for p in crawler.discover(selectors=["ebx"]).products] == ["ebx"]


def test_family_filter_applies_after_classification(crawler: DocsiteCrawler) -> None:
    assert [p.product_code for p in crawler.discover(family="messaging").products] == ["ems"]


def test_no_include_archived_skips_the_archive_request(
    client: DocsiteClient, crawl_config: ConfigManager, session: FakeSession
) -> None:
    """Archived siblings still appear -- the flag only skips the extra index request."""
    result = DocsiteCrawler(client, crawl_config, include_archived=False).discover()

    assert "6.0.1" not in _by_code(result, "ems").versions
    assert not [call for call in session.calls if "archive" in call]


def test_a_false_archive_flag_saves_the_request(session: FakeSession, crawl_config: ConfigManager) -> None:
    detail = PAYLOADS["/api/products/tibco-enterprise-message-service"]["result"]["product"]
    session.payloads["/api/products/tibco-enterprise-message-service"] = _envelope(
        "product", {**detail, "isArchiveExists": False}
    )
    _crawl(session, crawl_config)

    assert "/api/products/archive/tibco-enterprise-message-service" not in session.calls


def test_a_missing_archive_flag_still_checks(session: FakeSession, crawl_config: ConfigManager) -> None:
    """Absent is not false: the key is missing from some responses, and reading it
    as 'no archive' would silently lose every archived version."""
    detail = PAYLOADS["/api/products/tibco-enterprise-message-service"]["result"]["product"]
    session.payloads["/api/products/tibco-enterprise-message-service"] = _envelope(
        "product", {k: v for k, v in detail.items() if k != "isArchiveExists"}
    )
    _crawl(session, crawl_config)

    assert "/api/products/archive/tibco-enterprise-message-service" in session.calls


def test_progress_is_reported_per_product(crawler: DocsiteCrawler) -> None:
    seen: list[tuple[int, int, str]] = []
    crawler.discover(on_progress=lambda i, total, slug: seen.append((i, total, slug)))

    assert [item[0] for item in seen] == [1, 2, 3]
    assert all(item[1] == 3 for item in seen)


# -- crawler: partial failure -------------------------------------------------


def test_an_unreachable_product_is_excluded_not_emptied(
    session: FakeSession, crawl_config: ConfigManager
) -> None:
    """Critical: a product returned with zero versions would read to the merge as
    'every version was deleted upstream' and block the whole fetch."""
    del session.payloads["/api/products/tibco-ebx"]
    result = _crawl(session, crawl_config)

    assert [p.product_code for p in result.products] == ["ems"]
    assert any("tibco-ebx" in error for error in result.errors)


def test_a_failed_archive_index_keeps_the_active_versions(
    session: FakeSession, crawl_config: ConfigManager
) -> None:
    del session.payloads["/api/products/archive/tibco-enterprise-message-service"]
    result = _crawl(session, crawl_config)

    ems = _by_code(result, "ems")
    assert "10.5.0" in ems.versions
    assert "6.0.1" not in ems.versions
    assert any("archive index unavailable" in error for error in result.errors)


def test_a_failed_category_lookup_is_advisory_only(session: FakeSession, crawl_config: ConfigManager) -> None:
    del session.payloads["/api/bu_category_products"]
    result = _crawl(session, crawl_config)

    assert len(result.products) == 2
    assert _by_code(result, "ebx").family_source is FamilySource.UNCLASSIFIED
    assert any("advisory" in error for error in result.errors)


def test_a_failed_product_list_returns_nothing_rather_than_raising(
    session: FakeSession, crawl_config: ConfigManager
) -> None:
    del session.payloads["/api/a_to_z"]
    result = _crawl(session, crawl_config)

    assert result.products == []
    assert any("product list" in error for error in result.errors)
