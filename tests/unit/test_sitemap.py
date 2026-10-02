"""Unit tests for the Coveo sitemap fetcher and parser (planning.md Phase 33).

No network. The XML mirrors the live files observed 2026-10-02, including the
leaf's wrong default namespace (`.../sitemap.xsd`) that a namespace-strict parser
rejects, a duplicate product entry, and an unencoded space in a `loc`.
"""

import pytest

from docushift.discovery import DocsiteClient
from docushift.discovery.sitemap import SitemapCache, SitemapError, fetch, leaf_stem, parse_index, parse_urlset

BASE = "https://docs.tibco.com/ftp_portal/coveo"

ROOT = f"""<?xml version='1.0'?>
<sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
  <sitemap><loc>{BASE}/tibco-ems.xml</loc><lastmod>2026-10-01</lastmod></sitemap>
  <sitemap><loc>{BASE}/other.xml</loc><lastmod>2026-10-01</lastmod></sitemap>
  <sitemap><loc>{BASE}/tibco-ems.xml</loc><lastmod>2026-10-01</lastmod></sitemap>
</sitemapindex>""".encode()

PRODUCT = f"""<?xml version='1.0'?>
<sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
  <sitemap><loc>{BASE}/tibco-ems-10-5-1.xml</loc><lastmod>2026-09-17</lastmod></sitemap>
  <sitemap><loc>{BASE}/tibco-ems-10-5-0.xml</loc><lastmod>2026-09-17</lastmod></sitemap>
</sitemapindex>""".encode()

LEAF = b"""<?xml version='1.0'?>
<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd'
        xmlns:coveo='http://www.coveo.com/schemas/metadata'>
  <url>
    <loc>https://docs.tibco.com/pub/ems/10.5.1/doc/html/_shared/about-this-product.htm</loc>
    <lastmod>2026-09-16</lastmod>
    <coveo:metadata>
      <productversion>10.5.1</productversion>
      <access_level>Public</access_level>
      <d_name>About this Product</d_name>
    </coveo:metadata>
  </url>
  <url><loc>https://docs.tibco.com/pub/ems/10.5.1/doc/html/API Activity/x.htm</loc></url>
</urlset>"""


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code


class FakeSession:
    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self.calls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout: float | None = None):
        self.calls.append(url)
        if url not in self.files:
            return FakeResponse(b"", 404)
        return FakeResponse(self.files[url])


@pytest.fixture
def files() -> dict[str, bytes]:
    return {
        f"{BASE}/sitemap.xml": ROOT,
        f"{BASE}/tibco-ems.xml": PRODUCT,
        f"{BASE}/tibco-ems-10-5-1.xml": LEAF,
        # 10-5-0 is served as the docsite serves a missing path: 200, empty body.
        f"{BASE}/tibco-ems-10-5-0.xml": b"",
    }


def _client(session: FakeSession) -> DocsiteClient:
    return DocsiteClient({"crawl": {"rate_limit_per_second": 0}}, session=session)


def test_parse_leaf_despite_wrong_namespace():
    pages = parse_urlset(LEAF)
    assert [p.title for p in pages] == ["About this Product", ""]
    assert pages[0].version == "10.5.1" and pages[0].access_level == "Public"
    # Kept exactly as published; normalising is the join's decision.
    assert pages[1].loc.endswith("API Activity/x.htm")


def test_level_mismatch_and_garbage_raise():
    with pytest.raises(SitemapError):
        parse_index(LEAF)
    with pytest.raises(SitemapError):
        parse_urlset(b"<html>sign in</html")


def test_leaf_stem_matches_catalog_keys():
    assert leaf_stem("tibco-ems", "10.5.1") == "tibco-ems-10-5-1"


def test_fetch_walks_levels_and_records_failures(tmp_path, files):
    session = FakeSession(files)
    cache = SitemapCache(tmp_path)
    result = fetch(_client(session), cache, "/ftp_portal/coveo/sitemap.xml", ["tibco-ems", "absent"])

    assert result.duplicates == ["tibco-ems"]
    assert result.missing == ["absent"]
    # The empty 10-5-0 body is an error, not an empty page list.
    assert result.products == {"tibco-ems": ["tibco-ems-10-5-1"]}
    assert any("empty body" in e for e in result.errors)
    assert [p.title for p in cache.pages("tibco-ems", "10.5.1")][:1] == ["About this Product"]
    assert cache.pages("tibco-ems", "10.5.0") is None
    # `other` was not asked for, so it was not fetched.
    assert f"{BASE}/other.xml" not in session.calls


def test_unchanged_lastmod_is_reused(tmp_path, files):
    cache = SitemapCache(tmp_path)
    fetch(_client(FakeSession(files)), cache, "/ftp_portal/coveo/sitemap.xml", ["tibco-ems"])

    session = FakeSession(files)
    result = fetch(_client(session), cache, "/ftp_portal/coveo/sitemap.xml", ["tibco-ems"])
    # Root always; product and 10-5-1 reused; 10-5-0 retried because it never landed.
    assert result.reused == 2
    assert session.calls == [f"{BASE}/sitemap.xml", f"{BASE}/tibco-ems-10-5-0.xml"]


def test_cache_cannot_be_escaped(tmp_path):
    cache = SitemapCache(tmp_path / "coveo")
    assert cache.path("../../evil.xml") == tmp_path / "coveo" / "evil.xml"


LOGIN = b"""<!DOCTYPE html>
<html lang="en" data-ng-app="loginPage">
    <head>
        <title>Login</title>
        <link rel="stylesheet" href="/ftp_portal/stylesheets/style.css">
    </head>
</html>"""


def test_login_page_is_not_served_and_never_cached(tmp_path, files):
    # Observed 2026-10-02: 297 product and version files answered with the portal
    # login page and HTTP 200. Cached, they crashed every later `pages()` read.
    files[f"{BASE}/tibco-ems-10-5-0.xml"] = LOGIN
    cache = SitemapCache(tmp_path)
    result = fetch(_client(FakeSession(files)), cache, "/ftp_portal/coveo/sitemap.xml", ["tibco-ems"])

    assert result.not_served == ["tibco-ems-10-5-0.xml"]
    assert not any("10-5-0" in e for e in result.errors)
    assert result.products == {"tibco-ems": ["tibco-ems-10-5-1"]}
    assert cache.read("tibco-ems-10-5-0.xml") is None
    assert cache.pages("tibco-ems", "10.5.0") is None


def test_a_cached_login_page_is_refetched_and_dropped(tmp_path, files):
    # A cache written before the check existed: the login page sits on disk under
    # the product's name with a matching lastmod. It must not be reused.
    cache = SitemapCache(tmp_path)
    cache.write("tibco-ems.xml", LOGIN)
    cache.save_manifest({"files": {"tibco-ems.xml": "2026-10-01"}, "products": {"tibco-ems": ["tibco-ems-10-5-1"]}})
    files[f"{BASE}/tibco-ems.xml"] = LOGIN

    result = fetch(_client(FakeSession(files)), cache, "/ftp_portal/coveo/sitemap.xml", ["tibco-ems"])

    assert result.reused == 0
    assert result.not_served == ["tibco-ems.xml"]
    assert cache.read("tibco-ems.xml") is None
    assert "tibco-ems" not in cache.manifest()["products"]
    assert cache.pages("tibco-ems", "10.5.1") is None


def test_xml_of_the_wrong_level_is_an_error_not_not_served(tmp_path, files):
    files[f"{BASE}/tibco-ems-10-5-0.xml"] = PRODUCT
    result = fetch(_client(FakeSession(files)), SitemapCache(tmp_path), "/ftp_portal/coveo/sitemap.xml", ["tibco-ems"])
    assert result.not_served == []
    assert any(e.startswith("tibco-ems-10-5-0.xml: expected <urlset>") for e in result.errors)


def test_renamed_product_leaf_matched_by_version_suffix():
    from docushift.discovery.sitemap import match_leaf

    stems = ["spotfire-streaming-11-1-0", "tibco-streaming-11-1-2", "tibco-streaming-11-1-0-beta"]
    assert match_leaf(stems, "tibco-streaming", "11.1.2") == "tibco-streaming-11-1-2"
    assert match_leaf(stems, "tibco-streaming", "11.1.0") == "spotfire-streaming-11-1-0"
    assert match_leaf(["a-1-0", "b-1-0"], "c", "1.0") is None
    assert match_leaf(stems, "tibco-streaming", "9.9.9") is None


def test_version_suffix_cannot_claim_a_longer_version():
    from docushift.discovery.sitemap import match_leaf

    assert match_leaf(["old-name-2-1-0"], "new-name", "1.0") is None
    assert match_leaf(["old-name-2-1-0"], "new-name", "2.1.0") == "old-name-2-1-0"
