"""Phase 55: `verify` finds what was lost, and only that.

The verification rule from the plan: a fixture with one dropped paragraph, one
dropped image and one moved TOC entry produces exactly those findings; a clean
fixture, and one whose only differences are known drops, produce none.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from docushift.models import Catalog, SourceEngine
from docushift.sync import redirects
from docushift.reporting.findings import FindingsRun
from docushift.validation.tree import walk
from docushift.verify import images, live, published
from docushift.verify import text as texts
from docushift.verify import redirects as redirect_maps
from docushift.verify.driver import Verifier
from docushift.verify.fetch import Fetched
from docushift.verify.toc import Node, by_page, by_title, root
from tests.conftest import make_product, make_version
from tests.unit.test_flare import build, manifest, toc_files, topic

# -- text ------------------------------------------------------------------------


def test_a_clean_conversion_covers_every_sentence() -> None:
    old = texts.html_text(topic("Install", "<p>Run the installer. Then restart the service.</p>"),
                          "div#mc-main-content", ("div#feedback-survey",))
    new = texts.markdown_text("# Install\n\nRun the installer. Then restart the service.\n")

    cover = texts.coverage(old, new)
    assert cover.missing == [] and cover.percent == 100.0


def test_a_dropped_paragraph_is_quoted_sentence_by_sentence() -> None:
    old = texts.Text(["Keep this sentence here please.", "This whole paragraph went missing somewhere."])
    new = texts.markdown_text("Keep this sentence here please.\n")

    assert texts.coverage(old, new).missing == ["This whole paragraph went missing somewhere."]


def test_table_cells_match_however_the_row_is_laid_out() -> None:
    html = ("<div id='c'><table><tbody><tr><td>WebFOCUS URL</td><td>http://localhost:8080/ibi_apps</td>"
            "<td>The base URL of your server.</td></tr></tbody></table></div>")
    md = ("| Field | Default | Notes |\n| --- | --- | --- |\n"
          "| WebFOCUS URL | http://localhost:8080/ibi_apps | The base URL of your server. |\n")

    assert texts.coverage(texts.html_text(html, "#c"), texts.markdown_text(md)).missing == []


def test_comments_and_hidden_chrome_are_not_page_text() -> None:
    html = "<div id='c'><p>Real text stays here.</p><!-- <p>Note to writers: fill this in later.</p> --></div>"

    assert texts.html_text(html, "#c").blocks == ["Real text stays here."]


def test_a_hard_line_break_ends_a_block_as_aem_renders_it() -> None:
    """`**Question?**\\` then the answer: AEM serves them as two blocks (2026-10-23)."""
    md = "**Can the assistant see my reports?**\\\nNo. It reads only what you can.\n"

    assert texts.markdown_text(md).blocks == ["Can the assistant see my reports?", "No. It reads only what you can."]


def test_inline_code_keeps_angle_brackets_and_backslashes() -> None:
    new = texts.markdown_text("Settings live in `<install-root>/config\\.env` on disk.\n")

    assert "<install-root>/config\\.env" in new.blocks[0]


def test_a_changed_word_is_forgiven_and_a_dropped_clause_is_not() -> None:
    target = texts.markdown_text(
        "The assistant reads the page you are on and suggests three follow-up questions for you.\n")
    close = "The assistant reads the page you are on and suggests three follow-up questions for users."
    cut = "The assistant reads the page you are on and then writes a whole new report for you."

    assert texts.present(close, target)
    assert not texts.present(cut, target)


def test_the_landing_page_is_cut_where_the_converter_cuts_it() -> None:
    old = texts.Text(["Product overview text here.", "Release Documents", "Readme", "Release Notes"])

    assert texts.cut_at(old, frozenset({"release documents"})).blocks == ["Product overview text here."]


# -- images ----------------------------------------------------------------------


def _png(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_a_renamed_image_still_matches_by_content(tmp_path: Path) -> None:
    _png(tmp_path / "src/Resources/Images/a-very-long-original-name.png", b"same bytes")
    _png(tmp_path / "out/images/short.png", b"same bytes")
    page = tmp_path / "src/topic.htm"
    soup = BeautifulSoup("<div><img src='Resources/Images/a-very-long-original-name.png'></div>", "html.parser")

    found = images.html_images(soup.div, page)
    held = images.markdown_images("![](images/short.png)", tmp_path / "out/topic.md")

    assert images.missing(found, held) == []


def test_skin_pictures_are_chrome_and_a_dropped_picture_is_missing(tmp_path: Path) -> None:
    _png(tmp_path / "src/Skins/Default/transparent.gif", b"spacer")
    _png(tmp_path / "src/Resources/shot.png", b"screenshot")
    soup = BeautifulSoup("<div><img src='Skins/Default/transparent.gif'><img src='Resources/shot.png'></div>",
                         "html.parser")

    found = images.html_images(soup.div, tmp_path / "src/topic.htm")

    assert [p.src for p in found.pictures] == ["Resources/shot.png"]
    assert [p.src for p in images.missing(found, images.PageImages())] == ["Resources/shot.png"]


# -- TOC ------------------------------------------------------------------------


def _tree() -> Node:
    return root([
        Node("Guide", "guide.md", [Node("One", "one.md"), Node("Two", "two.md"), Node("Three", "three.md")]),
        Node("Other", "other.md", [Node("Four", "four.md")]),
    ])


def test_an_identical_toc_has_no_issues() -> None:
    assert by_page(_tree(), _tree()).issues == []


def test_a_moved_entry_is_one_move_and_not_also_a_reorder() -> None:
    new = root([
        Node("Guide", "guide.md", [Node("One", "one.md"), Node("Three", "three.md")]),
        Node("Other", "other.md", [Node("Two", "two.md"), Node("Four", "four.md")]),
    ])

    assert [(i.kind, i.key) for i in by_page(_tree(), new).issues] == [("moved", "two.md")]


def test_swapped_siblings_are_one_order_issue_for_their_parent() -> None:
    new = root([
        Node("Guide", "guide.md", [Node("Two", "two.md"), Node("One", "one.md"), Node("Three", "three.md")]),
        Node("Other", "other.md", [Node("Four", "four.md")]),
    ])

    assert [(i.kind, i.key) for i in by_page(_tree(), new).issues] == [("order", "guide.md")]


def test_a_missing_entry_is_reported_unless_it_is_a_known_drop() -> None:
    new = root([Node("Guide", "guide.md", [Node("One", "one.md"), Node("Two", "two.md")]),
                Node("Other", "other.md", [Node("Four", "four.md")])])

    assert [(i.kind, i.key) for i in by_page(_tree(), new).issues] == [("missing", "three.md")]
    assert by_page(_tree(), new, skip={"three.md"}).issues == []


def test_a_row_repeating_its_parents_page_adds_nothing_to_compare() -> None:
    old = root([Node("Guide", "guide.md", [Node("Guide again", "guide.md")])])

    assert by_page(old, root([Node("Guide", "guide.md")])).issues == []


def test_the_served_menu_is_matched_by_title_and_learns_each_url() -> None:
    local = root([Node("Install", "a.md", [Node("Linux", "b.md"), Node("Windows", "c.md")])])
    served = root([Node("Install", ref="u/a", children=[Node("Windows", ref="u/c"), Node("Linux", ref="u/b")])])

    compared = by_title(local, served)

    assert [(i.kind, i.key) for i in compared.issues] == [("order", "Install")]
    assert {local.children[0].children[0].title: compared.matched[id(local.children[0].children[0])].ref} == {
        "Linux": "u/b"}


# -- staging ---------------------------------------------------------------------

BASE = "https://stg.example.com"
VERSION = f"{BASE}/us/en/prod/online-help/1-0-0.html"


def _served(path: str, article: str = "", menu: str = "", title: str = "Guide") -> str:
    """A staging page: the menu, then the title *above* the article, as AEM lays it out."""
    return (
        f"<html><body><nav class='cmp-navigation'><ul class='cmp-navigation__group'>{menu}</ul></nav>"
        f"<main id='section-topic' data-page-path='/content/ibi/us/en/prod/online-help/1-0-0{path}'>"
        f"<h1 id='topic-title'>{title}</h1>"
        f"<div class='topic-renderer__content'>{article}</div></main></body></html>"
    )


def _item(title: str, href: str, children: str = "") -> str:
    sub = f"<ul class='cmp-navigation__group'>{children}</ul>" if children else ""
    return (f"<li class='cmp-navigation__item'><div class='cmp-navigation__item-container'>"
            f"<a class='cmp-navigation__item-link' href='{href}'>{title}</a></div>{sub}</li>")


class FakeFetcher:
    def __init__(self, pages: dict[str, tuple[int, bytes]]) -> None:
        self.pages, self.requests = pages, 0

    def get(self, url: str) -> Fetched:
        status, body = self.pages.get(url, (200, _served("").encode()))  # the home-page fallback
        return Fetched(url, status, body)


def test_the_version_url_is_built_from_the_locale_and_segment() -> None:
    assert published.version_url(BASE, "en-us", "prod", "online-help", "1-0-0") == VERSION


def test_the_menu_is_read_from_the_first_rows_page_before_the_version_stub() -> None:
    """`.../9-3-8.html` is a landing stub with no menu (2026-10-23); `_templates/Home.md`
    is served as `.../9-3-8/home.html` (the probe)."""
    toc = root([Node("Product", "_templates/Home.md"), Node("Guide", "guide.md")])

    assert published.entry_urls(BASE, "en-us", "prod", "online-help", "1-0-0", toc) == [
        f"{BASE}/us/en/prod/online-help/1-0-0/home.html", VERSION]


def test_the_page_title_above_the_article_is_page_text(tmp_path: Path) -> None:
    folder = tmp_path / "online-help" / "1-0-0"
    folder.mkdir(parents=True)
    (folder / "guide.md").write_text("# Choosing an AI Model Wisely\n\nBody text that is served here.\n",
                                     encoding="utf-8")
    menu = _item("Guide", "/us/en/prod/online-help/1-0-0/guide.html")
    url = f"{BASE}/us/en/prod/online-help/1-0-0/guide.html"
    fetcher = FakeFetcher({
        VERSION: (200, _served("", menu=menu).encode()),
        url: (200, _served("/guide", "<p>Body text that is served here.</p>", menu,
                           title="Choosing an AI Model Wisely").encode()),
    })

    checked = published.check(fetcher, VERSION, root([Node("Guide", "guide.md")]), folder)

    assert checked.pages["guide.md"].missing == []


def test_a_home_page_fallback_is_not_the_page() -> None:
    url = f"{BASE}/us/en/prod/online-help/1-0-0/guide/one.html"

    assert published.is_page(_served("/guide/one"), url)
    assert not published.is_page(_served(""), url)


def test_staging_reports_unlabelled_notes_dropped_alt_text_and_changed_bytes(tmp_path: Path) -> None:
    folder = tmp_path / "online-help" / "1-0-0"
    _png(folder / "images/a.png", b"repo bytes")
    _png(folder / "images/b.png", b"other bytes")
    (folder / "guide.md").write_text(
        "# Guide\n\n> [!NOTE]\n> Mind the gap please.\n\n![Alt words: here](images/a.png)\n\n"
        "![Plain](images/b.png)\n\nA served sentence that is long enough.\n", encoding="utf-8")
    menu = _item("Guide", "/us/en/prod/online-help/1-0-0/guide.html")
    article = ("<div class='lq'><a data-attr-keyref='!NOTE'></a> Mind the gap please.</div>"
               "<img src='/content/dam/ibi/us/en/prod/online-help/1-0-0/images/a.png'>"
               "<img src='/content/dam/ibi/us/en/prod/online-help/1-0-0/images/b.png' alt='Plain'>"
               "<p>A served sentence that is long enough.</p>")
    fetcher = FakeFetcher({
        VERSION: (200, _served("", menu=menu).encode()),
        f"{BASE}/us/en/prod/online-help/1-0-0/guide.html": (200, _served("/guide", article, menu).encode()),
        f"{BASE}/content/dam/ibi/us/en/prod/online-help/1-0-0/images/a.png": (200, b"repo bytes"),
        f"{BASE}/content/dam/ibi/us/en/prod/online-help/1-0-0/images/b.png": (200, b"stale bytes"),
    })

    checked = published.check(fetcher, VERSION, root([Node("Guide", "guide.md")]), folder)

    page = checked.pages["guide.md"]
    assert checked.reachable and checked.menu.issues == []
    assert page.callouts == 1 and page.missing == []
    assert page.alt_dropped == ["images/a.png"]
    assert page.broken_images == ["images/b.png: served bytes differ from the repo"]


# -- live sample -----------------------------------------------------------------


def test_the_sample_is_spread_across_the_version() -> None:
    rows = [(f"u{i}", f"p{i}") for i in range(100)]

    assert [r[0] for r in live.sample(rows, 4)] == ["u0", "u25", "u50", "u75"]
    assert live.sample(rows[:3], 20) == rows[:3]


def test_a_sign_in_page_is_uncheckable_not_drift() -> None:
    fetcher = FakeFetcher({"https://docs.example.com/p.htm": (
        200, b"<html><head><title>Sign in</title></head><body>pureauth login</body></html>")})

    assert live.check(fetcher, "https://docs.example.com/p.htm", texts.Text(["x"]), "body").status == "uncheckable"


# -- the driver, end to end -------------------------------------------------------

SLUG, NUMBER = "prod", "1.0.0"


def _fixture(config, state, *, drop_paragraph=False, drop_image=False, move_entry=False, orphan=False,
             maps=True):
    """A Flare package, its recorded conversion, and the published version folder."""
    extracted = config.extracted_dir("ibi", "webfocus") / SLUG / NUMBER
    html = extracted / "pkg/html"
    build(html, {
        "Data/HelpSystem.xml": manifest(default_url="Home.htm"),
        **toc_files(
            [{"i": 1, "n": [{"i": 2}, {"i": 3}]}],
            {"/guide.htm": {"i": [1], "t": ["Guide"], "b": [""]},
             "/one.htm": {"i": [2], "t": ["One"], "b": [""]},
             "/two.htm": {"i": [3], "t": ["Two"], "b": [""]}},
        ),
        "guide.htm": topic("Guide", "<p>The guide introduces the product and its parts.</p>"),
        "one.htm": topic("One", "<p>Step one installs the product on the server.</p>"
                                "<p>Step one also configures the default port.</p>"
                                "<img src='Resources/shot.png'>"),
        "two.htm": topic("Two", "<p>Step two connects the product to WebFOCUS.</p>"),
        "orphan.htm": topic("Orphan", "<p>A page that no TOC entry reaches at all.</p>"),
    })
    _png(html / "Resources/shot.png", b"shot")
    outputs = [("pkg/html/guide.htm", "guide.md", ""), ("pkg/html/one.htm", "one.md", ""),
               ("pkg/html/two.htm", "two.md", "")]
    if orphan:
        outputs.append(("pkg/html/orphan.htm", "unfiled/orphan.md", ""))
    state.record_output_map(SLUG, NUMBER, outputs)

    folder = config.root_dir / "repos/en-us-ibi-webfocus-userdocs/en-us" / SLUG / "online-help/1-0-0"
    one = "# One\n\nStep one installs the product on the server.\n"
    one += "" if drop_paragraph else "\nStep one also configures the default port.\n"
    one += "" if drop_image else "\n![](images/shot.png)\n"
    pages = {"guide.md": "# Guide\n\nThe guide introduces the product and its parts.\n", "one.md": one,
             "two.md": "# Two\n\nStep two connects the product to WebFOCUS.\n"}
    for name, body in pages.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(body, encoding="utf-8")
    _png(folder / "images/shot.png", b"shot")
    if move_entry:
        toc = ('docs:\n  - title: "Guide"\n    url: "guide.md"\n    subfolderlist:\n'
               '      - title: "One"\n        url: "one.md"\n  - title: "Two"\n    url: "two.md"\n')
    else:
        toc = ('docs:\n  - title: "Guide"\n    url: "guide.md"\n    subfolderlist:\n'
               '      - title: "One"\n        url: "one.md"\n      - title: "Two"\n        url: "two.md"\n')
    (folder / "toc.yml").write_text(toc, encoding="utf-8")
    if maps:
        _maps(folder, {f"{OLD}/{name}.htm": f"{name}.md#{name}" for name in ("guide", "one", "two")})
    return config.root_dir / "repos"


OLD = "https://docs.tibco.com/pub/prod/1.0.0/doc/html"


def _maps(folder: Path, rows: dict[str, str], product: dict[str, str] | None = None) -> None:
    """The version's `301.yml` and its product's, as `sync` writes them."""
    def write(path: Path, pairs: dict[str, str]) -> None:
        body = "".join(f"- from: {frm}\n  to: {to}\n  status: 301\n" for frm, to in pairs.items())
        path.write_text("redirects:\n" + body, encoding="utf-8")

    write(folder / "301.yml", rows)
    served = {frm: redirects.published("", "", "en-us", SLUG, "online-help", folder.name, to)
              for frm, to in rows.items()}
    write(folder.parent / "301.yml", served if product is None else product)


def _verify(config, state, target: Path, sample: int = 10, fetcher=None, host: str = "") -> FindingsRun:
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.FLARE)}
    findings = FindingsRun("verify")
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, findings, fetcher=fetcher,
                        base_url=host, redirect_sample=sample, seed=7)
    for folder in verifier.selection(SLUG, None):
        verifier.version(folder)
    findings.flush()
    return findings


def _codes(findings: FindingsRun) -> list[str]:
    return sorted(f.code for f in findings.recorded if f.code != "VERIFY_REDIRECT_SAMPLED")


def test_a_clean_version_produces_no_findings(config, state) -> None:
    assert _codes(_verify(config, state, _fixture(config, state))) == []


def test_another_languages_root_in_the_package_is_not_the_english_folders_loss(config, state) -> None:
    """Phase 64. WebFOCUS 9.3.5+ ships `html/ja-jp` as a Flare root of its own; the
    English folder was converted without it, so its topics are not missing."""
    target = _fixture(config, state)
    ja = config.extracted_dir("ibi", "webfocus") / SLUG / NUMBER / "pkg/html/ja-jp"
    build(ja, {
        "Data/HelpSystem.xml": manifest(default_url="Home.htm"),
        **toc_files([{"i": 1}], {"/guide.htm": {"i": [1], "t": ["ガイド"], "b": [""]}}),
        "guide.htm": topic("ガイド", "<p>製品の概要です。</p>"),
    })

    assert _codes(_verify(config, state, target)) == []


def test_only_known_drops_produce_no_loss(config, state) -> None:
    target = _fixture(config, state, orphan=True)

    assert _codes(_verify(config, state, target)) == ["VERIFY_TOPIC_UNFILED"]


def test_a_dropped_paragraph_image_and_moved_entry_are_exactly_what_is_found(config, state) -> None:
    target = _fixture(config, state, drop_paragraph=True, drop_image=True, move_entry=True)

    findings = _verify(config, state, target)

    assert _codes(findings) == ["VERIFY_IMAGE_MISSING", "VERIFY_TEXT_DROPPED", "VERIFY_TOC_MOVED"]
    dropped = next(f for f in findings.recorded if f.code == "VERIFY_TEXT_DROPPED")
    assert "Step one also configures the default port." in dropped.message


def test_the_selection_reads_only_online_help(config, state) -> None:
    target = _fixture(config, state)
    (target / "en-us-ibi-webfocus-userdocs/en-us" / SLUG / "release-information/1-0-0").mkdir(parents=True)

    folders = [v for e in walk(target, SLUG, None, "online-help") for v in e.versions]
    assert [f.doc_class for f in folders] == ["online-help"]


def test_a_locale_keeps_only_that_languages_folders(config, state) -> None:
    """Phase 64. An English-only change is checked without re-reading the `loc-` tree."""
    target = _fixture(config, state)
    (target / "loc-ibi-webfocus-userdocs/ja-jp" / SLUG / "online-help/1-0-0").mkdir(parents=True)
    product = make_product(SLUG, bu="ibi", family="webfocus")
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, FindingsRun("verify"))

    assert [f.locale for f in verifier.selection(SLUG, None)] == ["en-us", "ja-jp"]
    assert [f.locale for f in verifier.selection(SLUG, None, locale="en-us")] == ["en-us"]


# -- Phase 58: records, status, triage, waves ---------------------------------------


def test_a_verify_result_is_kept_per_run_and_the_latest_is_read_back(state) -> None:
    base = {"slug": "prod", "version": "1.0.0", "scope": "local", "outcome": "lost", "errors": 2}
    state.record_verify({**base, "run_id": 1, "at": "2026-10-20T10:00:00+00:00"})
    state.record_verify({**base, "run_id": 2, "at": "2026-10-23T10:00:00+00:00", "outcome": "clean", "errors": 0})

    latest = state.verify_latest()[("prod", "1.0.0")]

    assert (latest["run_id"], latest["outcome"]) == (2, "clean")
    assert len(state._all("SELECT * FROM verify_result")) == 2


def test_verify_status_reads_not_verified_the_outcome_and_stale_after_a_later_sync() -> None:
    from docushift.reporting.status import _verify

    placed = {("sync", "ok"): ("2026-10-22T09:00:00+00:00", "target")}
    checked = {"at": "2026-10-23T10:00:00+00:00", "outcome": "explained"}

    assert _verify(None, {}, "") == ("", "")
    assert _verify(None, placed, "2026-10-22") == ("not-verified", "")
    assert _verify(checked, placed, "2026-10-22") == ("explained", "2026-10-23")
    resynced = {("sync", "ok"): ("2026-10-24T09:00:00+00:00", "target")}
    assert _verify(checked, resynced, "2026-10-24") == ("stale", "2026-10-23")


def test_the_shipped_triage_file_loads(repo_root: Path) -> None:
    from docushift.verify import triage

    entries = triage.load(repo_root / "config" / "verify-triage.yaml")

    assert {e.code for e in entries} >= {"VERIFY_PUBLISHED_ALT_DROPPED", "VERIFY_PUBLISHED_CALLOUT_UNRENDERED"}


def test_a_malformed_triage_entry_stops_the_run_naming_it(tmp_path: Path) -> None:
    import pytest

    from docushift.verify import triage

    path = tmp_path / "verify-triage.yaml"
    path.write_text("triage:\n  - code: VERIFY_TEXT_DROPPED\n    decision: platform\n    reason: AEM\n",
                    encoding="utf-8")

    with pytest.raises(triage.TriageError, match="entry 1: a `platform` decision needs"):
        triage.load(path)


def test_triage_matches_by_code_and_narrows_by_product_and_path() -> None:
    from docushift.verify import triage

    entries = [triage.Entry("VERIFY_TEXT_DROPPED", "accepted", "intro rewritten", slug="prod",
                            path="*/intro.md")]

    assert triage.match(entries, "VERIFY_TEXT_DROPPED", "prod", "1.0.0", "guide/intro.md") is entries[0]
    assert triage.match(entries, "VERIFY_TEXT_DROPPED", "other", "1.0.0", "guide/intro.md") is None
    assert triage.match(entries, "VERIFY_IMAGE_MISSING", "prod", "1.0.0", "guide/intro.md") is None


def test_a_triaged_loss_is_reported_and_the_version_reads_explained(config, state) -> None:
    from docushift.verify import triage

    target = _fixture(config, state, drop_paragraph=True)
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.FLARE)}
    findings = FindingsRun("verify")
    entries = [triage.Entry("VERIFY_TEXT_DROPPED", "accepted", "rewritten on purpose", path="one.md")]
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, findings, triaged=entries)

    result = verifier.version(verifier.selection(SLUG, None)[0])
    findings.flush()

    assert result.outcome == "explained" and (result.errors, result.explained) == (0, 1)
    assert "[triage: accepted]" in findings.recorded[0].message
    assert next(r for r in result.rows if r["new_path"] == "one.md")["triage"] == "accepted"


def test_an_unexplained_loss_reads_lost(config, state) -> None:
    target = _fixture(config, state, drop_image=True)
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.FLARE)}
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, FindingsRun("verify"))

    assert verifier.version(verifier.selection(SLUG, None)[0]).outcome == "lost"


def test_a_wave_selects_by_bu_status_newest_version_and_size(config, state) -> None:
    target = _fixture(config, state)
    older = target / "en-us-ibi-webfocus-userdocs/en-us" / SLUG / "online-help/0-9-0"
    older.mkdir(parents=True)
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER), "0.9.0": make_version(SLUG, "0.9.0")}
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, FindingsRun("verify"))

    def segments(**kw) -> list[str]:
        return [f.segment for f in verifier.selection(None, None, **kw)]

    assert segments() == ["0-9-0", "1-0-0"]
    assert segments(latest_only=True) == ["1-0-0"]
    assert segments(bu="tibco") == []
    statuses = {(SLUG, NUMBER): "explained", (SLUG, "0.9.0"): "not-verified"}
    assert segments(statuses=statuses, wanted=("not-verified",)) == ["0-9-0"]
    assert segments(limit=1) == ["0-9-0"]


def test_each_run_keeps_its_own_report_and_the_index_links_it(config, state, tmp_path: Path) -> None:
    from docushift.verify import report

    target = _fixture(config, state)
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.FLARE)}
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, FindingsRun("verify"))
    result = verifier.version(verifier.selection(SLUG, None)[0])

    first = report.write_version(tmp_path, "ibi", result, "2026-10-23")
    second = report.write_version(tmp_path, "ibi", result, "2026-10-30")
    _, html = report.write_index(tmp_path, [{
        "bu": "ibi", "family": "webfocus", "slug": SLUG, "version": NUMBER, "verify_status": "clean",
        "verify_date": "2026-10-30", "scope": "local", "pages": "3", "errors": "0", "warnings": "0",
        "explained": "0", "findings": "", "commit": "", "report": "reports/verify/ibi/prod/1.0.0-2026-10-30.csv"}])

    assert first != second and first.is_file() and second.is_file()
    assert 'href="ibi/prod/1.0.0-2026-10-30.html"' in html.read_text(encoding="utf-8")


def test_the_staging_host_is_chosen_by_business_unit(project_root: Path) -> None:
    from docushift.config import ConfigManager

    (project_root / "config" / "publishing.yaml").write_text(
        'verify_base_urls:\n  ibi: "https://stg-docs.ibi.com/"\n  tibco: "https://stg-docs.tibco.com"\n',
        encoding="utf-8")

    assert ConfigManager(root_dir=project_root).verify_base_urls() == {
        "ibi": "https://stg-docs.ibi.com", "tibco": "https://stg-docs.tibco.com"}


# -- Phase 60: the 301 maps ----------------------------------------------------------


def _version_folder(target: Path) -> Path:
    return target / "en-us-ibi-webfocus-userdocs/en-us" / SLUG / "online-help/1-0-0"


def test_a_version_without_its_301_map_is_lost(config, state) -> None:
    target = _fixture(config, state, maps=False)

    assert _codes(_verify(config, state, target)) == ["VERIFY_REDIRECT_MAP_MISSING"]


def test_a_product_map_missing_or_disagreeing_with_the_version_is_incomplete(config, state) -> None:
    target = _fixture(config, state)
    folder = _version_folder(target)
    _maps(folder, {f"{OLD}/guide.htm": "guide.md#guide", f"{OLD}/one.htm": "one.md#one"},
          product={f"{OLD}/guide.htm": "us/en/prod/online-help/1-0-0/two.html#two"})

    findings = _verify(config, state, target)

    assert _codes(findings) == ["VERIFY_REDIRECT_MAP_INCOMPLETE", "VERIFY_REDIRECT_MAP_INCOMPLETE"]
    (folder.parent / "301.yml").unlink()
    assert _codes(_verify(config, state, target)) == ["VERIFY_REDIRECT_MAP_MISSING"]


def test_a_sampled_row_into_a_missing_anchor_or_the_wrong_page_is_found(config, state) -> None:
    target = _fixture(config, state)
    _maps(_version_folder(target), {f"{OLD}/guide.htm": "guide.md#nowhere", f"{OLD}/one.htm": "two.md#two",
                                    f"{OLD}/two.htm": "gone.md"})

    findings = _verify(config, state, target)

    assert _codes(findings) == ["VERIFY_REDIRECT_TARGET_MISSING", "VERIFY_REDIRECT_TARGET_MISSING",
                                "VERIFY_REDIRECT_WRONG_PAGE"]


def test_a_zero_sample_checks_only_that_the_maps_are_there(config, state) -> None:
    target = _fixture(config, state)
    _maps(_version_folder(target), {f"{OLD}/one.htm": "two.md#two"})

    assert _codes(_verify(config, state, target, sample=0)) == []


def test_the_sample_is_repeatable_from_its_seed(tmp_path) -> None:
    rows = [(f"{OLD}/p{i}.htm", f"p{i}.md") for i in range(40)]
    ctx = redirect_maps.Context(tmp_path, "en-us", SLUG, "online-help", "1-0-0", "", [], {}, tmp_path, "body")

    assert redirect_maps._pick(rows, 5, 7, ctx) == redirect_maps._pick(rows, 5, 7, ctx)
    assert redirect_maps._pick(rows, 5, 7, ctx) != redirect_maps._pick(rows, 5, 8, ctx)
    assert len(redirect_maps._pick(rows, 50, 7, ctx)) == 40


def test_coverage_names_a_published_topic_with_no_row_and_counts_the_rest(tmp_path) -> None:
    folder = tmp_path / "online-help/1-0-0"
    folder.mkdir(parents=True)
    _maps(folder, {f"{OLD}/one.htm": "one.md"})
    pages = [f"{OLD}/one.htm", f"{OLD}/two.htm", f"{OLD}/orphan.htm", f"{OLD}/api/index.html"]
    sources = {"pkg/html/one.htm": "one.md", "pkg/html/two.htm": "two.md",
               "pkg/html/orphan.htm": "unfiled/orphan.md"}
    ctx = redirect_maps.Context(folder, "en-us", SLUG, "online-help", "1-0-0", "", pages, sources,
                                tmp_path, "body")

    issues = redirect_maps.check(ctx, 0, 1).issues

    assert [(i.code, i.path) for i in issues] == [("VERIFY_REDIRECT_UNMAPPED", "two.md"),
                                                  ("VERIFY_REDIRECT_UNCONVERTED", "")]
    assert "1 more are unpublished orphans" in issues[1].message


def test_staging_that_serves_no_target_is_not_yet_there_and_one_gap_is_unserved(config, state) -> None:
    target = _fixture(config, state)
    nothing = FakeFetcher({})

    assert "VERIFY_REDIRECT_NOT_ON_STAGING" in _codes(_verify(config, state, target, fetcher=nothing, host=BASE))

    guide = f"{BASE}/us/en/{SLUG}/online-help/1-0-0/guide.html"
    some = FakeFetcher({guide: (200, _served("/guide").encode())})
    codes = _codes(_verify(config, state, target, fetcher=some, host=BASE))
    assert codes.count("VERIFY_REDIRECT_UNSERVED") == 2
    assert "VERIFY_REDIRECT_NOT_ON_STAGING" not in codes


def test_a_page_opening_at_its_own_top_heading_matches_the_bare_toc_entry(config, state) -> None:
    """Phase 63's unmerged reframe maps a topic to `page.md#top`; the TOC lists `page.md`."""
    target = _fixture(config, state)
    reframed = config.reframed_path("ibi", "webfocus", SLUG, NUMBER)
    reframed.mkdir(parents=True, exist_ok=True)
    (reframed / "redirects.yml").write_text(
        "redirects:\n" + "".join(f"- from: {n}.md\n  to: {n}.md#{n}\n" for n in ("guide", "one", "two")),
        encoding="utf-8")

    assert _codes(_verify(config, state, target)) == []


def test_escaped_markdown_and_a_run_together_label_are_not_dropped_text() -> None:
    source = texts.Text(["Copy the driver inside the <webfocus-ce>/wfs/lib folder now.",
                         "ResultYou can see five images loaded to your docker.",
                         "The URL is solr.{{ env | default }}.svc.cluster.local for the search."])
    page = texts.markdown_text("1. Copy the driver inside the \\<webfocus-ce>/wfs/lib folder now.\n\n"
                               "**Result** You can see five images loaded to your docker.\n\n"
                               "| Key | The URL is solr.{{ env \\| default }}.svc.cluster.local for the search. |\n")

    assert texts.coverage(source, page).missing == []


def test_a_heading_only_parent_given_a_page_is_the_same_parent() -> None:
    """Phase 63 gives a heading-only TOC row a generated page; its children did not move."""
    old = root([Node("Guide", None, [Node("One", "one.md"), Node("Two", "two.md")])])
    new = root([Node("Guide", "guide.md", [Node("One", "one.md"), Node("Two", "two.md")])])

    assert by_page(old, new).issues == []
    other = root([Node("Other", "other.md", [Node("One", "one.md"), Node("Two", "two.md")])])
    assert [i.kind for i in by_page(old, other).issues] == ["moved", "moved"]


def test_raw_html_entities_split_tokens_and_continued_lines_are_not_dropped_text() -> None:
    source = texts.Text(["All values come from <webfocus-ce>/scripts/helmfile and the defaults.",
                         "ETC_TAG = wfs-etc-9.3.7 (From export-defaults.sh)",
                         "NFS server with connectivity to PCF is available, You can check it using this command."])
    page = texts.markdown_text("<td>All values come from <code>&lt;webfocus-ce&gt;/scripts/helmfile</code> "
                               "and the defaults.</td>\n\n"
                               "<td>ETC_TAG = wfs-etc-<span>9.3.7</span> (From export-defaults.sh)</td>\n\n"
                               "NFS server with connectivity to PCF is available,\\\n"
                               "You can check it using this command.\n")

    assert texts.coverage(source, page).missing == []


# -- Phase 66: PDF-only versions -------------------------------------------------------

PDFS = {"install guide.pdf": b"%PDF install", "admin.pdf": b"%PDF admin"}


def _pdf_fixture(config, *, published=None, listed=None, extra=None) -> Path:
    """A package of PDFs only, and its `user-guides` folder as `sync` writes it."""
    package = config.extract_path("ibi", "webfocus", SLUG, NUMBER) / "pdf"
    package.mkdir(parents=True)
    for name, data in PDFS.items():
        (package / name).write_bytes(data)
    target = config.root_dir / "repos"
    folder = target / "en-us-ibi-webfocus-userdocs/en-us" / SLUG / "user-guides/1-0-0"
    folder.mkdir(parents=True)
    for name, data in (PDFS if published is None else published).items():
        (folder / name).write_bytes(data)
    for name, data in (extra or {}).items():
        (folder / name).write_bytes(data)
    links = "".join(f"- [{n}]({n.replace(' ', '%20')})\n" for n in (PDFS if listed is None else listed))
    (folder / "index.md").write_text(f"---\ntitle: Guides\n---\n\n# Guides\n\n{links}", encoding="utf-8")
    (folder / "toc.yml").write_text("docs: []\n", encoding="utf-8")
    (folder / "metadata.yml").write_text("{}\n", encoding="utf-8")
    return target


def _verify_pdfs(config, state, target: Path):
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.OTHER)}
    findings = FindingsRun("verify")
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, findings)
    results = [verifier.version(folder) for folder in verifier.selection(SLUG, None)]
    findings.flush()
    return findings, results


def test_a_pdf_only_version_published_as_shipped_is_clean(config, state) -> None:
    findings, results = _verify_pdfs(config, state, _pdf_fixture(config))

    assert _codes(findings) == []
    assert [(r.version, r.outcome) for r in results] == [(NUMBER, "clean")]
    assert sorted(row["new_path"] for row in results[0].rows) == [
        "user-guides/admin.pdf", "user-guides/install guide.pdf"]
    assert {row["published_status"] for row in results[0].rows} == {"ok"}


def test_a_missing_or_altered_pdf_is_lost(config, state) -> None:
    target = _pdf_fixture(config, published={"install guide.pdf": b"%PDF other"})

    findings, results = _verify_pdfs(config, state, target)

    assert _codes(findings) == ["VERIFY_DOCUMENT_CHANGED", "VERIFY_DOCUMENT_MISSING"]
    assert results[0].outcome == "lost"
    status = {row["new_path"]: (row["published_status"], row["findings"]) for row in results[0].rows}
    assert status["user-guides/admin.pdf"] == ("missing locally", "VERIFY_DOCUMENT_MISSING")


def test_an_unlisted_pdf_and_a_leftover_file_are_issues(config, state) -> None:
    target = _pdf_fixture(config, listed={"admin.pdf": b""}, extra={"old.pdf": b"%PDF old"})

    findings, results = _verify_pdfs(config, state, target)

    assert _codes(findings) == ["VERIFY_DOCUMENT_EXTRA", "VERIFY_DOCUMENT_UNLISTED"]
    assert results[0].outcome == "issues"


def test_a_version_with_help_and_pdfs_is_selected_once_and_both_are_checked(config, state) -> None:
    target = _fixture(config, state)
    package = config.extract_path("ibi", "webfocus", SLUG, NUMBER) / "pdf"
    package.mkdir(parents=True)
    (package / "admin.pdf").write_bytes(b"%PDF admin")
    guides = target / "en-us-ibi-webfocus-userdocs/en-us" / SLUG / "user-guides/1-0-0"
    guides.mkdir(parents=True)
    (guides / "index.md").write_text("# Guides\n\n- [Admin](admin.pdf)\n", encoding="utf-8")
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.FLARE)}
    findings = FindingsRun("verify")
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, findings)

    folders = verifier.selection(SLUG, None)
    result = verifier.version(folders[0])

    assert [f.doc_class for f in folders] == ["online-help"]
    assert result.outcome == "lost"
    assert result.codes == {"VERIFY_DOCUMENT_MISSING": 1}
    assert [row["new_path"] for row in result.rows][-1] == "user-guides/admin.pdf"


def test_placing_the_help_or_the_documents_after_the_check_reads_stale() -> None:
    from docushift.reporting.status import _verify

    checked = {"at": "2026-10-23T10:00:00+00:00", "outcome": "clean"}
    before = ("2026-10-22T09:00:00+00:00", "target")
    after = ("2026-10-24T09:00:00+00:00", "target")

    assert _verify(checked, {("sync-docs", "ok"): after}, "2026-10-24") == ("stale", "2026-10-23")
    assert _verify(checked, {("sync", "ok"): before, ("sync-docs", "ok"): after}, "2026-10-22") == \
        ("stale", "2026-10-23")
    assert _verify(checked, {("sync", "ok"): before, ("sync-docs", "ok"): before}, "2026-10-22") == \
        ("clean", "2026-10-23")


def test_a_release_note_published_under_user_guides_is_missing_from_its_own_folder(config, state) -> None:
    """Measured on Omni-Gen 4.3.0: published before release notes had their own folder."""
    target = _pdf_fixture(config, extra={"prod_1.0.0_release_notes.pdf": b"%PDF notes"})
    (config.extract_path("ibi", "webfocus", SLUG, NUMBER) / "pdf/prod_1.0.0_release_notes.pdf").write_bytes(
        b"%PDF notes")

    _, results = _verify_pdfs(config, state, target)

    status = {row["new_path"]: (row["published_status"], row["findings"]) for row in results[0].rows}
    assert status["user-guides/prod_1.0.0_release_notes.pdf"] == ("extra", "VERIFY_DOCUMENT_EXTRA")
    assert status["release-information/prod_1.0.0_release_notes.pdf"] == ("missing locally",
                                                                          "VERIFY_DOCUMENT_MISSING")


def test_a_translated_folder_reads_the_english_package_it_ships_in(config, state) -> None:
    """Phase 66. A `--locale ja-jp` run has no extracted tree of its own: the translated
    help ships inside the English package, so the check must find it there."""
    import shutil

    from docushift.config import ConfigManager

    target = _fixture(config, state)
    english = target / "en-us-ibi-webfocus-userdocs/en-us" / SLUG / "online-help/1-0-0"
    shutil.copytree(english, target / "loc-ibi-webfocus-userdocs/ja-jp" / SLUG / "online-help/1-0-0")
    localized = ConfigManager(root_dir=config.root_dir, locale="ja-jp")
    ja_state = localized.state_store()
    ja_state.record_output_map(SLUG, NUMBER, [("pkg/html/guide.htm", "guide.md", ""),
                                              ("pkg/html/one.htm", "one.md", ""), ("pkg/html/two.htm", "two.md", "")])
    product = make_product(SLUG, bu="ibi", family="webfocus")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.FLARE)}
    verifier = Verifier(localized, Catalog(products={SLUG: product}), ja_state, target, FindingsRun("verify"))

    results = [verifier.version(f) for f in verifier.selection(SLUG, None, locale="ja-jp")]

    # Compared page by page, nothing lost; the fixture has no `ja-jp` Flare root or
    # product-level 301.yml, which is what the two other codes say.
    assert [(r.folder.locale, r.skipped, len(r.rows)) for r in results] == [("ja-jp", "", 3)]
    assert set(results[0].codes) == {"VERIFY_TOC_UNCHECKED", "VERIFY_REDIRECT_MAP_MISSING"}
    ja_state.close()


def test_a_default_run_checks_each_language_against_its_own_conversion(config, state, catalog) -> None:
    """Phase 66. Without `--locale` a `ja-jp` folder was read with the English output map
    and its result replaced the English one in `state.db`; its report, another
    language's of the same day. Each language now runs on its own state and report."""
    import datetime
    import shutil

    from click.testing import CliRunner

    from docushift.cli import main
    from docushift.config import ConfigManager
    from docushift.state import StateStore

    target = _fixture(config, state)
    english = target / "en-us-ibi-webfocus-userdocs/en-us" / SLUG / "online-help/1-0-0"
    shutil.copytree(english, target / "loc-ibi-webfocus-userdocs/ja-jp" / SLUG / "online-help/1-0-0")
    ja_state = ConfigManager(root_dir=config.root_dir, locale="ja-jp").state_store()
    ja_state.record_output_map(SLUG, NUMBER, [("pkg/html/guide.htm", "guide.md", "")])
    ja_state.close()
    built = make_product(SLUG, bu="ibi", family="webfocus")
    built.versions = {NUMBER: make_version(SLUG, NUMBER, engine=SourceEngine.FLARE)}
    catalog.merge_fetch_results([built])

    result = CliRunner().invoke(main, ["--root", str(config.root_dir), "verify", "--target-dir", str(target),
                                       "--skip-published", "--live-sample", "0", "--redirect-sample", "0"],
                                color=False)

    assert "Traceback" not in result.output, result.output
    english_result = StateStore(config.state_db_path).verify_latest()[(SLUG, NUMBER)]
    ja = ConfigManager(root_dir=config.root_dir, locale="ja-jp").state_store()
    japanese_result = ja.verify_latest()[(SLUG, NUMBER)]
    ja.close()
    assert "/en-us/" in english_result["target"].replace("\\", "/")
    assert "/ja-jp/" in japanese_result["target"].replace("\\", "/")
    # Each against its own output map: three English pages, one Japanese.
    assert (english_result["pages"], japanese_result["pages"]) == (3, 1)
    day = datetime.date.today().isoformat()
    reports = sorted(p.name for p in (config.root_dir / "reports/verify/ibi" / SLUG).glob("*.csv"))
    assert reports == [f"{NUMBER}-{day}.csv", f"{NUMBER}-ja-jp-{day}.csv"]
