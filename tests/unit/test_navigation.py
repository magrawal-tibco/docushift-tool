"""Unit tests for Stage 6a: one version's navigation, out of what the engines report.

The synthesizer is the only place §10's three node rules run, and it is the only
place the per-unit lists become one tree -- so these tests are written against
*shapes the corpus actually has* rather than against a tidy invented one: a
version of several books (90.1% of WebWorks versions), a legal notice reported by
more than one of them (105 of 400 multi-book versions), a landing page absent from
the TOC (55 of 60 sampled Flare roots), and a version with no landing page at all
(every WebWorks collection).

They assert on the returned `Synthesis` and on rendered text, never on the private
helpers: how the tree is walked is an implementation detail, and which node ends
up first is the contract.
"""

from pathlib import Path, PurePosixPath

import pytest
import yaml

from docushift.converter.navigation import render_metadata, render_toc, synthesize
from docushift.engines.base import ConversionContext, Document, NavNode, Unit
from docushift.models import SourceEngine
from docushift.reporting.findings import FindingsRun


@pytest.fixture
def templates(repo_root: Path) -> Path:
    """The shipped templates, not a stub: their indentation is under test too."""
    return repo_root / "config" / "aem_templates"


@pytest.fixture
def context(tmp_path: Path) -> ConversionContext:
    return ConversionContext(
        tree=tmp_path / "tree",
        output=tmp_path / "out",
        engine=SourceEngine.WEBWORKS,
        slug="tibco-ems",
        version="10.4.0",
        product_name="TIBCO Enterprise Message Service",
        findings=FindingsRun("convert"),
    )


def page(relative: str, title: str = "") -> Document:
    """A converted topic, as an engine hands it over: unit-relative, already `.md`."""
    return Document(source=Path(relative), relative=PurePosixPath(relative), title=title)


def pair(entry: "str | tuple[str, str]") -> Document:
    """`pages=` takes a path, or a `(path, title)` where the title is the point."""
    return page(*entry) if isinstance(entry, tuple) else page(entry)


def node(label: str, relative: str | None = None, *children: NavNode) -> NavNode:
    return NavNode(
        label=label,
        document=PurePosixPath(relative) if relative else None,
        children=list(children),
    )


def book(name: str, *, title: str = "", pages: tuple[str, ...] = (), **rest) -> Unit:
    """One unit of work. `pages` names the documents; everything else is passed on."""
    for key in ("landing", "whats_new", "support", "legal"):
        if key in rest:
            rest[key] = PurePosixPath(rest[key])
    return Unit(
        root=Path(name),
        name=name,
        title=title,
        documents=[pair(entry) for entry in pages],
        **rest,
    )


def labels(nodes: list[NavNode]) -> list[str]:
    return [node.label for node in nodes]


def paths(nodes: list[NavNode]) -> list[str]:
    return [str(node.document) for node in nodes]


# -- assembling several units ---------------------------------------------------


def test_a_lone_unit_contributes_its_nodes_without_a_wrapper(context, templates) -> None:
    """A level with one child is not navigation -- the same rule §5.3.3 applies."""
    unit = book(
        "guide",
        pages=("intro.md", "setup.md"),
        nav=[node("Introduction", "intro.md"), node("Setup", "setup.md")],
        landing="intro.md",
    )

    result = synthesize(context, [unit], templates)

    assert labels(result.nodes) == ["Introduction", "Setup"]
    # Rebased onto the version root even though no wrapper was added: the unit's
    # subtree is where the files are, wrapper or not.
    assert paths(result.nodes) == ["guide/intro.md", "guide/setup.md"]
    assert result.generated == 0


def test_several_units_get_one_node_each_in_the_order_the_engine_returned(context, templates) -> None:
    """WebWorks returns `books.xml` order, which is non-alphabetical in 71%."""
    units = [
        book("user", title="User's Guide", pages=("home.md", "a.md"),
             nav=[node("A", "a.md")], landing="home.md"),
        book("admin", title="Administration", pages=("b.md",), nav=[node("B", "b.md")]),
    ]

    result = synthesize(context, units, templates)

    # Not re-sorted: `admin` would come first if it were.
    assert labels(result.nodes) == ["User's Guide", "Administration"]
    assert labels(result.nodes[0].children) == ["A"]


def test_a_unit_with_no_title_is_labelled_from_its_landing_page_then_its_stem(context, templates) -> None:
    """The chain exists because two of the four engines fill `Unit.title` and two do not."""
    units = [
        book(
            "one",
            pages=(("home.md", "Messaging Overview"), "a.md"),
            nav=[node("A", "a.md")],
            landing="home.md",
        ),
        book("tib_adas400_concepts", pages=("b.md",), nav=[node("B", "b.md")]),
    ]

    result = synthesize(context, units, templates)

    assert labels(result.nodes) == ["Messaging Overview", "Tib Adas400 Concepts"]


def test_a_unit_wrapper_takes_the_units_landing_page_as_its_own(context, templates) -> None:
    """One page, one position: the inner node pointing at it goes."""
    units = [
        book(
            "one",
            title="One",
            pages=("home.md", "a.md"),
            nav=[node("Home", "home.md"), node("A", "a.md")],
            landing="home.md",
        ),
        book("two", title="Two", pages=("b.md",), nav=[node("B", "b.md")]),
    ]

    result = synthesize(context, units, templates)

    assert str(result.nodes[0].document) == "one/home.md"
    assert labels(result.nodes[0].children) == ["A"]
    # And the wrapper that had no landing to take is the only one that needed a
    # page generated -- under its own subtree, not at the version root.
    assert [str(document.relative) for document in result.documents] == ["two/two.md"]


# -- What's New, second (Phase 11a) ---------------------------------------------


def test_whats_new_is_moved_to_second_from_wherever_the_source_filed_it(context, templates) -> None:
    """407 of 481 real ones are buried inside a guide. All of them end up here."""
    unit = book(
        "guide",
        pages=("home.md", "install.md", "_templates/Whats-New.md"),
        nav=[
            node("Home", "home.md"),
            node("Installation", "install.md", node("What's New", "_templates/Whats-New.md")),
        ],
        landing="home.md",
        whats_new="_templates/Whats-New.md",
    )

    result = synthesize(context, [unit], templates)

    assert paths(result.nodes) == [
        "guide/home.md", "guide/_templates/Whats-New.md", "guide/install.md",
    ]
    # Moved rather than copied: the node is gone from under Installation.
    assert result.nodes[2].children == []


def test_whats_new_in_no_toc_entry_is_inserted_rather_than_lost(context, templates) -> None:
    """74 roots have a real What's New that no TOC entry reaches."""
    unit = book(
        "guide",
        pages=("home.md", "install.md", ("_templates/Whats-New.md", "What's New")),
        nav=[node("Home", "home.md"), node("Installation", "install.md")],
        landing="home.md",
        whats_new="_templates/Whats-New.md",
    )

    result = synthesize(context, [unit], templates)

    assert labels(result.nodes) == ["Home", "What's New", "Installation"]


def test_whats_new_is_still_second_where_the_version_index_is_generated(context, templates) -> None:
    """No landing page: the node goes first and the generated index lands above it."""
    unit = book(
        "guide",
        pages=("a.md", ("_templates/Whats-New.md", "What's New")),
        nav=[node("A", "a.md")],
        whats_new="_templates/Whats-New.md",
    )

    result = synthesize(context, [unit], templates)

    assert labels(result.nodes)[1] == "What's New"
    assert result.landing == result.nodes[0].document


# -- the support / legal tail ---------------------------------------------------


def test_the_tail_is_moved_to_the_end_rather_than_appended(context, templates) -> None:
    """Moved: a second copy in place would put the notice in the tree twice."""
    unit = book(
        "guide",
        pages=("legal.md", "a.md", "support.md"),
        nav=[node("Legal", "legal.md"), node("A", "a.md"), node("Support", "support.md")],
        landing="a.md",
        support="support.md",
        legal="legal.md",
    )

    result = synthesize(context, [unit], templates)

    assert paths(result.nodes) == ["guide/a.md", "guide/support.md", "guide/legal.md"]


def test_the_first_unit_in_order_supplies_the_tail_and_the_rest_are_dropped(context, templates) -> None:
    """105 of 400 multi-book versions carry legal in more than one book.

    Positional and not hashed: in 83 of those the copies differ, but only by
    FrameMaker anchor ids, so content-addressing would keep all nine copies.
    """
    units = [
        book(
            f"book{index}",
            title=f"Book {index}",
            pages=("copyrigh.md", "topic.md"),
            nav=[node("Topic", "topic.md"), node("Important Information", "copyrigh.md")],
            legal="copyrigh.md",
        )
        for index in range(1, 4)
    ]

    result = synthesize(context, units, templates)

    assert str(result.nodes[-1].document) == "book1/copyrigh.md"
    assert result.dropped == 2
    # Dropped from the navigation only. The pages stay on disk, because a CSH
    # identifier or an inbound link may still reach one.
    assert all(not any(child.document and "copyrigh" in str(child.document)
                       for child in top.walk())
               for top in result.nodes[:-1])
    assert [f.code for f in context.findings.all] == ["NAV_NODE_DROPPED"]
    assert context.findings.all[0].count == 2


def test_a_duplicate_tail_page_that_has_children_is_left_where_it_is(context, templates) -> None:
    """It is a section named like a tail page; extracting it would move its children."""
    units = [
        book("one", title="One", pages=("home.md", "legal.md"),
             nav=[node("Legal", "legal.md")], landing="home.md", legal="legal.md"),
        book(
            "two",
            title="Two",
            pages=("start.md", "legal.md", "third-party.md"),
            nav=[node("Legal", "legal.md", node("Third Party", "third-party.md"))],
            landing="start.md",
            legal="legal.md",
        ),
    ]

    result = synthesize(context, units, templates)

    assert str(result.nodes[-1].document) == "one/legal.md"
    assert labels(result.nodes[1].children) == ["Legal"]
    assert result.dropped == 0


def test_a_tail_page_the_toc_never_listed_still_reaches_the_tail(context, templates) -> None:
    """WebWorks' `copyrigh.htm` is in the TOC of almost no book (§5.3.5)."""
    unit = book(
        "guide",
        pages=("a.md", "copyrigh.md"),
        nav=[node("A", "a.md")],
        landing="a.md",
        legal="copyrigh.md",
    )

    result = synthesize(context, [unit], templates)

    assert paths(result.nodes) == ["guide/a.md", "guide/copyrigh.md"]


# -- the landing page -----------------------------------------------------------


def test_the_landing_page_is_hoisted_to_first_when_the_toc_lists_it(context, templates) -> None:
    unit = book(
        "guide",
        pages=("a.md", "home.md"),
        nav=[node("A", "a.md"), node("Home", "home.md")],
        landing="home.md",
    )

    result = synthesize(context, [unit], templates)

    assert paths(result.nodes) == ["guide/home.md", "guide/a.md"]
    assert str(result.landing) == "guide/home.md"


def test_the_landing_page_is_inserted_when_the_toc_does_not_list_it(context, templates) -> None:
    """Flare's `DefaultUrl` is absent from the TOC in 55 of 60 sampled roots."""
    unit = book(
        "guide",
        pages=("a.md", ("home.md", "TIBCO EMS Documentation")),
        nav=[node("A", "a.md")],
        landing="home.md",
    )

    result = synthesize(context, [unit], templates)

    assert paths(result.nodes) == ["guide/home.md", "guide/a.md"]
    assert labels(result.nodes)[0] == "TIBCO EMS Documentation"


# -- generated pages ------------------------------------------------------------


def test_a_node_with_children_and_no_page_gets_one_generated(context, templates) -> None:
    """Flare's `'___'` sentinel: 165 per 60 roots, 158 of them with children."""
    unit = book(
        "guide",
        pages=(("home.md", "Home"), "ch/a.md", "ch/b.md"),
        nav=[node("Chapter One", None, node("A", "ch/a.md"), node("B", "ch/b.md"))],
        landing="home.md",
    )

    result = synthesize(context, [unit], templates)

    assert result.generated == 1
    generated = result.documents[0]
    # Beside the children it indexes, not over one of them.
    assert str(generated.relative) == "guide/ch/chapter-one.md"
    assert generated.frontmatter == {"generated": True}
    assert generated.title == "Chapter One"
    assert generated.body.splitlines()[0] == "# Chapter One"
    assert "- [A](a.md)" in generated.body
    assert str(result.nodes[1].document) == "guide/ch/chapter-one.md"


def test_a_node_with_neither_page_nor_children_is_dropped_and_counted(context, templates) -> None:
    """DITA's `lof`/`lot`/`ix`, and Flare's 7 childless sentinels."""
    unit = book(
        "guide",
        pages=("a.md",),
        nav=[node("A", "a.md"), node("List of Figures")],
        landing="a.md",
    )

    result = synthesize(context, [unit], templates)

    assert labels(result.nodes) == ["A"]
    assert result.dropped == 1


def test_a_generated_page_never_lands_on_top_of_a_converted_one(context, templates) -> None:
    unit = book(
        "guide",
        pages=("ch/a.md", "ch/chapter-one.md"),
        nav=[
            node("Chapter One", None, node("A", "ch/a.md")),
            node("Existing", "ch/chapter-one.md"),
        ],
    )

    result = synthesize(context, [unit], templates)

    assert str(result.documents[0].relative) == "guide/ch/chapter-one-2.md"


def test_a_generated_page_never_lands_on_a_converted_one_in_another_case(
    context, templates
) -> None:
    """The collision test folds case, because the shelf does not.

    `_slug` lower-cases a container's label, so a "Installation" node beside a
    converted `install/Installation.md` produced `install/installation.md` -- a
    different path to Python and the *same file* to Windows, which wrote the
    generated page straight into the topic. Three versions shipped that way and
    lost their text, and nothing in the run reported it; Stage 8's case-sensitive
    resolution found all three as `toc.yml` `LINK_BROKEN` rows on its first run.
    """
    unit = book(
        "guide",
        pages=("install/Installation.md", "install/Installation_Modes.md"),
        nav=[
            node("Installation", None, node("Modes", "install/Installation_Modes.md")),
            node("Installation Modes", "install/Installation.md"),
        ],
    )

    result = synthesize(context, [unit], templates)

    assert str(result.documents[0].relative) == "guide/install/installation-2.md"


def test_a_version_with_no_landing_page_gets_a_generated_index(context, templates) -> None:
    """WebWorks has none by design; DITA's TOC is a forest in 23 of 23 doc-sets."""
    units = [
        book("one", title="One", pages=("a.md",), nav=[node("A", "a.md")]),
        book("two", title="Two", pages=("b.md",), nav=[node("B", "b.md")]),
    ]

    result = synthesize(context, units, templates)

    assert str(result.landing) == "index.md"
    assert str(result.nodes[0].document) == "index.md"
    index = next(doc for doc in result.documents if str(doc.relative) == "index.md")
    assert index.title == "TIBCO Enterprise Message Service"
    assert "- [One](one/a.md)" not in index.body  # the wrapper's page, not its child's
    assert "- [One](" in index.body


def test_the_generated_index_prefers_the_name_the_collection_gave_itself(context, templates) -> None:
    units = [
        book("one", title="One", pages=("a.md",), nav=[node("A", "a.md")],
             metadata={"collection_name": "TIBCO Adapter for SAP"}),
        book("two", title="Two", pages=("b.md",), nav=[node("B", "b.md")]),
    ]

    result = synthesize(context, units, templates)

    assert result.documents[-1].title == "TIBCO Adapter for SAP"


# -- rendering ------------------------------------------------------------------


def test_render_toc_nests_children_and_survives_a_colon_in_a_title(templates) -> None:
    """A title holding a colon is ordinary prose here, and must not become a mapping."""
    nodes = [
        node("Overview", "home.md"),
        node("Chapter: One", "ch/index.md", node("A", "ch/a.md")),
    ]

    text = render_toc(nodes, templates, title="TIBCO EMS 10.4.0")
    parsed = yaml.safe_load(text)

    assert [item["title"] for item in parsed["items"]] == ["Overview", "Chapter: One"]
    assert parsed["items"][1]["children"] == [{"title": "A", "path": "ch/a.md"}]
    assert "for TIBCO EMS 10.4.0" in text.splitlines()[0]


def test_render_toc_keeps_the_anchor_a_node_carries(templates) -> None:
    """12.1% of Flare's TOC entries carry one, and entries routinely share a page."""
    nodes = [NavNode(label="Step 2", document=PurePosixPath("guide/setup.md"), anchor="step-2")]

    parsed = yaml.safe_load(render_toc(nodes, templates))

    assert parsed["items"][0]["path"] == "guide/setup.md#step-2"


def test_render_metadata_writes_the_keys_it_is_given_and_no_others(templates) -> None:
    text = render_metadata([("csg-version", "10.4.0")], templates, level="version")
    parsed = yaml.safe_load(text)

    assert parsed == {"csg-version": "10.4.0"}
    # The dotted form, quoted -- unquoted, `10.4.0` is a string but `10.4` is a float.
    assert 'csg-version: "10.4.0"' in text
    assert "(version level)" in text
