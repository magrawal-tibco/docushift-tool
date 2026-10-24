"""What a page says, as plain text, and whether one page says everything another did.

Both sides are reduced to **blocks** -- a paragraph, a list item, a table cell, a
heading -- of normalised words. A block boundary is where a shingle stops, so a
table compared cell by cell matches however Markdown or AEM reorders the text
between cells (`planning.md` Phase 55, A2).

A source sentence is **present** when its normalised text is a substring of the
target, or when at least `SHINGLE_HIT` of its 8-word shingles occur in the target.
The second rule forgives a changed word or two -- an expanded variable, a smart
quote the normaliser missed -- without forgiving a dropped clause. A page is
flagged by the sentences it lost, never by a percentage: one changed word on a
60-word page costs ~15% of its shingles, so a percentage cut-off flags every short
page (Phase 55, Decisions).
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

SHINGLE = 8
#: Share of a sentence's shingles the target must hold for the sentence to count.
SHINGLE_HIT = 0.8
#: A "sentence" shorter than this is a label, not prose -- `Note`, `Step 1` -- and
#: is never reported missing on its own.
MIN_SENTENCE_WORDS = 4

#: Elements whose text joins the surrounding run. **Everything else is a block**:
#: listing the inline set rather than the block set is what keeps a Flare table's
#: `tbody` -- or any wrapper nobody listed -- from fusing a whole table into one
#: block, which no shingle of a single cell can then match.
INLINE = frozenset({
    "a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "del", "dfn", "em", "font",
    "i", "ins", "kbd", "label", "mark", "q", "s", "samp", "small", "span", "strong",
    "sub", "sup", "time", "tt", "u", "var", "wbr", "nobr",
})
#: Never content, on either side.
DROPPED = ("script", "style", "noscript", "template", "svg", "button", "input", "select")

_QUOTES = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2010": "-", "\u2011": "-",
    "\u00a0": " ", "\u2009": " ", "\u200b": "", "\u00ad": "", "\u2026": "...",
    "\u2122": "", "\u00ae": "", "\u00a9": "",
})
_WORD = re.compile(r"[a-z0-9]+(?:['.\-_/][a-z0-9]+)*")
_ALNUM = re.compile(r"[a-z0-9]+")
_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+(?=\S)")


def normalise(text: str) -> str:
    """Lowercase, NFKC, straight quotes and dashes, trademark signs gone, one space."""
    folded = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    return " ".join(folded.split())


def words(text: str) -> list[str]:
    """The comparable words of `text`: letters and digits, punctuation dropped.

    Punctuation is noise across a conversion -- `**Note:**` and a skin-drawn
    `Note` are one word -- so it is not compared at all.
    """
    return _WORD.findall(normalise(text))


def shingles(tokens: list[str], size: int = SHINGLE) -> set[tuple[str, ...]]:
    """Every run of `size` consecutive tokens; the whole run when it is shorter."""
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def sentences(block: str) -> list[str]:
    """`block` split after `.`, `!`, `?`, `:` or `;` -- prose, roughly, which is enough."""
    return [part.strip() for part in _SENTENCE_END.split(block) if part.strip()]


@dataclass
class Text:
    """One page's text as blocks, plus the indexes a comparison needs."""

    blocks: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._joined = ""
        self._compact = ""
        self._shingles: set[tuple[str, ...]] | None = None

    @property
    def compact(self) -> str:
        """The page's letters and digits only, block breaks and word breaks gone (Phase 60)."""
        if not self._compact:
            self._compact = "".join(_compact(block) for block in self.blocks)
        return self._compact

    @property
    def joined(self) -> str:
        """Every block's words, space-separated, with ` | ` between blocks."""
        if not self._joined:
            self._joined = " | ".join(" ".join(words(block)) for block in self.blocks)
        return self._joined

    @property
    def shingle_set(self) -> set[tuple[str, ...]]:
        if self._shingles is None:
            found: set[tuple[str, ...]] = set()
            for block in self.blocks:
                found |= shingles(words(block))
            self._shingles = found
        return self._shingles

    @property
    def word_count(self) -> int:
        return sum(len(words(block)) for block in self.blocks)


@dataclass
class Coverage:
    """How much of a source page's text a target page holds."""

    source_words: int = 0
    present_words: int = 0
    missing: list[str] = field(default_factory=list)

    @property
    def percent(self) -> float:
        return 100.0 if not self.source_words else round(100.0 * self.present_words / self.source_words, 1)


def present(sentence: str, target: Text) -> bool:
    tokens = words(sentence)
    if not tokens:
        return True
    if f" {' '.join(tokens)} " in f" {target.joined} ":
        return True
    # The same letters in the same order, only the breaks differ (Phase 60): a source
    # that runs a label into its text ("ResultYou") against "**Result** You"; a
    # `<span>` splitting `wfs-etc-9.3.7`; a sentence a hard break or a `\` line
    # continuation splits into two blocks on the page. The cost: a page that lost
    # the spaces between words reads as present here.
    if len(tokens) >= MIN_SENTENCE_WORDS and _compact(sentence) in target.compact:
        return True
    if len(tokens) < SHINGLE:
        return False
    mine = shingles(tokens)
    return len(mine & target.shingle_set) >= SHINGLE_HIT * len(mine)


def _compact(text: str) -> str:
    return "".join(_ALNUM.findall(normalise(text)))


def coverage(source: Text, target: Text, ignore: frozenset[str] = frozenset()) -> Coverage:
    """Which of `source`'s sentences `target` holds. `ignore`: normalised sentences
    the conversion is known to drop or rewrite on purpose (Phase 55, A2)."""
    result = Coverage()
    for block in source.blocks:
        for sentence in sentences(block):
            tokens = words(sentence)
            if not tokens:
                continue
            result.source_words += len(tokens)
            if " ".join(tokens) in ignore or present(sentence, target):
                result.present_words += len(tokens)
            elif len(tokens) >= MIN_SENTENCE_WORDS:
                result.missing.append(" ".join(sentence.split()))
            else:
                result.present_words += len(tokens)
    return result


# -- HTML ---------------------------------------------------------------------


def html_blocks(container: Tag) -> list[str]:
    """The text of `container`, one string per block element, hidden text included.

    Hidden text is content: a Flare dropdown or toggler holds its body in the
    page with `display:none`, and the converter keeps it (Phase 55, A2).
    """
    for name in DROPPED:
        for tag in container.find_all(name):
            tag.decompose()
    out: list[str] = []

    def walk(node: Tag) -> None:
        run: list[str] = []
        for child in node.children:
            if isinstance(child, Tag):
                name = child.name.lower()
                if name == "br":
                    run.append(" ")
                elif name == "img":
                    continue
                # `madcap:variable` and kin are text in a run; any other
                # namespaced element is a container, like a `div`.
                elif name in INLINE or name in ("madcap:variable", "madcap:xref", "madcap:keyword"):
                    run.append(_inline_text(child))
                else:
                    flush(run)
                    walk(child)
            elif type(child) is NavigableString:
                # Exactly the text type: a Comment, CData or doctype is a
                # NavigableString subclass and is never page text.
                run.append(str(child))
        flush(run)

    def flush(run: list[str]) -> None:
        text = " ".join("".join(run).split())
        if text:
            out.append(text)
        run.clear()

    walk(container)
    return out


def _inline_text(tag: Tag) -> str:
    return "".join(str(s) for s in tag.descendants if type(s) is NavigableString)


def html_text(html: str, selector: str, drop: tuple[str, ...] = ()) -> Text | None:
    """The blocks inside the first `selector` match, or None if nothing matches.

    `drop` is CSS selectors removed first -- page chrome *inside* the container.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(selector)
    if container is None:
        return None
    for css in drop:
        for tag in container.select(css):
            tag.decompose()
    return Text(html_blocks(container))


# -- Markdown -----------------------------------------------------------------

_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# Not an escaped `\<`: `\<webfocus-ce>/scripts` renders "<webfocus-ce>/scripts", and
# deleting it as a tag read the sentence as dropped (Phase 60).
_TAG = re.compile(r"(?<!\\)<[^>]+>")
# A cell boundary, but not a `\|` inside a cell (Phase 60).
_CELL = re.compile(r"(?<!\\)\|")
_PREFIX = re.compile(r"^[ \t]*(?:>[ \t]?)*[ \t]*(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+[.)][ \t]+)?")
_FENCE = re.compile(r"^[ \t>]*(`{3,}|~{3,})")
_RULE = re.compile(r"^[ \t>]*(?:[-*_][ \t]*){3,}$")
_TABLE_RULE = re.compile(r"^[ \t>]*\|?[ \t:]*-{3,}[ \t:]*(\|[ \t:]*-{3,}[ \t:]*)*\|?[ \t]*$")
_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
#: A GitHub alert marker. Not page text on either side: AEM drops it (Phase 56,
#: counted by `published.py` as its own finding), and a source note has no such word.
_ALERT = re.compile(r"\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", re.IGNORECASE)


def markdown_text(text: str) -> Text:
    """The blocks of a Markdown page: one per paragraph, list item, heading or cell.

    Markup is stripped by pattern, not rendered -- this has to read the converter's
    output without trusting the converter's renderer. Image syntax is dropped
    (images are compared by `images.py`, and an `alt` is not page text in the
    source either); link text is kept and the destination dropped.
    """
    body = _FRONTMATTER.sub("", text, count=1)
    blocks: list[str] = []
    paragraph: list[str] = []
    fence = ""

    def flush() -> None:
        joined = " ".join(" ".join(paragraph).split())
        if joined:
            blocks.append(joined)
        paragraph.clear()

    for raw in body.splitlines():
        opened = _FENCE.match(raw)
        if fence:
            if opened and opened.group(1)[0] == fence[0]:
                fence = ""
                flush()
            else:
                paragraph.append(raw.strip())
            continue
        if opened:
            flush()
            fence = opened.group(1)
            continue
        if not raw.strip(" \t>") or _RULE.match(raw) or _TABLE_RULE.match(raw):
            flush()
            continue
        line = _inline(raw)
        stripped = raw.lstrip(" \t>")
        if stripped.startswith("|"):
            flush()
            cells = (" ".join(_inline(c).split()) for c in _CELL.split(stripped.strip().strip("|")))
            blocks.extend(cell for cell in cells if cell)
            continue
        if _PREFIX.match(raw).group(0).strip(" \t>"):
            flush()  # a heading or a list item starts a block of its own
        # A hard line break -- a trailing backslash or two spaces -- ends a block:
        # AEM renders `**Question?**\` and its answer as two (2026-10-23).
        hard = raw.endswith(("\\", "  "))
        paragraph.append(_PREFIX.sub("", line, count=1).rstrip().removesuffix("\\"))
        if hard:
            flush()
    flush()
    return Text([block for block in blocks if block.strip()])


_CODE_SPAN = re.compile(r"(`+)(.+?)\1")


def _inline(line: str) -> str:
    """One line with its inline markup gone. A code span is kept verbatim: inside
    backticks `<install-root>` is text, not a tag, and `config\\.env` keeps its
    backslash."""
    out: list[str] = []
    at = 0
    for span in _CODE_SPAN.finditer(line):
        out.append(_markup(line[at:span.start()]))
        out.append(span.group(2))
        at = span.end()
    out.append(_markup(line[at:]))
    return "".join(out)


def _markup(part: str) -> str:
    part = _ALERT.sub(" ", part)
    part = _IMAGE.sub(" ", part)
    part = _LINK.sub(r"\1", part)
    part = _TAG.sub(" ", part)
    # Raw HTML in a page writes `&lt;webfocus-ce&gt;`; the source's text is the
    # character (Phase 60). After the tags are gone, so a decoded `<` is text.
    part = html.unescape(part)
    part = _ESCAPE.sub(r"\1", part)
    return part.replace("**", "").replace("__", "")


def cut_at(text: Text, labels: frozenset[str]) -> Text:
    """`text` up to its first block that *is* one of `labels` (normalised).

    The Flare landing page's doc-portal sections, which the converter cuts the
    same way (`engines/flare.py::_trim_portal`, `PORTAL_BLOCKS`).
    """
    kept: list[str] = []
    for block in text.blocks:
        if " ".join(words(block)) in labels:
            break
        kept.append(block)
    return Text(kept)
