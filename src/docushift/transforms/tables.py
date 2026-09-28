"""HTML tables to GFM pipe tables -- or, where that would lose information, not.

**A table that is not GFM-safe passes through as HTML.** GFM has no `rowspan`, no
`colspan`, no nested table and no multi-block cell, so converting one anyway means
silently flattening a span into an adjacent cell -- which reads as a plausible
table and is a wrong one. Measured: 57% of Flare's tables are safe and 50.5% of
WebWorks' (multi-block cells 9,635, nested 3,815, spans 1,791), so this branch is
half the corpus rather than an edge case.

What is *not* here is the decision about which tables are tables at all. Both
Flare and WebWorks emit lists as single-column tables -- Flare's `AutoNumber_p_*`
(1,321 in 7% of sampled topics) and WebWorks' exact `div.<Kind>_outer > table >
tr > td` shape, whose `_inner`:`_outer` ratio is exactly 2.000 corpus-wide. Those
are lists and their engine converts them as lists before anything reaches this
module. Discriminating them needs engine-specific class names, and a generic
"looks like a layout table" heuristic here would take 86,702 WebWorks wrappers
from older output with it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from bs4 import NavigableString, Tag

# Block-level tags inside a cell. One is fine -- a cell wrapped in a single `<p>`
# is the common case and unwraps cleanly; two means the cell has structure that a
# pipe row cannot carry.
_BLOCKS = frozenset({"p", "div", "ul", "ol", "dl", "pre", "blockquote", "table", "h1",
                     "h2", "h3", "h4", "h5", "h6"})


class Unsafe(StrEnum):
    """Why a table cannot be a pipe table. Reported, so the ratio stays visible."""

    SPAN = "span"
    NESTED = "nested-table"
    MULTI_BLOCK = "multi-block-cell"
    RAGGED = "ragged-rows"
    EMPTY = "empty"


@dataclass
class Cell:
    tag: Tag
    header: bool = False
    colspan: int = 1
    rowspan: int = 1


@dataclass
class Table:
    rows: list[list[Cell]] = field(default_factory=list)
    # Index of the header row, or None. Not always row 0: WebWorks puts its
    # `div.CellHeading` in row 1 in 98.5% of content tables but has **no `<th>` at
    # all** (45 corpus-wide), so the engine supplies this rather than the markup.
    header_row: int | None = None


def _spans(cell: Tag, name: str) -> int:
    try:
        value = int(str(cell.get(name, "1")).strip())
    except (TypeError, ValueError):
        return 1
    return max(1, value)


def read(table: Tag, header_row: int | None = None) -> Table:
    """Reads a `<table>` into rows of cells. Structure only, no rendering.

    Rows are taken from `tr` at any depth *of this table*, so a `thead`/`tbody`
    split does not change the answer -- but a `tr` belonging to a nested table is
    excluded, because it is the nested table's row and counting it here would make
    every parent look ragged.
    """
    model = Table(header_row=header_row)
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = [
            Cell(cell, header=cell.name == "th",
                 colspan=_spans(cell, "colspan"), rowspan=_spans(cell, "rowspan"))
            for cell in row.find_all(["td", "th"], recursive=False)
        ]
        if cells:
            model.rows.append(cells)
    if model.header_row is None and model.rows and all(c.header for c in model.rows[0]):
        model.header_row = 0
    return model


def unsafe_reason(model: Table) -> Unsafe | None:
    """Why this table cannot be a pipe table, or None if it can."""
    if not model.rows:
        return Unsafe.EMPTY
    widths = {sum(cell.colspan for cell in row) for row in model.rows}
    for row in model.rows:
        for cell in row:
            if cell.colspan > 1 or cell.rowspan > 1:
                return Unsafe.SPAN
            if cell.tag.find("table") is not None:
                return Unsafe.NESTED
            if _block_count(cell.tag) > 1:
                return Unsafe.MULTI_BLOCK
    if len(widths) > 1:
        return Unsafe.RAGGED
    return None


def _block_count(cell: Tag) -> int:
    """Top-level block children, plus any loose text beside them.

    Counted at the top level only: a `<ul>` inside the cell's single `<p>` is one
    block with a list in it as far as a pipe row is concerned, and descending
    would call every ordinary paragraph multi-block.
    """
    blocks = sum(1 for child in cell.children
                 if isinstance(child, Tag) and child.name in _BLOCKS)
    if blocks and any(isinstance(child, NavigableString) and child.strip()
                      for child in cell.children):
        blocks += 1
    return blocks


def is_gfm_safe(model: Table) -> bool:
    return unsafe_reason(model) is None


def escape(text: str) -> str:
    """Makes one cell's rendered Markdown survive a pipe row.

    A newline ends the row, so it becomes `<br>` -- which GFM passes through and
    every renderer honours. A `|` would start a new column.
    """
    collapsed = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return " ".join(collapsed.split()).replace("|", r"\|")


def to_pipe(model: Table, render: Callable[[Tag], str]) -> str:
    """Emits a GFM pipe table. Caller has already checked `is_gfm_safe`.

    `render` turns one cell's contents into inline Markdown; it belongs to the
    engine, because what counts as emphasis is a class name in WebWorks and a real
    `<em>` in DITA.
    """
    width = max(len(row) for row in model.rows)
    header_index = model.header_row
    lines: list[str] = []

    if header_index is None:
        # GFM has no headerless table. An empty header row is the least-lossy
        # stand-in: the alternative is promoting a data row, which relabels the
        # column with a value.
        lines.append(_line([""] * width))
        lines.append(_line(["---"] * width))
        body = model.rows
    else:
        header = model.rows[header_index]
        lines.append(_line([escape(render(cell.tag)) for cell in header], width))
        lines.append(_line(["---"] * width))
        body = [row for index, row in enumerate(model.rows) if index != header_index]

    for row in body:
        lines.append(_line([escape(render(cell.tag)) for cell in row], width))
    return "\n".join(lines)


def _line(values: list[str], width: int | None = None) -> str:
    cells = list(values)
    if width is not None:
        cells += [""] * (width - len(cells))
    return "| " + " | ".join(cells) + " |"


#: Classes that survive a passthrough. Everything else goes. Measured on the
#: published EMS tree: 26,829 `class` attributes across 899 of 8,639 files, of
#: which **25,849 (96.3%) are Flare's generated `TableStyle-*` naming** -- a row
#: band and a column position in a stylesheet that does not travel with the
#: content, and therefore says nothing about what the table means.
#:
#: The ones below are the other 980. Each names something the plain text has
#: already lost -- `varname` (617), `MCXref xref` (184), `filepath`, the `note*`
#: family -- and a later phase turns them into real Markdown constructs rather
#: than discarding them, so dropping them here would be destroying the input to
#: that work.
#:
#: **A keep-list rather than a `TableStyle-*` strip-list.** A strip-list knows
#: one generator's vocabulary; DITA, DocBook and WebWorks each bring their own,
#: and anything unforeseen would pass through untouched. This fails closed, and
#: an engine with a vocabulary of its own passes it as `keep` -- which is what
#: WebWorks does with `SPAN_TO_TAG`, whose class names are the only record that
#: a span was code or emphasis.
SEMANTIC_CLASSES = frozenset({
    "note", "noteTip", "noteWarning", "noteHeadInTable",
    "varname", "filepath", "option", "cite",
    "MCXref", "xref", "tabletitle", "autonumber", "groupOfURLs",
})


#: Attributes that survive a passthrough. Everything else is presentation or
#: authoring-tool plumbing and goes with it.
#:
#: **Phase 23 widened Phase 21's scrub from `class` to every attribute**, and the
#: corpus is the argument. Measured on the published EMS tree, 887 files with a
#: table: **812 `style="mc-table-style: url('../Resources/TableStyles/Table.css')"`
#: pointing at a folder that does not exist anywhere under `output/`** -- a
#: dangling reference the link checker cannot see, because it reads `href` and
#: `src` and this is inside a `style`. **1,696 `<col title="C1">`**, which is not
#: a label but a *tooltip*: a reader hovering a column border sees "C1". And 201
#: assorted `data-mc-conditions`, `data-mc-autonum` and stray `xmlns`.
#:
#: The 1,386 genuine layout attributes -- `cellspacing`, `col style="width:
#: 169px"`, `td style="padding"` -- go too, which is the part Phase 21 declined
#: to do and a writer decided. **That is a rendering change and is not claimed to
#: be anything else**: the published stylesheet sizes these tables now, which is
#: better on a narrow screen and occasionally worse where a pixel width was
#: holding a command name on one line. It cannot be verified by showing that
#: nothing changed, and it is not.
#:
#: A keep-list again, for `SEMANTIC_CLASSES`' reason: a strip-list knows one
#: generator's vocabulary and lets the next one through untouched. What is kept
#: is structure and content -- what a cell spans, where a link goes, what an
#: anchor is called -- never how any of it looks.
STRUCTURAL_ATTRS = frozenset({
    "class",                                        # governed by `keep`, above
    "href", "src", "alt", "srcset", "usemap",       # where it points
    "id", "name", "headers", "scope",               # what it is called
    "colspan", "rowspan", "span",                   # what it covers
    "start", "value", "reversed", "type",           # list numbering, which is content
    "lang", "dir", "datetime",                      # language and time
})

#: Elements whose `title` a human wrote. Everywhere else it is generated -- the
#: 1,696 `<col title="C1">` above -- and a generated tooltip is worse than a
#: silent one, because it renders.
TITLE_BEARERS = frozenset({"a", "abbr", "area", "img", "iframe"})


def scrub(table: Tag, keep: frozenset[str] = SEMANTIC_CLASSES,
          attrs: frozenset[str] = STRUCTURAL_ATTRS) -> None:
    """Drops presentation from a subtree about to be emitted as HTML.

    **The root as well as its descendants.** `find_all(True)` returns descendants
    only, and a scrub written without the root in front of it is the
    predecessor's bug rather than a hypothetical one: `html-to-md`'s
    `_clean_table_html` iterates exactly that way, and its output carries 530
    `ebx_definitionList` classes of which every single one is on a `<table>` and
    not one is on a descendant.

    Mutates in place, which is safe for the same reason `markdown.rewrite`'s
    mutation is: the subtree is discarded as soon as the topic is rendered.

    An emptied `class` is deleted rather than left as `class=""` -- that shape is
    neither the old output nor the clean one, and would defeat a check written
    against either.

    A `<col>` left holding nothing is removed, and a `<colgroup>` emptied by that
    goes after it. Once the widths are gone a `<col/>` carries no information at
    all, and leaving 1,696 of them in the output would be keeping the skeleton of
    the decision rather than the decision.
    """
    for element in [table, *table.find_all(True)]:
        names = element.get("class")
        if names:
            kept = [name for name in names if name in keep]
            if kept:
                element["class"] = kept
            else:
                del element["class"]

        for name in [a for a in element.attrs if a not in attrs]:
            if name == "title" and element.name in TITLE_BEARERS:
                continue
            del element[name]

    # Two passes and in this order: a `<colgroup>` is only empty once its `<col>`
    # children have gone, and `find_all` hands back the parent first.
    for spec in table.find_all("col"):
        if not spec.attrs:
            spec.decompose()
    for group in table.find_all("colgroup"):
        if not group.attrs and not group.find(True):
            group.decompose()


def passthrough(table: Tag, keep: frozenset[str] = SEMANTIC_CLASSES,
                attrs: frozenset[str] = STRUCTURAL_ATTRS) -> str:
    """The table's own HTML, minus the authoring tool's styling, as a block.

    Blank-line padded so that Markdown treats it as an HTML block rather than
    trying to parse the first line as a paragraph.

    **Layout goes too, as of Phase 23.** Phase 21 kept `border`, `cellpadding`,
    `cellspacing`, `width` and `valign` on the argument that removing them is a
    rendering change rather than a cleanup, and bundling the two would leave any
    regression ambiguous about which caused it. That argument was about
    *sequencing*, and the sequence has now happened: the classes went first and
    were verified byte-for-byte, so this change stands on its own and the
    published stylesheet sizes the tables.
    """
    scrub(table, keep, attrs)
    return str(table)
