"""Phase 58, step 8: the old TOC of DITA, WebWorks and DocBook versions is read and compared.

Each reader is tried on a small package of its engine's shape; one driver test per
engine shows a `toc.yml` that lost an entry is reported as `VERIFY_TOC_ENTRY_MISSING`.
"""

from __future__ import annotations

from pathlib import Path

from docushift.models import Catalog, SourceEngine
from docushift.reporting.findings import FindingsRun
from docushift.verify import old_toc
from docushift.verify.driver import Verifier
from docushift.verify.toc import Node, by_page, root, tail_moved
from tests.conftest import make_product, make_version

SLUG, NUMBER = "prod", "1.0.0"


def _write(root: Path, files: dict[str, str]) -> None:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def _same(source: str) -> str:
    return source


def _keys(node, depth: int = 0) -> list[tuple[int, str, str | None]]:
    out = []
    for child in node.children:
        out.append((depth, child.title, child.key))
        out.extend(_keys(child, depth + 1))
    return out


def _no_marker(key: str, anchor: str) -> str:
    return f"{key}#{anchor}" if anchor and "#" not in key else key


# -- DITA ------------------------------------------------------------------------

GUID_A, GUID_B, GUID_C = "GUID-AAAA", "GUID-BBBB", "GUID-CCCC"


def _dita_topic(identifier: str, title: str, text: str) -> str:
    return (f'<html><head><meta name="DC.Identifier" content="{identifier}"><title>{title}</title></head>'
            f"<body><article><h1>{title}</h1><p>{text}</p></article></body></html>")


def _dita_package(root: Path, *, copy: bool = True) -> None:
    toc = ("<html><body><ul>"
           f'<li><a href="{GUID_A}.html">Intro</a>'
           f'<ul><li><a href="{GUID_B}.html">Install</a></li></ul></li>'
           "<li>Reference"
           f'<ul><li><a href="{GUID_C}.html">Options</a></li>'
           + (f'<li><a href="{GUID_B}1.html">Install again</a></li>' if copy else "")
           + "</ul></li></ul></body></html>")
    files = {
        "suitehelp_topic_list.html": toc,
        f"{GUID_A}.html": _dita_topic(GUID_A, "Intro", "The product does one thing well."),
        f"{GUID_B}.html": _dita_topic(GUID_B, "Install", "Run the installer on the server."),
        f"{GUID_C}.html": _dita_topic(GUID_C, "Options", "Every option has a default value."),
    }
    if copy:
        # SDL's republished copy: a new file name, the original's identifier plus `_unique_1`.
        files[f"{GUID_B}1.html"] = _dita_topic(f"{GUID_B}_unique_1", "Install", "Run the installer on the server.")
    _write(root, files)


DITA_OUT = {"html/GUID-AAAA.html": "intro.md", "html/GUID-BBBB.html": "install.md",
            "html/GUID-CCCC.html": "options.md"}


def test_a_dita_toc_keeps_sections_and_resolves_a_republished_copy_to_its_original(tmp_path: Path) -> None:
    _dita_package(tmp_path / "html")
    old = old_toc.dita_sets([tmp_path / "html"], tmp_path, DITA_OUT, DITA_OUT.get, _no_marker)

    assert _keys(old.tree) == [
        (0, "Intro", "intro.md"), (1, "Install", "install.md"),
        (0, "Reference", None), (1, "Options", "options.md"), (1, "Install again", "install.md"),
    ]
    assert old.unconverted == [] and old.unchecked == []


def test_a_dita_topic_the_toc_names_but_nobody_converted_is_reported(tmp_path: Path) -> None:
    _dita_package(tmp_path / "html", copy=False)
    converted = {k: v for k, v in DITA_OUT.items() if "CCCC" not in k}
    old = old_toc.dita_sets([tmp_path / "html"], tmp_path, converted, converted.get, _no_marker)

    assert old.unconverted == [("html/GUID-CCCC.html", "Options")]


# -- WebWorks --------------------------------------------------------------------


def _webworks_book(root: Path, title: str, *, stripped: bool = False) -> None:
    files = {
        "wwhdata/common/title.js": f'function GetTitle() {{ return "{title}"; }}',
        "intro.htm": "<html><body><h1>Intro</h1><p>What the book covers.</p></body></html>",
        "setup.htm": "<html><body><h1>Setup</h1><a name='99'></a><h2>Ports</h2><p>Open port 80.</p></body></html>",
    }
    if stripped:
        files["wwhdata/files.htm"] = '<html><body><a href="../intro.htm">Intro</a></body></html>'
    else:
        files["wwhdata/common/files.js"] = ('function A(P) {\n P.fA("Intro","intro.htm");\n'
                                            ' P.fA("Setup","setup.htm");\n}\n')
        files["wwhdata/js/toc.js"] = ('function A(P) {\n var B=P.fN("Intro","0");\n'
                                      ' var C=B.fN("Setup","1");\n C.fN("Ports","1#99");\n'
                                      ' P.fN("Heading only");\n}\n')
    _write(root, files)


def test_a_webworks_book_reads_its_toc_by_file_index_and_bookmark(tmp_path: Path) -> None:
    _webworks_book(tmp_path / "Book", "User Guide")
    outmap = {"Book/intro.htm": "intro.md", "Book/setup.htm": "setup.md"}
    old = old_toc.webworks_books([tmp_path / "Book"], tmp_path, outmap, outmap.get, _no_marker)

    assert _keys(old.tree) == [
        (0, "Intro", "intro.md"), (1, "Setup", "setup.md"), (2, "Ports", "setup.md#99"),
        (0, "Heading only", None),
    ]


def test_a_stripped_webworks_book_is_named_unchecked_and_its_sibling_is_still_read(tmp_path: Path) -> None:
    _webworks_book(tmp_path / "Full", "Full Guide")
    _webworks_book(tmp_path / "Bare", "Bare Guide", stripped=True)
    outmap = {"Full/intro.htm": "full/intro.md", "Full/setup.htm": "full/setup.md",
              "Bare/intro.htm": "bare/intro.md"}
    old = old_toc.webworks_books([tmp_path / "Bare", tmp_path / "Full"], tmp_path, outmap, outmap.get,
                                 _no_marker)

    assert old.unchecked == ["Bare: stripped book, no navigation on the old site"]
    assert [(d, t) for d, t, _ in _keys(old.tree)][:2] == [(0, "Intro"), (1, "Setup")]


def test_a_webworks_file_is_matched_without_regard_to_case(tmp_path: Path) -> None:
    _webworks_book(tmp_path / "Book", "User Guide")
    outmap = {"book/Intro.htm": "intro.md", "book/Setup.htm": "setup.md"}
    old = old_toc.webworks_books([tmp_path / "Book"], tmp_path, outmap, outmap.get, _no_marker)

    assert old.unconverted == [] and _keys(old.tree)[0] == (0, "Intro", "intro.md")


# -- DocBook ---------------------------------------------------------------------

STYLE = '<link rel="stylesheet" href="css/help.css">'


def _docbook_page(title: str, body: str, *, depth: int = 0) -> str:
    up = "../" * depth
    return (f'<html><head><meta name="generator" content="DocBook XSL Stylesheets V1.76.1">'
            f'<link rel="stylesheet" href="{up}css/help.css"><title>{title}</title></head><body>'
            f'<p id="mainhelp-navmenu"><a href="{up}index.html">Home</a> '
            f'<a href="{up}guide/index.html">The Guide</a></p>'
            f'<div id="mainContent">{body}</div></body></html>')


def _docbook_package(root: Path, *, part_toc: bool = True) -> None:
    book = ('<h1>The Guide</h1><div class="toc"><dl>'
            '<dt><a href="part.html">Part One</a></dt>'
            '<dd><dl><dt><a href="part.html#sec">A Section</a></dt></dl></dd>'
            '<dt><a href="other.html">Other</a></dt></dl></div>')
    part = '<h1>Part One</h1><p>Part text.</p>'
    if part_toc:
        part += '<div class="toc"><dl><dt><a href="deep.html">Deep Page</a></dt></dl></div>'
    _write(root, {
        "css/help.css": "body {}",
        "index.html": _docbook_page("Home", "<h1>Home</h1><p>Welcome.</p>"),
        "guide/index.html": _docbook_page("The Guide", book, depth=1),
        "guide/part.html": _docbook_page("Part One", part, depth=1),
        "guide/deep.html": _docbook_page("Deep Page", "<h1>Deep Page</h1><p>Deep text.</p>", depth=1),
        "guide/other.html": _docbook_page("Other", "<h1>Other</h1><p>Other text.</p>", depth=1),
    })


DOCBOOK_OUT = {"html/index.html": "index.md", "html/guide/index.html": "guide/index.md",
               "html/guide/part.html": "guide/part.md", "html/guide/deep.html": "guide/deep.md",
               "html/guide/other.html": "guide/other.md"}


def test_a_docbook_guide_follows_its_book_toc_and_each_page_s_own_toc(tmp_path: Path) -> None:
    _docbook_package(tmp_path / "html")
    old = old_toc.docbook_guides([tmp_path / "html"], tmp_path, DOCBOOK_OUT, DOCBOOK_OUT.get, _no_marker)

    assert _keys(old.tree) == [
        (0, "The Guide", "guide/index.md"),
        (1, "Part One", "guide/part.md"), (2, "A Section", "guide/part.md#sec"), (2, "Deep Page", "guide/deep.md"),
        (1, "Other", "guide/other.md"),
    ]


# -- through the driver ------------------------------------------------------------


def _verify(config, state, engine: SourceEngine, target: Path) -> list[str]:
    product = make_product(SLUG, bu="tibco", family="adapters")
    product.versions = {NUMBER: make_version(SLUG, NUMBER, engine=engine)}
    findings = FindingsRun("verify")
    verifier = Verifier(config, Catalog(products={SLUG: product}), state, target, findings)
    for folder in verifier.selection(SLUG, None):
        verifier.version(folder)
    findings.flush()
    return [f.code for f in findings.all if f.code.startswith("VERIFY_TOC")]


def _published(config, pages: dict[str, str], toc: str) -> Path:
    folder = config.root_dir / "repos/en-us-tib-adapters-userdocs/en-us" / SLUG / "online-help/1-0-0"
    _write(folder, {**pages, "toc.yml": toc})
    return config.root_dir / "repos"


def _toc(rows: list[tuple[str, str, list]]) -> str:
    def lines(items, indent: int) -> list[str]:
        out = []
        for title, url, children in items:
            pad = " " * indent
            out.append(f'{pad}- title: "{title}"')
            if url:
                out.append(f'{pad}  url: "{url}"')
            if children:
                out.append(f"{pad}  subfolderlist:")
                out.extend(lines(children, indent + 4))
        return out
    return "docs:\n" + "\n".join(lines(rows, 2)) + "\n"


def test_a_dita_toc_yml_that_lost_an_entry_is_reported(config, state) -> None:
    extracted = config.extract_path("tibco", "adapters", SLUG, NUMBER)
    _dita_package(extracted / "html", copy=False)
    state.record_output_map(SLUG, NUMBER, [(k, v, "") for k, v in DITA_OUT.items()])
    pages = {"intro.md": "# Intro\n\nThe product does one thing well.\n",
             "install.md": "# Install\n\nRun the installer on the server.\n",
             "options.md": "# Options\n\nEvery option has a default value.\n"}
    whole = [("Intro", "intro.md", [("Install", "install.md", [])]), ("Reference", "", [("Options", "options.md", [])])]
    assert _verify(config, state, SourceEngine.DITA, _published(config, pages, _toc(whole))) == []

    lost = [("Intro", "intro.md", []), ("Reference", "", [("Options", "options.md", [])])]
    codes = _verify(config, state, SourceEngine.DITA, _published(config, pages, _toc(lost)))
    assert codes == ["VERIFY_TOC_ENTRY_MISSING"]


def test_a_webworks_toc_yml_that_lost_a_bookmark_is_reported(config, state) -> None:
    extracted = config.extract_path("tibco", "adapters", SLUG, NUMBER)
    _webworks_book(extracted / "Book", "User Guide")
    state.record_output_map(SLUG, NUMBER, [("Book/intro.htm", "intro.md", ""), ("Book/setup.htm", "setup.md", "")])
    pages = {"intro.md": "# Intro\n\nWhat the book covers.\n",
             "setup.md": '# Setup\n\n## <a id="99"></a>Ports\n\nOpen port 80.\n'}
    whole = [("Intro", "intro.md", [("Setup", "setup.md", [("Ports", "setup.md#ports", [])])])]
    assert _verify(config, state, SourceEngine.WEBWORKS, _published(config, pages, _toc(whole))) == []

    lost = [("Intro", "intro.md", [("Setup", "setup.md", [])])]
    codes = _verify(config, state, SourceEngine.WEBWORKS, _published(config, pages, _toc(lost)))
    assert codes == ["VERIFY_TOC_ENTRY_MISSING"]


def test_a_docbook_toc_yml_that_lost_a_nested_section_is_reported(config, state) -> None:
    extracted = config.extract_path("tibco", "adapters", SLUG, NUMBER)
    _docbook_package(extracted / "html", part_toc=False)
    state.record_output_map(SLUG, NUMBER, [(k, v, "") for k, v in DOCBOOK_OUT.items()])
    pages = {"index.md": "# Home\n\nWelcome.\n", "guide/index.md": "# The Guide\n",
             "guide/part.md": '# Part One\n\nPart text.\n\n## <a id="sec"></a>A Section\n',
             "guide/deep.md": "# Deep Page\n\nDeep text.\n", "guide/other.md": "# Other\n\nOther text.\n"}
    section = [("A Section", "guide/part.md#a-section", [])]
    whole = [("The Guide", "guide/index.md", [("Part One", "guide/part.md", section),
                                               ("Other", "guide/other.md", [])])]
    assert _verify(config, state, SourceEngine.DOCBOOK, _published(config, pages, _toc(whole))) == []

    lost = [("The Guide", "guide/index.md", [("Part One", "guide/part.md", []), ("Other", "guide/other.md", [])])]
    codes = _verify(config, state, SourceEngine.DOCBOOK, _published(config, pages, _toc(lost)))
    assert codes == ["VERIFY_TOC_ENTRY_MISSING"]


# -- the converter's tail move (option A, 2026-11-02) --------------------------------


def test_the_support_and_legal_pages_moved_to_the_end_are_not_a_reorder() -> None:
    old = root([Node("Welcome", "welcome.md", [Node("Contacting Support for Spotfire Products", "contact.md",
                                                     [Node("Telephone", "contact.md#telephone")]),
                                                Node("Legal and Third-Party Notices", "legal.md")]),
                Node("Guide", "guide.md")])
    new = root([Node("Welcome", "welcome.md"), Node("Guide", "guide.md"),
                Node("Contacting Support for Spotfire Products", "contact.md",
                     [Node("Telephone", "contact.md#telephone")]),
                Node("Legal and Third-Party Notices", "legal.md")])

    assert by_page(tail_moved(old, new), new).issues == []
    assert {i.kind for i in by_page(old, new).issues} == {"moved"}


def test_any_other_page_moved_to_the_end_is_still_reported() -> None:
    old = root([Node("Overview", "overview.md"), Node("Guide", "guide.md"),
                Node("TIBCO Documentation and Support Services", "support.md")])
    new = root([Node("Guide", "guide.md"), Node("Overview", "overview.md"),
                Node("TIBCO Documentation and Support Services", "support.md")])

    assert [i.kind for i in by_page(tail_moved(old, new), new).issues] == ["order"]
