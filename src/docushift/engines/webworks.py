"""The WebWorks ePublisher engine: 691 books, 157 collections, and a 2:1 shape.

`architecture.md` §5.3, from a corpus survey on 2026-09-09 of 691 books, 195
versions, 110 products, 38,818 HTML topics and 1.49 GB, re-measured on 2026-09-11.
FrameMaker output carried through a 2007-era generator: nothing in it is semantic
HTML, and every decision below is a shape match against what the generator emits.

What the corpus decided, and what each costs to get wrong:

- **The unit of work is the book** (`wwhdata/`), and books are ordered by the
  collection's `wwhelp/books.xml` (§5.3.3). Declared order is authored order and
  is not alphabetical in 112 of 157 collections.
- **`body > blockquote` is the content, in 99.6% of topics, and all the chrome is
  outside it.** The selector *is* the chrome removal -- the exact reverse of Flare,
  where one chrome block is 47.7% of the corpus's hrefs (§5.1.6). The 118 misses
  are the 2004-2006 flavour and fall back to `<body>` with its trailing banner cut.
- **Every list is a table**, in the exact shape `div.<Kind>_outer > table > tr >
  td x 2` -- marker cell, content cell. The 2:1 `_outer`:`_inner` ratio holds
  corpus-wide and every one of 10,252 sampled `_outer` divs has exactly two cells,
  so this is a structural invariant and not a heuristic.
- **Indentation is in the class name and nowhere else.** No `_outer` ever nests
  inside another (0 of 7,341 sampled) and not one marker cell carries a `width`.
  `Step -> StepInd -> Step` and `Bullet -> ListDash -> Bullet` are the nesting
  signature, so depth is read off the kind: an `Ind` suffix or `ListDash` is one
  level in, a trailing `_2` is level two.
- **`Chapter_outer` is a heading wearing a list's clothes.** It shares the shape,
  but in 185 sampled topics that carry one, `N1Heading` is absent from **all 185**
  -- so it is the topic's own title and becomes `#`, not a bullet.
- **Cross-references are `javascript:WWHClickedPopup(book, file#anchor)`** and are
  99.7% of in-content links. Both arguments are readable, so this is a
  fully-specified link (§5.3.8) -- the predecessor deletes all 89,125 of them.
- **`l=` indexes `wwhdata/common/files.js`.** 68,915 of 68,915 resolve, every one
  to a file that exists; `wwhdata/files.htm` manages 88.43% and is never better.
  That is the predecessor's central bug (§5.3.10) and it fails *plausibly*: the
  TOC points at a real but wrong topic.
- **An `<a>` with no `href` is an anchor wrapped around prose**, 43 per topic. It
  is unwrapped for its text and re-emitted as an explicit anchor only where
  something points at it -- 6.46% of them. Keeping all 1.32M is noise; dropping
  all of them, as the predecessor does, breaks 85,219 links and all of CSH.

**Two departures from the predecessor's skip list, both deliberate.** `title.*`
and `copyrigh.*` are dropped by `_SKIP_FILENAMES` there and converted here: they
are 1,047 of the 1,086 files that `files.js` indexes and the TOC does not mention,
and `copyrigh.htm` is "Important Information", which is prose and frequently the
book's legal page (§5.3.5). `glossary` likewise. What is dropped is only what is
*generated*: the `index.htm`/`wwhsec.htm` framesets and the `lof`/`lot`/`ix` lists.

**One honest limit.** A book's topic set, its anchors and every reference in the
version are settled by a raw-text pre-pass before the first DOM is parsed, so a
topic that later renders empty leaves a link pointing at a page that was written
with no content rather than not written. `validate` (Phase 7) would name it. The
pre-pass is a regex scan and not a parse, which is what makes a second read of
every file affordable.
"""

import html as html_entities
import os
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import PreformattedString

from docushift.apiref import is_api_reference
from docushift.engines.base import (
    BaseEngine,
    ConversionContext,
    Document,
    NavNode,
    Unit,
    is_legal_label,
    is_support_label,
    register,
)
from docushift.engines.csh import CshFormat, read_csh_source
from docushift.engines.roots import is_skin_path
from docushift.engines.webworks_toc import (
    FileEntry,
    TocEntry,
    read_books,
    read_files,
    read_files_htm,
    read_return,
    read_text,
    read_toc,
)
from docushift.models import SourceEngine
from docushift.transforms import callouts, links, markdown
from docushift.transforms import code as code_transform
from docushift.transforms import tables as tables_transform

# The runtime, read for metadata and never emitted (§5.3.9). `tpl/` is skin
# imagery; `roots.SKIN_PREFIXES` already keeps the asset copier out of it, and this
# keeps the topic walk out of it too.
RUNTIME_DIRECTORIES = frozenset({"wwhdata", "wwhelp", "tpl"})

# Keyed on the first dot-separated segment of the stem, because the generator
# writes `title.1.1.htm` and `lof.2.htm` as often as `title.htm`.
STUB_STEMS = frozenset({"index", "wwhsec"})
GENERATED_LIST_STEMS = frozenset({"lof", "lot", "ix"})

_HTML_SUFFIXES = (".htm", ".html")

# `N1Heading` -> 1, `N3Syntax` -> 3. The numeral in the class *is* the level, which
# is the one place WebWorks is easier than Flare (§5.3.7).
_HEADING_CLASS = re.compile(r"^N(\d)(?:Heading|Syntax)$")
# Sub-headings with no numeral: `MinorHead` 19,531 and `Block-title` 12,788, which
# titles an error code. Both sit below `N3Heading` in every sample, so both are h4.
_FLAT_HEADINGS = {"minorhead": 4, "block-title": 4}

# `div.<Kind>_outer`, the list shape, and `div.<Kind>_inner`, its two cells.
_OUTER = re.compile(r"^(?P<kind>.+)_outer$")
# A run of these coalesces into one fence: `WCodeLine` 51,345, `CodeLine` 43,355,
# `CodeLineFirst` 10,196, against 60 `<pre>` elements in the whole corpus.
_CODE_LINE = ("codeline", "wcodeline")
_CONTINUATION = frozenset({"listcontinue", "listcontinueindent"})

# The marker cell's text, when the list is a bulleted one. Measured: `•` 5,712,
# `●` 462, `−` 954, `─` 12 -- a minus sign and a box-drawing
# character among them, because the glyph is whatever the FrameMaker tag drew.
_BULLETS = frozenset({
    "•", "●", "▪", "◦", "‣", "·",
    "-", "–", "—", "*", "o", "−", "─",
})
# `1.`, `2)`, `(3)`, `a.`, `iv.` -- an ordinal, however the template drew it.
_ORDINAL = re.compile(r"^\(?(?:\d+|[A-Za-z]|[ivxIVX]+)[.)]?$")
# Enough of the numeral system for a list marker: no procedure reaches step 40.
_ROMAN = {"i": 1, "v": 5, "x": 10}
# `Chapter 1`, `Appendix A`. Matched on the kind *and* on the marker text, because
# the kind is the measured signal and the text is the one a retagged book keeps.
_CHAPTER_KINDS = frozenset({"chapter", "appendix", "part"})
_CHAPTER_TEXT = re.compile(r"^(chapter|appendix|part)\b", re.IGNORECASE)

# `javascript:WWHClickedPopup('tib_bw_administration', 'admin.5.15.htm#1691748', '')`
# -- the only function name that appears, and the whitespace is real.
_POPUP = re.compile(
    r"""WWHClickedPopup\s*\(\s*(['"])(?P<book>.*?)\1\s*,\s*(['"])(?P<target>.*?)\3""",
    re.DOTALL,
)

# The pre-pass (§5.3.8). Regex over raw text rather than a parse: it runs over
# every topic in the version before any conversion, and a second full parse of
# 38,818 files to learn 85,219 anchor names is not worth what it buys.
_SCAN_ANCHOR = re.compile(r"""<a\s[^>]*?\b(?:name|id)\s*=\s*["']?([^"'\s>]+)""", re.IGNORECASE)
_SCAN_HREF = re.compile(r"""\bhref\s*=\s*["']([^"']*)["']""", re.IGNORECASE)

# `API Reference` and `API_Reference` name the same book: `context.js` normalizes
# every non-word character and the directory does not. 34 of 646 books disagree
# that way, so a popup is matched on the normalized form of both.
_NON_WORD = re.compile(r"\W+")

# `div.Icon<Kind>` in the first cell of a `table.IconTable`. The kind is the class
# minus its prefix; the cell itself holds a `.gif` and a `&nbsp;` and no prose.
_ICON_PREFIX = "icon"

# The vocabulary of §5.3.7. `LiveLink` -- 85,719 of them -- is deliberately absent:
# it is a transparent wrapper around the `<a>` that carries the cross-reference,
# and mapping it to anything, including plain text, is the predecessor's third bug.
SPAN_TO_TAG = {
    "Code": "code", "CodeItalic": "code", "CodeBold": "code",
    "Command": "code", "URL": "code", "ErrorVariable": "code", "codeph": "code",
    "Bold": "strong", "uicontrol": "strong", "wintitle": "strong",
    "option": "strong", "RunIn": "strong",
    "Italic": "em", "Emphasis": "em",
}

_SOUP = BeautifulSoup("", "html.parser")


# -- the renderer --------------------------------------------------------------


class WebWorksRenderer(markdown.Renderer):
    """FrameMaker's tag vocabulary, over `transforms/markdown.py`'s walk.

    The list, code and chapter-heading constructs are gone by the time this runs:
    `normalize()` has already turned them into `<ul>`, `<pre>` and `<h1>`, because
    they are *runs of siblings* and a per-element hook cannot see a run.
    """

    def __init__(self, engine: "WebWorksEngine", context: ConversionContext, unit: Unit,
                 index: "_Index", source: Path, output: PurePosixPath,
                 relative: PurePosixPath, base: PurePosixPath, key: str):
        self.engine = engine
        self.context = context
        self.unit = unit
        self.index = index
        self.source = source
        # Tree-relative, because a cross-book link is resolved against the version
        # and not against this book.
        self.output = output
        # Unit-relative -- what the driver writes and what the asset copier, whose
        # destination is already this unit's folder, resolves against.
        self.relative = relative
        # This topic's directory, tree-relative: the base every relative href
        # resolves against, which makes `../otherbook/x.htm` fall out for free.
        self.base = base
        self.key = key
        self.wanted = index.referenced.get(key, frozenset())
        # Filled as anchors are emitted, and handed to `Document.anchors`.
        self.emitted: set[str] = set()

    # -- blocks ---------------------------------------------------------------

    def block_override(self, tag: Tag) -> str | None:
        name = tag.name
        if name in ("script", "style"):
            return ""
        if name == "table":
            return self._table(tag)
        if name != "div":
            return None
        primary = _primary_class(tag)
        level = _heading_level(primary)
        if level:
            text = self.inline_children(tag).strip()
            return f"{'#' * level} {text}" if text else ""
        if primary.lower() == "figuretitle":
            # 98.3% of figure titles are followed by their image, so the caption
            # already reads in source order. Emitting it after the figure -- which
            # is where prose order would put a caption -- captions the wrong thing.
            text = self.inline_children(tag).strip()
            return markdown.wrap(text, "*") if text else ""
        return None

    def _table(self, tag: Tag) -> str | None:
        """Which of §5.3.7's three kinds of table this is. None means 'not mine'."""
        classes = {name.lower() for name in _raw_classes(tag)}
        if "icontable" in classes:
            claimed = self._callout(tag)
            if claimed is not None:
                return claimed
        if _is_layout(tag):
            return self._unwrap(tag)
        return self._content_table(tag)

    def _callout(self, tag: Tag) -> str | None:
        """`table.IconTable`, whose prose is in the cell the icon is *not* in.

        Reading the icon cell instead is the predecessor's fourth bug and turns all
        12,866 admonitions into an empty alert followed by a loose paragraph.
        """
        rows = _direct_rows(tag)
        cells = _direct_cells(rows[0]) if rows else []
        if len(cells) < 2:
            return None
        label = ""
        for div in cells[0].find_all("div"):
            for name in _raw_classes(div):
                if name.lower().startswith(_ICON_PREFIX) and len(name) > len(_ICON_PREFIX):
                    label = name[len(_ICON_PREFIX):]
                    break
            if label:
                break
        kind = callouts.alert_for(label) if label else None
        if kind is None:
            self.engine.unmapped_alert(self.context, self.unit, label or "IconTable")
            kind = callouts.Alert.NOTE
        body = "\n\n".join(block for block in self.blocks(cells[1]) if block.strip())
        return callouts.render(kind, body)

    def _unwrap(self, tag: Tag) -> str:
        """A layout table is a wrapper; its cells are blocks stacked in order.

        `role="presentation"` marks 149,326 of them and 86,702 identical ones carry
        no `role` at all, which is why the parent-class test sits beside it.
        """
        out: list[str] = []
        for row in _direct_rows(tag):
            for cell in _direct_cells(row):
                out.extend(self.blocks(cell))
        return "\n\n".join(block for block in out if block.strip())

    def _content_table(self, tag: Tag) -> str:
        """A real table, with its caption lifted out and its header row named.

        Content tables have no `<th>` -- 45 in the whole corpus -- so the header row
        is found by looking for `div.CellHeading`, which 98.5% of the tables with
        three or more rows have. Without it every one of them would come out
        headerless, and GFM has no headerless pipe table.
        """
        prefix: list[str] = []
        caption = tag.find("caption", recursive=False)
        if isinstance(caption, Tag):
            # 97.4% of `TableTitle`s are the last thing in their `<caption>`, so the
            # caption element reads normally -- but the shared walk reads `tr` only,
            # and left in place the caption is silently dropped.
            text = self.inline_children(caption).strip()
            caption.extract()
            if text:
                prefix.append(markdown.wrap(text, "*"))
        model = tables_transform.read(tag, header_row=_header_row(tag))
        if tables_transform.is_gfm_safe(model):
            body = tables_transform.to_pipe(model, self.inline_children)
        else:
            body = tables_transform.passthrough(self.rewrite(tag))
        return "\n\n".join([*prefix, body] if body.strip() else prefix)

    # -- inline ---------------------------------------------------------------

    def inline_override(self, tag: Tag) -> str | None:
        if tag.name == "a" and not tag.get("href"):
            return self._named_anchor(tag)
        if tag.name != "span":
            return None
        for name in _raw_classes(tag):
            mapped = SPAN_TO_TAG.get(name)
            if mapped == "strong":
                return markdown.wrap(self.inline_children(tag), "**")
            if mapped == "em":
                return markdown.wrap(self.inline_children(tag), "*")
            if mapped == "code":
                return code_transform.inline(markdown.text_of(tag))
        return None

    def _named_anchor(self, tag: Tag) -> str:
        """An `<a name>` with no href: an anchor *and* the block's leading prose.

        The generator wraps the first sentence of a block in the anchor, so the two
        have to be separated rather than chosen between. Returning only the text --
        the predecessor's second bug -- is silently right for the prose and
        destroys every anchor target in the corpus; deleting the element loses the
        sentence. Only the 6.46% something points at are re-emitted.
        """
        text = self.inline_children(tag)
        name = str(tag.get("name") or tag.get("id") or "")
        if not name or name not in self.wanted:
            return text
        self.emitted.add(name)
        # HTML-escaped, not Markdown-escaped: this is an attribute value, and a
        # backslash inside one is a literal character rather than an escape.
        return f'<a id="{html_entities.escape(name, quote=True)}"></a>{text}'

    # -- references (invariant 13) --------------------------------------------

    def link(self, tag: Tag) -> str | None:
        raw = str(tag.get("href") or "").strip()
        if not raw:
            return None
        popup = _POPUP.search(raw)
        if popup is not None:
            return self._popup(popup.group("book"), popup.group("target"))
        reference = links.classify(raw)
        if reference.kind is links.ReferenceKind.FRAGMENT:
            return self._same_page(reference.fragment)
        if reference.kind in (links.ReferenceKind.ABSOLUTE, links.ReferenceKind.ROOTED):
            # Every remaining `javascript:` href is a runtime control -- the popup
            # form was claimed above -- and there is nothing behind it to link to.
            return None if raw.lower().startswith("javascript:") else raw
        if not reference.resolvable:
            return None
        if not links.is_topic(reference.path):
            return self._asset(reference.raw)
        return self._topic(links.resolve(self.base, reference.path), reference.fragment, raw)

    def _popup(self, book: str, target: str) -> str | None:
        """One `WWHClickedPopup`, resolved against the whole version.

        Same-book popups resolve at 100% and cross-book ones at 52.6%; the 711 that
        do not name books the package never shipped, so there is no version-wide
        fallback to try -- §5.4.3's step 4 is a Flare remedy and stays one.
        """
        path, _, fragment = target.partition("#")
        name = self.index.by_key.get(_book_key(book))
        if name is None or not path:
            self.engine.dangling_link(self.context, self.unit, self.source, target)
            return None
        joined = posixpath.join(name, unquote(path)) if name else unquote(path)
        return self._topic(PurePosixPath(posixpath.normpath(joined)), fragment, target)

    def _same_page(self, fragment: str) -> str | None:
        if not fragment:
            return None
        if fragment not in self.index.anchors.get(self.key, frozenset()):
            self.engine.dangling_link(self.context, self.unit, self.source, f"#{fragment}")
            return None
        return f"#{fragment}"

    def _topic(self, resolved: PurePosixPath, fragment: str, raw: str) -> str | None:
        """A tree-relative source path to the Markdown this run will write.

        Tree-relative and not book-relative, so a cross-book popup and a
        `../other_book/x.htm` take the same path through the same table.
        """
        key = str(resolved).lower()
        target = self.index.topics.get(key)
        if target is None:
            self.engine.dangling_link(self.context, self.unit, self.source, raw)
            return None
        if fragment and fragment not in self.index.anchors.get(key, frozenset()):
            # References resolve at 99.81%, so this is a defect worth a line rather
            # than an expected condition. The page still resolves; the section does
            # not, and the link is emitted without its bookmark.
            self.engine.dangling_link(self.context, self.unit, self.source, raw)
            fragment = ""
        return links.emit(links.relative_to(self.output, target), fragment)

    def image(self, tag: Tag) -> str | None:
        """Images keep their source filename.

        `alt` is not a caption and not a name: the 22,126 images with no `alt` are
        exactly the 22,126 under `images/`, and every `tpl/` skin icon has one. It
        is a skin marker, and naming files from it -- as the predecessor does --
        would fall through to the fallback on 100% of content images.
        """
        return self._asset(str(tag.get("src") or ""))

    def _asset(self, raw: str) -> str | None:
        copier = self.context.assets
        if copier is None:  # pragma: no cover - the driver always sets one
            return None
        return copier.resolve(self.source, self.relative, raw).url or None


# -- the DOM passes ------------------------------------------------------------


def normalize(container: Tag) -> None:
    """Turns runs of siblings into the elements they stand for. Post-order.

    Three constructs here are *runs* rather than elements -- a code block is N
    sibling divs, a list is N sibling tables, and both can appear inside a list
    item -- so the children are normalized before their parent is. Pre-order would
    build the outer list out of cells whose own lists had not been built yet, and
    nested procedures are common enough that the difference is visible.
    """
    for child in [child for child in container.children if isinstance(child, Tag)]:
        normalize(child)
    _chapter_headings(container)
    _coalesce_code(container)
    _group_lists(container)


def _chapter_headings(parent: Tag) -> None:
    """`Chapter_outer` and `Appendix_outer` are the topic's title (§5.3.7).

    They wear the list shape, and taking the shape at face value would emit
    `- Chapter 1  Introduction` as the first line of 185 of every 1,361 topics.
    `N1Heading` is absent from every one of those topics, so this is the `h1`.
    """
    for child in [child for child in parent.children if isinstance(child, Tag)]:
        kind = _outer_kind(child)
        if kind is None:
            continue
        cells = _outer_cells(child)
        if cells is None:
            continue
        marker, content = cells
        label = _text(marker)
        if kind.lower() not in _CHAPTER_KINDS and not _CHAPTER_TEXT.match(label):
            continue
        heading = _SOUP.new_tag("h1")
        if label:
            heading.append(NavigableString(f"{label} "))
        heading.extend(list(content.children))
        child.replace_with(heading)


def _coalesce_code(parent: Tag) -> None:
    """Consecutive `*CodeLine` divs are one fenced block, not one fence each.

    104,896 of them against 60 `<pre>` elements corpus-wide. Fencing per div -- the
    predecessor's fifth bug -- turns a five-line command into five unrunnable
    one-line fences. The fence is bare: there is no language attribute anywhere in
    the corpus to read, and guessing one would be a fabrication made 100,000 times.
    """
    for run in _runs(parent, _is_code_line):
        lines = [_code_text(node) for node in run]
        while lines and not lines[-1].strip():
            lines.pop()
        block = _SOUP.new_tag("pre")
        block.string = "\n".join(lines)
        _drop_rules(run)
        _replace_run(run, [block])


def _drop_rules(run: list[Tag]) -> None:
    """The rule the generator drew above and below a code block.

    Every `hr` that survives chrome-stripping abuts a fence -- 44 of 44 across two
    versions -- so it is the box FrameMaker drew around the code and not a thematic
    break in the prose. The fence already draws it, and a `---` between a paragraph
    and its example reads as a section change the page never made.
    """
    for neighbour in (run[0].find_previous_sibling(), run[-1].find_next_sibling()):
        if isinstance(neighbour, Tag) and neighbour.name == "hr":
            neighbour.extract()


def _group_lists(parent: Tag) -> None:
    """A run of `_outer` siblings becomes one list, nested by kind (§5.3.7)."""
    for run in _list_runs(parent):
        blocks = _build_list(run)
        if blocks:
            _replace_run(run, blocks)


@dataclass
class _Level:
    """One open list in the nesting stack."""

    depth: int
    name: str
    tag: Tag

    def last(self) -> Tag | None:
        """The item a deeper list or a continuation paragraph attaches to."""
        items = self.tag.find_all("dd" if self.name == "dl" else "li", recursive=False)
        return items[-1] if items else None


def _build_list(run: list[Tag]) -> list[Tag]:
    """The list tree for one run of `_outer` divs and their continuations.

    Depth comes off the kind name because nothing else carries it (§5.3.7): no
    `_outer` nests inside another and no marker cell has a `width`. The run's own
    shallowest kind is the base, so a run that opens on a `ListDash` -- 115 of them
    in the sample -- is a top-level list rather than one indented under nothing.
    """
    kinds = [_outer_kind(node) for node in run]
    depths = [_list_depth(kind) for kind in kinds if kind is not None]
    if not depths:
        return []
    base = min(depths)

    out: list[Tag] = []
    stack: list[_Level] = []

    def open_level(depth: int, name: str) -> None:
        created = _SOUP.new_tag(name)
        parent = stack[-1].last() if stack else None
        if parent is not None:
            parent.append(created)
        else:
            out.append(created)
        stack.append(_Level(depth=depth, name=name, tag=created))

    for node, kind in zip(run, kinds, strict=True):
        cells = _outer_cells(node) if kind is not None else None
        if cells is None:
            # A `ListContinue` paragraph, a note set between two numbered steps, or
            # an `_outer` that is not the two-cell shape. All three are the previous
            # item's content rather than the list's, and none of them is dropped:
            # `out` catches the one that arrives before any item exists.
            target = stack[-1].last() if stack else None
            (target if target is not None else out).append(node.extract())
            continue
        marker, content = cells
        depth = max(_list_depth(kind) - base, 0)
        name = _item_kind(_text(marker))

        while len(stack) > 1 and stack[-1].depth > depth:
            stack.pop()
        if stack and stack[-1].depth > depth:
            stack.pop()
        if not stack or stack[-1].depth < depth:
            open_level(depth, name)
        elif stack[-1].name != name:
            # A kind change at the same level is a new list beside the old one,
            # never a continuation of it: `-` items and `1.` items are not one list.
            stack.pop()
            open_level(depth, name)

        level = stack[-1]
        if level.name == "dl":
            term = _SOUP.new_tag("dt")
            term.extend(list(marker.children))
            body = _SOUP.new_tag("dd")
            body.extend(list(content.children))
            level.tag.append(term)
            level.tag.append(body)
        else:
            item = _SOUP.new_tag("li")
            item.extend(list(content.children))
            level.tag.append(item)
    return out


def _item_kind(marker: str) -> str:
    """`ul`, `ol` or `dl`, from what the generator drew in the marker cell.

    The kind name is not enough on its own -- `Step` and `Bullet` both appear with
    and without numbering -- and the opaque `ID-000000c3_outer` kinds carry no hint
    at all. The marker text is the thing the reader actually saw: a glyph, an
    ordinal, or a term, and a term makes it a definition list. That last branch is
    what carries the `Action` / `Explanation` / `Source` message-reference triple,
    roughly 6,300 of each.
    """
    text = marker.strip()
    if not text or text in _BULLETS:
        return "ul"
    if _ORDINAL.match(text):
        return "ol"
    return "dl"


def _list_depth(kind: str) -> int:
    """How far in a list kind sits. Measured: the name is the only signal."""
    stem, _, trailing = kind.rpartition("_")
    if stem and trailing.isdigit():
        return max(int(trailing) - 1, 0)
    if kind.endswith("Ind") or kind == "ListDash":
        return 1
    return 0


def _list_runs(parent: Tag) -> list[list[Tag]]:
    """Runs of `_outer` siblings, bridged across whatever was set between them.

    Measured over 3,037 topics: a run of list items is interrupted 4,625 times, and
    in 1,271 of those the next marker is the **successor** of the last one -- the
    source numbered one procedure and set something between two of its steps. A
    note (325 interruptions, 123 numbered through), a figure title (240 / 153), an
    invisible `Anchor` div (246 / 163), a code block (107 / 80). Rendering each
    fragment as a fresh list restarts a nine-step procedure at 1 three times over.

    No class list predicts this: `Body` interrupts a run 890 times and continues it
    24. The marker does, exactly -- it is the generator writing down which list an
    item belongs to. So the run extends when the next `_outer` of the same kind
    carries the next ordinal, and the interruption becomes content of the item
    before it. A heading in the gap stops the bridge whatever the numbers say: it
    happens 987 times and the numbering continues through it once.
    """
    children = [child for child in parent.children if isinstance(child, Tag)]
    # Decided once: the lookahead below re-reads the same children on every break,
    # and `_starts_list` walks a table to answer.
    starts = [_starts_list(child) for child in children]
    found: list[list[Tag]] = []
    index = 0
    while index < len(children):
        if not starts[index]:
            index += 1
            continue
        end, last = index + 1, index
        while True:
            while end < len(children) and (
                starts[end] or _continues_list(children[end])
            ):
                if starts[end]:
                    last = end
                end += 1
            ahead = next((at for at in range(end, len(children)) if starts[at]), None)
            if ahead is None or not _bridges(
                children[last], children[ahead], children[end:ahead]
            ):
                break
            last, end = ahead, ahead + 1
        found.append(children[index:end])
        index = end
    return found


def _bridges(previous: Tag, following: Tag, gap: list[Tag]) -> bool:
    """Whether two interrupted `_outer` divs are one list rather than two."""
    kind = _outer_kind(previous)
    if kind is None or _outer_kind(following) != kind:
        return False
    if any(_is_heading(node) for node in gap):
        return False
    before, after = _outer_cells(previous), _outer_cells(following)
    if before is None or after is None:
        return False
    numbered = _ordinals(_text(before[0]))
    follows = _ordinals(_text(after[0]))
    return any(follows.get(scheme) == value + 1 for scheme, value in numbered.items())


def _ordinals(marker: str) -> dict[str, int]:
    """Every reading of a marker as a number, keyed by numbering scheme.

    `i.` is both the ninth letter and the first roman numeral, and the marker cell
    says nothing about which the author meant. Both readings are kept, and two
    markers are consecutive only within one scheme -- so `h.` is followed by `i.`
    and `i.` by `ii.`, and neither reading makes the other a successor.
    """
    text = marker.strip().lstrip("([").rstrip(".):]")
    if not text:
        return {}
    if text.isdigit():
        return {"decimal": int(text)}
    lowered = text.lower()
    found: dict[str, int] = {}
    if len(lowered) == 1 and "a" <= lowered <= "z":
        found["alpha"] = ord(lowered) - ord("a") + 1
    if all(char in _ROMAN for char in lowered):
        found["roman"] = _roman(lowered)
    return found


def _roman(text: str) -> int:
    total, highest = 0, 0
    for char in reversed(text):
        value = _ROMAN[char]
        total += -value if value < highest else value
        highest = max(highest, value)
    return total


def _is_heading(tag: Tag) -> bool:
    if tag.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return True
    return any(_heading_level(name) for name in _raw_classes(tag))


def _runs(parent: Tag, starts: Callable[[Tag], bool],
          continues: Callable[[Tag], bool] | None = None) -> list[list[Tag]]:
    """Maximal runs of element children, collected before anything is mutated."""
    children = [child for child in parent.children if isinstance(child, Tag)]
    found: list[list[Tag]] = []
    index = 0
    while index < len(children):
        if not starts(children[index]):
            index += 1
            continue
        end = index + 1
        while end < len(children) and (
            starts(children[end]) or (continues is not None and continues(children[end]))
        ):
            end += 1
        found.append(children[index:end])
        index = end
    return found


def _replace_run(run: list[Tag], blocks: list[Tag]) -> None:
    """Swaps a run for what it stood for, without taking its contents with it.

    Only the members still sitting where the run was are removed. `_build_list`
    re-parents the interruptions -- a note between two steps, a `ListContinue`
    paragraph -- into the item they belong to, and a blanket extract would pull
    each of them straight back out of the list it had just been put in and delete
    it: 1,302 continuation paragraphs and every note set inside a procedure.
    """
    anchor = run[0]
    parent = anchor.parent
    for block in reversed(blocks):
        anchor.insert_after(block)
    for node in run:
        if node.parent is parent:
            node.extract()


def _is_code_line(tag: Tag) -> bool:
    if tag.name != "div":
        return False
    return any(name.lower().startswith(_CODE_LINE) for name in _raw_classes(tag))


def _starts_list(tag: Tag) -> bool:
    return _outer_kind(tag) is not None and _outer_cells(tag) is not None


def _continues_list(tag: Tag) -> bool:
    return tag.name == "div" and any(
        name.lower() in _CONTINUATION for name in _raw_classes(tag)
    )


def _code_text(tag: Tag) -> str:
    """One code line. `&nbsp;` is the generator's indentation and becomes spaces."""
    return markdown.text_of(tag).replace("\xa0", " ").rstrip()


def _outer_kind(tag: Tag) -> str | None:
    if tag.name != "div":
        return None
    for name in _raw_classes(tag):
        match = _OUTER.match(name)
        if match is not None:
            return match.group("kind")
    return None


def _outer_cells(tag: Tag) -> tuple[Tag, Tag] | None:
    """The marker cell and the content cell, or None if the shape does not hold.

    Every one of 10,252 sampled `_outer` divs matches, so the None branch is a
    guard rather than a path -- but it is what keeps a retagged book rendering as
    an ordinary table instead of losing its content to a bad cell index.
    """
    table = tag.find("table", recursive=False)
    if not isinstance(table, Tag):
        return None
    rows = _direct_rows(table)
    if not rows:
        return None
    cells = _direct_cells(rows[0])
    if len(cells) < 2:
        return None
    return cells[0], cells[-1]


def _is_layout(tag: Tag) -> bool:
    """A wrapper rather than a table (§5.3.7).

    The `role` test alone is not enough: 86,702 layout tables identical to the
    149,326 that carry `role="presentation"` predate the attribute, and each of
    those would otherwise become a one-column pipe table. Almost all of them are
    already gone by this point -- `normalize()` consumed the `_outer` ones -- so
    the parent test catches the handful whose cell shape did not match.
    """
    if str(tag.get("role") or "").strip().lower() == "presentation":
        return True
    parent = tag.parent
    return isinstance(parent, Tag) and _outer_kind(parent) is not None


def _header_row(table: Tag) -> int | None:
    for index, row in enumerate(_direct_rows(table)):
        for cell in _direct_cells(row):
            if cell.find("div", class_="CellHeading") is not None:
                return index
    return None


def _strip_chrome(container: Tag, whole_body: bool) -> None:
    """Everything that is not prose.

    Selecting `body > blockquote` is itself the chrome removal for 99.6% of topics,
    so this pass is small: scripts, comments, and the breadcrumb trail that turns
    up inside the container in the older flavour. The `<body>` fallback is the
    only path that has to cut a banner, and it is the one where the banner is a
    direct child rather than something the selector already excluded.
    """
    for element in container.find_all(["script", "style", "noscript"]):
        element.decompose()
    for element in list(container.descendants):
        if isinstance(element, PreformattedString):
            element.extract()
    for element in container.find_all("div", class_="WebWorks_Breadcrumbs"):
        element.decompose()
    if not whole_body:
        return
    for child in [child for child in container.children if isinstance(child, Tag)]:
        if child.name == "hr" or (child.name == "table" and _is_banner(child)):
            child.decompose()


def _is_banner(table: Tag) -> bool:
    if str(table.get("align") or "").strip().lower() == "right":
        return True
    return any(
        name.lower().startswith("webworks_company_logo")
        for cell in table.find_all(["td", "th"])
        for name in _raw_classes(cell)
    )


# -- what the version knows before anything is parsed --------------------------


@dataclass
class _Book:
    """One book, read from its runtime and its disk layout, before conversion."""

    root: Path
    # Tree-relative, and `""` only when the tree is itself a book.
    name: str
    title: str = ""
    # Book-relative source paths, sorted -- what this book will convert.
    topics: list[str] = field(default_factory=list)
    files: list[FileEntry] = field(default_factory=list)
    toc: list[TocEntry] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)
    # Where this book sits in its collection, for ordering and for the tail rule.
    collection: str = ""
    collection_name: str = ""
    group: str = ""
    order: int = 0
    last: bool = False
    stripped: bool = False
    # `context.js` -- the name this book's own popups address it by, which is the
    # normalized directory name for 612 of 646 books and something else for 34.
    context_key: str = ""
    # Lazy `files.js` title lookup, built on the first topic and kept out of repr.
    _titles: dict[str, str] = field(default_factory=dict, repr=False)

    def aliases(self) -> set[str]:
        """Every normalized name a `WWHClickedPopup` may call this book.

        Both forms, because the two disagree in 34 books: the directory is
        `tib_amx_it_clr_installation` where `context.js` says `Installation`, and
        `API Reference` where it says `API_Reference`. Matching one alone loses
        every cross-book link into those books.
        """
        found = {_book_key(self.root.name)}
        if self.context_key:
            found.add(_book_key(self.context_key))
        return {key for key in found if key}

    def title_of(self, relative: str) -> str:
        """The `files.js` title for one topic, which is the cleaner of the two."""
        if not self._titles:
            self._titles = {entry.href.lower(): entry.title for entry in self.files}
        return self._titles.get(relative.lower(), "")


@dataclass
class _Index:
    """Everything cross-book, settled once per version (§5.3.8)."""

    books: dict[str, _Book] = field(default_factory=dict)
    # Normalized `context.js` value and directory name -> unit name. Both, because
    # the two disagree for 34 of 646 books and a popup names one of them.
    by_key: dict[str, str] = field(default_factory=dict)
    # Tree-relative source path (lowercased) -> tree-relative Markdown output.
    topics: dict[str, PurePosixPath] = field(default_factory=dict)
    # The same key -> the anchor names that file contains, and the ones pointed at.
    anchors: dict[str, set[str]] = field(default_factory=dict)
    referenced: dict[str, set[str]] = field(default_factory=dict)


# -- the engine ----------------------------------------------------------------


@register
class WebWorksEngine(BaseEngine):
    """WebWorks ePublisher / WWHelp."""

    engine = SourceEngine.WEBWORKS

    def __init__(self) -> None:
        # Per-version state: the driver builds one engine per version, which is the
        # scope the alert vocabulary and the cross-book index are shared at.
        self._alerts: set[str] = set()
        self._dropped = 0
        self._index = _Index()
        # Collection root -> which tail pages some book in it supplied.
        self._tails: dict[str, set[str]] = {}

    # -- the version -----------------------------------------------------------

    def units(self, context: ConversionContext) -> list[Path]:
        """Every book in the version, in the order `books.xml` declares them.

        Ordering is the engine's job and not the driver's because it is a *cross*-
        book fact: the collection's manifest sits one level above every unit, and
        by the time `convert_unit` is called the run has already been sequenced.
        The index is built here for the same reason -- a popup in the first book
        can name the last one.
        """
        roots = super().units(context)
        if not roots:
            context.record(
                "OUTPUT_ROOT_MISSING",
                message="WebWorks tree with no wwhdata/ book root -- nothing to convert",
            )
            return []
        ordered = self._order(context, roots)
        self._scan(context)
        return ordered

    def _order(self, context: ConversionContext, roots: list[Path]) -> list[Path]:
        """Books grouped by collection, declared order inside each (§5.3.3).

        A collection is exactly a `wwhelp/books.xml` that declares a book other
        than itself -- the discriminator the directory layout does not give, since
        every *book* ships a `wwhelp/` of its own. Books no manifest mentions come
        last: 89 of 691, and dropping them would drop real content.
        """
        known = set(roots)
        claimed: set[Path] = set()
        ordered: list[Path] = []
        for candidate in sorted({root.parent for root in roots} | {context.tree}):
            collection = read_books(candidate / "wwhelp" / "books.xml")
            if collection is None or not collection.books:
                continue
            declared: list[tuple[Path, str, int]] = []
            for order, reference in enumerate(collection.books):
                book = candidate / Path(*PurePosixPath(reference.directory).parts)
                if book not in known or book in claimed:
                    continue
                claimed.add(book)
                declared.append((book, reference.group, order))
            for position, (book, group, order) in enumerate(declared):
                self._index.books[_relative(context.tree, book)] = _Book(
                    root=book,
                    name=_relative(context.tree, book),
                    collection=_relative(context.tree, candidate),
                    collection_name=collection.name,
                    group=group if len(collection.groups) > 1 else "",
                    order=order,
                    last=position == len(declared) - 1,
                )
                ordered.append(book)

        for book in sorted(root for root in roots if root not in claimed):
            name = _relative(context.tree, book)
            self._index.books[name] = _Book(
                root=book, name=name, collection=name, last=True,
            )
            ordered.append(book)
        return ordered

    def _scan(self, context: ConversionContext) -> None:
        """Reads every book's runtime and every topic's raw text, once.

        A regex scan and not a parse. It settles three things that cannot be known
        one topic at a time: which files this run will write, which anchor names
        each file contains, and which of them anything points at -- the last of
        which decides, per §5.3.8, the one anchor in fifteen that is emitted.
        """
        index = self._index
        for book in index.books.values():
            self._read_book(context, book)
            for alias in book.aliases():
                index.by_key.setdefault(alias, book.name)
            for relative in book.topics:
                source = _join(book.name, relative)
                index.topics[source.lower()] = links.to_markdown(PurePosixPath(source))
            for entry in book.toc:
                for node in entry.walk():
                    if node.anchor and node.index is not None and 0 <= node.index < len(book.files):
                        target = _join(book.name, book.files[node.index].href)
                        _add(index.referenced, target.lower(), node.anchor)
            self._read_csh(book, index)

        for book in index.books.values():
            for relative in book.topics:
                self._scan_topic(book, relative, index)

    def _read_book(self, context: ConversionContext, book: _Book) -> None:
        runtime = book.root / "wwhdata"
        files_js = runtime / "common" / "files.js"
        if files_js.is_file():
            book.files = read_files(files_js)
        else:
            # The 45 stripped books (§5.3.1). Reported rather than skipped: 1,395
            # topics is too many to drop, and `files.htm` titles every one of them.
            book.stripped = True
            book.files = read_files_htm(runtime / "files.htm")
            context.record(
                "NAV_NODE_DROPPED",
                path=book.name,
                message="stripped book: no wwhdata/js/toc.js, so no navigation",
            )
        book.toc = read_toc(runtime / "js" / "toc.js")
        book.title = read_return(runtime / "common" / "title.js")
        book.context_key = read_return(runtime / "common" / "context.js")
        book.topics = self._topics(context, book)

    def _topics(self, context: ConversionContext, book: _Book) -> list[str]:
        """Every convertible topic under one book, book-relative and sorted.

        The disk is the population, not the TOC: 961 genuine orphans (3.2%) have
        real titles and no navigation reaches them, and a TOC-driven walk drops all
        961 without saying so.
        """
        nested = [
            other for other in self._index.books.values()
            if other.root != book.root and book.root in other.root.parents
        ]
        found: list[str] = []
        for path in _walk_files(book.root):
            if path.suffix.lower() not in _HTML_SUFFIXES:
                continue
            relative = PurePosixPath(path.relative_to(book.root).as_posix())
            if is_skin_path(relative.parts, self.engine) or relative.parts[0] in RUNTIME_DIRECTORIES:
                continue
            reason = self._rejection(path, relative, nested, context.api_roots)
            if reason:
                book.skipped[reason] = book.skipped.get(reason, 0) + 1
                continue
            found.append(str(relative))
        return sorted(found)

    def _rejection(self, path: Path, relative: PurePosixPath, nested: list[_Book],
                   api_roots: list[Path]) -> str:
        """Why this file is not a topic, or `""` if it is one (§5.3.9)."""
        stem = relative.stem.split(".")[0].lower()
        if stem in STUB_STEMS:
            return "runtime-stub"
        if stem in GENERATED_LIST_STEMS:
            return "generated-list"
        if any(other.root in path.parents for other in nested):
            return "nested-book"
        if self.skips_api_references and is_api_reference(path, api_roots):
            return "api-reference"
        return ""

    def _read_csh(self, book: _Book, index: _Index) -> None:
        """`topics.js` targets are anchors too -- 43% of them carry one (§5.4.4).

        Left out of the reference set, the CSH map resolves to the right page and
        the wrong place on it, for nearly half the identifiers in the corpus.
        """
        path = book.root / "wwhdata" / "common" / "topics.js"
        if not path.is_file():
            return
        for entry in read_csh_source(path, CshFormat.WEBWORKS_TOPICS).entries:
            if entry.anchor and entry.link:
                _add(index.referenced, _join(book.name, entry.link).lower(), entry.anchor)

    def _scan_topic(self, book: _Book, relative: str, index: _Index) -> None:
        """One topic's anchor names and one topic's outbound references."""
        source = book.root / Path(*PurePosixPath(relative).parts)
        text = read_text(source)
        if text is None:
            return
        key = _join(book.name, relative).lower()
        base = PurePosixPath(posixpath.dirname(_join(book.name, relative)))
        names = {match.group(1) for match in _SCAN_ANCHOR.finditer(text)}
        if names:
            index.anchors.setdefault(key, set()).update(names)

        for match in _POPUP.finditer(text):
            path, _, fragment = match.group("target").partition("#")
            if not fragment:
                continue
            name = index.by_key.get(_book_key(match.group("book")))
            if name is None or not path:
                continue
            joined = posixpath.join(name, unquote(path)) if name else unquote(path)
            _add(index.referenced, posixpath.normpath(joined).lower(), fragment)

        for match in _SCAN_HREF.finditer(text):
            raw = match.group(1)
            if "WWHClickedPopup" in raw:
                continue
            reference = links.classify(raw)
            if not reference.fragment:
                continue
            if reference.kind is links.ReferenceKind.FRAGMENT:
                _add(index.referenced, key, reference.fragment)
            elif reference.resolvable and links.is_topic(reference.path):
                target = str(links.resolve(base, reference.path)).lower()
                _add(index.referenced, target, reference.fragment)

    # -- one book --------------------------------------------------------------

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        name = _relative(context.tree, root)
        book = self._index.books.get(name) or _Book(root=root, name=name)
        unit = Unit(root=root, name=name)
        for reason, count in book.skipped.items():
            unit.skip(reason, count)
        unit.metadata = _metadata(book)

        documents: dict[str, Document] = {}
        for relative in book.topics:
            document = self._convert(context, unit, book, relative)
            if document is not None:
                documents[relative.lower()] = document

        unit.documents = list(documents.values())
        unit.nav = self._navigation(context, unit, book, documents)
        self._tail(context, unit, book, documents)
        return unit

    def _convert(self, context: ConversionContext, unit: Unit, book: _Book,
                 relative: str) -> Document | None:
        source = book.root / Path(*PurePosixPath(relative).parts)
        reported = _join(unit.name, relative)
        text = read_text(source)
        if text is None:
            unit.skip("unreadable")
            context.record("CONTENT_MISSING", path=reported, message="could not be read")
            return None

        soup = markdown.parse(text)
        body = soup.body
        if body is None:
            unit.skip("no-content-container")
            context.record("CONTENT_MISSING", path=reported, message="no <body>")
            return None
        container = body.find("blockquote", recursive=False)
        whole_body = not isinstance(container, Tag)
        if whole_body:
            # The 2004-2006 flavour: 5 books at 0% and 634 at 100%, with nothing in
            # between (§5.3.6). Its prose sits directly in the body with the banner
            # beside it, so the fallback is real content and not a failure.
            container = body

        _strip_chrome(container, whole_body=whole_body)
        normalize(container)

        output = PurePosixPath(_join(unit.name, relative))
        renderer = WebWorksRenderer(
            engine=self,
            context=context,
            unit=unit,
            index=self._index,
            source=source,
            output=links.to_markdown(output),
            relative=links.to_markdown(PurePosixPath(relative)),
            base=PurePosixPath(posixpath.dirname(str(output))),
            key=str(output).lower(),
        )
        rendered = renderer.render(container)
        if not rendered.strip():
            unit.skip("empty")
            context.record("CONTENT_MISSING", path=reported, message="converted to nothing")
            return None

        return Document(
            source=source,
            relative=links.to_markdown(PurePosixPath(relative)),
            title=book.title_of(relative) or _title(soup),
            body=rendered,
            anchors=renderer.emitted,
        )

    # -- navigation ------------------------------------------------------------

    def _navigation(self, context: ConversionContext, unit: Unit, book: _Book,
                    documents: dict[str, Document]) -> list[NavNode]:
        """The book's TOC as nodes, plus the orphans it does not reach.

        The forest is returned as-is: 583 of 645 books have more than one top-level
        node, and §6.2 makes the book itself the parent with children and no page.
        """
        filed: set[str] = set()
        self._dropped = 0
        nodes = [
            node for node in (self._node(entry, book, documents, filed) for entry in book.toc)
            if node is not None
        ]

        orphans = [
            document for key, document in documents.items() if key not in filed
        ]
        if orphans:
            context.record("TOC_ORPHAN", path=unit.name, count=len(orphans),
                           message=f"{len(orphans)} converted topic(s) in no TOC entry")
            nodes.append(NavNode(
                label="Unfiled",
                children=[NavNode(label=document.nav_label, document=document.relative)
                          for document in sorted(orphans, key=lambda d: str(d.relative))],
            ))
        if self._dropped:
            context.record("NAV_NODE_DROPPED", path=unit.name, count=self._dropped,
                           message=f"{self._dropped} node(s) with no page and no children")
        return nodes

    def _node(self, entry: TocEntry, book: _Book, documents: dict[str, Document],
              filed: set[str]) -> NavNode | None:
        key = ""
        if entry.index is not None and 0 <= entry.index < len(book.files):
            key = book.files[entry.index].href.lower()
        document = documents.get(key)
        if document is not None:
            filed.add(key)

        children = [
            child for child in
            (self._node(child, book, documents, filed) for child in entry.children)
            if child is not None
        ]
        if document is not None:
            children = [child for child in children if child.document != document.relative]
        if document is None and not children:
            self._dropped += 1
            return None
        return NavNode(
            label=entry.label or (document.title if document is not None else ""),
            document=document.relative if document is not None else None,
            anchor=entry.anchor,
            children=children,
        )

    def _tail(self, context: ConversionContext, unit: Unit, book: _Book,
              documents: dict[str, Document]) -> None:
        """Support and legal, which here can be a page *or* a whole book (§5.3.5).

        31 books are one of these two pages and nothing else, so the label comes
        from `title.js` when the book is one of them and from a top-level TOC node
        otherwise. Absence is reported **once per collection**, not once per book:
        a 40-book collection has one legal page by design, and 39 rows saying the
        other 39 books lack one would bury the collection that genuinely does.
        """
        supplied = self._tails.setdefault(book.collection, set())
        for attribute, matches, label in (
            ("support", is_support_label, "support"),
            ("legal", is_legal_label, "legal"),
        ):
            found = self._tail_page(book, documents, matches)
            if found is not None:
                setattr(unit, attribute, found)
                supplied.add(label)
        if not book.last:
            return
        for label in ("support", "legal"):
            if label not in supplied:
                context.record("TAIL_PAGE_MISSING", path=book.collection or unit.name,
                               message=f"no {label} page in this collection")

    def _tail_page(self, book: _Book, documents: dict[str, Document],
                   matches: Callable[[str, str], bool]) -> PurePosixPath | None:
        if book.title and matches(book.title, ""):
            # A standalone tail book: three files, of which the framesets are
            # already skipped, so the one remaining page is the tail. Sorted rather
            # than first-seen, so two survivors resolve the same way every run.
            ordered = sorted(documents.values(), key=lambda document: str(document.relative))
            return ordered[0].relative if ordered else None
        for entry in book.toc:
            if entry.index is None or not 0 <= entry.index < len(book.files):
                continue
            href = book.files[entry.index].href
            if matches(entry.label, href):
                document = documents.get(href.lower())
                if document is not None:
                    return document.relative
        # The TOC is not where these pages live. `copyrigh.htm` is in 446 books and
        # in the TOC of almost none of them -- it is the second-largest group of
        # orphans in the corpus -- so a TOC-only search finds a legal page for 2
        # books in 70. Sorted, so a book with two candidates answers the same way
        # every run.
        for document in sorted(documents.values(), key=lambda item: str(item.relative)):
            if matches(document.title, str(document.relative)):
                return document.relative
        return None

    # -- findings the renderer raises -----------------------------------------

    def unmapped_alert(self, context: ConversionContext, unit: Unit, label: str) -> None:
        """One row per distinct label. `IconSecurity` is the corpus's only miss.

        It is left out of `transforms/callouts.py` on purpose: GFM has five alert
        kinds and none of them is "security", so the honest outcome is a NOTE and a
        line saying the label was dropped -- not a sixth alias quietly aliased onto
        WARNING.
        """
        if label in self._alerts:
            return
        self._alerts.add(label)
        context.record("ALERT_LABEL_UNMAPPED", path=unit.name,
                       message=f"{label!r} is outside the alert vocabulary; rendered as NOTE")

    def dangling_link(self, context: ConversionContext, unit: Unit, source: Path,
                      raw: str) -> None:
        context.record("TOPIC_LINK_DANGLING", path=unit.name, count=1,
                       message=f"{source.name} -> {raw}")


# -- small readers -------------------------------------------------------------


def _metadata(book: _Book) -> dict[str, str]:
    """What Phase 6 needs to synthesize the collection index it has no page for.

    §5.3.5: WebWorks has no `DefaultUrl` and both candidate files are framesets, so
    `unit.landing` stays None here and §6.2 generates the node. These are its
    inputs, carried rather than guessed at.
    """
    values = {
        "collection": book.collection,
        "collection_name": book.collection_name,
        "book_group": book.group,
        "book_order": str(book.order),
        "book_title": book.title,
    }
    return {key: value for key, value in values.items() if value}


def _walk_files(root: Path):
    for directory, names, files in os.walk(root):
        names[:] = [name for name in sorted(names) if name.lower() not in RUNTIME_DIRECTORIES]
        for name in sorted(files):
            yield Path(directory) / name


def _title(soup: BeautifulSoup) -> str:
    """`<title>`, which agrees with `files.js` in 30,537 of 30,601 topics.

    Only the fallback: `files.js` is the cleaner of the two -- its titles are the
    ones without the `&nbsp;` padding -- and there is no `h1` to fall back to,
    since the topic's own heading is a `div.N1Heading`.
    """
    tag = soup.find("title")
    return " ".join(tag.get_text(" ").split()) if isinstance(tag, Tag) else ""


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ").split()) if node is not None else ""


def _raw_classes(tag: Tag) -> list[str]:
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


def _primary_class(tag: Tag) -> str:
    classes = _raw_classes(tag)
    return classes[0] if classes else ""


def _heading_level(name: str) -> int:
    match = _HEADING_CLASS.match(name)
    if match is not None:
        return min(int(match.group(1)), 6)
    return _FLAT_HEADINGS.get(name.lower(), 0)


def _direct_rows(table: Tag) -> list[Tag]:
    rows: list[Tag] = []
    for child in table.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "tr":
            rows.append(child)
        elif child.name in ("thead", "tbody", "tfoot"):
            rows.extend(row for row in child.children
                        if isinstance(row, Tag) and row.name == "tr")
    return rows


def _direct_cells(row: Tag) -> list[Tag]:
    return [child for child in row.children
            if isinstance(child, Tag) and child.name in ("td", "th")]


def _book_key(value: str) -> str:
    """`API Reference` and `API_Reference` are the same book (§5.3.3)."""
    return _NON_WORD.sub("_", value.strip()).strip("_").lower()


def _join(unit: str, relative: str) -> str:
    return f"{unit}/{relative}" if unit else relative


def _add(into: dict[str, set[str]], key: str, value: str) -> None:
    into.setdefault(key, set()).add(value)


def _relative(tree: Path, path: Path) -> str:
    try:
        return path.relative_to(tree).as_posix()
    except ValueError:  # pragma: no cover - the driver walks from the tree
        return path.name


__all__ = ["SPAN_TO_TAG", "WebWorksEngine", "WebWorksRenderer", "normalize"]
