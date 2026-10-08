"""Requirements §6: the checks Reframe runs on its own output before it ships it.

"Reframe must self-validate and fail the stage if any check fails." That sentence
is the reason this module exists as something other than a test. The merge is a
one-way door -- §1: "Reframe cannot be re-run to fix a bad boundary" -- so the run
that produced a tree is the last moment anyone is in a position to reject it
cheaply. A check that lives only in the test suite protects the reference corpus
and no other doc set.

Every check returns a list of human-readable failures rather than raising, so one
run reports all of them instead of the first. The driver turns each into a
`REFRAME_SELF_CHECK_FAILED` finding and refuses the swap.

**What is deliberately not fatal.** Requirements §8 lists defects that arrive in
the input: dangling in-page anchors and links into trees that are not there. The
link check is therefore stated as *newly* broken -- a relative `.md` target that
exists on disk but that no page claims. A target that was already missing before
the merge is counted, named, and allowed. Attributing it to Reframe would make the
stage fail on a defect it cannot fix and did not cause.

Determinism (C5, and §6's last row) is the one criterion not checkable from inside
a single run. It is pinned by `tests/unit/test_reframe.py` rendering the same input
twice, and by running the stage twice with `--force` over the corpus.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from docushift.reframe.packer import Page
from docushift.reframe.pages import LinkCounts
from docushift.reframe.toc import TocEntry


def audit(
    pages: Sequence[Page],
    located: dict[PurePosixPath, tuple[Page, str]],
    roots: Sequence[TocEntry],
    words_in: int,
    words_out: int,
    added: int,
    counts: LinkCounts,
    unnavigated: frozenset[PurePosixPath] = frozenset(),
    queue: Sequence[dict[str, str]] = (),
    csh: dict[str, str] | None = None,
    anchors: dict[PurePosixPath, frozenset[str]] | None = None,
    mirrored: dict[PurePosixPath, frozenset[str]] | None = None,
    placements: dict[int, tuple[Page, str]] | None = None,
) -> list[str]:
    """Every §6 check that failed, named. An empty list is a passing merge.

    `unnavigated` names the pages carried through from topics the TOC never listed
    (`packer.carry`). They are exempt from reachability and from nothing else --
    they must still be anchored, single-directory, redirected and word-conserving.

    `placements` is `assign`'s per-row record. A topic listed under two guides has
    one copy per guide (Phase 29) but one entry in `located`, the first; the
    anchor and reachability checks read the rows so the second copy counts
    (Phase 47).
    """
    failures: list[str] = []
    failures.extend(_words(words_in, words_out, added))
    failures.extend(_anchors(pages, located))
    failures.extend(_directories(pages))
    failures.extend(_guides(pages, roots))
    failures.extend(_navigation(pages, located, roots, unnavigated, placements or {}))
    failures.extend(_links(counts))
    failures.extend(_redirects(pages, located))
    failures.extend(_queue(pages, queue))
    failures.extend(_csh(csh or {}, anchors or {}, mirrored or {}))
    return failures


def _words(words_in: int, words_out: int, added: int) -> list[str]:
    """Word conservation: output == input plus the scaffolding that declared itself.

    An equality, not a tolerance. `render` returns exactly what each topic's
    heading shift added -- one token for an anchored H1, more for a synthesized
    one -- so any other difference is content that moved or vanished, which is the
    failure this check is for. A tolerance here would hide precisely that.
    """
    expected = words_in + added
    if words_out == expected:
        return []
    return [
        f"word conservation: {words_out} words out, expected {expected} "
        f"({words_in} in + {added} added by anchors and headings); "
        f"difference {words_out - expected}"
    ]


def _anchors(pages: Sequence[Page], located: dict[PurePosixPath, tuple[Page, str]]) -> list[str]:
    failures: list[str] = []
    total = sum(len(page.anchors) for page in pages)
    topics = sum(len(page.topics) for page in pages)
    if total != topics:
        failures.append(f"anchors: {total} anchors for {topics} topics")
    # Every anchored topic is located, and nothing is located that no page anchors.
    # Compared as sets of sources: a topic under two guides is anchored once per
    # copy and located once (Phase 47), so the counts legitimately differ.
    anchored = {source for page in pages for source in page.anchors}
    if anchored != set(located):
        failures.append(f"anchors: {len(located)} topics located, {len(anchored)} anchored")
    for page in pages:
        seen = list(page.anchors.values())
        if len(set(seen)) != len(seen):
            duplicated = sorted({a for a in seen if seen.count(a) > 1})
            failures.append(f"anchors: {page.path} repeats {', '.join(duplicated)}")
    return failures


def _directories(pages: Sequence[Page]) -> list[str]:
    """R4.2. Enforced by the packer, so a failure here means the packer regressed."""
    failures = []
    for page in pages:
        spread = sorted({topic.directory for topic in page.topics})
        if len(spread) > 1:
            failures.append(f"directory integrity: {page.path} spans {', '.join(spread)}")
    return failures


def _guides(pages: Sequence[Page], roots: Sequence[TocEntry]) -> list[str]:
    """R1.1: every topic a TOC row placed sits on a page of that row's own guide.

    Phase 47. `project`'s path-only match put IBM MQ 8.7.0's second-guide copy on a
    first-guide page, and no other check could see it: anchors, reachability and
    words all still added up. Topics no row placed (`node` 0) are not checked.
    """
    guide_of_row = {id(entry): root.title for root in roots for entry in root.walk()}
    failures = []
    for page in pages:
        strays = sorted({str(topic.source) for topic in page.topics
                         if topic.node and guide_of_row.get(topic.node, page.guide) != page.guide})
        if strays:
            failures.append(f"guide integrity: {page.path} ({page.guide}) holds {', '.join(strays[:3])} "
                            f"from another guide")
    return failures


def _navigation(
    pages: Sequence[Page],
    located: dict[PurePosixPath, tuple[Page, str]],
    roots: Sequence[TocEntry],
    unnavigated: frozenset[PurePosixPath],
    placements: dict[int, tuple[Page, str]],
) -> list[str]:
    """TOC completeness and reachability, checked in both directions.

    Completeness alone would pass a tree that also emitted pages nothing links to;
    reachability alone would pass a TOC that quietly lost a branch. The pair is
    what makes "the merge is invisible to users" (R3) an assertion rather than a
    hope, and losing a branch is exactly the failure the unrecognised-schema error
    in the driver exists to prevent one dialect earlier.
    """
    failures: list[str] = []
    nodes = [entry for root in roots for entry in root.walk() if entry.path is not None]
    missing = [str(entry.path) for entry in nodes if entry.path not in located]
    if missing:
        shown = ", ".join(missing[:5])
        failures.append(
            f"TOC completeness: {len(missing)} node(s) point at no page ({shown}"
            f"{', ...' if len(missing) > 5 else ''})"
        )

    # Each row reaches the copy placed for it, else the first copy (a row deduped
    # within its guide places nothing of its own).
    reachable = {
        placements.get(id(entry), located.get(entry.path))[0].path
        for entry in nodes if entry.path in located
    } | unnavigated
    orphaned = sorted(str(page.path) for page in pages if page.path not in reachable)
    if orphaned:
        shown = ", ".join(orphaned[:5])
        failures.append(
            f"reachability: {len(orphaned)} page(s) not reachable from the TOC ({shown}"
            f"{', ...' if len(orphaned) > 5 else ''})"
        )
    return failures


def _links(counts: LinkCounts) -> list[str]:
    """Zero *newly* broken. See the module docstring for why the word matters."""
    if counts.orphaned:
        return [
            f"links: {counts.orphaned} relative target(s) exist in the source tree but "
            f"belong to no page -- the merge broke them"
        ]
    return []


def _queue(pages: Sequence[Page], queue: Sequence[dict[str, str]]) -> list[str]:
    """R6: every queued row names a page that was actually written.

    The same class of bug `_redirects` catches, at the same cost. A writer opening
    the queue and finding a path that is not there loses the one thing the queue is
    for -- and would reasonably conclude the whole file is stale.
    """
    written = {str(page.path) for page in pages}
    missing = sorted(row["page_path"] for row in queue if row["page_path"] not in written)
    if not missing:
        return []
    shown = ", ".join(missing[:5])
    return [
        f"review queue: {len(missing)} row(s) name a page that was not written "
        f"({shown}{', ...' if len(missing) > 5 else ''})"
    ]


def _redirects(pages: Sequence[Page], located: dict[PurePosixPath, tuple[Page, str]]) -> list[str]:
    """R5: one 301 per source topic, zero dangling.

    Dangling is checked against the pages actually built, not against the map that
    produced them, so a page dropped between packing and writing is caught here
    rather than by a reader following a redirect into a 404.
    """
    failures: list[str] = []
    known = {page.path: page for page in pages}
    for source, (page, anchor) in sorted(located.items()):
        built = known.get(page.path)
        if built is None:
            failures.append(f"redirects: {source} points at {page.path}, which was not written")
        elif anchor not in built.anchors.values():
            failures.append(f"redirects: {source} points at {page.path}#{anchor}, which has no such anchor")
    return failures


def _csh(
    csh: dict[str, str],
    anchors: dict[PurePosixPath, frozenset[str]],
    mirrored: dict[PurePosixPath, frozenset[str]],
) -> list[str]:
    """20f. Every Help button resolves against the tree that is about to be swapped.

    Checked against what `_write` actually rendered rather than against `located`,
    because the two halves this can get wrong are both in the bytes: the anchor a
    CSH value points at is an `<a id>` marker inside a topic body, and the mirror
    is a frontmatter key. Re-deriving either from the page model would be the audit
    checking its own arithmetic.

    Three findings and not one, because they fail for different reasons -- a
    missing page means the retarget did not fire, a missing anchor means the
    marker did not survive the body copy, and a missing mirror entry means
    `_frontmatter` dropped it. `validate` would report all three later; §6's whole
    point is that it should never get the chance.
    """
    failures: list[str] = []
    for identifier, value in sorted(csh.items()):
        target, _, fragment = value.partition("#")
        page = PurePosixPath(target)
        if page not in anchors:
            failures.append(f"csh: {identifier} -> {value}, which is not a merged page")
            continue
        if fragment and fragment.lower() not in anchors[page]:
            failures.append(f"csh: {identifier} -> #{fragment} is not an anchor in {target}")
        if identifier not in mirrored.get(page, frozenset()):
            failures.append(f"csh: {identifier} is not in {target}'s frontmatter (design.md 9.5)")
    return failures
