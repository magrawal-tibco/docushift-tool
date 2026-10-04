"""R6 and R7.1: the pages a human has to decide about, and why.

This is the interface between the mechanical stage and the writer, and the
requirements put it on the critical path rather than in the polish pile:
"Reframe deliberately does not resolve these cases itself." Everything else the
stage emits is an assertion about what it did; this is the list of things it
declined to do on purpose.

**Two of R6's five flags annotate rather than queue** (planning §20c, measured).
`title-inherited` is specified as "`n_topics > 1` and the page title equals its
first topic's title" -- but R7 *defines* the page title as the first topic's, so
the second clause is true by construction and the condition reduces to
`n_topics > 1`. It fires on 107 of EMS 10.5.1's 124 pages. `single-topic` fires
on the other 17, and R6's own table calls it "usually fine". Between them they
cover every page, which is the outcome R6 rules out one line above the table:
"a queue containing every page is not a queue." So both are computed, both are
recorded on every page in `reframe.yml`, both appear in a queued row's `flags`
column -- and neither, alone, puts a page in front of a writer. The three
structural flags queue 18 pages, against R6's own predicted 25-30.

Widening that later is a change to `QUEUEING` and nothing else, because the
flags themselves are computed for every page either way.

**A sixth flag, `shortened`, is not R6's and does queue** (Phase 34, R1-03). A
page whose filename does not carry its whole title publishes an address a reader
cannot read the page off -- the 50-character cut took its last words, or a name
pinned in `rename-map.csv` says less. That file already had the column, and 66
EMS pages sat in it with nothing pointing a writer at them. The filename is the
URL (Phase 29), so choosing a better one is an editorial decision like the rest.

**There is no better page title available, and it was checked.** The obvious
reading of R7.1's "emit the best title it can" is to name a page after the TOC
node whose subtree it covers. Measured: 30 of 124 pages are exactly one subtree,
and in every case that node's title is the *identical string* to the first
topic's. It has to be -- the packer emits a subtree's own node first (top-down
since Phase 28, bottom-up before it, and true of both), so that node contributes
the first topic of the page it collapses into.
The improvement R7.1 wants is a human one, which is why the flag exists.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from docushift.reframe.packer import Page
from docushift.reframe.toc import TocEntry
from docushift.utils.csvio import read_rows, write_rows

#: R6's columns, unchanged. A published contract with an editorial pass that does
#: not exist yet: adding a column later is cheap, renaming one is not.
COLUMNS = ("page_path", "guide", "n_topics", "words", "flags", "detail")

#: Declared order, R6's table order, then `shortened`. `flags` and `detail` are
#: emitted in it, so two runs over one input cannot disagree about which clause
#: comes first.
FLAGS = ("reference-list", "oversized", "title-inherited", "heterogeneous", "single-topic",
         "shortened")

#: The flags that put a page in the queue. See the module docstring: the two left
#: out are not weaker signals, they are conditions that hold for every page.
QUEUEING = frozenset({"reference-list", "oversized", "heterogeneous", "shortened"})

#: R6's `reference-list` thresholds. Named because they are editorial judgments
#: that a second doc set may want tuned, not facts about Markdown.
_LIST_TOPICS = 20
_LIST_MEDIAN_WORDS = 100


@dataclass(frozen=True)
class Flag:
    """One judgment being asked for, and the numbers it turns on."""

    name: str
    #: Free text. The flag says *which* decision; this carries what it depends on,
    #: so the writer does not have to open the page to find out.
    detail: str


def branches(roots: Sequence[TocEntry]) -> dict[PurePosixPath, str]:
    """Each topic's depth-2 TOC ancestor, by title. R6's `heterogeneous` scope.

    A top-level row's *own* topic has no depth-2 ancestor and is simply absent from
    the map, rather than bucketed under its own title. R6 says "depth-2 ancestor"
    and a guide's landing topic does not have one -- and the alternative makes a
    page holding a parent topic plus its single child branch read as spanning two
    branches, which is the one shape that is obviously not heterogeneous. Measured
    on EMS 10.5.1: 5 pages either way against 7, and the two it drops are that
    false positive. A page merging a guide's landing topic with *several* branches
    still flags, on the branches.
    """
    found: dict[PurePosixPath, str] = {}

    def walk(node: TocEntry, depth: int, branch: str | None) -> None:
        if node.path is not None and branch is not None and node.path not in found:
            found[node.path] = branch
        for child in node.children:
            walk(child, depth + 1, branch if branch is not None else (child.title if depth == 0 else None))

    for root in roots:
        walk(root, 0, None)
    return found


def inspect(
    page: Page, max_words: int, ancestors: dict[PurePosixPath, str], *, shortened: bool = False
) -> list[Flag]:
    """Every flag this page raises, queueing or not, in `FLAGS` order.

    `shortened` is `packer.shortened`'s answer, passed in rather than recomputed
    so the queue and `rename-map.csv`'s column cannot disagree about a page.
    """
    found: list[Flag] = []
    count = len(page.topics)
    median = int(statistics.median([topic.words for topic in page.topics])) if page.topics else 0

    if count >= _LIST_TOPICS and median <= _LIST_MEDIAN_WORDS:
        found.append(Flag(
            "reference-list",
            f"{count} topics averaging {median} words -- table, split, or stay granular",
        ))
    if page.words > max_words:
        found.append(Flag(
            "oversized",
            f"{page.words:,} words over a {max_words:,} cap; a source topic may need splitting",
        ))
    if count > 1:
        found.append(Flag(
            "title-inherited",
            f"titled after the first of {count} topics",
        ))

    # A carried-through page has no TOC node at all, so every topic misses the map
    # and the set is `{None}` -- one bucket, correctly not heterogeneous.
    spread = sorted({ancestors[t.source] for t in page.topics if t.source in ancestors})
    if len(spread) > 1:
        shown = ", ".join(spread[:3]) + (", ..." if len(spread) > 3 else "")
        found.append(Flag("heterogeneous", f"spans {len(spread)} TOC branches ({shown})"))

    if count == 1:
        found.append(Flag("single-topic", "one topic; no merge decision was taken"))
    if shortened and page.topics:
        found.append(Flag(
            "shortened",
            f'named "{page.path.stem}" for the title "{page.topics[0].title}"; '
            f"a better name goes in rename-map.csv",
        ))
    return found


def queues(flags: Sequence[Flag]) -> bool:
    """Whether this page's flags are enough to ask a human to look at it."""
    return any(flag.name in QUEUEING for flag in flags)


def rows(
    pages: Sequence[Page], flagged: dict[PurePosixPath, list[Flag]]
) -> list[dict[str, str]]:
    """R6's queue, in reading order -- not sorted by `page_path`.

    A writer works a guide at a time, and reading order is already deterministic,
    so sorting would buy nothing and cost the ordering that makes the file
    navigable beside `reframe.yml`.
    """
    built: list[dict[str, str]] = []
    for page in pages:
        flags = flagged.get(page.path, [])
        if not queues(flags):
            continue
        built.append({
            "page_path": str(page.path),
            "guide": page.guide,
            "n_topics": str(len(page.topics)),
            "words": str(page.words),
            "flags": ";".join(flag.name for flag in flags),
            "detail": "; ".join(flag.detail for flag in flags),
        })
    return built


#: What a row a writer worked says once its page is no longer flagged (X2-06).
NO_LONGER_QUEUED = "no longer flagged by this merge; kept for the decision recorded in this row"


def previous(path: Path) -> list[dict[str, str]]:
    """The queue as it stands before a re-merge rewrites it: what a writer may have worked.

    Read, not tolerated: a queue that cannot be read fails the version (the
    driver reports it), because rewriting it would drop whatever was in it.
    """
    return read_rows(path) if path.is_file() else []


def write(path: Path, queue: Sequence[dict[str, str]],
          worked: Sequence[dict[str, str]] = ()) -> None:
    """One `review-queue.csv`. CSV and not YAML because a human edits this one.

    Through `csvio.write_rows`, so it gets the same BOM the catalog CSVs get --
    titles carry `®` and `™`, and Excel reads those as mojibake without it.

    **A writer's own columns survive a re-merge** (Phase 34, X2-06). The docs call
    this file the one meant to be edited, and every re-merge rewrote it from
    scratch with the six stock columns. Any column a writer added to `worked`,
    the queue as it stood, is carried over by `page_path`. The six stock columns
    are this run's measurement and are rewritten. A worked row whose page is no
    longer flagged is kept at the end, so a recorded decision is never dropped.
    """
    extra = [column for column in dict.fromkeys(key for row in worked for key in row)
             if column and column not in COLUMNS]
    by_page = {row.get("page_path", ""): row for row in worked if row.get("page_path")}
    rows = []
    for row in queue:
        kept = by_page.pop(row["page_path"], {})
        rows.append({**row, **{column: kept.get(column, "") for column in extra}})
    for page, kept in by_page.items():
        if any(kept.get(column, "").strip() for column in extra):
            rows.append({"page_path": page, "guide": kept.get("guide", ""),
                         "detail": NO_LONGER_QUEUED,
                         **{column: kept.get(column, "") for column in extra}})
    write_rows(path, (*COLUMNS, *extra), rows)


def tally(flagged: dict[PurePosixPath, list[Flag]]) -> dict[str, int]:
    """How many pages raised each flag, in `FLAGS` order. For the run report."""
    counted = {name: 0 for name in FLAGS}
    for flags in flagged.values():
        for flag in flags:
            counted[flag.name] += 1
    return {name: count for name, count in counted.items() if count}
