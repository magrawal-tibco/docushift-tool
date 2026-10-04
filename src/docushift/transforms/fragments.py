"""Retargeting a `#fragment` from an inert marker onto the heading it belongs to.

**The platform ignores `<a id="...">` and generates its own anchor from heading
text.** Confirmed against a real instance, 2026-09-30. Reframe learned that for
merged pages in Phase 29; this is the same lesson for the trees that publish
*unmerged*, and the numbers are what make it a phase of its own:

| published tree | fragments resolving before |
|---|---|
| ActiveSpaces, EMS (merged) | 92%, 97% |
| **Streaming (unmerged)** | **0 of 45,248** |
| **Runtime Agent (unmerged)** | **0 of 4,531** |

Roughly 50,000 published cross-references, and **not one of them ever worked**.
Nothing reported it because `validate` resolved a fragment against the very
markers the converter had just emitted -- the checker agreeing with the emitter
rather than with the renderer.

Of Streaming 11.2.1's 5,670 internal fragment links, **5,670 target a marker
that is present on disk**. So the information needed is all there; what is
missing is the step that turns a marker into the anchor a reader can actually
reach.

**The rule: a marker belongs to the nearest heading.** Markdown-rendered Flare
and DocBook put a cross-reference target either immediately above the heading it
labels -- which is where `markdown.anchor_marker` hoists it, precisely so the
marker cannot pollute the heading's own slug -- or part-way down a section, in
which case the section's heading is the closest thing a reader can be sent to.
So: the next heading if one follows before any prose, otherwise the previous
one. Other markers are not prose: a run of them above a heading all belong to
it (X1-01).

**This is a demotion, not a repair, and it should be read as one.** A link that
pointed at a sentence now points at the section containing it. That is less
precise than the author wrote and is the whole of what the platform can express
-- the same trade `csh._value` took for Help buttons, for the same reason: the
alternative on offer is not precision, it is a link that goes nowhere.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable

from docushift.utils.anchors import HEADING, anchor_run


def _mask_code(text: str) -> str:
    """`validation.references.mask_code`, imported late and deliberately.

    `transforms` sits below `validation`, and importing it at module scope makes
    `import docushift.sync` fail with a partially-initialised package: the chain
    runs sync -> converter -> transforms -> validation -> sync. One function
    deep in a lower layer is not worth inverting the dependency for, and
    reimplementing the masker would be worse -- it is the thing that stops a
    `# comment` in a shell sample being read as a heading, and two copies of it
    is how one of them stops being fixed.
    """
    from docushift.validation.references import mask_code

    return mask_code(text)

#: An anchor target the engines emit: `<a id="X"></a>` on its own, or inline.
_MARKER = re.compile(r'<a\s+(?:id|name)\s*=\s*"([^"]*)"\s*>\s*</a>', re.IGNORECASE)
#: Between a marker and the heading it labels there is only blank space -- and
#: other markers, which render nothing. Anything else means the marker sits *in*
#: the preceding section rather than above the next one.
_ONLY_BLANK = re.compile(r"\A[\s]*\Z")


def marker_targets(text: str) -> dict[str, str]:
    """Every `<a id>` in this document, mapped to the anchor a reader can reach.

    Keyed lower-case on both sides, because renderers fold anchor case and a
    rewrite that did not would miss the half of the corpus that capitalises its
    identifiers (`ID-2FC4B4A1`). And keyed on the name as written, not as
    `markdown.anchor_marker` HTML-escaped it into the attribute: `R&amp;D` is
    the target `R&D` (Phase 34, beside R8-08).

    A document with no headings at all yields nothing: there is no anchor to
    send anybody to, and inventing one would replace a link that fails visibly
    with a link that fails quietly somewhere else.
    """
    masked = _mask_code(text)
    headings = [(match.start(), match.group(2)) for match in HEADING.finditer(masked)]
    if not headings:
        return {}
    anchors = anchor_run([title for _start, title in headings])

    found: dict[str, str] = {}
    for marker in _MARKER.finditer(masked):
        name = html.unescape(marker.group(1)).strip()
        if not name:
            continue
        after = [index for index, (start, _t) in enumerate(headings) if start >= marker.end()]
        before = [index for index, (start, _t) in enumerate(headings) if start < marker.start()]
        chosen: int | None = None
        if after:
            index = after[0]
            # Sibling markers are stripped from the gap first (X1-01). The
            # heading hoist writes a run of them on one line, and Flare puts three
            # or four on a heading, so counting them as prose sent every marker
            # but the last to the previous section: 391 markers across the
            # converted trees, and 19 of TRA Runtime Agent 5.13.0's 108 Help IDs.
            gap = _MARKER.sub("", masked[marker.end():headings[index][0]])
            if _ONLY_BLANK.match(gap):
                chosen = index
        if chosen is None:
            chosen = before[-1] if before else (after[0] if after else None)
        if chosen is not None and anchors[chosen]:
            found[name.lower()] = anchors[chosen]
    return found


#: The three rewritable reference syntaxes, with the destination named so it can
#: be replaced in place. Same shapes `reframe/pages.py` uses and for the same
#: reason: `validation.references`' patterns are tuned for *counting* and expose
#: no span to edit.
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
_GROUPS = ("angle", "bare", "double", "single")


def retarget(body: str, anchor_for: Callable[[str, str], str | None]) -> tuple[str, int]:
    """Rewrites every `#fragment` that names a marker onto its heading's anchor.

    `anchor_for(path, fragment)` is the caller's resolver: it knows where `path`
    lands and what markers that document holds, and returns the replacement
    fragment or `None` to leave the reference exactly as written. Returning
    `None` is the common case and the important one -- a fragment this pass
    cannot place is reported, never guessed at.

    Both arguments arrive as written in the Markdown, so percent-encoded:
    decoding is the resolver's job, as it is for every other reader of a URL
    (R8-08). The replacement is a heading slug, which never needs encoding.

    Fence-aware through `mask_code`, matching on the mask and editing the
    original by offset, so a `](#x)` inside a shell sample is prose.
    """
    masked = _mask_code(body)
    edits: list[tuple[int, int, str]] = []
    for pattern in (_MD_INLINE, _MD_REFDEF, _HTML_REF):
        for match in pattern.finditer(masked):
            for name in _GROUPS:
                try:
                    raw = match.group(name)
                except IndexError:  # pragma: no cover - pattern without that group
                    continue
                if raw is None:
                    continue
                path, separator, fragment = raw.partition("#")
                if not separator or not fragment:
                    continue
                replacement = anchor_for(path, fragment)
                if replacement is None or replacement == fragment:
                    continue
                start = match.start(name)
                edits.append((start + len(path) + 1, match.end(name), replacement))
                break
    if not edits:
        return body, 0
    out: list[str] = []
    cursor = 0
    for start, end, text in sorted(edits):
        if start < cursor:  # pragma: no cover - overlapping spans
            continue
        out.append(body[cursor:start])
        out.append(text)
        cursor = end
    out.append(body[cursor:])
    return "".join(out), len(edits)
