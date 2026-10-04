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
import unicodedata
from collections import Counter
from collections.abc import Iterable

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
# Whitespace and hard breaks at the ends of a run, where a break means nothing.
# After `_collapse` every newline is part of a break, and a text backslash is
# always escaped as a pair, so a backslash followed by a newline is a break.
_EDGE_BREAKS = re.compile(r"^(?:\s|\\\n)+|(?:\s|\\\n)+$")
_EDGES = re.compile(r"((?:\s|\\\n)*)(.*?)((?:\s|\\\n)*)", re.DOTALL)

# What `_join_inline` puts between two inline runs that would otherwise fuse: an
# empty comment, which every renderer drops and every slug rule strips as a tag.
_SEAM = "<!-- -->"
_DELIMITERS = "*`~"

# Embedded media and drawings. GFM has no syntax for any of them, so the walk
# could only emit their fallback text or nothing -- an `<iframe>` of a video
# vanished whole. Each is counted, and one with an absolute URL becomes a link
# to it (Phase 34, R8-13). None was found in the five families measured, which is
# why this is a count rather than a construct.
_UNRENDERED = frozenset({"iframe", "video", "audio", "object", "embed", "svg", "canvas", "math"})

# The `<ol type>` values GFM has no marker for. `1` is what GFM draws anyway.
_NUMBERING = frozenset({"a", "A", "i", "I"})

_WHITESPACE = re.compile(r"\s+")
_ESCAPES = re.compile(r"([\\`*\[\]<])")
# Only what would start a *block* if it led a line. Applied per line, after the
# inline run is assembled, because that is the only point at which "leads a line"
# is a fact rather than a guess.
_LEADING = re.compile(r"^(\s*)([#>+=|-]|\d+[.)])(\s|$)")

# An anchor *target* this module emitted, recognisable so a heading can hoist it
# back out. Written with `id=` rather than Flare's `name=`: HTML5 dropped `name`
# on `<a>`, so no modern renderer resolves it. (Since Phase 29 `validate` counts
# no attribute as an anchor at all: `ANCHOR_MISSING` is a fragment naming no
# heading.)
_MARKER = re.compile(r'<a id="[^"]*"></a>')


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


def anchor_target(tag: Tag) -> str:
    """The fragment `tag` is a destination for, or `""` if it is not one.

    An `<a>` with no `href` is not a broken link, it is a place other pages point
    at, and Flare writes every one of its cross-references that way:
    `<a name="ID-2FC4B4A1"></a>`. Both spellings are read because the corpus
    mixes them and because an engine may have modernised its own output.
    """
    for attribute in ("name", "id"):
        value = tag.get(attribute)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def anchor_marker(target: str) -> str:
    """`target` as the inline HTML that makes `#target` resolve in the output."""
    return f'<a id="{_html_escape(target)}"></a>' if target else ""


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

    # How many links this walk flattened into a fence. A GFM fence cannot hold a
    # link at all, so a `<pre>` that contains one loses it -- 4,964 of the 13,126
    # swallowed references measured for Phase 8, nearly all of them the return
    # type in a C signature. Counted rather than recorded one by one, and read by
    # the engine after the walk: the residue of a fix has to be a number in the
    # run report rather than a paragraph in a design document.
    flattened_links = 0

    @property
    def unrendered(self) -> Counter[str]:
        """Elements this walk had no Markdown for, by tag (R8-13).

        Read by the engine after the walk, as `flattened_links` is. Kept per
        instance rather than on the class, where every renderer would share it.
        """
        return self.__dict__.setdefault("_unrendered", Counter())

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
        return self._gather(node.children)

    def _gather(self, children: Iterable[object]) -> list[str]:
        """`blocks` over any run of sibling nodes, not only a whole element's."""
        out: list[str] = []
        run: list[str] = []

        def flush() -> None:
            text = _trim(_collapse(_join_inline(run)))
            run.clear()
            if text:
                out.append(escape_leading(text))

        for child in children:
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
            # A target inside a heading is hoisted above it rather than left in
            # the line. `slugify_heading` reads the raw title, so `## <a
            # id="X"></a>Configuring Users` would change `#configuring-users` --
            # breaking every fragment that resolves today in the act of fixing
            # 424 that do not. Out here both anchors work and the slug is the
            # same string it was. A `<br>` is a space: a heading is one line, and
            # a break in it split the title from its second half (R8-13).
            inline = _trim(self.inline_children(tag)).replace(_BREAK, " ")
            markers = "".join(_MARKER.findall(inline))
            text = _MARKER.sub("", inline).strip()
            out = [markers] if markers else []
            if text:
                out.append(f"{'#' * _HEADINGS[name]} {text}")
            return out
        if name == "p" or name == "dd" or name == "li":
            return self.blocks(tag)
        if name == "dt":
            term = _trim(self.inline_children(tag)).replace(_BREAK, " ")
            return [f"**{term}**"] if term else []
        if name in ("ul", "ol"):
            listed = self.list(tag, ordered=name == "ol")
            return [listed] if listed else []
        if name == "dl":
            return self.blocks(tag)
        if name == "pre":
            # The fence keeps its links' *words* and loses the links. Emitting the
            # block as passthrough HTML instead -- one call, exactly what `table`
            # below does -- would recover them at the cost of turning every such
            # block into an HTML blob, and in this corpus the link is a decorative
            # type cross-reference inside a function signature. The trade is
            # recorded rather than hidden: see `flattened_links`.
            self.flattened_links += len(tag.find_all("a", href=True))
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
        """One list. Nested lists arrive as blocks of their `<li>` and indent.

        An ordered list honours `start`. Flare's step tables carry their drawn
        number, and a procedure interrupted by a note or a paragraph resumes at
        step 3 -- emitted from 1, 110 of 1,285 numbered items in the families
        carried the wrong number (R5-02).

        **Everything in the list is read, not only its `<li>`s** (Phase 34,
        R8-01). A paragraph, a `<pre>`, a note or a nested `<ul>` written straight
        into the list belongs to the item before it, which is where a browser
        draws it; ahead of the first item it leads the list. Reading `<li>` alone
        dropped 62 such elements in the families without a count -- ActiveSpaces
        5.2.0's JDBC registration lost its whole procedure, sentence and code.

        An `<ol type="a">` or `type="i"` is emitted as HTML around Markdown item
        bodies (`_typed_list`), because GFM can only draw `1.` (R8-14).
        """
        lead: list[str] = []
        entries: list[list[str]] = []
        loose_nodes: list[object] = []

        def place() -> None:
            if loose_nodes:
                (entries[-1] if entries else lead).extend(self._gather(loose_nodes))
                loose_nodes.clear()

        for child in tag.children:
            if isinstance(child, Tag) and child.name == "li":
                place()
                entries.append(self.blocks(child))
            else:
                loose_nodes.append(child)
        place()

        first = _start(tag) if ordered else 1
        style = _numbering(tag) if ordered else ""
        if style:
            body = _typed_list(style, first, entries) if entries else ""
            return "\n\n".join(block for block in [*lead, body] if block)

        items = []
        for number, blocks in enumerate(entries, start=first):
            marker = f"{number}. " if ordered else "- "
            body = "\n\n".join(blocks or [""])
            items.append(marker + _indent(body, len(marker)))
        # Loose lists (blank line between items) render every item as a paragraph;
        # a list whose items are one block each stays tight, which is what a
        # procedure should look like.
        loose = any("\n\n" in item for item in items)
        listed = ("\n\n" if loose else "\n").join(items)
        return "\n\n".join(block for block in [*lead, listed] if block)

    def table(self, tag: Tag) -> str:
        """A pipe table where GFM can carry it, the original HTML where it cannot."""
        model = tables_transform.read(tag)
        if tables_transform.is_gfm_safe(model):
            # A target in no cell -- Flare puts the table's own between `<col>`
            # and `<thead>` -- is invisible to `read`, so a pipe table would drop
            # it. Hoisted out in front, where the rows cannot swallow it. The
            # passthrough branch below needs none of this: `rewrite` walks the
            # whole subtree.
            markers = "".join(
                anchor_marker(anchor_target(found))
                for found in tag.find_all("a")
                if found.find_parent(["td", "th"]) is None
            )
            blocks = [markers] if markers else []
            # The caption, which `read` cannot see either: an italic line ahead of
            # the table, as WebWorks writes its own. 237 captions in three families
            # vanished on this path without a word (Phase 34, R8-06). Its target
            # is already among the hoisted markers above, taken from the tag
            # rather than from the rendered text, whose whitespace is collapsed:
            # one EMS target has a pasted table, newlines and all, in its name.
            caption = tag.find("caption", recursive=False)
            if isinstance(caption, Tag):
                text = _trim(self.inline_children(caption)).replace(_BREAK, " ")
                text = _MARKER.sub("", text).strip()
                if text:
                    blocks.append(wrap(text, "*"))
            blocks.append(tables_transform.to_pipe(model, self.inline_children))
            return "\n\n".join(blocks)
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
            target = anchor_target(anchor)
            if target:
                # `name=` in, `id=` out. 1,092 of the tree's missing anchors were
                # targets inside a table, unwrapped away by the branch below.
                del anchor["name"]
                anchor["id"] = target
            if url:
                anchor["href"] = url
            elif not target:
                # The text was authored and stays; only the claim that it leads
                # somewhere is dropped.
                anchor.unwrap()
        return tag

    # -- inline ----------------------------------------------------------------

    def inline_children(self, tag: Tag) -> str:
        return _collapse(_join_inline(self._inline_node(child) for child in tag.children))

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
        if name in _UNRENDERED:
            return self._unrendered_element(node)
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
            return self.code_span(node)
        if name in _KEEP_AS_HTML:
            inner = _trim(self.inline_children(node))
            return f"<{name}>{inner}</{name}>" if inner else ""
        return self.inline_children(node)

    def code_span(self, tag: Tag) -> str:
        """Inline code, with the links inside it kept rather than flattened.

        Rendering a code span from its *text* -- which is what every one of the
        five inline sites used to do, one in here and one in each engine -- means
        an `<a>` inside one never reaches `link()`, so the reference is neither
        resolved nor reported. It is not dropped, it is never classified, which is
        why nothing in the register ever mentioned it. Measured over all 13
        in-scope products, 88,691 files: **13,126** swallowed references, and this
        is the path that recovers the 8,162 of them that are not inside a `<pre>`.

        Two shapes, because GFM only has syntax for one of them:

        - **The anchor is the span's whole content** -- 7,863 of the 8,162. The
          nesting inverts to ``[`text`](url)``. The test is on the span's *text*,
          not on its child list, because 218 of those -- all DocBook -- wrap the
          anchor in another element, and a direct-childness check would skip every
          one of them. CommonMark binds a code span tighter than a link, so a `]`
          in the code does not close the link text.
        - **The anchor shares the span** with prose, a second anchor, or a
          trailing identifier fragment -- 299, of which 68 hold more than one
          anchor. GFM cannot put a link inside a code span, so the span is emitted
          as HTML, which is `_KEEP_AS_HTML`'s reason and `tables.passthrough`'s.
          Rebuilt from the subtree rather than dumped from the source, so the
          authoring tool's classes do not reach the output.

        A `link()` of `None` -- a `javascript:` skin button, an unresolvable
        target -- renders exactly what it rendered before. This adds links; it
        never removes a code span.

        An anchor *target* inside the span is hoisted out in front of it, for the
        same reason a heading hoists one above itself (§5.7): it cannot be a
        destination inside backticks, and Flare puts one there often enough that
        100 of the `ems` tree's missing anchors were a `<a name=>` inside a
        `<code>` in a table cell.
        """
        markers = "".join(anchor_marker(anchor_target(found)) for found in tag.find_all("a"))
        return markers + self._code_span_body(tag)

    def _code_span_body(self, tag: Tag) -> str:
        anchors = tag.find_all("a", href=True)
        if not anchors:
            return code_transform.inline(text_of(tag))

        body = code_transform.inline(text_of(tag))
        if len(anchors) == 1:
            anchor = anchors[0]
            if _collapse(text_of(tag)).strip() == _collapse(text_of(anchor)).strip():
                url = self.link(anchor)
                return f"[{body}]({url})" if url and body else body

        inner = "".join(self._code_fragment(child) for child in tag.children)
        stripped = inner.strip()
        return f"<code>{stripped}</code>" if stripped else ""

    def _code_fragment(self, node: object) -> str:
        """One child of a code span that is being emitted as HTML.

        Text is HTML-escaped rather than Markdown-escaped -- inside a `<code>` the
        backslashes would be literal -- and an anchor keeps its words whether or
        not the hook gives it a URL.
        """
        if is_text(node):
            return _html_escape(_collapse(str(node)))
        if not isinstance(node, Tag):
            return ""
        if node.name == "a" and node.get("href"):
            text = "".join(self._code_fragment(child) for child in node.children)
            url = self.link(node)
            return f'<a href="{_html_escape(url)}">{text}</a>' if url else text
        return "".join(self._code_fragment(child) for child in node.children)

    def _anchor(self, tag: Tag) -> str:
        """One `<a>`: its destination, its link, or both.

        The two are independent, and treating the absence of an `href` as "not a
        link, therefore nothing" deleted 1,679 of the `ems` tree's cross-reference
        targets while every `href="#..."` pointing at them survived (Phase 16).
        The marker leads, so it sits *before* the text it labels.
        """
        text = _trim(self.inline_children(tag))
        url = self.link(tag)
        marker = anchor_marker(anchor_target(tag))
        if not url:
            return marker + text
        if not text:
            # A link with no text is either an anchor target or a broken one;
            # emitting `[](url)` renders as nothing and hides both.
            return marker
        return f"{marker}[{text}]({url})"

    def _unrendered_element(self, tag: Tag) -> str:
        """Media the walk cannot express: counted, and linked where it can be.

        Only an absolute URL is linked. A relative one is a file in the source
        layout that nothing resolved or copied, and emitting it would be a URL
        this module invented (invariant 13). Without one the element renders
        what it always did, its fallback text.
        """
        self.unrendered[tag.name] += 1
        source = tag.find("source")
        for value in (tag.get("src"), tag.get("data"), source.get("src") if isinstance(source, Tag) else None):
            url = str(value or "").strip()
            if url.lower().startswith(("http://", "https://")):
                return f"[{escape(url)}]({url})"
        return self.inline_children(tag)

    def _image(self, tag: Tag) -> str:
        url = self.image(tag)
        if not url:
            return ""
        alt = _collapse(str(tag.get("alt", ""))).strip()
        return f"![{escape(alt)}]({url})"


def _html_escape(text: str) -> str:
    """The three characters that would end a tag or an attribute early."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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


def _join_inline(parts: Iterable[str]) -> str:
    """Inline runs, joined so that each one still reads as the run it is.

    GFM has no way to close one run and open the next against it: `<b>ssl</b>`
    `<b>.</b>` gave `**ssl****.**`, `<b>Default value:</b><i>none</i>` gave
    `**Default value:***none*`, and two adjacent `<code>`s one span holding two
    backticks -- 353 literal `**` and 849 merged code spans in the families
    (Phase 34, R8-07). An empty HTML comment between them renders as nothing
    and gives each delimiter a neighbour it can close or open against.
    """
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if out and _fuses(out[-1], part):
            out.append(_SEAM)
        out.append(part)
    return "".join(out)


def _fuses(left: str, right: str) -> bool:
    """Would `right` written straight after `left` stop either being its own run?

    Three ways, all CommonMark's flanking rules: two delimiters touching; a
    closing `*` or `~` after punctuation with a word straight after it, which
    cannot close; and the mirror of that for an opening one.
    """
    before, after = left[-1], right[0]
    if before in _DELIMITERS and after in _DELIMITERS:
        return True
    if before in "*~" and _is_word(after):
        inner = left.rstrip(before)[-1:]
        return bool(inner) and _is_punctuation(inner)
    if after in "*~" and _is_word(before):
        inner = right.lstrip(after)[:1]
        return bool(inner) and _is_punctuation(inner)
    return False


def _is_punctuation(char: str) -> bool:
    """CommonMark's punctuation: the Unicode P and S categories."""
    return unicodedata.category(char)[0] in "PS"


def _is_word(char: str) -> bool:
    return not char.isspace() and not _is_punctuation(char)


def _trim(text: str) -> str:
    """`str.strip`, plus any hard break at either end.

    A break is a backslash and a newline, and only means something between two
    lines. `strip` took the newline and left the backslash, so a paragraph ending
    in `<br>` printed a `\\`, and DocBook's `<br class="figure-break">` alone made
    a paragraph of one: 2,064 such paragraphs and 81 trailing ones in the
    families (Phase 34, R8-05).
    """
    return _EDGE_BREAKS.sub("", text)


def wrap(text: str, marker: str) -> str:
    """Emphasis, with the surrounding spaces moved outside the markers.

    `** bold **` is not bold in any GFM renderer, and MadCap's spans routinely
    include the trailing space. A hard break at either end moves out with them:
    `<b>Warning<br/></b>` left it inside as `**Warning\\**`, whose backslash
    escaped the closing marker (R8-05).
    """
    head, stripped, rear = _EDGES.fullmatch(text).groups()  # type: ignore[union-attr]
    if not stripped:
        return " " if text else ""
    return f"{_padding(head)}{marker}{stripped}{marker}{_padding(rear)}"


def _padding(edge: str) -> str:
    """What one end of an emphasis run leaves outside it: a break, a space, or nothing."""
    if _BREAK in edge:
        return _BREAK
    return " " if edge else ""


def _start(tag: Tag) -> int:
    """An `<ol start>`, or 1. GFM numbers from 0 up, so nothing below that."""
    raw = str(tag.get("start") or "").strip()
    return int(raw) if raw.isdigit() else 1


def _numbering(tag: Tag) -> str:
    """An `<ol type>` GFM cannot draw -- letters or roman numerals -- or `""`."""
    raw = str(tag.get("type") or "").strip()
    return raw if raw in _NUMBERING else ""


def _typed_list(style: str, first: int, entries: list[list[str]]) -> str:
    """An ordered list numbered `a.` or `i.`, as HTML whose item bodies stay Markdown.

    GFM numbers every list `1.`, and GitHub's stylesheet restyles nested lists by
    depth rather than by type, so DocBook's `numeration="loweralpha"` sub-steps
    read "2" where the prose says "step b": 980 lists in 10 Streaming versions
    (Phase 34, R8-14). The blank lines around each body are what keep it
    Markdown: an HTML block ends at the first one, so emphasis, code, links and
    nested lists between `<li>` and `</li>` are parsed rather than shown raw.
    """
    start = f' start="{first}"' if first != 1 else ""
    items = []
    for blocks in entries:
        body = "\n\n".join(block for block in blocks if block)
        items.append(f"<li>\n\n{body}\n\n</li>" if body else "<li></li>")
    return "\n".join([f'<ol type="{style}"{start}>', *items, "</ol>"])


def _indent(text: str, width: int) -> str:
    pad = " " * width
    lines = text.split("\n")
    return "\n".join([lines[0]] + [(pad + line).rstrip() for line in lines[1:]])


def _quote(block: str) -> str:
    return "\n".join(f"> {line}".rstrip() for line in block.split("\n"))
