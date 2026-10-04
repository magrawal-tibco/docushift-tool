"""Pulling every reference out of a published Markdown file.

Stage 8's reader. It answers one question -- *what does this page point at?* --
and it answers it for a linter rather than for a renderer, which is why it is not
a Markdown parser. Four rules, and three of them are corpus-measured over the
sample published tree of 2026-09-16 (`planning.md` Phase 7b):

- **Markdown syntax is not enough.** 2,520 of the sample's 40,054 references are
  raw `<a href>` / `<img src>` in the HTML the engines pass through for tables GFM
  cannot express, spread over 366 files. A reader that only sees `![](…)` reports
  a clean tree while those images 404.
- **The HTML is multiline.** `<img>` attributes routinely wrap, so a line-oriented
  match undercounts. The tag patterns here are bounded by `>` rather than by `\\n`,
  which costs nothing and is the whole fix.
- **Fenced blocks and inline spans are masked; indented lines are not.** Measured:
  **zero** references live inside 79,497 fenced lines and 928,552 characters of
  code span, so the masking buys nothing today and is kept only because an engine
  that starts emitting sample HTML inside a fence would otherwise break a gating
  command. Honouring CommonMark's *indented* code blocks, on the other hand, would
  silently stop checking **953 real references** -- four-space indentation in
  converted help is list continuation, not code. So this reader is deliberately
  not CommonMark-correct, in one direction, on purpose.
- **HTML blocks are masked for the Markdown patterns only.** CommonMark does not
  parse inline Markdown inside a block-level HTML block, so `[%s](%s:%d)` in a
  passthrough table row is text. Reading it as a link produced the one
  `LINK_BROKEN` on the `ems` tree, against a printf format string present
  verbatim in the source HTML. The `<a href>` pattern still runs over those
  regions -- that is where most of them live. (Anchors are heading slugs only
  since Phase 29, so no `id=`/`name=` pattern runs anywhere; see `anchors()`.)
- **Masking preserves offsets.** Code regions are overwritten with spaces rather
  than deleted, so every match's line number is the line number in the file the
  reader will open. A finding that names the wrong line is a finding somebody
  stops trusting.

Anchors are computed here too, from the same text, because the question "does
`#foo` exist in that file" is the same question read from the other end.
"""

import re
from dataclasses import dataclass

from docushift.utils import anchors as anchors_util

# A quoted or bare HTML attribute value. Three groups, one per quoting style; the
# bare form exists because hand-written passthrough HTML in the corpus uses it.
_ATTR = r"""(?:"([^"]*)"|'([^']*)'|([^\s"'>`=]+))"""

# `[^>]*?` spans newlines already -- a negated class is not line-bounded -- which
# is the multiline-awareness the module docstring promises.
_HTML_REF = re.compile(
    r"<(?:a|img|source|iframe|link|embed|video|audio)\b[^>]*?\b(?:href|src|poster)\s*=\s*" + _ATTR,
    re.IGNORECASE,
)
# `id=` and `name=` on any tag: an anchor target the engines emit 11,887 times in
# 2,036 files of the sample, and the reason an anchor check can work at all.
_HTML_ANCHOR = re.compile(r"<[a-zA-Z][^>]*?\b(?:id|name)\s*=\s*" + _ATTR, re.IGNORECASE)

# Inline link or image. The destination is either `<bracketed>` or bare, and an
# optional title follows in any of Markdown's three quotings.
_MD_INLINE = re.compile(
    r"!?\[(?:[^\]\\]|\\.)*\]\(\s*(?:<([^>\n]*)>|([^)\s]*))"
    r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)"""
)
# A reference definition, `[label]: destination "title"`.
_MD_REFDEF = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*(?:<([^>\n]*)>|(\S+))", re.MULTILINE)
# `<https://example.com>`. Always absolute by definition, counted for completeness.
_AUTOLINK = re.compile(r"<([a-zA-Z][a-zA-Z0-9+.\-]*:[^<>\s]*)>")

# CommonMark's HTML-block type 6 tag list, verbatim. `a`, `b`, `span`, `code`,
# `img` are deliberately *not* in it: an inline tag opening a line suspends
# nothing, so a Markdown link beside one is still a link.
_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|"
    "dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|"
    "frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|legend|li|link|main|menu|"
    "menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|"
    "tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_HTML_BLOCK_6 = re.compile(rf"^[ \t]{{0,3}}</?(?:{_BLOCK_TAGS})(?:[ \t>]|/>|$)", re.IGNORECASE)
# Type 7: one complete tag, alone on its line.
_HTML_BLOCK_7 = re.compile(r"^[ \t]{0,3}(?:<[a-zA-Z][^>]*>|</[a-zA-Z][a-zA-Z0-9-]*[ \t]*>)[ \t]*$")

_FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+)(?!`)(?:[^`\n]|(?!\1)`)+\1")
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n.*?^---[ \t]*\r?$", re.DOTALL | re.MULTILINE)
_HEADING = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$", re.MULTILINE)


@dataclass(frozen=True)
class RawReference:
    """One `href`/`src` as it was written, and where it was written."""

    raw: str
    line: int
    # `markdown` or `html`. Kept because the split is the measurement that
    # justifies reading the HTML at all, and a run can report it back.
    syntax: str


def _blank(text: str) -> str:
    """The same text, same length, same newlines, nothing else."""
    return "".join("\n" if char == "\n" else " " for char in text)


def mask_code(text: str) -> str:
    """Overwrites frontmatter, fenced blocks and code spans with spaces.

    Offsets survive, so a line number computed on the result is a line number in
    the original. Indentation is deliberately *not* treated as code -- see the
    module docstring, and the 953 references that decision keeps in scope.
    """
    matter = _FRONTMATTER.match(text)
    if matter:
        text = _blank(matter.group(0)) + text[matter.end():]

    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        marker = _FENCE.match(line)
        if fence is None:
            if marker:
                fence = marker.group(1)[0] * len(marker.group(1))
                out.append(_blank(line))
            else:
                out.append(line)
            continue
        # Inside a fence. A closing marker must use the same character and be at
        # least as long as the opener, which is CommonMark's rule and also what
        # stops a ```` ``` ```` inside a ```` ```` ```` block from ending it early.
        if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
            fence = None
        out.append(_blank(line))

    return _CODE_SPAN.sub(lambda m: _blank(m.group(0)), "".join(out))


def mask_html_blocks(text: str) -> str:
    """Overwrites block-level HTML regions with spaces, offsets preserved.

    For the Markdown patterns only. Inside an HTML block CommonMark emits the
    source through untouched, so brackets and parentheses there are punctuation.
    Measured over the published `ems` tree: of 15,112 Markdown-syntax references
    in 8,657 files this removes **one**, and that one is a `%s:%d` in an error
    table. A block runs from its opening line to the next blank line.
    """
    out: list[str] = []
    inside = False
    for line in text.splitlines(keepends=True):
        if inside:
            out.append(_blank(line))
            if not line.strip():
                inside = False
            continue
        if _HTML_BLOCK_6.match(line) or _HTML_BLOCK_7.match(line):
            inside = True
            out.append(_blank(line))
            continue
        out.append(line)
    return "".join(out)


def frontmatter(text: str) -> str:
    """The YAML frontmatter block's body, or `""`. Not parsed here."""
    matter = _FRONTMATTER.match(text)
    if not matter:
        return ""
    lines = matter.group(0).splitlines()
    return "\n".join(lines[1:-1])


def _value(match: re.Match[str], *groups: int) -> str:
    for index in groups:
        found = match.group(index)
        if found is not None:
            return found
    return ""


def references(text: str) -> list[RawReference]:
    """Every reference in one Markdown file, in no particular order.

    Duplicates are kept. The same broken link cited four times in one page is four
    things to fix in that page, and folding them here would hide three of them.
    """
    masked = mask_code(text)
    # One `count` over the whole string per match beats `text[:pos].count` inside
    # the loop, which is quadratic on a 40,000-line API page.
    newlines = [index for index, char in enumerate(masked) if char == "\n"]

    def line_of(position: int) -> int:
        low, high = 0, len(newlines)
        while low < high:
            mid = (low + high) // 2
            if newlines[mid] < position:
                low = mid + 1
            else:
                high = mid
        return low + 1

    # The Markdown patterns read the text with HTML blocks blanked out as well;
    # the HTML pattern below reads it with only code masked, because a real
    # `<a href>` inside a passthrough table is the majority of them.
    prose = mask_html_blocks(masked)

    found: list[RawReference] = []
    for match in _MD_INLINE.finditer(prose):
        found.append(RawReference(_value(match, 1, 2), line_of(match.start()), "markdown"))
    for match in _MD_REFDEF.finditer(prose):
        found.append(RawReference(_value(match, 1, 2), line_of(match.start()), "markdown"))
    for match in _AUTOLINK.finditer(prose):
        found.append(RawReference(match.group(1), line_of(match.start()), "markdown"))
    for match in _HTML_REF.finditer(masked):
        found.append(RawReference(_value(match, 1, 2, 3), line_of(match.start()), "html"))
    return [ref for ref in found if ref.raw.strip()]


def slugify_heading(title: str) -> str:
    """A heading's anchor, GitHub's way: tags out, punctuation out, spaces to dashes.

    Re-exported from `utils/anchors.py` rather than defined here. It used to live
    in this module, which was right while the checker was its only caller; once
    Reframe had to *emit* the same anchor (Phase 29) a second copy would have let
    the writer and the checker agree with each other and both be wrong about what
    the platform does.
    """
    return anchors_util.slugify_heading(title)


def anchors(text: str) -> set[str]:
    """Every fragment `#foo` that resolves inside this file.

    **Computed heading slugs, and nothing else (Phase 29).** This used to add the
    explicit `id=` / `name=` attributes the engines pass through, on the reasonable
    assumption that an `<a id>` in the output is an anchor in the output. It is
    not: the platform generates anchors from heading text and ignores the
    attributes entirely, confirmed 2026-09-30.

    Counting them made this function agree with the emitter instead of with the
    renderer, which is the failure mode a linter exists to catch rather than to
    have. It is also *why* the old anchors went wrong unnoticed -- they were
    slugged from source filenames, checked against themselves, and passed.

    Dropping them raises `ANCHOR_MISSING` on every mid-topic Flare anchor
    (`#ID-000071DF`, `#top`) that no heading backs. Those links genuinely do not
    work, there is nothing in the content that can make them work, and a warning
    naming them is the only honest output. The slugs are lower case by
    construction, and callers compare a fragment to them exactly (Phase 34,
    R11-08): this used to fold both sides on the belief that renderers fold
    anchor case, but a browser matches a fragment to an id case-sensitively.
    """
    return {
        anchor
        for anchor in anchors_util.anchor_run(
            [title for _level, title in _HEADING.findall(mask_code(text))]
        )
        if anchor
    }
