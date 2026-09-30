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

Anchors are emitted as `markdown.anchor_marker` on its own block above the heading
(planning §20.3), not as the POC's `{#anchor}`. GFM has no attribute syntax, so
`## Title {#a}` renders the braces as literal text and the anchor does not exist;
the passthrough `<a id="..."></a>` is the house idiom and is what `slugify_heading`
and `references.anchors()` already agree on.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import yaml

from docushift.reframe.packer import Page
from docushift.transforms import links
from docushift.transforms.markdown import anchor_marker
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
_HEADING = re.compile(r"^[ \t]{0,3}(?P<hashes>#{1,6})[ \t]+(?P<text>.*?)[ \t]*#*[ \t]*$", re.MULTILINE)
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


def shift_headings(body: str, title: str, anchor: str, level: int = 2) -> tuple[str, int]:
    """R2.1. Returns the shifted body and how many tokens the shift added.

    The topic's first H1 becomes the anchored heading at `level`; every other
    heading moves by the same offset, capped at H6 (requirements §7). A topic with
    no H1 gets a synthesized one from its TOC title.

    **`level` is the topic's place in its page, not a constant.** It was a constant
    `2` until parent-leads packing (`planning.md` Phase 28): every topic became a
    sibling `##` however deeply the TOC had nested it, because a page was a run of
    topics rather than a subtree. Now a page *is* a subtree, so its root takes `1`
    and a topic `d` levels below it takes `1 + d`. The default keeps every caller
    that has no tree to consult -- `carry`'s untocked pages, `project`'s new
    topics -- emitting exactly what they emitted before.

    The token delta is returned rather than recomputed because §6's word
    conservation is an *equality*, and the only honest way to check an equality is
    to have each step declare what it added. It is *measured* rather than asserted
    for the reason the first corpus run found: `<a id="x"></a>` is two
    whitespace-delimited tokens, not the one that requirements §6's "+1 per topic"
    assumes, and a hand-written constant simply encodes whichever anchor syntax was
    in mind when it was written.

    **The delta does not depend on `level`, and that is worth stating rather than
    noticing.** `#` through `######` are each one whitespace-delimited token, so
    moving a heading is free at *any* offset, and so is the H6 cap collapsing two
    depths onto one. The cost is the marker, plus a synthesized heading and its
    title where a topic had no H1 to anchor -- exactly as before.
    """
    marker = anchor_marker(anchor)
    hashes = "#" * level
    edits: list[tuple[int, int, str]] = []
    found = False
    for match in _HEADING.finditer(mask_code(body)):
        depth = len(match.group("hashes"))
        text = body[match.start("text"):match.end("text")]
        if depth == 1 and not found:
            found = True
            edits.append((match.start(), match.end(), f"{marker}\n\n{hashes} {text}"))
        else:
            edits.append((match.start(), match.start("hashes") + depth,
                          "#" * min(depth + level - 1, 6)))

    shifted = _apply(body, edits)
    if found:
        return shifted, word_count(marker)
    heading = f"{marker}\n\n{hashes} {title}"
    added = word_count(marker) + 1 + word_count(title)
    return (f"{heading}\n\n{shifted}" if shifted else heading), added


def rewrite_links(
    body: str,
    source: PurePosixPath,
    page: PurePosixPath,
    located: dict[PurePosixPath, tuple[Page, str]],
    existing: frozenset[PurePosixPath],
    counts: LinkCounts,
) -> str:
    """R4. Retargets every relative reference in one topic body onto the new layout.

    External, server-rooted and pure-fragment references are returned untouched,
    which is R4's first clause and also the only safe reading: a `#foo` written by
    an author points inside the topic it was written in, and that topic's content
    is still contiguous on the merged page.

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
            replacement = _retarget(body[start:end], source, page, located, existing, counts)
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
) -> str | None:
    """One reference's new destination, or `None` to leave it exactly as written."""
    reference = links.classify(raw)
    if not reference.resolvable:
        return None
    counts.checked += 1

    target = links.resolve(source.parent, reference.path)
    found = located.get(target)
    if found is not None:
        destination, anchor = found
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
    moved = links.relative_to(page, target)
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
        body = rewrite_links(body.strip(), topic.source, page.path, located, existing, counts)
        body, extra = shift_headings(body, topic.title, page.anchors[topic.source], topic.level)
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


def tally(counts: LinkCounts) -> Counter[str]:
    """The link counts as a `Counter`, for the report and the manifest."""
    return Counter(
        checked=counts.checked,
        rewritten=counts.rewritten,
        intra=counts.intra,
        inter=counts.inter,
        asset=counts.asset,
        unresolved=counts.unresolved,
    )
