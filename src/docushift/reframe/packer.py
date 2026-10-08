"""R1 and R2: which topics become one page, and what each one is called.

The packer decides layout and nothing else. It never opens a topic body -- word
counts arrive through a callable -- so the whole of R1 is testable against a dict
of sizes, and the body rewriting in `pages.py` cannot accidentally influence a
boundary. Layout is the one decision Reframe cannot take back (requirements §1:
"every layout decision is permanent"), so it is worth isolating.

**The parent-leads rule** (R1, rewritten in `planning.md` Phase 28): a page is a
*subtree*, never a cut through the middle of a sibling list. Walk the TOC from the
top; a node whose whole subtree fits under the cap and sits in one source
directory becomes one page. A node whose subtree does not becomes a page of its
own body, and its children are then grouped into pages holding one or more *whole
consecutive* child-subtrees of that same parent. A child that still does not fit
recurses by the same rule. The cap is a cap and never a target (R1.2) -- there is
no minimum size and nothing is ever joined to reach one. Top-level items are hard
boundaries (R1.1), now structurally: each root's recursion emits its own pages.

**Why it was changed.** The predecessor walked bottom-up and, when a subtree
overflowed, packed its contents greedily in reading order without regard to whose
children they were. Measured on the source TOCs, that made **27 of ActiveSpaces'
46 pages and 67 of EMS' 124** span more than one TOC parent -- so a majority of
merged pages were arbitrary sibling runs with no single topic they were *about*,
and no page could carry a meaningful H1. Grouping only whole sibling subtrees
fixes that at a cost of roughly a fifth more pages (46 -> ~56, 124 -> ~160).
Refusing to group siblings *at all* was measured too and is far worse: 119 and
628 pages, median page 416 and 159 words.

Two places this deliberately departs from the proof-of-concept:

- **Emitted pages keep their place in reading order.** The POC appended pages to
  one shared list as the recursion unwound, so an overflowing child subtree's
  pages landed *before* the page holding its own parent's topic -- which reads
  earlier. Here `_subtree` returns pages already in reading order: the parent's
  own page first, then each child's, and an open run is flushed before a child
  recurses so nothing jumps in front of it.
- **R4.2 is enforced here, not checked afterwards.** A join is refused when the
  two sides come from different source directories, so "no page spans two source
  directories" holds by construction. On the reference corpus every top-level
  subtree is single-directory and this changes nothing; it is the sets that are
  not laid out that way which would otherwise produce a page whose relative asset
  paths are correct for only half its content.

The POC's `MIN_WORDS` is not reimplemented (R1.2), and its unused basename-keyed
`dest` map is not ported (requirements §10).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath

from docushift.reframe.toc import TocEntry
from docushift.transforms.headings import compact
from docushift.utils import naming
from docushift.utils.anchors import anchor_run
from docushift.utils.naming import is_unfiled


@dataclass(frozen=True)
class Topic:
    """One source topic, as layout needs to see it."""

    #: The title from the TOC row, not from the body's H1. R2.1 uses it only when
    #: a topic has no H1 of its own; the two disagree often enough to matter.
    title: str
    #: Relative to the converted tree's root, exactly as `toc.yml` wrote it.
    source: PurePosixPath
    words: int
    #: The title of this topic's TOC parent, or "" at the top level. Carried so
    #: that a page needing disambiguation can be qualified with the section it
    #: belongs to -- `installation-overview` rather than a bare `overview`, which
    #: names nothing and which twenty pages in one doc set are called (Phase 29).
    parent: str = ""
    #: `id()` of the TOC row this placement came from, or 0 for a topic that no
    #: row placed (`carry`). Since a topic listed
    #: under two guides is now packed once per guide, the source path alone no
    #: longer identifies which page a given row resolves to -- `toc.retarget`
    #: needs the row, and the row is what this remembers.
    node: int = 0
    #: The heading level this topic's own H1 takes on its merged page (R2.1).
    #: An absolute level rather than a depth, because `pages.render` wants the
    #: answer and not the arithmetic -- and because `carry` and `project`'s
    #: new-topic path can keep the default without knowing any tree at all.
    #: Defaulted so every construction site that predates parent-leads packing
    #: keeps emitting exactly what it emitted before.
    level: int = 2

    @property
    def directory(self) -> str:
        """The source directory R4.1 places a page in and R4.2 forbids mixing."""
        return str(self.source.parent)


@dataclass
class Page:
    """One merged page: its topics in reading order, and where it will be written."""

    guide: str
    topics: list[Topic]
    #: Assigned by `assign`, relative to the output root. R4.1: the first topic's
    #: directory, named after the first topic's file.
    path: PurePosixPath = PurePosixPath(".")
    #: Source path -> anchor, unique within this page (R2). Insertion-ordered, so
    #: iterating it walks the page's sections top to bottom.
    anchors: dict[PurePosixPath, str] = field(default_factory=dict)
    #: Source path -> {anchor on the topic's own converted page -> anchor here}.
    #: Every heading of every topic, not only the topic's own, because since
    #: Phase 30 a link names the exact heading it means and the merge renumbers
    #: repeated headings across the whole page (R9-01, R9-02). Filled by `assign`.
    sections: dict[PurePosixPath, dict[str, str]] = field(default_factory=dict)

    @property
    def words(self) -> int:
        return sum(topic.words for topic in self.topics)

    @property
    def directory(self) -> str:
        return self.topics[0].directory if self.topics else ""

    def heading(self, source: PurePosixPath, fragment: str) -> str | None:
        """Where a heading `fragment` of topic `source` landed on this page, or None.

        Lower-cased before the lookup because renderers fold anchor case, which is
        the rule `validation.references.anchors` checks by.
        """
        return self.sections.get(source, {}).get(fragment.lower())


@dataclass(frozen=True)
class _Unit:
    """A run of topics a parent may still absorb whole. Never crosses a directory."""

    topics: tuple[Topic, ...]
    #: 20e. A unit a writer has taken out of the merge: it is still a unit, so it
    #: keeps its place in reading order, but no join may reach it from either side.
    separate: bool = False

    @property
    def words(self) -> int:
        return sum(topic.words for topic in self.topics)

    @property
    def directory(self) -> str:
        return self.topics[0].directory


#: GFM's deepest heading. A page rooted high in a deep tree runs out of levels --
#: measured, 10 of ActiveSpaces' 324 topics and 4 of EMS' 1,441, and only when a
#: page spans the whole tree depth. Capping flattens two depths onto H6; it never
#: *skips* a level, so `design.md` invariant 14 still holds.
_DEEPEST = 6


def pack(roots: Sequence[TocEntry], words_of: Callable[[PurePosixPath], int], max_words: int,
         keep_separate: Sequence[str] = ()) -> list[Page]:
    """Every page one version becomes, in reading order.

    `roots` are the top-level TOC rows; each is packed independently, which is
    R1.1. `words_of` is asked for exactly one count per topic.

    `keep_separate` is 20e's writer override: source-path prefixes whose topics
    are not merged with anything, so that subtree keeps Stage 6's one-page-per
    topic layout. It only ever *refuses* a join, like the cap -- there is no
    entry that can make a page bigger, which is what keeps a hand-edited config
    from being able to invent a layout the packer would not otherwise produce.
    """
    pages: list[Page] = []
    prefixes = tuple(keep_separate)
    for root in roots:
        # **One `claimed` per guide, not one per version (Phase 29).** A topic
        # listed under two guides used to be packed once, with every later node
        # becoming a row pointing at the first guide's page. That was right while
        # a URL was a file path: one file, one address, two ways to navigate to
        # it. It stopped being right when the address became the TOC chain --
        # the second guide's node then resolves to a URL sitting under the
        # *first* guide, so a reader who navigated through B is told they are in
        # A. A copy per guide is the only shape the new URL model can express.
        #
        # Still deduped *within* a guide, where the second listing is a
        # cross-reference rather than a second placement. Measured corpus-wide:
        # 36 extra copies, 32 of them DataSynapse (out of scope), so 4 pages in
        # scope -- EMS 10.4.0 and 10.4.1.
        claimed: set[PurePosixPath] = set()
        # R1.1 is structural now: a root's recursion emits that root's pages and
        # returns, so nothing can span two roots however much room is left.
        pages.extend(_subtree(root, root.title, words_of, max_words, claimed, prefixes))
    return pages


#: One reference page as the pin carries it: where it was written, which source
#: topics shared it, and which guide it belongs to. Must be taken *after* `assign`,
#: since the name is what `assign` decided and half the point of pinning is that
#: the name does not move either. The guide is there because a topic listed under
#: two guides is on two reference pages, one per guide (Phase 47).
_Reference = tuple[PurePosixPath, tuple[PurePosixPath, ...], str]


def layout_of(pages: Sequence[Page]) -> list[_Reference]:
    """One version's topic->page mapping, in the form the pin carries to its siblings.

    Paths and source paths, and nothing else: titles and word counts are recomputed
    from the version being merged, because they are its own. The page *name* is not,
    and that is a deliberate addition to what R1.4 asks for. R4.1 names a page after
    its first topic, so a reference page whose first topic a version happens not to
    have would be renamed after the second one -- same topics, same grouping, and a
    different URL. Measured on ActiveSpaces: two pages per version, which is two
    broken cross-version links per version for no editorial reason at all.
    """
    return [(page.path, tuple(topic.source for topic in page.topics), page.guide) for page in pages]


def project(
    reference: Sequence[_Reference],
    roots: Sequence[TocEntry],
    words_of: Callable[[PurePosixPath], int],
    max_words: int,
    keep_separate: Sequence[str] = (),
) -> list[Page]:
    """R1.4: lay this version out against a reference version's mapping, not its own.

    `pack` is greedy and therefore chaotic across versions -- one topic gaining 50
    words pushes it past the cap, bumps it to the next page and cascades every
    boundary after it. Measured on ActiveSpaces, two adjacent versions of the same
    322-330 topics packed into 56 and 46 pages sharing only 41. So a doc set with
    more than one eligible version pins one of them and the rest are *projected*:
    a topic joins the page its own source path holds in the reference.

    Three rules, each the one the requirement leaves implicit:

    - **A topic the reference does not have gets its own page**, packed by the
      normal rule with its neighbours but never joined onto a projected page. R1.4
      covers only topics missing *from* a version; joining a new one would move a
      projected boundary and un-pin that version, which is the whole failure.
    - **Pages appear in this version's reading order**, first-surviving-topic first,
      because a version whose TOC genuinely changed should read in its own order.
    - **Sections within a page keep the reference's order**, so two versions of one
      page correspond section by section and not merely as a set.

    A projected page also keeps the reference's *name*, which `assign` then leaves
    alone -- see `layout_of` for why recomputing it would move URLs.

    `keep_separate` still wins: a topic a writer took out of the merge is its own
    page here too, exactly as in `pack`.
    """
    prefixes = tuple(keep_separate)
    # Keyed by guide as well as source (Phase 47): a topic under two guides sits on
    # one reference page per guide, and each guide's copy follows its own.
    # A source on exactly one reference page still matches by path alone, as it
    # did before, so a guide retitled between versions keeps its pinned pages.
    group_of: dict[tuple[str, PurePosixPath], int] = {}
    rank_of: dict[tuple[str, PurePosixPath], int] = {}
    pages_of: dict[PurePosixPath, list[int]] = {}
    for index, (_, group, guide) in enumerate(reference):
        for rank, source in enumerate(group):
            if (guide, source) not in group_of:
                group_of[guide, source] = index
                rank_of[guide, source] = rank
            pages_of.setdefault(source, []).append(index)
    only_of = {source: indexes[0] for source, indexes in pages_of.items() if len(set(indexes)) == 1}

    # This version's reading order, deduped the way `pack` dedupes: per guide, so
    # the first node in a guide to reach a path owns it there and later nodes in
    # that guide become TOC rows pointing at it. `node` and the depth are kept per
    # row, because with one copy per guide the path no longer names one placement.
    order: list[tuple[PurePosixPath, str, str, int, bool]] = []
    depth_of: dict[int, int] = {}
    earlier: set[PurePosixPath] = set()
    for root in roots:
        claimed: set[PurePosixPath] = set()
        for depth, entry in _walk_depth(root):
            if entry.path is None or entry.path in claimed:
                continue
            claimed.add(entry.path)
            depth_of[id(entry)] = depth
            order.append((entry.path, entry.title, root.title, id(entry), entry.path in earlier))
        earlier |= claimed

    def projected(path: PurePosixPath, guide: str, copy: bool) -> int | None:
        # A later guide's copy matches its own guide only. Through the path-only
        # match it would land on the first guide's reference page, which is one
        # guide's topic on another guide's page (IBM MQ 8.7.0, Phase 47).
        index = group_of.get((guide, path), None if copy else only_of.get(path))
        return None if index is None or separated(path, prefixes) else index

    def rank(index: int, source: PurePosixPath) -> int:
        _, group, guide = reference[index]
        return rank_of.get((guide, source), group.index(source))

    members: dict[int, list[Topic]] = {}
    guide_of: dict[int, str] = {}
    for path, title, guide, node, copy in order:
        index = projected(path, guide, copy)
        if index is None:
            continue
        group = members.setdefault(index, [])
        # Two guides reaching one reference page through the path-only match: the
        # page holds the topic once, and the second guide's row points at it.
        if any(topic.source == path for topic in group):
            continue
        group.append(Topic(title, path, words_of(path), node=node))
        guide_of.setdefault(index, guide)

    pages: list[Page] = []
    emitted: set[int] = set()
    pending: list[_Unit] = []
    pending_guide = ""

    def flush() -> None:
        nonlocal pending, pending_guide
        if pending:
            pages.extend(_close_run(pending, pending_guide, max_words))
            pending = []
            pending_guide = ""

    for path, title, guide, node, copy in order:
        index = projected(path, guide, copy)
        if index is None:
            # R1.1: a run of new topics never spans two guides either.
            if pending and pending_guide != guide:
                flush()
            if not pending:
                pending_guide = guide
            # `level=1`: a topic the reference does not have is packed on its own
            # merits, so the first on its page supplies that page's H1 and
            # `_close_run` drops the rest below it. Left at the `Topic` default
            # these published 43 pages opening at `##` with nothing above them.
            pending.append(_Unit((Topic(title, path, words_of(path), node=node, level=1),),
                                 separate=separated(path, prefixes)))
            continue
        if index in emitted:
            continue
        emitted.add(index)
        # A run of new topics never spans a projected boundary, which is what keeps
        # the projection intact rather than merely mostly intact.
        flush()
        topics = sorted(members[index], key=lambda topic: rank(index, topic.source))
        pages.append(Page(guide_of[index], _relevel(topics, depth_of), path=reference[index][0]))
    flush()
    return pages


def _relevel(topics: Sequence[Topic], depth_of: dict[int, int]) -> list[Topic]:
    """Heading levels for a projected page, read off *this* version's own TOC.

    The pin carries which topics share a page and what that page is called; it
    does not carry their depths, and it must not -- a version whose tree is a
    level shallower here should read as one. So levels are recomputed from the
    depths in hand, relative to the shallowest topic on the page, and everything
    from the second topic at that shallowest depth onward drops one, which is the
    rule `_close_run` applies when it groups sibling subtrees.

    One consequence to accept: a page whose leading topic this version does not
    have re-roots on the next one, so its internal levels shift. The page *name*
    does not move, which is what R1.4 protects.
    """
    if not topics:
        return []
    depths = [depth_of.get(topic.node, 1) for topic in topics]
    base = min(depths)
    # `compact` is Phase 27's rule, reused rather than re-derived: the page holds
    # only the topics this version has, so the TOC rows between two of them may
    # be absent and their raw depths gap. Compacting by nesting depth closes that
    # the same way it closes an authored `h3 -> h6`. Rebased to 1 *before* it,
    # because `compact` caps at H6: on raw depths a page seven rows down came out
    # at level 0, a heading with no `#` (Phase 47, Service Grid 3.4.3).
    levels = compact([depth - base + 1 for depth in depths])
    seen_root = False
    demote = False
    out: list[Topic] = []
    for topic, depth, level in zip(topics, depths, levels, strict=True):
        if depth == base:
            demote = seen_root
            seen_root = True
        out.append(replace(topic, level=min(level + (1 if demote else 0), _DEEPEST)))
    return out


def _walk_depth(entry: TocEntry, depth: int = 1):
    """`TocEntry.walk`, but saying how deep each node is. Depth is a property of
    the traversal rather than of the node, so it is not a field on `TocEntry`."""
    yield depth, entry
    for child in entry.children:
        yield from _walk_depth(child, depth + 1)


def separated(source: PurePosixPath, prefixes: Sequence[str]) -> bool:
    """Whether one source path is at or under a `keep_separate` entry (20e).

    Compared on path *parts* rather than as a string prefix, so `users-guide/mon`
    does not match `users-guide/monitoring.md`. An entry naming a file matches
    that file; an entry naming a directory matches everything beneath it.
    """
    parts = source.parts
    for prefix in prefixes:
        head = PurePosixPath(prefix).parts
        if head and parts[:len(head)] == head:
            return True
    return False


#: The `guide` stamped on a topic the navigation never listed. Visible in the
#: page's own frontmatter, because a writer opening it should see immediately that
#: it is not reachable from the TOC.
UNNAVIGATED = "Not in navigation"


def carry(
    sources: Sequence[PurePosixPath],
    title_of: Callable[[PurePosixPath], str],
    words_of: Callable[[PurePosixPath], int],
) -> list[Page]:
    """One single-topic page per `.md` file the TOC never mentions.

    These are carried through rather than merged or dropped, and the reasoning is
    worth stating because "drop it" looks tidier. Stage 7 publishes the whole
    `output/` tree, so a topic missing from `toc.yml` is *already published* and
    already linkable -- Runtime Agent 5.13.0 has two, its second guide's legal and
    support pages (since 2026-10-02; before that, one was `Third_Party_Libraries_`,
    the target of a live link). Dropping them would make Reframe delete published content as a side
    effect of a navigation gap, which is not a trade a merge stage gets to make.

    They are pages, not raw copies, so their own links are rewritten onto the new
    layout by the same pass as everything else. What they are not is TOC nodes:
    they were never in the navigation and R3 only promises to preserve what was.
    `audit` is told to exempt them from the reachability check for that reason.
    """
    # `level=1`: a carried page is one topic alone, so that topic *is* the page and
    # takes its H1, exactly as a one-subtree page does. Leaving it at the `Topic`
    # default published 35 ActiveSpaces pages and 8 EMS ones opening at `##` with
    # no heading above them, which is the defect Phase 28 set out to remove.
    return [Page(UNNAVIGATED, [Topic(title_of(source), source, words_of(source), level=1)])
            for source in sources]


def _subtree(
    node: TocEntry,
    guide: str,
    words_of: Callable[[PurePosixPath], int],
    max_words: int,
    claimed: set[PurePosixPath],
    prefixes: Sequence[str] = (),
    parent: str = "",
) -> list[Page]:
    """Every page this node's subtree becomes, in reading order.

    Two rules, in order. **The whole subtree is one page** when it is allowed to
    be. Otherwise **the node stands alone** and its children are grouped into
    pages of whole sibling subtrees -- which is the guarantee the whole rewrite
    exists for: a page's topics always share one TOC parent, so the page's first
    topic is the thing the page is about.
    """
    whole = _collect(node, words_of, max_words, claimed, prefixes, parent)
    if whole is not None:
        _commit(whole, claimed)
        return [Page(guide, list(whole))] if whole else []

    pages: list[Page] = []
    if node.path is not None and node.path not in claimed:
        # The node's own body, alone. It is often a short landing paragraph above
        # a list of children -- 10 of ActiveSpaces' ~56 pages come out under 200
        # words this way -- and that is the honest shape: the TOC has a node here,
        # so the merged tree needs a page here for it to point at.
        claimed.add(node.path)
        pages.append(Page(guide, [Topic(node.title, node.path, words_of(node.path),
                                        parent=parent, node=id(node), level=1)]))

    run: list[_Unit] = []

    def flush() -> None:
        pages.extend(_close_run(run, guide, max_words))
        run.clear()

    for child in node.children:
        unit = _collect(child, words_of, max_words, claimed, prefixes, node.title)
        if unit is None:
            # This child overflows and will emit its own pages. Flush first, or
            # a later sibling that still fits would jump in front of them.
            flush()
            pages.extend(_subtree(child, guide, words_of, max_words, claimed, prefixes,
                                  node.title))
            continue
        if not unit:
            continue
        _commit(unit, claimed)
        run.append(_Unit(unit, separate=any(separated(t.source, prefixes) for t in unit)))
    flush()
    return pages


def _collect(
    node: TocEntry,
    words_of: Callable[[PurePosixPath], int],
    max_words: int,
    claimed: set[PurePosixPath],
    prefixes: Sequence[str],
    parent: str = "",
) -> tuple[Topic, ...] | None:
    """This subtree as one page's worth of topics, or None if it may not be one.

    Levels are assigned as though the subtree were alone on a page: its root at
    H1 and each topic one below its nearest *emitted* ancestor, capped at H6
    (requirements §7). When the caller puts two sibling subtrees on one page it
    bumps the later ones by one, so the second never collides with the first's H1.

    **The nearest emitted ancestor, not the raw TOC depth.** A node contributes no
    topic when it is a bare container row or when an earlier guide already claimed
    its path, and counting those nodes anyway leaves a hole: EMS' `Appendix B`
    page came out `#` then `####` because the two rows between them were claimed
    elsewhere. That is the same defect Phase 27 spent itself removing from the
    converter, reintroduced one stage later, so the rule here is the same one --
    depth is measured in what is actually emitted.

    **Nothing is claimed here.** The walk reads `claimed` to skip topics an
    earlier TOC node already owns, and accumulates its own `seen` set for a path
    a subtree lists twice; the caller `_commit`s only once it has accepted the
    result. A rejected probe that had mutated `claimed` would silently drop every
    topic it touched -- the one way this recursion can lose content, and the
    reason the probe and the commit are two functions rather than one walk.
    """
    topics: list[Topic] = []
    seen: set[PurePosixPath] = set()
    total = 0

    def walk(entry: TocEntry, level: int, parent: str) -> bool:
        nonlocal total
        emitted = False
        if entry.path is not None and entry.path not in claimed and entry.path not in seen:
            if separated(entry.path, prefixes):
                return False  # 20e: a writer took this out of the merge.
            seen.add(entry.path)
            words = words_of(entry.path)
            total += words
            if total > max_words:
                return False
            topics.append(Topic(entry.title, entry.path, words, parent=parent,
                                node=id(entry), level=min(level, _DEEPEST)))
            emitted = True
        below = level + 1 if emitted else level
        # A row that contributed no topic is not a parent anybody can be named
        # after, so its own children inherit the parent it had.
        under = entry.title if emitted else parent
        return all(walk(child, below, under) for child in entry.children)

    if not walk(node, 1, parent):
        return None
    # R4.2 is enforced here rather than checked afterwards. A subtree that fits by
    # words but straddles two source directories must still fall to the second
    # rule, or `audit._directories` discards the whole tree.
    if not _one_directory(topics):
        return None
    return tuple(topics)


def _commit(topics: Sequence[Topic], claimed: set[PurePosixPath]) -> None:
    """Takes ownership of an accepted `_collect` result."""
    claimed.update(topic.source for topic in topics)


def _close_run(units: Sequence[_Unit], guide: str, max_words: int) -> list[Page]:
    """Groups whole sibling subtrees, in TOC order, into pages.

    Every unit here is one child's entire subtree and they all share one parent,
    so a page this closes can only ever hold whole siblings. A page is closed when
    the next subtree would take it over the cap (R1.2 -- the cap only ever refuses
    a join) or would bring in a second source directory (R4.2). A subtree over the
    cap on its own never reaches here; R1.3 forbids splitting a topic body, so an
    oversized *topic* still becomes an oversized page through the first rule.
    """
    pages: list[Page] = []
    current: list[Topic] = []
    roots = 0

    def close() -> None:
        nonlocal current, roots
        if current:
            pages.append(Page(guide, current))
            current = []
            roots = 0

    for unit in units:
        if current and (
            unit.separate
            or sum(topic.words for topic in current) + unit.words > max_words
            or current[0].directory != unit.directory
        ):
            close()
        # The first subtree on a page keeps its own levels and supplies the page's
        # H1. Every later sibling drops one, so it reads as a section *after* the
        # first rather than as a second H1 -- and its own children drop with it,
        # which is what stops a parent and its child landing on the same level.
        roots += 1
        current.extend(unit.topics if roots == 1 else _demote(unit.topics))
        if unit.separate:
            close()
    close()
    return pages


def _demote(topics: Sequence[Topic]) -> list[Topic]:
    return [replace(topic, level=min(topic.level + 1, _DEEPEST)) for topic in topics]


def _one_directory(topics: Sequence[Topic]) -> bool:
    return len({topic.directory for topic in topics}) <= 1


def assign(
    pages: Sequence[Page],
    headings_of: Callable[[Topic], list[str]] | None = None,
    placements: dict[int, tuple[Page, str]] | None = None,
) -> dict[PurePosixPath, tuple[Page, str]]:
    """Names every page and anchors every topic. Returns source -> (page, anchor).

    R4.1 places a page beside its first topic and names it after that topic's
    file. Filenames dedup against the full output path -- two directories may each
    hold an `overview.md` -- with the **looping** `-2`, `-3`, ... suffix R2 insists
    on: `tibemslookupcontext2.md` slugs to `tibemslookupcontext-2` by itself, so a
    single attempt hands two different names the same slug (requirements §7).

    **Anchors are predicted, not chosen (Phase 29).** The platform generates them
    from heading text and ignores anything this tool writes, so `headings_of`
    supplies every heading a topic will render, in document order, and
    `utils/anchors.anchor_run` numbers the page's whole run the way the platform
    numbers it. A topic's own anchor is the one its *first H1* gets -- or, where
    the body has no H1 and `pages.shift_headings` synthesizes one from the TOC
    title, the anchor that synthesized heading gets.

    **The run has to cover sub-headings too**, which is why the callable returns a
    list rather than one string. A topic's `## Location` competes for `#location`
    with another topic's `# Location` on the same page, and numbering only the
    topic headings would predict `location` where the platform produces
    `location-1`. 400 of 1,700 merged pages repeat a heading.

    `headings_of` is optional so the packer stays testable against a dict of
    sizes, as `words_of` already keeps it: with no reader, a topic is assumed to
    render one heading, its title.

    A page that already carries a path was named by `project` off the pinned
    reference and is left exactly as it is (R1.4). Those names are reserved up
    front rather than as they are reached, so a topic new to this version cannot
    take a name a projected page further down the tree is going to want.
    """
    located: dict[PurePosixPath, tuple[Page, str]] = {}
    by_node: dict[int, tuple[Page, str]] = {} if placements is None else placements
    # Keyed by the TOC parent, because that is the folder `relocate` will put the
    # page in and therefore the only scope a name can actually clash in.
    taken_stems: dict[str, set[str]] = {}
    for page in pages:
        if page.path != PurePosixPath("."):
            taken_stems.setdefault("", set()).add(page.path.stem.lower())
    for page in pages:
        first = page.topics[0]
        if page.path == PurePosixPath("."):
            if page.guide == UNNAVIGATED:
                # No TOC row, so no TOC scope either (R9-03). It used to be named
                # in the *root* scope -- `parent` is "" -- and so took a `-2` from
                # any top-level page with its title, though it was written into
                # another folder entirely: TRA Runtime Agent 5.13.0's second
                # guide's legal and support pages both did. Provisional and
                # unsuffixed, like a navigated page: `relocate` decides its folder
                # and settles uniqueness against the pages actually in it.
                page.path = first.source.parent / f"{_name_for(first, set())}.md"
                if is_unfiled(first.source):
                    # Phase 43: an orphan keeps its converted path, so the two
                    # trees agree and nothing about it changes but its links.
                    page.path = first.source
            else:
                siblings = taken_stems.setdefault(naming.slugify(first.parent), set())
                stem = _name_for(first, siblings)
                siblings.add(stem.lower())
                # Provisional, beside the source. `relocate` moves it into the
                # TOC's folder chain straight after this. Deliberately *not*
                # deduped here: two pages under different parents may collide
                # transiently, and suffixing now would carry a `-2` the final
                # folders make unnecessary into the published URL.
                page.path = first.source.parent / f"{stem}.md"

        titles: list[str] = []
        owned: list[int] = []
        for topic in page.topics:
            found = list(headings_of(topic)) if headings_of else []
            if not found:
                # No H1 in the body: `shift_headings` prepends the TOC title.
                found = [topic.title]
            owned.append(len(titles))
            titles.extend(found)

        run = anchor_run(titles)
        ends = [*owned[1:], len(titles)]
        for topic, index, end in zip(page.topics, owned, ends, strict=True):
            anchor = run[index]
            page.anchors[topic.source] = anchor
            # R9-01/R9-02: the topic's own run is what its converted page numbered,
            # and so what every incoming `#fragment` names. Position i of that run
            # is position `index + i` of the page's. A topic with no H1 has its
            # synthesized title in slot 0 here and not on its source page, which
            # shifts the source numbering only when a real heading repeats that
            # title -- a shape no measured topic has (`_Source.headings`).
            own = anchor_run(titles[index:end])
            page.sections[topic.source] = {
                mine: theirs for mine, theirs in zip(own, run[index:end], strict=True) if mine
            }
            # First placement wins the source-keyed entry: it is what
            # `redirects` and `csh` resolve through, and those want one
            # canonical destination per topic rather than a guide-specific one.
            located.setdefault(topic.source, (page, anchor))
            if topic.node:
                by_node[topic.node] = (page, anchor)
    return located


def relocate(pages: Sequence[Page], roots: Sequence[TocEntry]) -> int:
    """Moves every navigated page into a folder chain mirroring the TOC.

    **Because the folder chain is the URL.** AEM builds an address from the TOC
    chain of node filenames, so laying the directories out the same way makes the
    repo path and the published address the same string -- and the path-based URL
    the rest of the tool already computes becomes right by construction rather
    than by a second, parallel calculation that can drift from it.

    A page that has child pages becomes a folder named after its own file, with
    those children inside it; its own page sits beside the folder. So the
    Installation section is `installation.md` next to `installation/`, and its
    children are `installation/requirements.md` -- `/installation` and
    `/installation/requirements` respectively, which is what a reader sees.

    **A page `carry` produced goes in with its guide (R9-03).** The TOC never
    mentioned it, so there is no chain of its own; it used to be left in its raw
    source folder, which published `trahelp/_templates/…` -- a folder name that
    is MadCap's plumbing, not a place a reader navigated to. It now sits among
    the children of the shallowest navigated page from its own source directory,
    which is in practice that guide's landing page: TRA Runtime Agent 5.13.0's
    second legal page lands at `tibco-runtime-agent/legal-and-third-party-
    notices.md`, the address it held while the TOC still listed it and the one
    the user pinned back on 2026-10-04. It stays out of `toc.yml` and keeps its
    `Not in navigation` guide; only the folder is borrowed. A carried page whose
    directory no navigated page shares stays in that directory, as before.

    Returns how many pages moved. Must run **before** `pages.render`, because the
    renderer resolves every relative link and asset path against `page.path`.
    """
    # By row first: a topic under two guides has one copy per guide, and keyed by
    # source alone the last copy owned both rows, so the second guide's copy was
    # filed in the first guide's folder (Phase 47).
    owner: dict[PurePosixPath, Page] = {}
    owner_of_row: dict[int, Page] = {}
    for page in pages:
        for topic in page.topics:
            owner.setdefault(topic.source, page)
            if topic.node:
                owner_of_row[topic.node] = page

    placed: dict[int, PurePosixPath] = {}

    def walk(entry: TocEntry, folder: PurePosixPath) -> None:
        page = owner_of_row.get(id(entry)) or (owner.get(entry.path) if entry.path is not None else None)
        # Only the page's *leading* topic puts it in the tree: an absorbed topic
        # is a section, and its TOC row must not move the page it was merged into.
        below = folder
        if page is not None and page.topics[0].source == entry.path:
            if id(page) not in placed:
                placed[id(page)] = folder / page.path.name
            below = folder / page.path.stem
        for child in entry.children:
            walk(child, below)

    for root in roots:
        walk(root, PurePosixPath())

    # R9-03. A carried page borrows the folder of the shallowest navigated page
    # that leads from its source directory; ties go to reading order, because
    # `pages` is in it and `sorted` is stable. Carried pages come last in
    # `pages`, so in the uniqueness pass below a navigated page keeps its name
    # and a carried one takes the `-2` -- now only for a clash in that folder.
    homes: dict[str, PurePosixPath] = {}
    navigated = [page for page in pages if page.guide != UNNAVIGATED and page.topics]
    for page in sorted(navigated, key=lambda page: len(placed.get(id(page), page.path).parts)):
        where = placed.get(id(page), page.path)
        homes.setdefault(page.directory, where.parent / where.stem)
    for page in pages:
        if page.guide == UNNAVIGATED and page.directory in homes:
            placed[id(page)] = homes[page.directory] / page.path.name

    # Final uniqueness is settled here, not in `assign`, because here is where a
    # page's folder is actually known -- and it covers **every** page, not only
    # the ones this function moves. `assign` deliberately leaves a navigated
    # page's provisional path undeduped, so a page the walk above does not reach
    # keeps a name that may already be taken. Runtime Agent 5.13.0 found this the
    # only way it can be found: 118 pages merged, 116 files on disk, two writes
    # landing on one path and the audit catching the arithmetic.
    taken: set[PurePosixPath] = set()
    moved = 0
    for page in pages:
        target = placed.get(id(page), page.path)
        if target in taken:
            target = _unique(target.parent, target.stem, ".md", taken)
        taken.add(target)
        if target != page.path:
            page.path = target
            moved += 1
    return moved


def override(
    pages: Sequence[Page], approved: dict[PurePosixPath, PurePosixPath]
) -> tuple[set[PurePosixPath], dict[PurePosixPath, PurePosixPath]]:
    """Puts back the names a previous run recorded and a human kept.

    Runs after `relocate`, so an approved path wins over both the computed name
    and the computed folder: a writer who moved a page in `rename-map.csv` moved
    it on purpose. Returns `(applied, refused)`: the leading-topic sources whose
    page took a path other than the computed one, and source -> wanted path for
    every pin refused.

    Keyed on the leading topic's *source*, which is the one identity that
    survives a rename -- keying on the old path would stop matching the moment
    the override took effect, which is the first run.

    An approved path that another page ends up holding is refused rather than
    applied: two pages at one path is a page silently lost, and the record is
    not worth that. The caller reports each one (R9-05) and the page keeps its
    computed name. **Judged against the final set of paths, not in page order**
    (R9-05): a pin onto a path a later page is itself pinned away from is not a
    clash, and refusing it was an accident of which page came first. A page
    staying on its computed path beats any pin onto that path; between two pins
    onto one path, reading order decides. A refusal sends that page back to its
    computed path, which may in turn refuse another pin, hence the loop.
    """
    moving: dict[int, PurePosixPath] = {}
    for page in pages:
        if not page.topics:  # pragma: no cover - a page always leads with a topic
            continue
        wanted = approved.get(page.topics[0].source)
        if wanted is not None and wanted != page.path:
            moving[id(page)] = wanted

    refused: dict[PurePosixPath, PurePosixPath] = {}
    while True:
        # Keyed case-insensitively (X2-12): `User-Guide.md` and `user-guide.md`
        # are one file on NTFS, so the second write replaced the first and the
        # run blamed "a page write landed outside the layout".
        holders: dict[str, list[Page]] = {}
        for page in pages:
            holders.setdefault(str(moving.get(id(page), page.path)).casefold(), []).append(page)
        losers: list[Page] = []
        for held in holders.values():
            if len(held) < 2:
                continue
            staying = [page for page in held if id(page) not in moving]
            keep = staying[0] if staying else held[0]
            losers.extend(page for page in held if page is not keep and id(page) in moving)
        if not losers:
            break
        for page in losers:
            refused[page.topics[0].source] = moving.pop(id(page))

    applied: set[PurePosixPath] = set()
    for page in pages:
        if id(page) in moving:
            page.path = moving[id(page)]
            applied.add(page.topics[0].source)
    return applied, refused


def asset_destination(source: PurePosixPath) -> PurePosixPath:
    """Where an asset lands in the merged tree: lower-cased directories, same file.

    **A folder, not a file, is renamed here**, and only in case. §6.4's rule that
    an asset keeps its name byte-for-byte is intact -- `AS_Workflow_V-two.png`
    stays exactly that -- because the thing that moves is the directory above it.

    It has to move because `relocate` puts pages in lower-cased slug folders
    while assets kept their source casing, and the two then collide. ActiveSpaces
    has a source directory `Concepts/` and a page folder `concepts/`: on Windows
    the copy silently lands in the folder that already exists, so the tree looks
    right and every image link in it reads `../Concepts/…` against a directory
    spelled `concepts`. On Linux those are two directories and the image 404s --
    a defect that could not be seen on the machine that produced it.

    One function, called by the copier and by `pages.rewrite_links`, because the
    whole failure was the two disagreeing.
    """
    return PurePosixPath(*(part.lower() for part in source.parent.parts), source.name)


def shortened(pages: Sequence[Page]) -> set[PurePosixPath]:
    """The pages whose name lost words to the 50-character cut.

    Flagged for review rather than quietly accepted: the cut takes the *tail* of
    a title, which is where the distinguishing words usually are. Measured over
    1,505 merged pages, 90 of them -- `deployment-scenario-running-activespaces`
    from "Deployment Scenario for Running ActiveSpaces Processes as Windows
    Services". Nothing here tries to do better; it says which ones a human or a
    model should look at -- in `rename-map.csv` (`reframe/renames.py`) and, since
    R1-03, as a queueing flag in `review-queue.csv` (`reframe/review.py`).

    The driver drops from this set every page `override` actually moved (R9-12):
    a name somebody wrote into `rename-map.csv` *is* the answer to the flag, and
    judging it against the title again re-queued it on every run.
    """
    marked: set[PurePosixPath] = set()
    for page in pages:
        if not page.topics:  # pragma: no cover
            continue
        first = page.topics[0]
        full = naming.normalize(first.title)
        if full and not page.path.stem.startswith(full) and not page.path.stem.endswith(full):
            marked.add(first.source)
    return marked


def _name_for(first: Topic, taken: set[str]) -> str:
    """The filename stem for a page led by `first`. Phase 29's rule.

    **From the title, because the filename is the URL.** AEM builds an address
    from the TOC chain of filenames, so a page named after its *source* stem
    publishes MadCap's 20-character truncation to readers: 428 of 1,700 merged
    pages disagreed with their own title, one of them publishing a page titled
    "Upgrading to Release 5.13.0" as `upgrading-to-release-5-12-4`.

    **Uniqueness is scoped to the TOC parent, not to the doc set.** `relocate`
    puts a page in a folder named after its parent, so two pages in different
    sections cannot collide on disk *or* in a URL -- `/installation/requirements`
    and `/upgrading/requirements` are already distinct addresses that read
    correctly. The spec asked for doc-set-wide uniqueness and a parent prefix on
    every generic name, which was the right rule when folders were flat; with the
    chain restored it buys nothing and costs `/installation/installation-
    requirements`. Same scope as the folder, which is the scope a clash can
    actually happen in.

    Where two pages under *one* parent do share a title there is no prose left to
    tell them apart, so the numeric suffix is what remains.
    """
    stem = naming.slugify(first.title, first.source.stem)
    if not stem:
        stem = naming.slugify("", first.source.stem) or "page"
    if stem.lower() in taken:
        # Room for the suffix first, or `-2` would push the name past the cut and
        # the platform would truncate it back onto the name it collided with.
        stem = _suffixed(naming.shorten(stem, naming.MAX_SEGMENT - 2), taken)
    return stem


def _unique(directory: PurePosixPath, stem: str, suffix: str, taken: set[PurePosixPath]) -> PurePosixPath:
    candidate = directory / f"{stem}{suffix}"
    index = 1
    while candidate in taken:
        index += 1
        candidate = directory / f"{stem}-{index}{suffix}"
    return candidate


def _suffixed(stem: str, taken: set[str]) -> str:
    candidate, index = stem, 1
    while candidate in taken:
        index += 1
        candidate = f"{stem}-{index}"
    return candidate
