"""Backslash escapes AEM does not read: `\\<` and `\\\\` in prose (DOCOPS-360).

AEM's Markdown renderer handles code spans and fenced code, but not CommonMark's
backslash escapes in normal text. The reader saw `\\<clus_name>` in FTL's headings
and `Systems\\\\ArchiverDemo` in Foresight's paths (staging, 2026-11-12/13). So the
converter's final text, and R002's repair of the trees already written, use forms
AEM shows as meant:

- `\\<` becomes `&lt;` (FTL 7.3.0, tested on staging);
- `\\\\`, one escaped backslash, becomes a single `\\` when the next character is a
  letter, a digit, or a space with more text after it on the line (Foresight 6.0.0,
  tested on staging). A plain backslash is only an escape before ASCII punctuation,
  and a hard line break only before the line ending, so neither can start one;
- any other `\\\\` -- before punctuation, at the end of a line or of the text --
  becomes `BACKSLASH_BEFORE_PUNCT`. A plain `\\` there would escape the next
  character (`\\*` is an asterisk, not a backslash and an asterisk) or turn the line
  ending into a hard break.

Every other escape (`\\*`, `\\_`, `\\[`, `\\#`, `\\|` ...) is left exactly as it is.

**Where the text is not Markdown prose, nothing changes:** front matter (YAML, where
`\\\\` is YAML's own escape), fenced and indented code blocks, code spans, raw HTML
blocks, and inline HTML tags and comments. Inside raw HTML a backslash escape is not
processed by any renderer, so `\\\\` there is the source's own text: BusinessWorks'
`<span class="Code">\\\\</span> signifies to split when a backslash` and EMS's
`<code>'^.*_SERVER\\\\.tibco\\\\.com'</code>` in a raw table cell mean two backslashes
(measured with `git grep`, 2026-11-14). The HTML blocks are CommonMark's: a line
opening with a block tag (`<table>`, `<p>`, `<div>` ...) or a lone complete tag runs
to the next blank line; `<pre>`, `<script>`, `<style>` and `<textarea>` run to their
closing tag; a comment to its `-->`. Text after a blank line inside raw HTML is
Markdown again (`_typed_list`'s item bodies) and is fixed like any prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: What a backslash is written as where a plain `\` would escape the next character
#: or end the line as a hard break. **Not yet confirmed on staging** (DOCOPS-360):
#: `&lt;` and a plain `\` are; a decimal reference is the same mechanism as `&lt;`,
#: but if AEM shows it raw, this constant is the one place to change.
BACKSLASH_BEFORE_PUNCT = "&#92;"

# A backslash escape, as CommonMark reads it: a backslash and one ASCII punctuation
# character. Scanned left to right with the alternatives below, so `\\\*` is an
# escaped backslash and then an escaped asterisk, never the reverse.
_TOKEN = re.compile(
    r"(?P<escape>\\[!-/:-@\[-`{-~])"
    # A code span on one line: a run of backticks closed by a run of the same length.
    r"|(?P<code>(?<!`)(?P<ticks>`+)(?!`)[^\n]*?(?<!`)(?P=ticks)(?!`))"
    # Inline raw HTML: a comment, a tag, an autolink. Its attribute values are not
    # Markdown, so a backslash in `<a id="C:\\x">` is the attribute's own.
    r"|(?P<html><!--[\s\S]*?-->|</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>"
    r"|<[A-Za-z][A-Za-z0-9+.\-]*:[^<>\s]*>)"
)

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n.*?^---[ \t]*(?:\r?\n|\Z)", re.DOTALL | re.MULTILINE)
# Any quote marks and list markers in front of a fence: `> ```` in a note, a fence
# indented under a nested list item. Read generously -- a line misread as code is
# left alone, which is the safe side.
_FENCE = re.compile(r"^(?:[ \t]*>)*[ \t]*(?:(?:[-+*]|\d{1,9}[.)])[ \t]+)?(?P<fence>`{3,}|~{3,})(?P<rest>.*)$")
_QUOTES = re.compile(r"^(?:[ \t]{0,3}>[ ]?)*")
_ITEM = re.compile(r"^(?P<indent> *)(?P<marker>[-+*]|\d{1,9}[.)])(?P<gap> +|$)")

# CommonMark's HTML-block start conditions (1, 2, 6, 7). Type 6's tag list, verbatim.
_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|"
    "dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|"
    "frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|legend|li|link|main|menu|"
    "menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|"
    "tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_HTML_RAW = re.compile(r"^<(pre|script|style|textarea)(?:[\s>]|$)", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"^<!--")
_HTML_BLOCK = re.compile(rf"^</?(?:{_BLOCK_TAGS})(?:[\s>]|/>|$)", re.IGNORECASE)
_HTML_LONE_TAG = re.compile(r"^(?:<[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$")


@dataclass
class Fixed:
    text: str
    angles: int = 0
    backslashes: int = 0

    @property
    def count(self) -> int:
        return self.angles + self.backslashes


def backslash(after: str) -> str:
    """One escaped backslash, written for the text that follows it.

    `after` is the rest of the line after the `\\\\` (with its line ending, if any).
    """
    following = after[:1]
    if following.isalnum():
        return "\\"
    if following == " " and after.strip(" \t\r\n"):
        return "\\"
    return BACKSLASH_BEFORE_PUNCT


def _fix_prose(text: str, into: Fixed) -> str:
    """`text`, a run of Markdown prose lines, with the two escapes rewritten."""

    def replace(match: re.Match[str]) -> str:
        token = match.group("escape")
        if token is None:
            return match.group(0)  # a code span or raw HTML: not prose
        if token == "\\<":
            into.angles += 1
            return "&lt;"
        if token == "\\\\":
            into.backslashes += 1
            end = match.end()
            stop = text.find("\n", end)
            return backslash(text[end:] if stop < 0 else text[end:stop + 1])
        return token

    return _TOKEN.sub(replace, text)


def _width(spaces: str) -> int:
    width = 0
    for char in spaces:
        width = width + 4 - width % 4 if char == "\t" else width + 1
    return width


def fix_markdown(text: str, frontmatter: bool = True) -> Fixed:
    """`text` with prose `\\<` and `\\\\` rewritten for AEM. Idempotent; line endings kept.

    `frontmatter=False` reads a leading `---` as Markdown: the converter's page body
    has no front matter yet when it is fixed.
    """
    result = Fixed(text)
    head = ""
    if frontmatter and (matter := _FRONTMATTER.match(text)):
        head, text = matter.group(0), text[matter.end():]

    out: list[str] = []
    prose: list[str] = []

    def flush() -> None:
        if prose:
            out.append(_fix_prose("".join(prose), result))
            prose.clear()

    def skip(line: str) -> None:
        flush()
        out.append(line)

    fence = ""          # the open fence's marker, while inside one
    html_end = None     # the open HTML block's end condition: "", or a closing text
    items: list[int] = []  # content columns of the open list items
    depth = 0           # blockquote depth of the previous line
    blank = True        # the previous line was blank (or this is the first)
    code = False        # the previous line was indented code

    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if fence:
            closing = _FENCE.match(bare)
            if (closing and closing["fence"][0] == fence[0] and len(closing["fence"]) >= len(fence)
                    and not closing["rest"].strip()):
                fence = ""
            skip(line)
            blank = code = False
            continue
        if html_end is not None:
            if html_end == "":
                if not bare.strip():
                    html_end = None
                    prose.append(line)
                    blank, code = True, False
                    continue
            elif html_end in bare.lower():
                html_end = None
            skip(line)
            blank = code = False
            continue

        quotes = _QUOTES.match(bare).group(0)
        inner = bare[len(quotes):]
        level = quotes.count(">")
        if level != depth:
            items.clear()
            depth = level
        if not inner.strip():
            prose.append(line)
            blank = True
            continue
        stripped = inner.lstrip(" \t")
        indent = _width(inner[:len(inner) - len(stripped)])
        if blank:
            while items and indent < items[-1]:
                items.pop()
        base = items[-1] if items else 0

        # A fence first, at any indent: one misread as opening code leaves the text
        # after it alone, which is the safe side. A backtick in a backtick fence's
        # info string makes the line a code span instead (CommonMark).
        opened = _FENCE.match(bare)
        if opened and not (opened["fence"][0] == "`" and "`" in opened["rest"]):
            fence = opened["fence"]
            skip(line)
            blank = code = False
            continue

        # Indented code: four columns past the container, not continuing a paragraph.
        if indent >= base + 4 and (blank or code):
            skip(line)
            blank, code = False, True
            continue
        code = False

        if indent < base + 4:
            if _HTML_RAW.match(stripped):
                tag = _HTML_RAW.match(stripped).group(1).lower()
                if f"</{tag}>" not in stripped.lower():
                    html_end = f"</{tag}>"
                skip(line)
                blank = False
                continue
            if _HTML_COMMENT.match(stripped):
                if "-->" not in stripped[4:]:
                    html_end = "-->"
                skip(line)
                blank = False
                continue
            if _HTML_BLOCK.match(stripped) or (blank and _HTML_LONE_TAG.match(stripped)):
                html_end = ""
                skip(line)
                blank = False
                continue

        item = _ITEM.match(inner)
        if item:
            start = len(item["indent"])
            while items and start < items[-1]:
                items.pop()
            gap = len(item["gap"])
            items.append(start + len(item["marker"]) + (gap if 1 <= gap <= 4 else 1))
        prose.append(line)
        blank = False

    flush()
    result.text = head + "".join(out)
    return result


def count(text: str) -> int:
    """How many escapes `fix_markdown` would rewrite in `text`."""
    return fix_markdown(text).count
