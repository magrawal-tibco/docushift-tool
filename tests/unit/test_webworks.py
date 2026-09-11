"""Unit tests for the WebWorks ePublisher engine (planning.md Phase 5d).

Every fixture is a whole book -- `wwhdata/common/files.js`, `wwhdata/js/toc.js`
and a handful of topics -- because that is the unit the engine works in and
because none of §5.3's rules are visible below it. A topic's title comes from
`files.js`, its place in the navigation from an *index* into `files.js`, and
whether an anchor survives from whether some other book pointed at it.

The assertions are on the corpus's rules and not on WebWorks in general. The ones
that look oddly specific are the ones where the obvious implementation is wrong on
real input, and five of them are the predecessor's shipped bugs (§5.3.10):

- `toc.js` indexes `files.js`, never `wwhdata/files.htm` -- the two disagree for
  98 books, which resolve nothing at all through the second;
- an `<a name>` with no href carries the block's first sentence, so it is split
  rather than chosen between;
- a `WWHClickedPopup` is a cross-reference and not a dead `javascript:` href;
- an `IconTable`'s prose is in the cell the icon is *not* in;
- consecutive `CodeLine` divs are one fence, not one fence each.

A sixth is the interrupted procedure: a note or a figure set between two steps
does not start a second list, because the source numbered them one.
"""

from collections.abc import Mapping
from pathlib import Path

from docushift.engines.base import ConversionContext, Unit
from docushift.engines.roots import find_output_roots
from docushift.engines.webworks import (
    SPAN_TO_TAG,
    WebWorksEngine,
    normalize,
)
from docushift.engines.webworks_toc import (
    calls,
    read_books,
    read_files,
    read_files_htm,
    read_return,
    read_text,
    read_toc,
)
from docushift.models import SourceEngine
from docushift.reporting.findings import FindingsRun
from docushift.transforms.assets import AssetCopier
from docushift.transforms.markdown import parse

# -- fixtures in the small ------------------------------------------------------


def build(directory: Path, files: Mapping[str, str | bytes]) -> Path:
    for name, text in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")
    return directory


def topic(title: str, body: str, *, charset: str = "utf-8") -> str:
    """One generated topic: the charset declaration, the `blockquote`, the banner.

    The `blockquote` is not decoration -- `body > blockquote` is where the prose
    is in 99.6% of the corpus, and selecting it is most of what chrome removal is.
    """
    return (
        "<html><head>"
        f'<meta http-equiv="Content-Type" content="text/html; charset={charset}">'
        f"<title>{title}</title>"
        "</head><body>"
        '<table align=\"right\"><tr><td class="WebWorks_Company_Logo">logo</td></tr></table>'
        '<div class="WebWorks_Breadcrumbs">Guide : ' f"{title}</div>"
        f"<blockquote>{body}</blockquote>"
        "</body></html>"
    )


def heading(text: str, level: int = 1) -> str:
    return f'<div class="N{level}Heading">{text}</div>'


def item(kind: str, marker: str, content: str) -> str:
    """One list item: `div.<Kind>_outer` wrapping a two-cell layout table.

    The shape is exact -- 10,252 of 10,252 sampled `_outer` divs have two cells,
    the marker in the first and the prose in the last -- and the engine's cell
    lookup is a shape match, so a fixture that got it wrong would pass for the
    wrong reason.
    """
    return (
        f'<div class="{kind}_outer"><table role="presentation"><tr>'
        f'<td><div class="{kind}_inner">{marker}</div></td>'
        f'<td><div class="{kind}_inner">{content}</div></td>'
        "</tr></table></div>"
    )


def note(body: str, icon: str = "IconNote") -> str:
    return (
        '<table class="IconTable"><tr>'
        f'<td><div class="{icon}"></div></td>'
        f'<td><div class="CellBody">{body}</div></td>'
        "</tr></table>"
    )


def files_js(*entries: tuple[str, str]) -> str:
    """`wwhdata/common/files.js`, written the way the generator writes it."""
    body = "\n".join(f'  P.fA("{title}","{href}");' for title, href in entries)
    return f"function  FileList_Object(P)\n{{\n{body}\n}}\n"


def toc_js(*lines: str) -> str:
    return "function  TocList_Object(P)\n{\n" + "\n".join(lines) + "\n}\n"


def node(variable: str, parent: str, label: str, location: str = "") -> str:
    """`A = P.fN("Label","3#anchor")` -- the assignment *is* the nesting."""
    target = f"{variable} = " if variable else ""
    return f'  {target}{parent}.fN("{label}","{location}");'


def book(name: str, *, topics: Mapping[str, str | bytes],
         files: tuple[tuple[str, str], ...],
         toc: str = "", title: str = "", context: str = "") -> dict[str, str | bytes]:
    """One complete book: its runtime under `wwhdata/`, its topics beside it."""
    out: dict[str, str | bytes] = {f"{name}/{k}" if name else k: v for k, v in topics.items()}
    prefix = f"{name}/" if name else ""
    out[f"{prefix}wwhdata/common/files.js"] = files_js(*files)
    if toc:
        out[f"{prefix}wwhdata/js/toc.js"] = toc
    if title:
        out[f"{prefix}wwhdata/common/title.js"] = (
            f'function  WWHBookData_Title()\n{{\n  return "{title}";\n}}\n'
        )
    if context:
        out[f"{prefix}wwhdata/common/context.js"] = (
            f'function  WWHBookData_Context()\n{{\n  return "{context}";\n}}\n'
        )
    return out


def books_xml(*declarations: tuple[str, str]) -> str:
    """`wwhelp/books.xml`, with the self-declaration every book also ships."""
    entries = "".join(
        f'<BookGroup name="{group}"><Book directory="{directory}"/></BookGroup>'
        if group else f'<Book directory="{directory}"/>'
        for directory, group in declarations
    )
    return f'<?xml version="1.0"?>\n<WebWorksHelpBooks name="Product Docs">{entries}</WebWorksHelpBooks>'


# -- running one tree -----------------------------------------------------------


class Run:
    """One conversion of one extracted tree, with its units and its findings."""

    def __init__(self, units: list[Unit], findings: FindingsRun, tree: Path):
        self.units = units
        self.findings = findings
        self.tree = tree

    @property
    def unit(self) -> Unit:
        return self.units[0]

    def named(self, name: str) -> Unit:
        for unit in self.units:
            if unit.name == name:
                return unit
        raise AssertionError(f"{name} not among {[unit.name for unit in self.units]}")

    def document(self, relative: str, unit: Unit | None = None):
        target = unit or self.unit
        for document in target.documents:
            if str(document.relative) == relative:
                return document
        raise AssertionError(f"{relative} not among {[str(d.relative) for d in target.documents]}")

    def body(self, relative: str, unit: Unit | None = None) -> str:
        return self.document(relative, unit).body

    def names(self, unit: Unit | None = None) -> list[str]:
        return sorted(str(d.relative) for d in (unit or self.unit).documents)

    def codes(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for finding in self.findings.all:
            tally[finding.code] = tally.get(finding.code, 0) + finding.count
        return tally

    def messages(self, code: str) -> list[str]:
        return [f.message for f in self.findings.all if f.code == code]


def run(tmp_path: Path, files: Mapping[str, str | bytes]) -> Run:
    """Converts every book in a tree, in the order the engine returns them."""
    tree = build(tmp_path / "tree", files)
    output = tmp_path / "out"
    findings = FindingsRun("convert")
    context = ConversionContext(
        tree=tree,
        output=output,
        engine=SourceEngine.WEBWORKS,
        slug="prod",
        version="1.0.0",
        product_name="TIBCO BusinessEvents",
        api_roots=[],
        output_roots=find_output_roots(tree, SourceEngine.WEBWORKS),
        findings=findings,
    )
    engine = WebWorksEngine()
    units = []
    for root in engine.units(context):
        name = root.relative_to(tree).as_posix()
        context.assets = AssetCopier(root, SourceEngine.WEBWORKS, output / name if name else output)
        units.append(engine.convert_unit(context, root))
    return Run(units, findings, tree)


def one(tmp_path: Path, body: str, **extra: str) -> str:
    """The Markdown for a single topic in a single book. The common case."""
    result = run(tmp_path, book(
        "guide",
        topics={"page.htm": topic("Page", body), **extra},
        files=(("Page", "page.htm"),),
        toc=toc_js(node("", "P", "Page", "0")),
    ))
    return result.body("page.md")


# -- reading the runtime (§5.3.3, §5.3.4) ---------------------------------------


def test_the_toc_index_addresses_files_js(tmp_path: Path) -> None:
    """The predecessor's central bug: `l` is a position in `files.js`.

    The two indexes are given deliberately different orders here, because that is
    the corpus's shape -- `files.htm` resolves 88.4% against `files.js`'s 100.0%,
    and is never the better of the two -- so a reader that fell back to `files.htm`
    would file both pages under the wrong node rather than fail visibly.
    """
    result = run(tmp_path, {
        **book(
            "guide",
            topics={
                "intro.htm": topic("Introduction", heading("Introduction")),
                "setup.htm": topic("Setup", heading("Setup")),
            },
            files=(("Introduction", "intro.htm"), ("Setup", "setup.htm")),
            toc=toc_js(node("", "P", "Introduction", "0"), node("", "P", "Setup", "1")),
        ),
        "guide/wwhdata/files.htm": (
            '<html><body><a href="../setup.htm">Setup</a>'
            '<a href="../intro.htm">Introduction</a></body></html>'
        ),
    })
    assert [(n.label, str(n.document)) for n in result.unit.nav] == [
        ("Introduction", "intro.md"),
        ("Setup", "setup.md"),
    ]


def test_a_stripped_book_keeps_its_topics_and_reports_the_missing_nav(tmp_path: Path) -> None:
    """45 books ship `wwhdata/files.htm` and neither `files.js` nor `toc.js`.

    They hold 1,395 topics between them. Skipping the book would drop all of them
    silently; converting it without a word would report navigation the book does
    not have. So: converted, unfiled, and one line saying why.
    """
    result = run(tmp_path, {
        "guide/wwhdata/files.htm":
            '<html><body><a href="../intro.htm">Introduction</a></body></html>',
        "guide/intro.htm": topic("Introduction", heading("Introduction")),
    })
    assert result.names() == ["intro.md"]
    assert result.document("intro.md").title == "Introduction"
    assert [n.label for n in result.unit.nav] == ["Unfiled"]
    assert any("stripped book" in message for message in result.messages("NAV_NODE_DROPPED"))


def test_nesting_comes_from_the_receiver_variable(tmp_path: Path) -> None:
    """`X = Y.fN(...)` makes the node a child of `Y`. There are no brackets."""
    entries = tuple((f"Topic {n}", f"t{n}.htm") for n in range(3))
    result = run(tmp_path, book(
        "guide",
        topics={f"t{n}.htm": topic(f"Topic {n}", heading(f"Topic {n}")) for n in range(3)},
        files=entries,
        toc=toc_js(
            node("A", "P", "Topic 0", "0"),
            node("B", "A", "Topic 1", "1"),
            node("", "B", "Topic 2", "2"),
        ),
    ))
    [root] = result.unit.nav
    assert root.label == "Topic 0"
    assert [child.label for child in root.children] == ["Topic 1"]
    assert [grand.label for grand in root.children[0].children] == ["Topic 2"]


def test_an_unknown_receiver_is_a_root_rather_than_a_dropped_node(tmp_path: Path) -> None:
    """The function's parameter is `P` in every corpus file -- and is not assumed.

    A generator that renamed it would otherwise produce an empty TOC and 100%
    orphans without a single line of complaint.
    """
    path = tmp_path / "toc.js"
    path.write_text(
        toc_js(node("A", "Q", "First", "0"), node("", "A", "Child", "1")),
        encoding="utf-8",
    )
    forest = read_toc(path)
    assert [entry.label for entry in forest] == ["First"]
    assert [child.label for child in forest[0].children] == ["Child"]


def test_a_label_only_node_survives_without_a_page(tmp_path: Path) -> None:
    """55 of 68,970 entries carry no `l`. The node is real; only its page is not."""
    result = run(tmp_path, book(
        "guide",
        topics={"t.htm": topic("Topic", heading("Topic"))},
        files=(("Topic", "t.htm"),),
        toc=toc_js(node("A", "P", "Part One"), node("", "A", "Topic", "0")),
    ))
    [root] = result.unit.nav
    assert (root.label, root.document) == ("Part One", None)
    assert [child.label for child in root.children] == ["Topic"]


def test_a_node_with_neither_page_nor_children_is_counted_not_silent(tmp_path: Path) -> None:
    result = run(tmp_path, book(
        "guide",
        topics={"t.htm": topic("Topic", heading("Topic"))},
        files=(("Topic", "t.htm"),),
        toc=toc_js(node("", "P", "Topic", "0"), node("", "P", "Gone", "9")),
    ))
    assert result.codes()["NAV_NODE_DROPPED"] == 1


def test_percent_encoded_hrefs_and_directories_are_decoded(tmp_path: Path) -> None:
    """One rule, two places: 22 `<Book directory>` values and every `files.js` href.

    Decoding takes declared-book resolution from 580 to 602 of 602, and it is the
    difference between a file being found and a topic silently vanishing.
    """
    result = run(tmp_path, {
        "wwhelp/books.xml": books_xml(("My%20Guide", "")),
        **book(
            "My Guide",
            topics={"error messages.htm": topic("Messages", heading("Messages"))},
            files=(("Messages", "error%20messages.htm"),),
            toc=toc_js(node("", "P", "Messages", "0")),
        ),
    })
    assert [unit.name for unit in result.units] == ["My Guide"]
    assert [(n.label, str(n.document)) for n in result.unit.nav] == [("Messages", "error messages.md")]


def test_declared_book_order_is_authored_order(tmp_path: Path) -> None:
    """Not alphabetical in 112 of 157 collections, so sorting scrambles most of them."""
    files = {"wwhelp/books.xml": books_xml(("zebra", ""), ("alpha", ""))}
    for name in ("alpha", "zebra"):
        files.update(book(
            name,
            topics={"t.htm": topic(name, heading(name))},
            files=((name, "t.htm"),),
            toc=toc_js(node("", "P", name, "0")),
        ))
    result = run(tmp_path, files)
    assert [unit.name for unit in result.units] == ["zebra", "alpha"]
    assert [unit.metadata["book_order"] for unit in result.units] == ["0", "1"]


def test_a_book_no_manifest_declares_is_converted_last(tmp_path: Path) -> None:
    """89 of 691 books are in no `books.xml`. Dropping them drops real content."""
    files = {"wwhelp/books.xml": books_xml(("declared", ""))}
    for name in ("declared", "orphan"):
        files.update(book(
            name,
            topics={"t.htm": topic(name, heading(name))},
            files=((name, "t.htm"),),
            toc=toc_js(node("", "P", name, "0")),
        ))
    result = run(tmp_path, files)
    assert [unit.name for unit in result.units] == ["declared", "orphan"]


def test_a_single_book_group_is_not_emitted_as_a_level(tmp_path: Path) -> None:
    """143 of 157 collections have one group named after themselves.

    A tree with one child at every level is not navigation, so the level is carried
    only when the manifest declares two or more.
    """
    files = {"wwhelp/books.xml": books_xml(("only", "Product Docs"))}
    files.update(book(
        "only",
        topics={"t.htm": topic("Only", heading("Only"))},
        files=(("Only", "t.htm"),),
        toc=toc_js(node("", "P", "Only", "0")),
    ))
    result = run(tmp_path, files)
    assert "book_group" not in result.unit.metadata
    assert result.unit.metadata["collection_name"] == "Product Docs"


def test_two_book_groups_are_carried_into_the_metadata(tmp_path: Path) -> None:
    files = {"wwhelp/books.xml": books_xml(("admin", "Administration"), ("dev", "Development"))}
    for name in ("admin", "dev"):
        files.update(book(
            name,
            topics={"t.htm": topic(name, heading(name))},
            files=((name, "t.htm"),),
            toc=toc_js(node("", "P", name, "0")),
        ))
    result = run(tmp_path, files)
    assert [unit.metadata["book_group"] for unit in result.units] == ["Administration", "Development"]


# -- decoding (§5.3.1) ----------------------------------------------------------


def test_the_declared_charset_wins_over_utf8(tmp_path: Path) -> None:
    """294 topics declare `iso-8859-1` and 196 fail a strict UTF-8 decode.

    Every one of them declares the charset that reads it, which is why there is no
    guessing here -- and why `errors="replace"` is the third attempt and not the
    first: it would turn a legible `é` into a replacement character.
    """
    latin = topic("Caf\u00e9", heading("Caf\u00e9"), charset="iso-8859-1")
    result = run(tmp_path, book(
        "guide",
        topics={"t.htm": latin.encode("iso-8859-1")},
        files=(("Caf\u00e9", "t.htm"),),
        toc=toc_js(node("", "P", "Caf\u00e9", "0")),
    ))
    assert "Caf\u00e9" in result.body("t.md")


def test_an_unreadable_topic_is_reported_rather_than_skipped(tmp_path: Path) -> None:
    result = run(tmp_path, book(
        "guide",
        topics={"t.htm": "<html><head><title>T</title></head></html>"},
        files=(("T", "t.htm"),),
        toc=toc_js(node("", "P", "T", "0")),
    ))
    assert result.names() == []
    assert result.codes()["CONTENT_MISSING"] == 1


# -- what is a topic (§5.3.9) ---------------------------------------------------


def test_the_runtime_directories_are_never_topics(tmp_path: Path) -> None:
    """`wwhdata/`, `wwhelp/` and `tpl/` are the generator's, not the writer's."""
    result = run(tmp_path, {
        **book(
            "guide",
            topics={"t.htm": topic("T", heading("T"))},
            files=(("T", "t.htm"),),
            toc=toc_js(node("", "P", "T", "0")),
        ),
        "guide/wwhelp/wwhimpl/js/html/frames.htm": "<html><body><p>frameset</p></body></html>",
        "guide/tpl/toolbar.htm": "<html><body><p>skin</p></body></html>",
    })
    assert result.names() == ["t.md"]


def test_framesets_and_generated_lists_are_counted_by_reason(tmp_path: Path) -> None:
    """`index`, `wwhsec`, `lof`, `lot`, `ix` -- keyed on the first dotted segment.

    The generator writes `lof.2.htm` as often as `lof.htm`, so a whole-stem test
    would let half of them through as topics with no prose in them.
    """
    result = run(tmp_path, book(
        "guide",
        topics={
            "t.htm": topic("T", heading("T")),
            "index.htm": topic("Index", "<p>frameset</p>"),
            "wwhsec.1.htm": topic("Section", "<p>frameset</p>"),
            "lof.2.htm": topic("Figures", "<p>generated</p>"),
            "ix.htm": topic("Index", "<p>generated</p>"),
        },
        files=(("T", "t.htm"),),
        toc=toc_js(node("", "P", "T", "0")),
    ))
    assert result.names() == ["t.md"]
    assert result.unit.skipped == {"runtime-stub": 2, "generated-list": 2}


def test_a_topic_the_toc_never_reaches_is_kept_and_reported(tmp_path: Path) -> None:
    """961 genuine orphans have real titles. The disk is the population, not the TOC."""
    result = run(tmp_path, book(
        "guide",
        topics={
            "t.htm": topic("T", heading("T")),
            "loose.htm": topic("Loose Page", heading("Loose Page")),
        },
        files=(("T", "t.htm"), ("Loose Page", "loose.htm")),
        toc=toc_js(node("", "P", "T", "0")),
    ))
    assert result.names() == ["loose.md", "t.md"]
    assert [n.label for n in result.unit.nav] == ["T", "Unfiled"]
    assert result.codes()["TOC_ORPHAN"] == 1


def test_a_nested_book_belongs_to_itself(tmp_path: Path) -> None:
    """Roots nest in the corpus, so the outer book must not claim the inner one's."""
    files = book(
        "outer",
        topics={"t.htm": topic("Outer", heading("Outer"))},
        files=(("Outer", "t.htm"),),
        toc=toc_js(node("", "P", "Outer", "0")),
    )
    files.update(book(
        "outer/inner",
        topics={"t.htm": topic("Inner", heading("Inner"))},
        files=(("Inner", "t.htm"),),
        toc=toc_js(node("", "P", "Inner", "0")),
    ))
    result = run(tmp_path, files)
    assert sorted(unit.name for unit in result.units) == ["outer", "outer/inner"]
    assert result.named("outer").skipped["nested-book"] == 1
    assert result.names(result.named("outer")) == ["t.md"]


def test_a_tree_with_no_book_root_is_reported(tmp_path: Path) -> None:
    result = run(tmp_path, {"loose.htm": topic("Loose", heading("Loose"))})
    assert result.units == []
    assert "OUTPUT_ROOT_MISSING" in result.codes()


# -- headings and chrome (§5.3.6, §5.3.7) ---------------------------------------


def test_the_heading_level_is_the_numeral_in_the_class(tmp_path: Path) -> None:
    body = heading("Top", 1) + heading("Middle", 2) + heading("Deep", 3)
    rendered = one(tmp_path, body)
    assert "# Top" in rendered
    assert "## Middle" in rendered
    assert "### Deep" in rendered


def test_a_flat_sub_heading_lands_below_the_deepest_numbered_one(tmp_path: Path) -> None:
    """`MinorHead` 19,531 and `Block-title` 12,788 carry no numeral and sit below h3."""
    rendered = one(tmp_path, heading("Deep", 3) + '<div class="MinorHead">Procedure</div>')
    assert "#### Procedure" in rendered


def test_a_chapter_outer_is_the_title_and_not_a_list_item(tmp_path: Path) -> None:
    """It wears the list shape and is the `h1`: `N1Heading` is absent from all 185.

    Taking the shape at face value emits `- Chapter 1 Introduction` as the topic's
    first line, which is what a purely structural reading produces.
    """
    rendered = one(tmp_path, item("Chapter", "Chapter 1", "Introduction"))
    assert rendered.startswith("# Chapter 1 Introduction")
    assert "- Chapter" not in rendered


def test_the_banner_and_the_breadcrumbs_are_not_prose(tmp_path: Path) -> None:
    rendered = one(tmp_path, heading("Page"))
    assert "logo" not in rendered
    assert "Guide :" not in rendered


def test_the_older_flavour_keeps_its_prose_when_there_is_no_blockquote(tmp_path: Path) -> None:
    """5 books at 0% and 634 at 100%, with nothing in between (§5.3.6).

    Its prose sits directly in the body beside the banner, so the fallback is real
    content -- and it is the only path where the banner has to be cut by hand.
    """
    raw = (
        "<html><head><title>Old</title></head><body>"
        '<table align="right"><tr><td class="WebWorks_Company_Logo">logo</td></tr></table>'
        "<hr>"
        '<div class="N1Heading">Old Flavour</div><div class="Body">Prose.</div>'
        "</body></html>"
    )
    result = run(tmp_path, book(
        "guide",
        topics={"old.htm": raw},
        files=(("Old Flavour", "old.htm"),),
        toc=toc_js(node("", "P", "Old Flavour", "0")),
    ))
    rendered = result.body("old.md")
    assert "# Old Flavour" in rendered
    assert "Prose." in rendered
    assert "logo" not in rendered


# -- lists (§5.3.7) -------------------------------------------------------------


def test_consecutive_outer_divs_are_one_list(tmp_path: Path) -> None:
    rendered = one(tmp_path, "".join(
        item("Bullet", "\u2022", f"Point {n}") for n in range(3)
    ))
    assert rendered.strip() == "- Point 0\n- Point 1\n- Point 2"


def test_the_marker_decides_the_list_kind(tmp_path: Path) -> None:
    """`Step` and `Bullet` both appear with and without numbering, and the opaque
    `ID-000000c3_outer` kinds carry no hint at all -- so the glyph is read."""
    assert "1. First" in one(tmp_path, item("Step", "1.", "First"))
    assert "- Dashed" in one(tmp_path, item("ListDash", "\u2212", "Dashed"))
    definition = one(tmp_path, item("MessageItem", "Action", "Restart the engine."))
    assert "Action" in definition
    assert "Restart the engine." in definition


def test_depth_is_read_off_the_kind_name(tmp_path: Path) -> None:
    """The only signal there is: no marker cell has a `width` and no `_outer` nests.

    `StepInd` and `ListDash` are the indented forms, so a `Step`/`StepInd` pair is
    one nested list rather than two flat ones.
    """
    rendered = one(tmp_path, (
        item("Step", "1.", "Outer step")
        + item("StepInd", "a.", "Inner step")
        + item("Step", "2.", "Next step")
    ))
    assert "1. Outer step" in rendered
    assert "\n   1. Inner step" in rendered
    assert "\n2. Next step" in rendered


def test_a_run_that_opens_indented_is_still_a_top_level_list(tmp_path: Path) -> None:
    """115 runs in the sample open on a `ListDash`, with no outer list above them."""
    rendered = one(tmp_path, item("ListDash", "\u2212", "Alone"))
    assert rendered.strip() == "- Alone"


def test_a_note_between_two_steps_does_not_restart_the_numbering(tmp_path: Path) -> None:
    """A run is interrupted 4,625 times per 3,037 topics and continues in 1,271.

    The next marker is the successor of the last one, so the source numbered them
    one procedure. Rendering each fragment as a fresh list restarts a nine-step
    procedure at 1 three times over -- and the note, re-parented into the step it
    belongs to, must not be deleted on the way.
    """
    rendered = one(tmp_path, (
        item("Step", "1.", "First step")
        + note("Watch out.")
        + item("Step", "2.", "Second step")
    ))
    assert "1. First step" in rendered
    assert "2. Second step" in rendered
    assert "   > [!NOTE]\n   > Watch out." in rendered


def test_a_heading_between_two_steps_starts_a_new_list(tmp_path: Path) -> None:
    """987 runs are broken by a heading and the numbering continues through one."""
    rendered = one(tmp_path, (
        item("Step", "1.", "First procedure")
        + heading("Second Procedure", 2)
        + item("Step", "2.", "Looks consecutive")
    ))
    assert "1. First procedure" in rendered
    assert "## Second Procedure" in rendered
    assert "1. Looks consecutive" in rendered


def test_a_restarted_marker_is_two_lists(tmp_path: Path) -> None:
    """The bridge is the successor test and nothing looser: `1.` after `2.` is new."""
    rendered = one(tmp_path, (
        item("Step", "1.", "First")
        + item("Step", "2.", "Second")
        + '<div class="Body">Prose between.</div>'
        + item("Step", "1.", "Fresh start")
    ))
    assert rendered.count("1. First") == 1
    assert "Prose between." in rendered
    assert rendered.rstrip().endswith("1. Fresh start")


def test_a_continuation_paragraph_belongs_to_its_item(tmp_path: Path) -> None:
    """1,302 `ListContinue` paragraphs, all of which used to be extracted twice."""
    rendered = one(tmp_path, (
        item("Step", "1.", "Run the installer")
        + '<div class="ListContinue">It takes a while.</div>'
    ))
    assert "1. Run the installer\n\n   It takes a while." in rendered


# -- code, callouts and tables (§5.3.7) -----------------------------------------


def test_consecutive_code_lines_are_one_fence(tmp_path: Path) -> None:
    """104,896 code-line divs against 60 `<pre>` elements corpus-wide.

    A fence per div turns a five-line command into five unrunnable one-line fences.
    """
    rendered = one(tmp_path, (
        '<div class="CodeLineFirst">bin/be-engine \\</div>'
        '<div class="CodeLine">  --propFile x.props \\</div>'
        '<div class="CodeLine">  --deploy</div>'
    ))
    assert rendered.count("```") == 2
    assert "bin/be-engine \\\n  --propFile x.props \\\n  --deploy" in rendered


def test_the_rule_drawn_around_a_code_block_is_not_a_thematic_break(tmp_path: Path) -> None:
    rendered = one(tmp_path, (
        '<hr class="Line"><div class="CodeLine">run()</div><hr class="Line">'
    ))
    assert "---" not in rendered
    assert "```\nrun()\n```" in rendered


def test_nbsp_indentation_in_a_code_line_becomes_spaces(tmp_path: Path) -> None:
    rendered = one(tmp_path, '<div class="CodeLine">&nbsp;&nbsp;indented</div>')
    assert "```\n  indented\n```" in rendered


def test_an_icon_table_reads_the_cell_the_icon_is_not_in(tmp_path: Path) -> None:
    """The predecessor's fourth bug: reading the icon cell empties 12,866 alerts."""
    rendered = one(tmp_path, note("Back up the store first.", icon="IconWarning"))
    assert rendered.strip() == "> [!WARNING]\n> Back up the store first."


def test_an_unmapped_icon_falls_back_to_a_note_and_is_reported(tmp_path: Path) -> None:
    """`IconSecurity` is the corpus's only miss, and GFM has five alert kinds.

    Inventing a sixth would produce a callout no renderer draws, so the fallback is
    the safe one and the line is what says the mapping was incomplete.
    """
    result = run(tmp_path, book(
        "guide",
        topics={"page.htm": topic("Page", note("Rotate the keys.", icon="IconSecurity"))},
        files=(("Page", "page.htm"),),
        toc=toc_js(node("", "P", "Page", "0")),
    ))
    assert result.body("page.md").startswith("> [!NOTE]")
    assert any("Security" in message for message in result.messages("ALERT_LABEL_UNMAPPED"))


def test_a_layout_table_is_unwrapped_rather_than_rendered(tmp_path: Path) -> None:
    """149,326 carry `role="presentation"` and 86,702 identical ones carry nothing."""
    rendered = one(tmp_path, (
        '<table role="presentation"><tr><td><div class="Body">Left.</div></td>'
        '<td><div class="Body">Right.</div></td></tr></table>'
    ))
    assert "|" not in rendered
    assert "Left." in rendered
    assert "Right." in rendered


def test_a_content_table_finds_its_header_row_by_cell_heading(tmp_path: Path) -> None:
    """Content tables have no `<th>` -- 45 in the whole corpus -- and GFM has no
    headerless pipe table, so `div.CellHeading` is what names the row."""
    rendered = one(tmp_path, (
        "<table><tr>"
        '<td><div class="CellHeading">Parameter</div></td>'
        '<td><div class="CellHeading">Description</div></td>'
        "</tr><tr>"
        '<td><div class="CellBody">pageSize</div></td>'
        '<td><div class="CellBody">Rows per page.</div></td>'
        "</tr></table>"
    ))
    assert "| Parameter | Description |" in rendered
    assert "| pageSize | Rows per page. |" in rendered


def test_a_table_caption_is_lifted_out_before_the_rows_are_read(tmp_path: Path) -> None:
    """The shared walk reads `tr` only, so a caption left in place is dropped."""
    rendered = one(tmp_path, (
        '<table><caption><div class="TableTitle">Table 3 Settings</div></caption>'
        '<tr><td><div class="CellHeading">Name</div></td></tr>'
        '<tr><td><div class="CellBody">timeout</div></td></tr></table>'
    ))
    assert "*Table 3 Settings*" in rendered
    assert "| Name |" in rendered


def test_a_figure_title_stays_where_the_source_put_it(tmp_path: Path) -> None:
    """98.3% of figure titles are followed by their image, so source order reads."""
    rendered = one(
        tmp_path,
        '<div class="FigureTitle">Figure 2 The wizard</div><p><img src="images/w.gif"></p>',
        **{"images/w.gif": "GIF89a"},
    )
    assert rendered.index("*Figure 2 The wizard*") < rendered.index("![](images/w.gif)")


# -- inline spans (§5.3.7) ------------------------------------------------------


def test_the_span_map_covers_the_three_kinds_and_leaves_livelink_alone() -> None:
    """`LiveLink` is a *link* wrapper: mapping it to a tag would swallow the href."""
    assert SPAN_TO_TAG["Code"] == "code"
    assert SPAN_TO_TAG["uicontrol"] == "strong"
    assert SPAN_TO_TAG["Emphasis"] == "em"
    assert "LiveLink" not in SPAN_TO_TAG


def test_inline_spans_become_their_markdown(tmp_path: Path) -> None:
    rendered = one(tmp_path, (
        '<div class="Body">Click <span class="uicontrol">Next</span>, then run '
        '<span class="Code">be-engine</span> in <span class="Italic">bin</span>.</div>'
    ))
    assert "**Next**" in rendered
    assert "`be-engine`" in rendered
    assert "*bin*" in rendered


# -- references (§5.3.8, invariant 13) ------------------------------------------


def test_a_cross_reference_becomes_a_relative_markdown_link(tmp_path: Path) -> None:
    result = run(tmp_path, book(
        "guide",
        topics={
            "a.htm": topic("A", '<div class="Body">See <a href="b.htm#s1">B</a>.</div>'),
            "b.htm": topic("B", '<a name="s1"></a>' + heading("B")),
        },
        files=(("A", "a.htm"), ("B", "b.htm")),
        toc=toc_js(node("", "P", "A", "0"), node("", "P", "B", "1#s1")),
    ))
    assert "[B](b.md#s1)" in result.body("a.md")


def test_a_popup_is_a_cross_book_reference_and_not_a_dead_javascript_href(tmp_path: Path) -> None:
    """The predecessor's third bug. Same-book popups resolve at 100%.

    The book is named by its `context.js` value, which disagrees with the directory
    name for 34 of 646 books -- so both are keys into the same table.
    """
    files = book(
        "guide",
        topics={"a.htm": topic("A", (
            '<div class="Body">See <a href="javascript:WWHClickedPopup('
            "'refbook', 'ref.htm#p9', '');\">the reference</a>.</div>"
        ))},
        files=(("A", "a.htm"),),
        toc=toc_js(node("", "P", "A", "0")),
    )
    files.update(book(
        "reference",
        topics={"ref.htm": topic("Ref", '<a name="p9"></a>' + heading("Ref"))},
        files=(("Ref", "ref.htm"),),
        toc=toc_js(node("", "P", "Ref", "0#p9")),
        context="refbook",
    ))
    result = run(tmp_path, files)
    assert "[the reference](../reference/ref.md#p9)" in result.body("a.md", result.named("guide"))


def test_a_popup_naming_a_book_the_package_never_shipped_is_reported(tmp_path: Path) -> None:
    """711 of them, and no version-wide fallback would find any: the book is absent."""
    result = run(tmp_path, book(
        "guide",
        topics={"a.htm": topic("A", (
            '<div class="Body">See <a href="javascript:WWHClickedPopup('
            "'missing', 'x.htm#p1', '');\">elsewhere</a>.</div>"
        ))},
        files=(("A", "a.htm"),),
        toc=toc_js(node("", "P", "A", "0")),
    ))
    assert "elsewhere" in result.body("a.md")
    assert "](" not in result.body("a.md")
    assert result.codes()["TOPIC_LINK_DANGLING"] == 1


def test_a_named_anchor_keeps_its_sentence_and_its_target(tmp_path: Path) -> None:
    """The predecessor's second bug. The generator wraps the block's first sentence
    in the anchor, so returning only the text is silently right for the prose and
    destroys every target -- and deleting the element loses the sentence."""
    result = run(tmp_path, book(
        "guide",
        topics={
            "a.htm": topic("A", '<div class="Body">See <a href="b.htm#s1">B</a>.</div>'),
            "b.htm": topic("B", '<div class="N1Heading"><a name="s1">Section One</a></div>'),
        },
        files=(("A", "a.htm"), ("B", "b.htm")),
        toc=toc_js(node("", "P", "A", "0"), node("", "P", "B", "1")),
    ))
    assert '# <a id="s1"></a>Section One' in result.body("b.md")
    assert result.document("b.md").anchors == {"s1"}


def test_an_anchor_nothing_points_at_is_not_emitted(tmp_path: Path) -> None:
    """Only 6.46% of 85,219 anchor names are ever referenced. The rest are noise."""
    rendered = one(tmp_path, '<div class="N1Heading"><a name="99001">Section</a></div>')
    assert rendered.strip() == "# Section"


def test_a_csh_target_counts_as_a_reference(tmp_path: Path) -> None:
    """43% of `topics.js` targets carry an anchor (§5.4.4).

    Left out of the reference set, the help map resolves to the right page and the
    wrong place on it for nearly half the identifiers in the corpus.
    """
    result = run(tmp_path, {
        **book(
            "guide",
            topics={"a.htm": topic("A", '<div class="N1Heading"><a name="ctx1">A</a></div>')},
            files=(("A", "a.htm"),),
            toc=toc_js(node("", "P", "A", "0")),
        ),
        "guide/wwhdata/common/topics.js": (
            "function  WWHBookData_MatchTopic(P)\n{\n  var C = null;\n"
            '  if(P=="HelpID")C="a.htm#ctx1";\n  return C;\n}\n'
        ),
    })
    assert '<a id="ctx1"></a>' in result.body("a.md")


def test_a_same_page_fragment_that_names_nothing_is_reported(tmp_path: Path) -> None:
    result = run(tmp_path, book(
        "guide",
        topics={"a.htm": topic("A", '<div class="Body">See <a href="#gone">below</a>.</div>')},
        files=(("A", "a.htm"),),
        toc=toc_js(node("", "P", "A", "0")),
    ))
    assert "below" in result.body("a.md")
    assert result.codes()["TOPIC_LINK_DANGLING"] == 1


def test_an_image_keeps_its_source_filename(tmp_path: Path) -> None:
    """The name comes from `src`, never from `alt`.

    The 22,126 images with no `alt` are exactly the 22,126 under `images/`, and
    every `tpl/` skin icon has one -- so `alt` is a skin marker, and naming the
    copied file from it, as the predecessor does, falls through to a synthesized
    name on 100% of content images.
    """
    rendered = one(
        tmp_path,
        '<p><img src="images/wizard.gif" alt="Toolbar"></p>',
        **{"images/wizard.gif": "GIF89a"},
    )
    assert "(images/wizard.gif)" in rendered


# -- titles and tail pages (§5.3.4, §5.3.5) -------------------------------------


def test_the_files_js_title_wins_over_the_title_element(tmp_path: Path) -> None:
    """They agree in 30,537 of 30,601, and `files.js` is the cleaner of the two:
    its titles are the ones without the `&nbsp;` padding."""
    result = run(tmp_path, book(
        "guide",
        topics={"t.htm": topic("Chapter\u00a01\tIntroduction", heading("Introduction"))},
        files=(("Prerequisites &amp; Dependencies", "t.htm"),),
        toc=toc_js(node("", "P", "Intro", "0")),
    ))
    assert result.document("t.md").title == "Prerequisites & Dependencies"


def test_the_title_element_is_the_fallback_when_files_js_has_no_entry(tmp_path: Path) -> None:
    result = run(tmp_path, book(
        "guide",
        topics={"loose.htm": topic("Loose Page", heading("Loose Page"))},
        files=(),
        toc="",
    ))
    assert result.document("loose.md").title == "Loose Page"


def test_the_copyright_page_is_the_legal_page(tmp_path: Path) -> None:
    """`copyrigh.htm` -- truncated, and titled `Important Information` in 99 of 101.

    It is in the TOC of almost none of them and is the second-largest group of
    orphans in the corpus, so a TOC-only search finds a legal page for 2 books in
    70 rather than 57.
    """
    result = run(tmp_path, book(
        "guide",
        topics={
            "t.htm": topic("T", heading("T")),
            "copyrigh.htm": topic("Important Information", heading("Important Information")),
        },
        files=(("T", "t.htm"), ("Important Information", "copyrigh.htm")),
        toc=toc_js(node("", "P", "T", "0")),
    ))
    assert str(result.unit.legal) == "copyrigh.md"


def test_a_whole_book_can_be_the_support_page(tmp_path: Path) -> None:
    """31 books are one of these two pages and nothing else, so `title.js` is read."""
    files = {"wwhelp/books.xml": books_xml(("guide", ""), ("support", ""))}
    files.update(book(
        "guide",
        topics={"t.htm": topic("T", heading("T"))},
        files=(("T", "t.htm"),),
        toc=toc_js(node("", "P", "T", "0")),
    ))
    files.update(book(
        "support",
        topics={"page.htm": topic("Support", heading("TIBCO Documentation and Support Services"))},
        files=(("Support", "page.htm"),),
        title="TIBCO Documentation and Support Services",
    ))
    result = run(tmp_path, files)
    assert str(result.named("support").support) == "page.md"


def test_a_missing_tail_page_is_reported_once_per_collection(tmp_path: Path) -> None:
    """A 40-book collection has one legal page by design, and 39 rows saying the
    other 39 lack one would bury the collection that genuinely does."""
    files = {"wwhelp/books.xml": books_xml(("a", ""), ("b", ""))}
    for name in ("a", "b"):
        files.update(book(
            name,
            topics={"t.htm": topic(name, heading(name))},
            files=((name, "t.htm"),),
            toc=toc_js(node("", "P", name, "0")),
        ))
    result = run(tmp_path, files)
    assert result.codes()["TAIL_PAGE_MISSING"] == 2


def test_the_landing_page_is_left_for_phase_six(tmp_path: Path) -> None:
    """Both candidate files are framesets and there is no `DefaultUrl` to read, so
    §6.2 generates the node from the metadata carried here rather than guessing."""
    result = run(tmp_path, book(
        "guide",
        topics={"t.htm": topic("T", heading("T"))},
        files=(("T", "t.htm"),),
        toc=toc_js(node("", "P", "T", "0")),
        title="Developer's Guide",
    ))
    assert result.unit.landing is None
    assert result.unit.metadata["book_title"] == "Developer's Guide"


# -- the readers, without a DOM -------------------------------------------------


def test_a_call_is_parsed_and_never_executed() -> None:
    """These files ship with a runtime that could put an expression in an argument,
    so a call whose arguments are not all literals is skipped rather than guessed."""
    found = calls(
        'P.fA("One","a.htm");\n'
        "P.fA(computeTitle(),\"b.htm\");\n"
        "X = P.fN('Two\\u0027s', '3#top');\n",
        "fA",
    )
    assert [call.arguments for call in found] == [("One", "a.htm")]
    [nested] = calls("X = P.fN('Two\\u0027s', '3#top');", "fN")
    assert nested.arguments == ("Two's", "3#top")
    assert (nested.receiver, nested.target) == ("P", "X")


def test_a_comparison_is_not_read_as_an_assignment() -> None:
    [call] = calls('if (A == P.fN("Label","0")) { }', "fN")
    assert call.target == ""


def test_an_unterminated_literal_ends_the_call_rather_than_the_file() -> None:
    found = calls('P.fA("Broken\nP.fA("Good","g.htm");', "fA")
    assert [call.arguments for call in found] == [("Good", "g.htm")]


def test_files_htm_hrefs_resolve_against_the_wwhdata_directory(tmp_path: Path) -> None:
    """They are written relative to `wwhdata/` and climb out of it: `../admin.htm`.

    Resolved against the book instead, all 1,395 topics in the 45 stripped books
    point at files that do not exist.
    """
    path = tmp_path / "files.htm"
    path.write_text(
        '<html><body><a href="../admin.5.15.htm">Admin</a></body></html>',
        encoding="utf-8",
    )
    assert [(e.title, e.href) for e in read_files_htm(path)] == [("Admin", "admin.5.15.htm")]


def test_a_books_xml_that_declares_only_itself_is_not_a_collection(tmp_path: Path) -> None:
    """Every *book* ships a `wwhelp/` too, so `<Book directory="."/>` is the
    discriminator the directory layout does not give."""
    path = tmp_path / "books.xml"
    path.write_text(
        '<?xml version="1.0"?><WebWorksHelpBooks name="Guide">'
        '<Book directory="."/></WebWorksHelpBooks>',
        encoding="utf-8",
    )
    collection = read_books(path)
    assert collection is not None
    assert collection.books == []


def test_a_namespaced_books_xml_is_read_the_same_way(tmp_path: Path) -> None:
    path = tmp_path / "books.xml"
    path.write_text(
        '<?xml version="1.0"?>'
        '<ns:WebWorksHelpBooks xmlns:ns="urn:webworks" name="Docs">'
        '<ns:BookGroup name="Admin"><ns:Book directory="admin"/></ns:BookGroup>'
        "</ns:WebWorksHelpBooks>",
        encoding="utf-8",
    )
    collection = read_books(path)
    assert collection is not None
    assert [(b.directory, b.group) for b in collection.books] == [("admin", "Admin")]


def test_an_unparseable_books_xml_is_absence_and_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "books.xml"
    path.write_text("<WebWorksHelpBooks><Book", encoding="utf-8")
    assert read_books(path) is None


def test_read_return_reads_the_one_string_in_title_js(tmp_path: Path) -> None:
    path = tmp_path / "title.js"
    path.write_text(
        'function  WWHBookData_Title()\n{\n  return "Developer&#8217;s Guide";\n}\n',
        encoding="utf-8",
    )
    assert read_return(path) == "Developer\u2019s Guide"


def test_read_text_never_raises_on_a_file_that_is_not_there(tmp_path: Path) -> None:
    assert read_text(tmp_path / "gone.js") is None


def test_files_js_hrefs_are_percent_decoded(tmp_path: Path) -> None:
    path = tmp_path / "files.js"
    path.write_text(files_js(("Messages", "error%20messages.4.001.htm")), encoding="utf-8")
    assert [entry.href for entry in read_files(path)] == ["error messages.4.001.htm"]


# -- the normalizer, without an engine ------------------------------------------


def test_normalize_is_post_order_so_a_nested_list_is_built_first() -> None:
    """A procedure inside a table cell is common enough that pre-order shows.

    Building the outer construct first would read cells whose own lists had not
    been grouped yet, and the inner items would render as stray tables.
    """
    soup = parse(
        "<html><body><div>"
        '<table role="presentation"><tr><td>'
        + item("Bullet", "\u2022", "Inner")
        + "</td></tr></table>"
        "</div></body></html>"
    )
    container = soup.find("div")
    assert container is not None
    normalize(container)
    assert container.find("ul") is not None
    assert container.find("li").get_text(strip=True) == "Inner"
