"""Admonitions to a bold label in a blockquote.

**AEM does not render GitHub alerts** (Phase 55's probe, 2026-10-22). It reads
`> [!TIP]` as a quote holding an empty key reference, so the reader got the text
with no "Tip" and no box. A note is therefore `> **Tip:**` with its body on the
very next line -- one paragraph, "**Tip:** text" -- which staging renders as a
bold label in a quote (Phase 56). The kinds stay the five GitHub has, so the
vocabulary is closed and lives here rather than in each engine. What each
engine has to do to *find* an admonition is entirely its own -- Flare's label is a
`data-mc-autonum` attribute the skin's CSS renders and must be recovered
(`architecture.md` §5.1.8), DITA's is a `span.*title` that must be deleted because
leaving it duplicates the label (§5.2.5), and WebWorks' is a `div.Icon<Kind>` in
the *first* cell of a `table.IconTable` whose prose is in the second (§5.3.7). All
three then arrive here with a label string and a body.

**An unmapped label falls back to `NOTE` and is reported**, never dropped. A
label the tool has not seen is evidence about the corpus; silently rendering it as
a plain blockquote loses both the label and the fact that it existed.

`fix_markdown` applies the same rule to Markdown already written with the old
`> [!KIND]` marker, so a published tree is repaired without a re-conversion and
reads exactly as a fresh one would.
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class Alert(StrEnum):
    """The five admonition kinds. There is no sixth, so there is no fallback kind."""

    NOTE = "NOTE"
    TIP = "TIP"
    IMPORTANT = "IMPORTANT"
    WARNING = "WARNING"
    CAUTION = "CAUTION"

    @property
    def label(self) -> str:
        """The word the reader sees: `Note`, `Tip`, `Important`, `Warning`, `Caution`."""
        return self.value.capitalize()


# DITA's admonition vocabulary is the widest of the three (13 `@type` values), so
# it sets the shape of this table; Flare's four and WebWorks' icon names fall
# inside it. Mapped by meaning rather than by name: `danger` is stronger than
# `warning` and the strongest kind is `CAUTION`, so that is where it goes.
_ALIASES: dict[str, Alert] = {
    "note": Alert.NOTE,
    "notes": Alert.NOTE,
    "notice": Alert.NOTE,
    "remember": Alert.NOTE,
    "othernote": Alert.NOTE,
    "tip": Alert.TIP,
    "hint": Alert.TIP,
    "fastpath": Alert.TIP,
    "important": Alert.IMPORTANT,
    "attention": Alert.IMPORTANT,
    "restriction": Alert.IMPORTANT,
    "warning": Alert.WARNING,
    "trouble": Alert.WARNING,
    "caution": Alert.CAUTION,
    "danger": Alert.CAUTION,
}


def alert_for(label: str) -> Alert | None:
    """The alert a source label maps to, or None if the vocabulary has not seen it.

    Matched case-insensitively and with punctuation stripped, because the label
    arrives as rendered prose as often as as a class name: `Note:`, `NOTE`,
    `div.noteWarning` and DITA's `@type="warning"` are one thing four ways.
    """
    folded = "".join(ch for ch in label.lower() if ch.isalpha())
    return _ALIASES.get(folded)


def _opens_table(line: str) -> bool:
    """Whether a body line starts a pipe table.

    The one block that must not follow the label directly: GFM would read the
    label line as the table's header row. Every other block -- prose, a list, a
    fence, a heading -- either joins the label's paragraph or interrupts it.
    """
    return line.lstrip().startswith("|")


def render(kind: Alert, body: str, label: str | None = None) -> str:
    """One admonition: the bold label, then the body quoted line by line.

    `label` is an authored word that says more than the kind (`Remember`,
    `Fastpath`); without one the kind's own word is used. A trailing colon is
    the label's punctuation, written once here.

    The body starts on the line after the label with no blank line between, so
    the two read as one paragraph -- except before a table (`_opens_table`). A
    blank line further *inside* the body must still carry the `>` or the quote
    ends there and the rest of the admonition renders as body text -- which is how
    a two-paragraph warning becomes one paragraph of warning and one of prose.
    """
    word = (label or "").strip().rstrip(":").strip() or kind.label
    lines = body.strip("\n").split("\n")
    head = [f"> **{word}:**"]
    if _opens_table(lines[0]):
        head.append(">")
    quoted = [f"> {line}".rstrip() for line in lines]
    return "\n".join([*head, *quoted])


# -- repairing Markdown written with `> [!KIND]` (Phase 56) --------------------

#: The quote prefix of a line: any indent (a note inside a list item), an optional
#: list marker (a note opening a list item, `- > [!IMPORTANT]`), then one or more
#: `>` with any spaces between them (`>    > [!NOTE]`, a note in a list item inside
#: a note). Group `quote` is reused verbatim, so the rewritten line sits exactly
#: where the old one did. The list marker and the wide spacing were added when the
#: Container Editions wave left three such notes unlabelled (2026-10-25).
_QUOTE = r"(?P<quote>[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+)?(?:>[ \t]*)+)"
_MARKER = re.compile(rf"^{_QUOTE}\[!(?P<kind>[A-Za-z]+)\][ \t]*$")
_LABEL_LINE = re.compile(rf"^{_QUOTE}\*\*(?P<word>[^*\n]+?):\*\*[ \t]*$")
#: An authored label the engine put first in the body (`**Remember:** text`): DITA
#: wrote one wherever the label said more than the kind. The colon is required --
#: DocBook's captions (`**Caution 2**`) are titles, not labels, and have none.
_RUN_IN = re.compile(rf"^{_QUOTE}\*\*(?P<word>[^*\n]+?):\*\*(?:[ \t]+(?P<rest>.*))?$")
_FENCE = re.compile(r"^[ \t]*(?:>[ \t]?)*[ \t]*(?P<fence>`{3,}|~{3,})")


def _depth(quote: str) -> int:
    return quote.count(">")


_BULLET = re.compile(r"^([ \t]*)((?:[-*+]|\d+[.)])[ \t]+)")


def _continued(quote: str) -> str:
    """`quote` as a following line writes it: a list marker becomes its width in
    spaces, or the line would open a new list item (`- >` under `- > **Note:**`)."""
    return _BULLET.sub(lambda m: m[1] + " " * len(m[2]), quote, count=1)


def _blank_quote(line: str, depth: int) -> bool:
    """A quote line with nothing in it, at exactly `depth`."""
    stripped = line.rstrip("\r\n")
    return stripped.strip(" \t>") == "" and ">" in stripped and _depth(stripped) == depth


def _eol(line: str) -> str:
    return line[len(line.rstrip("\r\n")):]


@dataclass
class Fixed:
    """What `fix_markdown` changed in one text."""

    original: str
    text: str = ""
    markers: int = 0
    blanks: int = 0
    #: Notes that open with a table, so keep one blank line after the label.
    tables: int = 0

    @property
    def changed(self) -> bool:
        return self.text != self.original


def fix_markdown(text: str) -> Fixed:
    """`text` with every `> [!KIND]` marker made a bold label, as `render` writes it.

    Touches only marker lines and the line after a label: a blank quote line there
    is dropped, unless a table follows (`_opens_table`), and an authored
    `**Remember:**` opening the body becomes the label. Lines inside a fenced code
    block are content and are left alone. Line endings are kept as found, and a
    second run changes nothing.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    result = Fixed(text, text)
    fence = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        bare = line.rstrip("\r\n")
        opened = _FENCE.match(bare)
        if fence:
            if opened and opened["fence"][0] == fence[0] and len(opened["fence"]) >= len(fence):
                fence = ""
            out.append(line)
            i += 1
            continue
        if opened:
            fence = opened["fence"]
            out.append(line)
            i += 1
            continue

        marker = _MARKER.match(bare)
        labelled = None if marker else _LABEL_LINE.match(bare)
        if labelled and alert_for(labelled["word"]) is None:
            labelled = None
        if not marker and not labelled:
            out.append(line)
            i += 1
            continue

        found = marker or labelled
        quote = found["quote"]
        depth = _depth(quote)
        i += 1
        if marker:
            kind = alert_for(marker["kind"]) or Alert.NOTE
            word = kind.label
            result.markers += 1
            run_in = _RUN_IN.match(lines[i].rstrip("\r\n")) if i < len(lines) else None
            if run_in and _depth(run_in["quote"]) == depth and alert_for(run_in["word"]) is not None:
                word = run_in["word"].strip()
                rest = run_in["rest"]
                if rest:
                    lines[i] = f"{run_in['quote']}{rest}{_eol(lines[i])}"
                else:
                    i += 1
            label_line = f"{quote}**{word}:**{_eol(line)}"
        else:
            label_line = line

        blanks = 0
        while i + blanks < len(lines) and _blank_quote(lines[i + blanks], depth):
            blanks += 1
        following = lines[i + blanks] if i + blanks < len(lines) else ""
        i += blanks
        out.append(label_line)
        if _opens_table(following.lstrip(" \t>")):
            # Exactly one blank quote line, whatever was there: none would make
            # the label the table's header row.
            result.tables += 1
            result.blanks += max(blanks - 1, 0)
            out.append(f"{_continued(quote).rstrip()}{_eol(line) or chr(10)}")
        else:
            result.blanks += blanks
    result.text = "".join(out)
    return result
