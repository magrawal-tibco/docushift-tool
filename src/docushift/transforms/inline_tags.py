"""`<samp>` and `<var>`, which AEM removes with their text (DOCOPS-371).

Staging drops both elements and the words inside them. Mainframe Substation ES,
CICS and IMS 2.14.0 `lta-agent-messages` read "The supported codes are,, and"
where the source has `<samp>1</samp>`, `<samp>2</samp>`, `<samp>3.</samp>`. The
converter's Markdown walk already writes `<var>` as emphasis and `<samp>` as a
code span; the tags survive only in raw HTML, which is mostly tables that GFM cannot
carry (`tables.passthrough`).

Keeping the tags is the Digital Platform's fix. This is the fallback, **off by
default**: the converter applies it when `config/converter.yaml` sets
`aem.inline_tags_rewrite: true`, and R003 rewrites trees already published the
same way, so a repaired page reads exactly as a fresh conversion would.

- In Markdown prose, `<samp>x</samp>` becomes `` `x` `` and `<var>x</var>` becomes
  `*x*`. An element that holds other markup or spans a line keeps its content and
  is renamed instead, as below.
- In raw HTML, `<samp>` becomes `<code>` and `<var>` becomes `<em>`, attributes kept.
- Front matter, fenced and indented code and code spans are left alone: a tag
  there is shown as typed, not rendered. `escapes.split_markdown` decides which is
  which, the same classification R002 uses.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from docushift.transforms import code as code_transform
from docushift.transforms import escapes

#: What each tag becomes inside raw HTML.
RENAMED = {"samp": "code", "var": "em"}

# One start or end tag. The lookahead keeps `<variable>` and `<sample>` out.
_TAG = re.compile(r"<(?P<end>/?)(?P<name>samp|var)(?=[\s/>])(?P<rest>[^<>]*)>", re.IGNORECASE)

# Prose, scanned left to right: a code span is skipped whole, so a tag inside one
# stays as typed; a whole element with plain text becomes Markdown; any other tag is
# renamed.
_PROSE = re.compile(
    r"(?P<code>(?<!`)(?P<ticks>`+)(?!`)[^\n]*?(?<!`)(?P=ticks)(?!`))"
    r"|(?P<element><(?P<name>samp|var)(?:\s[^<>]*)?>(?P<body>[^<\n]*)</(?P=name)\s*>)"
    r"|(?P<tag></?(?:samp|var)(?=[\s/>])[^<>]*>)",
    re.IGNORECASE,
)

# A CommonMark backslash escape: in a code span the backslash would show.
_ESCAPED = re.compile(r"\\([!-/:-@\[-`{-~])")


@dataclass
class Fixed:
    text: str
    count: int = 0


def _rename(match: re.Match[str], into: Fixed) -> str:
    if not match.group("end"):
        into.count += 1
    name = RENAMED[match.group("name").lower()]
    return f"<{match.group('end')}{name}{match.group('rest')}>"


def _markdown(name: str, body: str) -> str:
    """One whole element as a code span or as emphasis."""
    if name == "samp":
        return code_transform.inline(html.unescape(_ESCAPED.sub(r"\1", body)))
    stripped = body.strip()
    if not stripped:
        return body
    head = body[:len(body) - len(body.lstrip())]
    rear = body[len(body.rstrip()):]
    return f"{' ' if head else ''}*{stripped}*{' ' if rear else ''}"


def _fix_prose(text: str, into: Fixed) -> str:
    def replace(match: re.Match[str]) -> str:
        if match.group("code") is not None:
            return match.group(0)
        if match.group("element") is not None:
            into.count += 1
            return _markdown(match.group("name").lower(), match.group("body"))
        return _TAG.sub(lambda tag: _rename(tag, into), match.group("tag"))

    return _PROSE.sub(replace, text)


def fix_markdown(text: str, frontmatter: bool = True) -> Fixed:
    """`text` with every `<samp>` and `<var>` outside code rewritten. Idempotent.

    The count is the elements rewritten (a lone end tag is renamed, uncounted).
    `frontmatter=False` reads a leading `---` as Markdown, as `escapes.fix_markdown`.
    """
    result = Fixed(text)
    parts: list[str] = []
    for kind, chunk in escapes.split_markdown(text, frontmatter):
        if kind == escapes.PROSE:
            parts.append(_fix_prose(chunk, result))
        elif kind == escapes.HTML:
            parts.append(_TAG.sub(lambda match: _rename(match, result), chunk))
        else:
            parts.append(chunk)
    result.text = "".join(parts)
    return result
