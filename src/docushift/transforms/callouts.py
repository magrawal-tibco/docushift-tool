"""Admonitions to GitHub alerts.

GitHub renders exactly five (`NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`), so
the vocabulary is closed and lives here rather than in each engine. What each
engine has to do to *find* an admonition is entirely its own -- Flare's label is a
`data-mc-autonum` attribute the skin's CSS renders and must be recovered
(`architecture.md` §5.1.8), DITA's is a `span.*title` that must be deleted because
leaving it duplicates the label (§5.2.5), and WebWorks' is a `div.Icon<Kind>` in
the *first* cell of a `table.IconTable` whose prose is in the second (§5.3.7). All
three then arrive here with a label string and a body.

**An unmapped label falls back to `NOTE` and is reported**, never dropped. A
label the tool has not seen is evidence about the corpus; silently rendering it as
a plain blockquote loses both the label and the fact that it existed.
"""

from enum import StrEnum


class Alert(StrEnum):
    """The five GitHub renders. There is no sixth, so there is no fallback kind."""

    NOTE = "NOTE"
    TIP = "TIP"
    IMPORTANT = "IMPORTANT"
    WARNING = "WARNING"
    CAUTION = "CAUTION"


# DITA's admonition vocabulary is the widest of the three (13 `@type` values), so
# it sets the shape of this table; Flare's four and WebWorks' icon names fall
# inside it. Mapped by meaning rather than by name: `danger` is stronger than
# `warning` and GitHub's strongest is `CAUTION`, so that is where it goes.
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


def render(kind: Alert, body: str) -> str:
    """One GFM alert. The body is quoted line by line, blank lines included.

    A blank line inside a blockquote must still carry the `>` or the quote ends
    there and the rest of the admonition renders as body text -- which is how a
    two-paragraph warning becomes one paragraph of warning and one of prose.
    """
    lines = body.strip("\n").split("\n")
    quoted = "\n".join(f"> {line}".rstrip() for line in lines)
    return f"> [!{kind}]\n{quoted}"
