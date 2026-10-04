"""Phase 22: the live docsite URL a converted topic is served at today.

Everything here is about declining to guess. The module's whole design premise is
that four source layouts exist in one catalog and a rule that infers the fifth is
wrong in a way nobody sees until a reader follows a dead redirect -- so most of
these tests assert that a malformed or absent declaration produces `None` rather
than a plausible URL.
"""

from docushift import origins

TEMPLATE = "https://docs.tibco.com/pub/{folder_path}/doc/{path}"
EMS = {"tibco-enterprise-message-service": {"template": TEMPLATE, "drop_segments": 1}}


# -- the declaration -------------------------------------------------------------


def test_a_declared_product_yields_its_template() -> None:
    found = origins.template_for(EMS, "tibco-enterprise-message-service")
    assert found == origins.OriginTemplate(template=TEMPLATE, drop_segments=1)


def test_an_undeclared_product_yields_nothing_rather_than_a_default() -> None:
    """The routine answer, not an error: one product is declared today."""
    assert origins.template_for(EMS, "tibco-runtime-agent") is None
    assert origins.template_for({}, "tibco-enterprise-message-service") is None


def test_a_template_that_cannot_place_the_path_is_declined() -> None:
    """It would render one URL for every topic in the product -- which is to say
    it would redirect eight thousand pages to the same place and look declared."""
    declared = {"ems": {"template": "https://docs.tibco.com/pub/{folder_path}/doc/"}}
    assert origins.template_for(declared, "ems") is None


def test_an_empty_or_unreadable_declaration_is_the_same_as_none() -> None:
    assert origins.template_for({"ems": {"template": "  "}}, "ems") is None
    assert origins.template_for({"ems": "a string"}, "ems") is None
    assert origins.template_for(
        {"ems": {"template": TEMPLATE, "drop_segments": "one"}}, "ems") is None


def test_drop_segments_defaults_to_keeping_the_whole_path() -> None:
    found = origins.template_for({"ems": {"template": TEMPLATE}}, "ems")
    assert found is not None and found.drop_segments == 0


# -- the folder the docsite serves from -------------------------------------------


def test_the_folder_comes_off_the_url_the_downloader_actually_fetched() -> None:
    assert origins.folder_path(
        "https://docs.tibco.com/pub/ems/10.5.1/TIB_ems_10.5.1_docs.zip") == "ems/10.5.1"


def test_a_nested_package_folder_keeps_every_segment_between_pub_and_the_file() -> None:
    assert origins.folder_path(
        "https://docs.tibco.com/pub/bw/plugins/6.1.0/x.zip") == "bw/plugins/6.1.0"


def test_an_archived_versions_zip_path_is_not_read_as_a_docsite_url() -> None:
    """The API returns it verbatim and its shape is not this one; inventing a
    folder from it would produce redirects into a tree that is not served."""
    assert origins.folder_path("/archive/ems/TIB_ems_8.0.0_docs.zip") is None
    assert origins.folder_path("https://docs.tibco.com/pub/x.zip") is None
    assert origins.folder_path(None) is None
    assert origins.folder_path("") is None


# -- one URL ----------------------------------------------------------------------


def test_the_package_wrapper_is_dropped_and_the_rest_is_the_served_path() -> None:
    template = origins.OriginTemplate(TEMPLATE, drop_segments=1)
    assert origins.origin_url(template, "ems/10.5.1", "TIB_ems_10.5.1/html/intro.htm") == (
        "https://docs.tibco.com/pub/ems/10.5.1/doc/html/intro.htm")


def test_a_path_with_nothing_left_after_the_drop_yields_no_url() -> None:
    """Reported by the caller rather than quietly rendered as the folder root,
    which would 301 a page to the product's landing page and look deliberate."""
    template = origins.OriginTemplate(TEMPLATE, drop_segments=1)
    assert origins.origin_url(template, "ems/10.5.1", "TIB_ems_10.5.1") is None


def test_the_path_is_percent_encoded_the_way_every_other_url_here_is() -> None:
    template = origins.OriginTemplate(TEMPLATE, drop_segments=0)
    url = origins.origin_url(template, "ems/10.5.1", "html/about this product.htm")
    assert url.endswith("doc/html/about%20this%20product.htm")


# -- a version's rows -------------------------------------------------------------


def test_a_topic_that_moved_points_at_the_page_that_absorbed_it() -> None:
    template = origins.OriginTemplate(TEMPLATE, drop_segments=1)
    built, dropped = origins.rows(
        {"pkg/html/intro.htm": "users-guide/intro.md"},
        {"users-guide/intro.md": "users-guide/getting-started.md#intro"},
        template, "ems/10.5.1")
    assert dropped == []
    assert built == [{
        "from": "https://docs.tibco.com/pub/ems/10.5.1/doc/html/intro.htm",
        "to": "users-guide/getting-started.md#intro",
        "status": 301,
    }]


def test_a_topic_that_did_not_move_takes_its_own_output_path() -> None:
    """The only correct default, and the one that makes this work for a product
    that never reframes at all."""
    template = origins.OriginTemplate(TEMPLATE, drop_segments=1)
    built, _ = origins.rows({"pkg/html/intro.htm": "users-guide/intro.md"}, {},
                            template, "ems/10.5.1")
    assert built[0]["to"] == "users-guide/intro.md"


def test_the_sources_that_produced_no_url_are_returned_rather_than_dropped() -> None:
    """So the caller can assert the count against `output_map` instead of
    discovering a short map after cutover."""
    template = origins.OriginTemplate(TEMPLATE, drop_segments=2)
    built, dropped = origins.rows({"pkg/intro.htm": "intro.md"}, {},
                                  template, "ems/10.5.1")
    assert built == [] and dropped == ["pkg/intro.htm"]


def test_rows_are_sorted_by_the_side_a_web_server_looks_them_up_on() -> None:
    template = origins.OriginTemplate(TEMPLATE, drop_segments=1)
    built, _ = origins.rows(
        {"pkg/html/z.htm": "z.md", "pkg/html/a.htm": "a.md"}, {}, template, "ems/1")
    assert [row["from"] for row in built] == sorted(row["from"] for row in built)


def test_the_document_uses_the_key_the_existing_parser_already_reads() -> None:
    """One shape for both maps, so `sync/redirects.parse` needs no variant."""
    assert origins.document([{"from": "a", "to": "b"}]) == {
        "redirects": [{"from": "a", "to": "b"}]}


# -- Phase 33: derived from the docsite's sitemap ---------------------------------

LIVE = "https://docs.tibco.com/pub/ems/10.5.1/doc/html"
SOURCES = {f"tib_ems_docs/html/{name}": f"out/{name}" for name in ("a.htm", "b.htm", "API Activity/c.htm")}
PAGES = [f"{LIVE}/a.htm", f"{LIVE}/b.htm", f"{LIVE}/API Activity/c.htm", f"{LIVE}/api/ref.htm"]


def test_the_sitemap_derives_the_mapping_ems_declares() -> None:
    """Drop 1 under `.../doc` and drop 2 under `.../doc/html` are the same URLs,
    so they are one answer, not a tie; the smaller drop names it."""
    found = origins.derive(SOURCES, PAGES, "ems/10.5.1")
    assert found.template == origins.OriginTemplate(
        template="https://docs.tibco.com/pub/ems/10.5.1/doc/{path}", drop_segments=1
    )
    assert (found.hits, found.rival, found.sources) == (3, 0, 3)


def test_pages_the_tool_does_not_convert_do_not_lower_coverage() -> None:
    """Coverage is of the converted sources; the API reference only adds listed pages."""
    pages = PAGES + [f"{LIVE}/api/ref{i}.htm" for i in range(50)]
    assert origins.derive(SOURCES, pages, "ems/10.5.1").template is not None


def test_low_coverage_derives_nothing() -> None:
    sources = dict(SOURCES) | {f"tib_ems_docs/html/x{i}.htm": "out" for i in range(5)}
    found = origins.derive(sources, PAGES, "ems/10.5.1")
    assert found.template is None and found.hits == 3 and found.sources == 8


def test_two_different_answers_of_equal_weight_derive_nothing() -> None:
    other = "https://docs.tibco.com/pub/ems/10.5.1/doc/mirror"
    pages = [f"{LIVE}/a.htm", f"{other}/html/b.htm"]
    found = origins.derive({"w/html/a.htm": "", "w/html/b.htm": ""}, pages, "ems/10.5.1")
    assert found.template is None and found.rival > 0


def test_a_page_of_another_folder_cannot_win() -> None:
    """The folder guard: a matching tail under another version is not this version's page."""
    pages = [p.replace("10.5.1", "10.4.0") for p in PAGES]
    assert origins.derive(SOURCES, pages, "ems/10.5.1").template is None
    assert origins.derive(SOURCES, pages, None).template is not None


def test_no_pages_or_no_sources_derive_nothing() -> None:
    assert origins.derive(SOURCES, [], "ems/10.5.1").template is None
    assert origins.derive({}, PAGES, "ems/10.5.1").template is None


def test_a_derived_template_renders_rows_that_match_the_listing() -> None:
    template = origins.derive(SOURCES, PAGES, "ems/10.5.1").template
    built, dropped = origins.rows(SOURCES, {}, template, "")
    assert not dropped
    kept, unlisted = origins.listed(built, PAGES)
    # `API%20Activity` (emitted) and `API Activity` (published) are one page.
    assert len(kept) == 3 and unlisted == []
    assert origins.unmapped(kept, PAGES) == [f"{LIVE}/api/ref.htm"]


def test_a_row_the_sitemap_does_not_list_is_split_out() -> None:
    built = [{"from": f"{LIVE}/a.htm", "to": "a", "status": 301},
             {"from": f"{LIVE}/gone.htm", "to": "g", "status": 301}]
    kept, unlisted = origins.listed(built, PAGES)
    assert [row["to"] for row in kept] == ["a"]
    assert unlisted == [f"{LIVE}/gone.htm"]


def test_a_brace_in_a_published_path_is_not_a_placeholder() -> None:
    live = "https://docs.tibco.com/pub/x/1.0/doc{s}"
    template = origins.derive({"w/a.htm": "a"}, [f"{live}/a.htm"], "x/1.0").template
    built, _ = origins.rows({"w/a.htm": "a"}, {}, template, "")
    assert built[0]["from"] == f"{live}/a.htm"


def test_page_path_decodes_and_drops_the_host() -> None:
    assert origins.page_path(f"{LIVE}/API%20Activity/c.htm") == "pub/ems/10.5.1/doc/html/API Activity/c.htm"


# -- R1-07: a declaration that fails validation is named, not ignored --------------

ZIP = "https://docs.tibco.com/pub/ems/10.5.1/TIB_ems_10.5.1_docs.zip"


def codes_of(built: origins.Built) -> list[str]:
    return [code for code, _, _ in built.findings]


def test_a_rejected_declaration_is_reported_and_says_why() -> None:
    """`drop_segments: "one"` used to read as no declaration at all: the sitemap
    took over and its message said none was declared, so the human who wrote
    one was never told it had been thrown away."""
    declared = {"ems": {"template": TEMPLATE, "drop_segments": "one"}}

    built = origins.build(declared, "ems", ZIP, SOURCES, {}, PAGES)

    rejected = [f for f in built.findings if f[0] == "ORIGIN_TEMPLATE_REJECTED"]
    assert len(rejected) == 1 and "drop_segments" in rejected[0][1]
    # The sitemap still answers, row by row, so the version is not left without a map.
    assert built.rows is not None and len(built.rows) == 3


def test_a_rejected_declaration_with_no_sitemap_does_not_claim_none_was_declared() -> None:
    declared = {"ems": {"template": "https://docs.tibco.com/pub/{folder_path}/doc/"}}

    built = origins.build(declared, "ems", ZIP, SOURCES, {}, [])

    assert codes_of(built) == ["ORIGIN_TEMPLATE_REJECTED", "ORIGIN_SITEMAP_MISSING"]
    assert "{path}" in built.findings[0][1]
    assert "no template in" not in built.findings[1][1]
    assert built.rows is None


def test_a_template_naming_an_unknown_placeholder_is_rejected_rather_than_raising() -> None:
    """`str.format` raised `KeyError` mid-run on `{version}`."""
    declared = {"ems": {"template": "https://docs.tibco.com/pub/{version}/{path}"}}

    assert origins.template_for(declared, "ems") is None
    built = origins.build(declared, "ems", ZIP, SOURCES, {}, [])
    assert codes_of(built)[0] == "ORIGIN_TEMPLATE_REJECTED"
    assert "{version}" in built.findings[0][1]


def test_an_undeclared_product_raises_no_rejection() -> None:
    assert "ORIGIN_TEMPLATE_REJECTED" not in codes_of(
        origins.build({}, "ems", ZIP, SOURCES, {}, PAGES))


def test_sources_too_short_for_drop_segments_have_their_own_code_and_count() -> None:
    """They were reported as `ORIGIN_TEMPLATE_UNDECLARED` with a count of 1 --
    the wrong condition, and a magnitude that said one whatever the number."""
    declared = {"ems": {"template": TEMPLATE, "drop_segments": 2}}
    output_map = {"a.htm": "a.md", "b.htm": "b.md", "pkg/html/c.htm": "c.md"}

    built = origins.build(declared, "ems", ZIP, output_map, {}, [])

    short = [f for f in built.findings if f[0] == "ORIGIN_PATH_TOO_SHORT"]
    assert len(short) == 1 and short[0][2] == 2
    assert "ORIGIN_TEMPLATE_UNDECLARED" not in codes_of(built)


# -- why there is no page list (X1-11) -----------------------------------------------


def _leaf(tmp_path, products: dict, leaves: dict[str, str]) -> None:
    from docushift.discovery.sitemap import SitemapCache

    cache = SitemapCache(tmp_path / "coveo")
    for stem, body in leaves.items():
        cache.write(f"{stem}.xml", body.encode())
    cache.save_manifest({"files": {}, "products": products})


URLSET = ("<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd'>"
          "<url><loc>https://docs.tibco.com/pub/ems/1.0/doc/a.htm</loc></url></urlset>")


def test_a_corrupt_manifest_is_no_list_with_a_reason_rather_than_an_exception(tmp_path) -> None:
    """X1-11. `json.loads` raised out of `page_list`, and only `SitemapError` was caught."""
    (tmp_path / "coveo").mkdir()
    (tmp_path / "coveo" / "manifest.json").write_text("{not json", encoding="utf-8")

    pages, reason = origins.listing(tmp_path, "ems", "1.0")

    assert pages == [] and "manifest.json cannot be read" in reason
    assert origins.page_list(tmp_path, "ems", "1.0") == []


def test_no_leaf_and_a_missing_leaf_file_are_told_apart(tmp_path) -> None:
    """X1-11. Both were one `None`, so the finding could not say which."""
    _leaf(tmp_path, {"ems": ["ems-1-0"]}, {})

    assert "lists no page list for 2.0" in origins.listing(tmp_path, "ems", "2.0")[1]
    assert "ems-1-0.xml" in origins.listing(tmp_path, "ems", "1.0")[1]
    assert "is missing" in origins.listing(tmp_path, "ems", "1.0")[1]
    assert "no product file for ftl" in origins.listing(tmp_path, "ftl", "1.0")[1]


def test_a_listed_version_has_its_pages_and_no_reason(tmp_path) -> None:
    _leaf(tmp_path, {"ems": ["ems-1-0"]}, {"ems-1-0": URLSET})

    assert origins.listing(tmp_path, "ems", "1.0") == (
        ["https://docs.tibco.com/pub/ems/1.0/doc/a.htm"], "")


def test_the_missing_sitemap_finding_carries_the_reason() -> None:
    built = origins.build({}, "ems", None, {"a.htm": "a.md"}, {}, [], "there is no cache/coveo/manifest.json")

    assert built.rows is None
    assert "(there is no cache/coveo/manifest.json)" in built.findings[0][1]
