"""HTML to GitHub-Flavored Markdown: the walk all three engines share.

Phase 5a built the six *decisions* that differ by construct -- alerts, tables,
code fences, links, assets, CSH -- and deliberately built no walker, because at
that point nothing walked. Phase 5b needs one, and putting it in `flare.py` would
mean DITA and WebWorks each writing a third paragraph-and-list renderer whose
disagreements would surface as three different Markdown dialects in one repo.

So the walk is here and the *vocabulary* is the engine's, through four hooks:

- `block_override(tag)` / `inline_override(tag)` -- the engine claims a construct
  before the generic dispatch sees it. Flare's `div.noteWarning` is an alert here
  and a plain `div` everywhere else.
- `link(tag)` / `image(tag)` -- the URL, or `None` to keep the text and drop the
  link. Resolution is invariant 13's business (`transforms/assets.py`), which is
  why this module never touches the filesystem and never emits a URL it invented.

Two rules in here are corpus-measured rather than conventional:

- **A table that is not GFM-safe is emitted as HTML** (`transforms/tables.py`);
  43% of Flare's tables take that branch.
- **Text is escaped narrowly.** `\\`, `` ` ``, `*`, `[`, `]` and `<` always, and a
  block-starting character only when it actually starts a line. Escaping `_` as
  well -- the obvious wider net -- would put a backslash inside every
  `MY_ENV_VAR` in a corpus whose subject matter is configuration files, and GFM
  gives no intra-word emphasis to `_` anyway.
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import PreformattedString

from docushift.transforms import code as code_transform
from docushift.transforms import tables as tables_transform

# The parser every engine uses. `lxml` for speed and for its tolerance of the
# unclosed tags a 2009 authoring tool emits, at the cost of the workaround below.
PARSER = "lxml"

# MadCap uses `<![CDATA[ ]]>` as a literal-text carrier -- and `lxml` deletes the
# section outright, because CDATA is not a thing in HTML. In a 3,411-file sample
# 130 files carry 300 sections: 170 hold nothing but the space that separates a
# word from the inline `<span>` after it, 130 hold plain text, and **none hold
# markup**. Left to the parser, "ensure that the `libjvm` library" loses its space
# and 130 sections lose their words, so the section is unwrapped before parsing
# and its contents are escaped -- text in, text out, whatever an unsampled one
# turns out to contain.
_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)

_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

# Containers with no meaning of their own: recursed into, never emitted. A `div`
# is the whole of Flare's block structure, so this is the main path.
_TRANSPARENT = frozenset({
    "div", "section", "article", "main", "aside", "header", "footer", "nav",
    "figure", "figcaption", "form", "fieldset", "center", "body", "html",
})

_BLOCKS = _TRANSPARENT | set(_HEADINGS) | {
    "p", "ul", "ol", "dl", "dt", "dd", "li", "pre", "table", "blockquote", "hr",
}

# Emitted as raw HTML because GFM has no syntax for them and dropping the tag
# changes what the text says (`H<sub>2</sub>O`).
_KEEP_AS_HTML = frozenset({"sub", "sup"})

# The hard line break, emitted for `<br>`: a backslash rather than two trailing
# spaces, because invisible whitespace is the one Markdown construct an editor
# silently eats.
_BREAK = "\\\n"

_WHITESPACE = re.compile(r"\s+")
_ESCAPES = re.compile(r"([\\`*\[\]<])")
# Only what would start a *block* if it led a line. Applied per line, after the
# inline run is assembled, because that is the only point at which "leads a line"
# is a fact rather than a guess.
_LEADING = re.compile(r"^(\s*)([#>+=|-]|\d+[.)])(\s|$)")


def parse(text: str) -> BeautifulSoup:
    """Parses one source topic. The engines' single entry point to bs4."""
    return BeautifulSoup(_CDATA.sub(_unwrap_cdata, text), PARSER)


def _unwrap_cdata(match: re.Match[str]) -> str:
    body = match.group(1)
    return body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def is_text(node: object) -> bool:
    """Is this node visible text?

    `Comment`, `CData`, `Doctype` and `ProcessingInstruction` are all
    `NavigableString` subclasses in bs4, so the obvious `isinstance` test is true
    for every one of them and emits their contents into the prose. Real corpus
    topics carry `<![CDATA[ ]]>` inside content and commented-out markup beside
    it, so this is the difference between a paragraph and a paragraph followed by
    a stylesheet.
    """
    return isinstance(node, NavigableString) and not isinstance(node, PreformattedString)


def escape(text: str) -> str:
    """Escapes the inline metacharacters, and nothing else."""
    return _ESCAPES.sub(r"\\\1", text)


def escape_leading(text: str) -> str:
    """Escapes a block-starting character that ended up at the start of a line."""
    return "\n".join(_LEADING.sub(r"\1\\\2\3", line) for line in text.split("\n"))


def text_of(node: Tag) -> str:
    """The visible text of a subtree, with `<br>` as a real newline.

    `get_text()` drops the break, which turns a `<pre>` of shell commands into one
    unrunnable line -- the predecessor carries the same fix as its twelfth pass.
    """
    parts: list[str] = []
    for descendant in node.descendants:
        if is_text(descendant):
            parts.append(str(descendant))
        elif isinstance(descendant, Tag) and descendant.name == "br":
            parts.append("\n")
    return "".join(parts)


class Renderer:
    """Walks a parsed subtree and emits GFM blocks. Subclassed per engine."""

    # -- hooks -----------------------------------------------------------------

    def block_override(self, tag: Tag) -> str | None:
        """The engine's answer for this element in block position, or None."""
        return None

    def inline_override(self, tag: Tag) -> str | None:
        """The engine's answer for this element in inline position, or None."""
        return None

    def link(self, tag: Tag) -> str | None:
        """The URL for an `<a>`, or None to emit its text unlinked."""
        href = tag.get("href")
        return str(href) if href else None

    def image(self, tag: Tag) -> str | None:
        """The URL for an `<img>`, or None to emit nothing at all."""
        src = tag.get("src")
        return str(src) if src else None

    # -- blocks ----------------------------------------------------------------

    def render(self, node: Tag) -> str:
        """Every block under `node`, blank-line separated."""
        return "\n\n".join(self.blocks(node))

    def blocks(self, node: Tag) -> list[str]:
        """`node`'s children as a list of Markdown blocks.

        Loose inline content between block elements is gathered into a paragraph
        rather than dropped: MadCap emits bare text beside a `<table>` often
        enough that discarding it would lose sentences.
        """
        out: list[str] = []
        run: list[str] = []

        def flush() -> None:
            text = _collapse("".join(run)).strip()
            run.clear()
            if text:
                out.append(escape_leading(text))

        for child in node.children:
            if is_text(child):
                run.append(escape(str(child)))
                continue
            if not isinstance(child, Tag):
                continue
            override = self.block_override(child)
            if override is not None:
                flush()
                if override.strip():
                    out.append(override)
                continue
            if child.name not in _BLOCKS:
                run.append(self.inline(child))
                continue
            flush()
            out.extend(self._block(child))
        flush()
        return out

    def _block(self, tag: Tag) -> list[str]:
        name = tag.name
        if name in _TRANSPARENT:
            return self.blocks(tag)
        if name in _HEADINGS:
            text = self.inline_children(tag).strip()
            return [f"{'#' * _HEADINGS[name]} {text}"] if text else []
        if name == "p" or name == "dd" or name == "li":
            return self.blocks(tag)
        if name == "dt":
            term = self.inline_children(tag).strip()
            return [f"**{term}**"] if term else []
        if name in ("ul", "ol"):
            return [self.list(tag, ordered=name == "ol")]
        if name == "dl":
            return self.blocks(tag)
        if name == "pre":
            return [code_transform.fence(text_of(tag))]
        if name == "blockquote":
            inner = self.blocks(tag)
            return ["\n".join(_quote(block) for block in inner)] if inner else []
        if name == "hr":
            return ["---"]
        if name == "table":
            rendered = self.table(tag)
            return [rendered] if rendered.strip() else []
        return self.blocks(tag)  # pragma: no cover - _BLOCKS and this switch agree

    def list(self, tag: Tag, ordered: bool) -> str:
        """One list. Nested lists arrive as blocks of their `<li>` and indent."""
        items: list[str] = []
        for number, child in enumerate(tag.find_all("li", recursive=False), start=1):
            marker = f"{number}. " if ordered else "- "
            blocks = self.blocks(child) or [""]
            body = "\n\n".join(blocks)
            items.append(marker + _indent(body, len(marker)))
        if not items:
            return ""
        # Loose lists (blank line between items) render every item as a paragraph;
        # a list whose items are one block each stays tight, which is what a
        # procedure should look like.
        loose = any("\n\n" in item for item in items)
        return ("\n\n" if loose else "\n").join(items)

    def table(self, tag: Tag) -> str:
        """A pipe table where GFM can carry it, the original HTML where it cannot."""
        model = tables_transform.read(tag)
        if tables_transform.is_gfm_safe(model):
            return tables_transform.to_pipe(model, self.inline_children)
        return tables_transform.passthrough(self.rewrite(tag))

    def rewrite(self, tag: Tag) -> Tag:
        """Resolves the references inside a subtree that is emitted as raw HTML.

        Invariant 13 does not stop at the edge of a pipe table. 43% of Flare's
        tables cannot be one, and passing their source HTML through unchanged
        would emit `src="images/x.png"` -- a path in the *source* layout, pointing
        at a file nothing ever copied, in the one branch where no hook was
        consulted. The subtree is mutated in place, which is safe because it is
        discarded as soon as the topic is rendered.
        """
        for image in tag.find_all("img"):
            url = self.image(image)
            if url:
                image["src"] = url
            else:
                image.decompose()
        for anchor in tag.find_all("a"):
            url = self.link(anchor)
            if url:
                anchor["href"] = url
            else:
                # The text was authored and stays; only the claim that it leads
                # somewhere is dropped.
                anchor.unwrap()
        return tag

    # -- inline ----------------------------------------------------------------

    def inline_children(self, tag: Tag) -> str:
        return _collapse("".join(self._inline_node(child) for child in tag.children))

    def inline(self, node: Tag) -> str:
        return self._inline_node(node)

    def _inline_node(self, node: object) -> str:
        if is_text(node):
            return escape(str(node))
        if not isinstance(node, Tag):
            return ""
        override = self.inline_override(node)
        if override is not None:
            return override
        name = node.name
        if name == "br":
            return _BREAK
        if name in ("script", "style"):
            return ""
        if name == "a":
            return self._anchor(node)
        if name == "img":
            return self._image(node)
        if name in ("strong", "b"):
            return wrap(self.inline_children(node), "**")
        if name in ("em", "i", "cite", "var", "dfn"):
            return wrap(self.inline_children(node), "*")
        if name in ("del", "s", "strike"):
            return wrap(self.inline_children(node), "~~")
        if name in ("code", "tt", "kbd", "samp"):
            return code_transform.inline(text_of(node))
        if name in _KEEP_AS_HTML:
            inner = self.inline_children(node).strip()
            return f"<{name}>{inner}</{name}>" if inner else ""
        return self.inline_children(node)

    def _anchor(self, tag: Tag) -> str:
        text = self.inline_children(tag).strip()
        url = self.link(tag)
        if not url:
            return text
        if not text:
            # A link with no text is either an anchor target or a broken one;
            # emitting `[](url)` renders as nothing and hides both.
            return ""
        return f"[{text}]({url})"

    def _image(self, tag: Tag) -> str:
        url = self.image(tag)
        if not url:
            return ""
        alt = _collapse(str(tag.get("alt", ""))).strip()
        return f"![{escape(alt)}]({url})"


def _collapse(text: str) -> str:
    """Browser whitespace rules: any run of it is one space, hard breaks survive.

    Collapsing has to happen *around* an already-emitted `<br>` rather than over
    it, or the break -- which is a backslash and a newline -- becomes a backslash
    and a space, and the line it ended runs into the next one.
    """
    parts = [_WHITESPACE.sub(" ", part) for part in text.split(_BREAK)]
    if len(parts) == 1:
        return parts[0]
    last = len(parts) - 1
    trimmed = [
        (part.lstrip() if index else part).rstrip() if index < last else part.lstrip()
        for index, part in enumerate(parts)
    ]
    return _BREAK.join(trimmed)


def wrap(text: str, marker: str) -> str:
    """Emphasis, with the surrounding spaces moved outside the markers.

    `** bold **` is not bold in any GFM renderer, and MadCap's spans routinely
    include the trailing space.
    """
    stripped = text.strip()
    if not stripped:
        return " " if text else ""
    lead = " " if text[:1].isspace() else ""
    tail = " " if text[-1:].isspace() else ""
    return f"{lead}{marker}{stripped}{marker}{tail}"


def _indent(text: str, width: int) -> str:
    pad = " " * width
    lines = text.split("\n")
    return "\n".join([lines[0]] + [(pad + line).rstrip() for line in lines[1:]])


def _quote(block: str) -> str:
    return "\n".join(f"> {line}".rstrip() for line in block.split("\n"))
