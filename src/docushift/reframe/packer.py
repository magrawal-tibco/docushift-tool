"""R1 and R2: which topics become one page, and what each one is called.

The packer decides layout and nothing else. It never opens a topic body -- word
counts arrive through a callable -- so the whole of R1 is testable against a dict
of sizes, and the body rewriting in `pages.py` cannot accidentally influence a
boundary. Layout is the one decision Reframe cannot take back (requirements §1:
"every layout decision is permanent"), so it is worth isolating.

**The bottom-up rule** (R1): walk the TOC depth-first in reading order; a subtree
whose words fit under the cap comes back to its parent as one absorbable unit, and
a subtree that does not is packed greedily into pages on the spot. The cap is a
cap and never a target (R1.2) -- there is no minimum size and nothing is ever
joined to reach one. Top-level items are hard boundaries (R1.1).

Two places this deliberately departs from the proof-of-concept:

- **Emitted pages keep their place in reading order.** The POC appended pages to
  one shared list as the recursion unwound, so an overflowing child subtree's
  pages landed *before* the page holding its own parent's topic -- which reads
  earlier. Here `_subtree` returns a single ordered run of already-closed `Page`s
  and still-absorbable `_Unit`s, and the packer splices around the pages rather
  than past them. Reading order is then an invariant of the return type.
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

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from docushift.reframe.toc import TocEntry
from docushift.utils.slug import slugify


@dataclass(frozen=True)
class Topic:
    """One source topic, as layout needs to see it."""

    #: The title from the TOC row, not from the body's H1. R2.1 uses it only when
    #: a topic has no H1 of its own; the two disagree often enough to matter.
    title: str
    #: Relative to the converted tree's root, exactly as `toc.yml` wrote it.
    source: PurePosixPath
    words: int

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

    @property
    def words(self) -> int:
        return sum(topic.words for topic in self.topics)

    @property
    def directory(self) -> str:
        return self.topics[0].directory if self.topics else ""


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


#: What `_subtree` returns: closed pages and open units, interleaved in reading order.
_Item = Page | _Unit


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
    # A topic listed under two guides is shared, not duplicated: the first node to
    # reach it owns the content and every later node becomes a TOC row pointing at
    # the same `page.md#anchor` (`toc.retarget` looks the path up, so repeats fall
    # out for free). Measured: EMS has a perfect TOC-to-disk bijection and never
    # exercises this, but GridServer 7.2.0 lists `Typographical_Conventions.md`
    # three times, and packing it three times copies its body onto three pages.
    claimed: set[PurePosixPath] = set()
    prefixes = tuple(keep_separate)
    for root in roots:
        # `_close_run` is what turns the last open units into pages, so a guide
        # that fits entirely under the cap becomes exactly one page here.
        items = _subtree(root, root.title, words_of, max_words, claimed, prefixes)
        pages.extend(_close_run(items, root.title, max_words))
    return pages


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
    already linkable -- Runtime Agent 5.13.0 has two, one of them the target of a
    live link. Dropping them would make Reframe delete published content as a side
    effect of a navigation gap, which is not a trade a merge stage gets to make.

    They are pages, not raw copies, so their own links are rewritten onto the new
    layout by the same pass as everything else. What they are not is TOC nodes:
    they were never in the navigation and R3 only promises to preserve what was.
    `audit` is told to exempt them from the reachability check for that reason.
    """
    return [Page(UNNAVIGATED, [Topic(title_of(source), source, words_of(source))]) for source in sources]


def _subtree(
    node: TocEntry,
    guide: str,
    words_of: Callable[[PurePosixPath], int],
    max_words: int,
    claimed: set[PurePosixPath],
    prefixes: Sequence[str] = (),
) -> list[_Item]:
    """This node and its descendants, as an ordered run of pages and units."""
    items: list[_Item] = []
    if node.path is not None and node.path not in claimed:
        claimed.add(node.path)
        items.append(_Unit((Topic(node.title, node.path, words_of(node.path)),),
                           separate=separated(node.path, prefixes)))
    for child in node.children:
        items.extend(_subtree(child, guide, words_of, max_words, claimed, prefixes))

    units = [item for item in items if isinstance(item, _Unit)]
    # Collapsible only if nothing below has already been closed into a page: once
    # a boundary exists inside this subtree, the subtree is not one unit any more.
    # A separated unit is the same kind of boundary, arrived at by a writer's
    # decision instead of by the cap.
    if len(units) == len(items) and units and not any(unit.separate for unit in units):
        topics = tuple(topic for unit in units for topic in unit.topics)
        if sum(unit.words for unit in units) <= max_words and _one_directory(topics):
            return [_Unit(topics)]
    return list(_close_run(items, guide, max_words))


def _close_run(items: Iterable[_Item], guide: str, max_words: int) -> list[Page]:
    """Greedily packs the units of one run, in TOC order, around its closed pages.

    A page is closed when the next unit would take it over the cap (R1.2 -- the cap
    only ever refuses a join) or would bring in a second source directory (R4.2).
    A unit that is over the cap on its own is still placed whole: R1.3 forbids
    splitting a topic body, so an oversized topic becomes an oversized page.
    """
    pages: list[Page] = []
    current: list[Topic] = []

    def close() -> None:
        nonlocal current
        if current:
            pages.append(Page(guide, current))
            current = []

    for item in items:
        if isinstance(item, Page):
            # Already closed further down the tree. Keep it where reading order
            # put it rather than letting later units jump in front of it.
            close()
            pages.append(item)
            continue
        if current and (
            item.separate
            or sum(topic.words for topic in current) + item.words > max_words
            or current[0].directory != item.directory
        ):
            close()
        current.extend(item.topics)
        # Closed after it as well, which is what makes the verb "granular" rather
        # than "split here": the next unit starts a page instead of joining this
        # one from behind.
        if item.separate:
            close()
    close()
    return pages


def _one_directory(topics: Sequence[Topic]) -> bool:
    return len({topic.directory for topic in topics}) <= 1


def assign(pages: Sequence[Page]) -> dict[PurePosixPath, tuple[Page, str]]:
    """Names every page and anchors every topic. Returns source -> (page, anchor).

    R4.1 places a page beside its first topic and names it after that topic's
    file; R2 slugs an anchor from each topic's own filename. Both dedup with the
    **looping** `-2`, `-3`, ... suffix R2 insists on: `tibemslookupcontext2.md`
    slugs to `tibemslookupcontext-2` all by itself, so a single attempt hands two
    different topics the same anchor (requirements §7). Measured over the whole
    corpus: 16 slugs collide, and 11 stems already end in `-N`.

    Filenames dedup against the full output path -- two directories may each hold
    an `overview.md` -- while anchors dedup per page, which is the scope R2 asks
    for and the scope a fragment is resolved in.
    """
    located: dict[PurePosixPath, tuple[Page, str]] = {}
    taken_files: set[PurePosixPath] = set()
    for page in pages:
        first = page.topics[0]
        stem = slugify(first.source.stem)
        directory = first.source.parent
        page.path = _unique(directory, stem, ".md", taken_files)
        taken_files.add(page.path)

        taken_anchors: set[str] = set()
        for topic in page.topics:
            anchor = _suffixed(slugify(topic.source.stem), taken_anchors)
            taken_anchors.add(anchor)
            page.anchors[topic.source] = anchor
            located[topic.source] = (page, anchor)
    return located


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
