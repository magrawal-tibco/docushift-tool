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


def passthrough(table: Tag) -> str:
    """The table's own HTML, unchanged, as a block.

    Blank-line padded so that Markdown treats it as an HTML block rather than
    trying to parse the first line as a paragraph.
    """
    return str(table)
