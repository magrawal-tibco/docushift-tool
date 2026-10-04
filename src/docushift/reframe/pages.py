"""R2.1, R4 and R7: turning a `Page`'s topics into one page's bytes.

Everything here is **fence-aware**, which is the one thing requirements §7 singles
out as a latent corruption in the proof-of-concept: its heading and link regexes
ran over the raw body, so a `# comment` line in a shell sample became a heading --
and if it preceded the topic's real H1, it became the *anchored* heading and took
the topic's identity with it. The reference corpus has zero heading-like lines
inside fences, so the POC never fired it; a corpus with them would be corrupted
silently. Fence-awareness costs nothing and is not optional.

The mechanism is `validation.references.mask_code`: it overwrites frontmatter,
fenced blocks and code spans with spaces **without changing any offset**, so a
match found in the mask is a span in the original. Every scan here matches against
a mask and edits the original by offset. That is also why the patterns below are
declared here rather than imported: the sibling module's are tuned for *counting*
references and expose no destination span to rewrite.

**A section's anchor is not emitted at all any more (Phase 29).** It used to be an
`<a id="..."></a>` block above the heading, slugged from the source filename. AEM
ignores those and generates its own anchor from the heading text, so the markers
were inert and -- worse -- wrong: they agreed with the platform's answer for 7,153
of 18,657, and 94% of internal links carry a fragment. An anchor that looks real
and is inert is the reason 11,500 of them drifted with nothing reporting it. The
heading text is now the single source of truth, predicted by `utils/anchors.py`
and checked by `references.anchors()` through the same function.

Stage 6a's markers stay, and the distinction matters: those preserve a *source*
anchor (`<a name="ID-2FC4B4A1">`) that points into the middle of a topic and has
no heading to be derived from. Nothing here can replace one, so nothing here
removes one.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import yaml

from docushift.reframe.packer import Page, asset_destination
from docushift.transforms import links
from docushift.utils.anchors import HEADING
from docushift.validation.references import mask_code, mask_html_blocks

# Same shape as `validation/references.py`'s, with the destination named so it can
# be replaced in place. Only the three rewritable syntaxes are here: an autolink
# is absolute by construction and a bare URL in text is not a reference.
_MD_INLINE = re.compile(
    r"!?\[(?:[^\]\\]|\\.)*\]\(\s*(?:<(?P<angle>[^>\n]*)>|(?P<bare>[^)\s]*))"
    r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)"""
)
_MD_REFDEF = re.compile(
    r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*(?:<(?P<angle>[^>\n]*)>|(?P<bare>\S+))", re.MULTILINE
)
_HTML_REF = re.compile(
    r"<(?:a|img|source|iframe|link|embed|video|audio)\b[^>]*?\b(?:href|src|poster)\s*=\s*"
    r"""(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s"'>`=]+))""",
    re.IGNORECASE,
)
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n.*?^---[ \t]*\r?$\r?\n?", re.DOTALL | re.MULTILINE)

#: Every destination group name, in the order a match may carry them.
_DESTINATIONS = ("angle", "bare", "double", "single")


@dataclass
class LinkCounts:
    """R4's tally, and the numerator of §6's "zero newly broken links" check."""

    #: Relative references examined. External, rooted and pure-fragment refs are
    #: left alone by R4 and are not counted -- there is nothing to get wrong.
    checked: int = 0
    #: Resolved onto the same merged page, so the link became a bare `#anchor`.
    intra: int = 0
    #: Resolved onto another page.
    inter: int = 0
    #: A non-`.md` target whose relative path was recomputed from the new page.
    asset: int = 0
    #: A relative target that does not exist in the source tree either. Left
    #: exactly as written and reported -- on the reference corpus these are the 92
    #: pre-existing `.html` links into a sibling resources tree (requirements §8),
    #: which Reframe neither caused nor may fail on.
    unresolved: int = 0
    #: A relative target that *does* exist in the source tree but belongs to no
    #: page. This is the only breakage the merge itself can create, and it is what
    #: §6's "zero newly broken links" is measured on.
    orphaned: int = 0
    #: Same-topic `#fragment`s re-pointed because the merge renumbered the heading
    #: they name (R9-01). Kept out of `checked`, which counts relative references
    #: only, so the §6 arithmetic over those stays what it was.
    renumbered: int = 0

    @property
    def rewritten(self) -> int:
        return self.intra + self.inter + self.asset


def split_frontmatter(text: str) -> tuple[str, str]:
    """`(frontmatter block, body)`. The block keeps its `---` delimiters."""
    matter = _FRONTMATTER.match(text)
    if not matter:
        return "", text
    return matter.group(0), text[matter.end():]


def title_of(text: str, fallback: str) -> str:
    """A topic's own frontmatter `title`, for the topics the TOC never named.

    Only used for carried-through topics: everywhere else the TOC row's title is
    the right one, and R2.1 relies on that being the writer-facing name rather than
    whatever the converter put in the file.
    """
    matter, _ = split_frontmatter(text)
    try:
        loaded = yaml.safe_load(matter.strip("-\r\n")) if matter else None
    except yaml.YAMLError:
        return fallback
    if isinstance(loaded, dict):
        found = loaded.get("title")
        if isinstance(found, str) and found.strip():
            return found.strip()
    return fallback


def word_count(body: str) -> int:
    """Whitespace-delimited tokens. The unit §6's conservation check is stated in."""
    return len(body.split())


def shift_headings(body: str, title: str, level: int = 2) -> tuple[str, int]:
    """R2.1. Returns the shifted body and how many tokens the shift added.

    The topic's first H1 moves to `level`; every other heading moves by the same
    offset, capped at H6 (requirements §7). A topic with no H1 gets a synthesized
    one from its TOC title.

    **No anchor is written.** It used to take an `anchor` argument and emit an
    `<a id>` above the heading; Phase 29 established that the platform ignores
    those and derives the anchor from the heading text instead, so the parameter
    went with the markup. The anchor a caller needs is `utils/anchors.anchor_run`
    over this page's headings.

    **`level` is the topic's place in its page, not a constant.** It was a constant
    `2` until parent-leads packing (`planning.md` Phase 28): every topic became a
    sibling `##` however deeply the TOC had nested it, because a page was a run of
    topics rather than a subtree. Now a page *is* a subtree, so its root takes `1`
    and a topic `d` levels below it takes `1 + d`. The default keeps every caller
    that has no tree to consult -- `carry`'s untocked pages, `project`'s new
    topics -- emitting exactly what they emitted before.

    The token delta is returned rather than recomputed because §6's word
    conservation is an *equality*, and the only honest way to check an equality is
    to have each step declare what it added.

    **It is now zero whenever the topic has an H1**, and that is the phase's own
    arithmetic rather than a simplification: moving a heading is free -- `#`
    through `######` are each one whitespace-delimited token, at any offset, and
    the H6 cap collapsing two depths onto one is free for the same reason. The
    marker used to cost 2. All that remains is the synthesized heading and its
    title, for a topic that had no H1 of its own.
    """
    hashes = "#" * level
    edits: list[tuple[int, int, str]] = []
    found = False
    for match in HEADING.finditer(mask_code(body)):
        depth = len(match.group("hashes"))
        if depth == 1 and not found:
            found = True
            edits.append((match.start("hashes"), match.start("hashes") + depth, hashes))
        else:
            edits.append((match.start("hashes"), match.start("hashes") + depth,
                          "#" * min(depth + level - 1, 6)))

    shifted = _apply(body, edits)
    if found:
        return shifted, 0
    heading = f"{hashes} {title}"
    added = 1 + word_count(title)
    return (f"{heading}\n\n{shifted}" if shifted else heading), added


def rewrite_links(
    body: str,
    source: PurePosixPath,
    page: PurePosixPath,
    located: dict[PurePosixPath, tuple[Page, str]],
    existing: frozenset[PurePosixPath],
    counts: LinkCounts,
    here: Page | None = None,
) -> str:
    """R4. Retargets every relative reference in one topic body onto the new layout.

    External and server-rooted references are returned untouched, which is R4's
    first clause. **A pure `#foo` is not, any more (R9-01).** It points inside the
    topic it was written in, and that topic's content is still contiguous on the
    merged page -- but its *anchor* is not: `anchor_run` numbers the whole page,
    so a topic's second `#### Import` becomes `import-2` and a bare `#import`
    lands on an earlier topic's heading. EMS 10.5.1's Kafka page did exactly that.
    `here` is the page being rendered, whose `sections` say where this topic's
    headings went; a fragment that names none of them (a Stage 6a marker, or one
    already dangling in the source) is left as written.

    Note that R4.2 makes the asset case a near no-op in practice: every topic on a
    page shares the page's own directory, so a recomputed relative path is almost
    always the path that was already there. The recomputation still runs, because
    "almost always" is a property of a corpus and not of the requirement.
    """
    masked_markdown = mask_html_blocks(mask_code(body))
    masked_html = mask_code(body)

    edits: list[tuple[int, int, str]] = []
    for pattern, masked in (
        (_MD_INLINE, masked_markdown),
        (_MD_REFDEF, masked_markdown),
        (_HTML_REF, masked_html),
    ):
        for match in pattern.finditer(masked):
            span = _destination(match)
            if span is None:
                continue
            start, end = span
            replacement = _retarget(body[start:end], source, page, located, existing, counts,
                                    here)
            if replacement is not None:
                edits.append((start, end, replacement))
    return _apply(body, edits)


def _destination(match: re.Match[str]) -> tuple[int, int] | None:
    """The span of whichever destination group this match actually filled."""
    for name in _DESTINATIONS:
        if name in match.groupdict() and match.group(name) is not None:
            start, end = match.span(name)
            return (start, end) if end > start else None
    return None


def _retarget(
    raw: str,
    source: PurePosixPath,
    page: PurePosixPath,
    located: dict[PurePosixPath, tuple[Page, str]],
    existing: frozenset[PurePosixPath],
    counts: LinkCounts,
    here: Page | None = None,
) -> str | None:
    """One reference's new destination, or `None` to leave it exactly as written."""
    reference = links.classify(raw)
    if reference.kind is links.ReferenceKind.FRAGMENT and here is not None:
        moved = here.heading(source, reference.fragment) if reference.fragment else None
        if moved is None or moved == reference.fragment:
            return None
        counts.renumbered += 1
        return "#" + moved
    if not reference.resolvable:
        return None
    counts.checked += 1

    target = links.resolve(source.parent, reference.path)
    found = located.get(target)
    if found is not None:
        destination, anchor = found
        # R9-02: a fragment naming a heading inside the target topic keeps that
        # heading. Since Phase 30 converted links point at the exact sub-heading,
        # and handing every one the topic's section anchor sent 503 of them to
        # the top of the right topic instead of the section the author named.
        # Only a fragment naming no heading there -- a marker, or none at all --
        # falls back to the section anchor, which is R4's original rule.
        if reference.fragment:
            anchor = destination.heading(target, reference.fragment) or anchor
        if destination.path == page:
            counts.intra += 1
            return "#" + anchor
        counts.inter += 1
        return links.emit(links.relative_to(page, destination.path), anchor)

    if target not in existing:
        # R4's "unresolvable": leave it exactly as written and count it. It pointed
        # at nothing before the merge and points at the same nothing after, so
        # repathing it would only move a broken link somewhere less obvious. On the
        # reference corpus this is the 92 `.html` references into a sibling
        # resources tree that requirements §8 already attributes to Stage 6.
        counts.unresolved += 1
        return None

    if target.suffix.lower() == ".md":
        # It exists and it is a topic, but no page claims it -- so it was never in
        # the TOC. Only the merge can produce this, and §6 is measured on it.
        counts.orphaned += 1
        return None

    counts.asset += 1
    # Against where the asset *lands*, not where it came from: `relocate` puts
    # pages in lower-cased slug folders and the copier lower-cases the asset's
    # directory to match. Computing this from the source path is how a link came
    # to read `../Concepts/x.png` for a file written to `concepts/x.png`.
    moved = links.relative_to(page, asset_destination(target))
    emitted = links.emit(moved, reference.fragment)
    return f"{emitted}?{reference.query}" if reference.query else emitted


def _apply(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Splices non-overlapping `(start, end, replacement)` edits into `text`.

    Sorted rather than assumed sorted: the three link patterns are scanned one
    after another, so their matches arrive interleaved. An overlap would mean two
    patterns claimed the same bytes, which is a bug here and not in the corpus --
    dropping the later edit keeps the output valid while the tests catch it.
    """
    out: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(edits):
        if start < cursor:
            continue
        out.append(text[cursor:start])
        out.append(replacement)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def render(
    page: Page,
    read: Callable[[PurePosixPath], str],
    located: dict[PurePosixPath, tuple[Page, str]],
    existing: frozenset[PurePosixPath],
    counts: LinkCounts,
    csh: dict[PurePosixPath, list[str]] | None = None,
) -> tuple[str, int]:
    """One merged page's full text, and the tokens its scaffolding added.

    Links are rewritten before headings are shifted, so the scanner sees bytes that
    still correspond one-to-one with the source file. R7's three keys are dumped
    through `yaml.safe_dump` rather than interpolated into `"..."`: the POC did the
    latter and a title containing a quote produced a page with invalid frontmatter.
    """
    parts = [_frontmatter(page, csh or {})]
    added = 0
    for topic in page.topics:
        _, body = split_frontmatter(read(topic.source))
        body = rewrite_links(body.strip(), topic.source, page.path, located, existing, counts,
                             page)
        body, extra = shift_headings(body, topic.title, topic.level)
        parts.append(body)
        added += extra
    return "\n\n".join(parts) + "\n", added


def _frontmatter(page: Page, csh: dict[PurePosixPath, list[str]]) -> str:
    """R7. `title` is the first topic's, which R7.1 calls a known weakness -- 20c's
    review queue flags it as `title-inherited` rather than this stage guessing.

    A merged page also inherits the `csh:` key of every topic it absorbed (20f).
    That key is §9.5's mirror of `csh.yml`, and `validation/csh.py` checks the two
    against each other; building this block from the `Page` alone dropped all 154
    identifiers in the corpus, which is a `CSH_FRONTMATTER_MISMATCH` per Help
    button. Unioned and re-sorted rather than concatenated per topic, because the
    page is now one page and the mirror describes the page.
    """
    data: dict[str, Any] = {
        "title": page.topics[0].title,
        "guide": page.guide,
        "merged_from": len(page.topics),
    }
    identifiers = sorted({name for topic in page.topics for name in csh.get(topic.source, ())})
    if identifiers:
        data["csh"] = identifiers
    dumped = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=10**6)
    return f"---\n{dumped}---"


