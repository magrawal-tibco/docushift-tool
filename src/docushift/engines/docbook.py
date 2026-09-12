"""The DocBook engine: 10 versions, 2 products, and no runtime metadata at all.

`architecture.md` §5.6, measured on 2026-09-11 against the `html-to-md` cache.
The corpus's fourth and last convertible engine and its smallest by version
count -- `str` at six versions and `sfire-sfds` at four, all of them near-copies
of one another. It is also the only engine with no sidecar to read: no TOC file,
no file index, no CSH map. Everything below is recovered from the HTML, which
one stylesheet at one version (`DocBook XSL Stylesheets V1.76.1`) wrote.

What the corpus decided:

- **One unit per version, rooted at `<tree>/html`.** A `str` version also ships up
  to eight top-level directories that duplicate a guide already under `html/`,
  **byte for byte** -- identical N, differ 0, only-here 0, in 42 of 42 measured.
  `engines/roots.py` rejects them by asking whether a page's stylesheet link
  resolves inside its own directory, and this engine reports each one.
- **`div#mainContent` is the container and the chrome removal in one.** 1,178 of
  1,178 pages have it and every header, breadcrumb, nav menu and footer is
  *outside* it -- the WebWorks shape (§5.3.6), not DITA's interleaved one.
- **Navigation is three sources.** A recursive `div.toc` walk covers 100% of the
  pages in 21 of 24 guides; a two-hop link graph covers the three generated
  guides that ship no `div.toc`, taking the unfiled total from ~430 to 42 of
  1,178 (3.6%); and `p#mainhelp-navmenu` supplies the top level's order and its
  short labels for 13 of the 24 guides.
- **Only DocBook-marked pages convert.** The package holds four generators and the
  prose is a quarter of the file count -- `html/apidocs` alone is 2,265-2,481
  javadoc and Doxygen files. Every other page is skipped **with a reason**.
- **The tail pages come from `div#footer`, never from a title.** Matching on the
  label picks `apiguide/thirdpartylibs.html` -- "Using Third-Party JARs and Native
  Libraries", a real technical topic -- because `is_legal_label` matches "third
  party" and the wrong page sorts first. The footer names both pages by `li` id
  on 100% of sampled pages, so there is nothing to guess.

Three things measured here that are the tempting wrong answer elsewhere:

1. **A mapped span must not be mapped naively.** 3,145 `span.bold` contain a
   `strong`, 2,088 `span.command` do, 1,235 `span.keycap` do, and 661
   `span.emphasis` contain an `em`. Wrapping those again emits `****text****`, so
   a normalize pass unwraps the redundant child and `span.emphasis` is never
   mapped at all -- its `em` already says everything the class does.
2. **No fragment in the corpus resolves to an element `id`.** 5,548 fragments are
   referenced; 5,539 hit a plain `a[name]`, 0 hit an `a.ix`, 9 hit nothing. So
   DITA's id-pairing pass (§5.2.8) is not needed, and the 3,347 `a.ix` index
   markers -- whose `name` is human-readable prose with spaces -- are dropped
   whole rather than emitted as anchors nothing points at.
3. **`html/index.html` is a real landing page.** It is a `div.book` with prose,
   not a frameset stub, so `unit.landing` is a converted document. This is the
   only one of the four engines that does not leave Phase 6 to synthesize one.

**Two parses per page**, the idiom `dita.py` established for the same reason: the
plan pass settles which anchors anything points at and which page every href
names, and neither can be known from the file being rewritten. 1,178 pages is
small enough that reading twice is cheaper than holding 1,178 DOMs.
"""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from bs4 import Tag
from bs4.element import PreformattedString

from docushift.apiref import is_api_reference
from docushift.engines.base import (
    BaseEngine,
    ConversionContext,
    Document,
    NavNode,
    Unit,
    is_legal_label,
    register,
)
from docushift.engines.roots import is_docbook_page, is_skin_path
from docushift.models import SourceEngine
from docushift.transforms import callouts, links, markdown
from docushift.transforms import code as code_transform

# The one container (§5.6.4). Present on 1,178 of 1,178 pages, with every piece of
# chrome outside it, so selecting it *is* the chrome removal. There is deliberately
# no `<body>` fallback: a page without it would convert its own header, breadcrumb
# trail and footer into prose, which is worse than the reported absence.
CONTENT_ID = "mainContent"

# Publisher-generated navigation inside the container. `toc.yml` reproduces it
# exactly and correctly, so emitting it as well puts a link list at the top of
# every book and part page. The same call `dita.py` makes about `div.familylinks`.
NAVIGATION_CLASSES = frozenset({"toc", "navheader", "navfooter"})

# DocBook's admonition vocabulary, which is **closed at five** and maps completely:
# note 535, caution 239, important 211, tip 52, warning 33. Every one is
# `div.<kind> > h3.title + body`, so the class is the kind and the `h3.title` is
# the printed label GFM supplies for itself. Because all five map,
# `ALERT_LABEL_UNMAPPED` is not reachable from this engine -- a property of the
# source, not an omission (§5.6.7).
ADMONITION_CLASSES = frozenset({"note", "tip", "important", "warning", "caution"})

# A caption that precedes its content in source order: `div.figure` is
# `a + p.title + div.figure-contents` and `div.example` is
# `a + p.title[b] + div.example-contents[pre]`. `div.abstract` also carries a
# `p.title` and it is **empty on every occurrence**, which the generic path
# already renders as nothing -- so it is not listed here.
CAPTIONED_CLASSES = frozenset({"figure", "example"})

# §5.6.7. Only what was measured: `bold` 3,145, `command` 2,088, `keycap` 1,235.
# `command` maps to code rather than to bold on purpose -- the stylesheet renders
# a command name in bold and DocBook means it as a command, which is the same
# correction `dita.py` makes for `cmdname`. `emphasis` is deliberately absent:
# it wraps an `em` that already says it, and mapping it would emphasise twice.
SPAN_TO_STYLE = {
    "command": "code",
    "bold": "strong",
    "keycap": "strong",
}

# What a mapped span may contain exactly once and redundantly. Unwrapped before
# the walk sees it, because `**` around already-`**` text is `****text****`.
REDUNDANT_WRAPPERS = frozenset({"strong", "b", "em", "i"})

# The top-level menu, on `html/index.html` and `html/lvindex.html` alike. 14
# entries naming 13 of the 24 guide directories; the labels wrap across lines in
# some versions (`SB\n  Start`), so they are whitespace-collapsed on the way in.
MENU_ID = "mainhelp-navmenu"

# The tail pages, declared by `li` id in `div#footer` on 100% of sampled pages
# (§5.6.9). `is_legal_label` already matches `legal-and-third-party-notices` and
# `copyright`; support does not match "contact" and must not be widened to, so
# the one id this engine needs lives here rather than in `engines/base.py`.
FOOTER_ID = "footer"
FOOTER_SUPPORT_IDS = frozenset({"contact"})

# The generators that share the package with DocBook (§5.6.1). Named so that a
# skipped page says *why* it was skipped rather than only that it was.
FOREIGN_MARKERS: tuple[tuple[bytes, str], ...] = (
    (b"Generated by javadoc", "javadoc"),
    (b"javadoc/", "javadoc"),
    (b"Doxygen", "doxygen"),
    (b"doxygen", "doxygen"),
    (b"Doxia", "doxia"),
)
_HEAD_BYTES = 6000

_HTML_SUFFIXES = (".htm", ".html")
_HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]

# How far the recursive `div.toc` walk descends, and how many hops the link-graph
# fallback takes. The measured book TOC nests one level and its part pages carry a
# duplicate of their own slice, so 4 is slack rather than a limit; the graph is 2
# because that is what was measured to close the gap (§5.6.5).
_TOC_DEPTH = 4
_GRAPH_HOPS = 2


# -- the renderer --------------------------------------------------------------


class DocBookRenderer(markdown.Renderer):
    """DocBook XSL's vocabulary, over `transforms/markdown.py`'s walk."""

    def __init__(self, engine: "DocBookEngine", context: ConversionContext, unit: Unit,
                 plan: "_Plan", page: "_Page"):
        self.engine = engine
        self.context = context
        self.unit = unit
        self.plan = plan
        self.page = page
        self.source = page.source
        self.output = page.output

    # -- blocks ---------------------------------------------------------------

    def block_override(self, tag: Tag) -> str | None:
        if tag.name in ("script", "style"):
            return ""
        classes = _classes(tag)
        if tag.name == "table" and "simplelist" in classes:
            return self._simplelist(tag)
        if tag.name != "div":
            return None
        if classes & NAVIGATION_CLASSES:
            return ""
        kinds = sorted(classes & ADMONITION_CLASSES)
        if kinds:
            return self._admonition(tag, kinds[0])
        if classes & CAPTIONED_CLASSES:
            return self._captioned(tag)
        return None

    def _admonition(self, tag: Tag, name: str) -> str:
        """One admonition, with its printed label deleted (§5.6.7).

        The `h3.title` reads "Note", "Caution" and so on, and GFM's alert syntax
        draws that label itself -- leaving it emits `> [!NOTE]` followed by
        `### Note`. All five kinds map, so `alert_for` never returns None here and
        there is no unmapped-label branch to report from.
        """
        for title in tag.find_all("h3", class_="title", recursive=False):
            title.decompose()
        kind = callouts.alert_for(name) or callouts.Alert.NOTE
        return callouts.render(kind, "\n\n".join(self.blocks(tag)))

    def _captioned(self, tag: Tag) -> str:
        """A figure or an example: the caption first, italic, then the content."""
        caption = ""
        for title in tag.find_all("p", class_="title", recursive=False):
            caption = " ".join(markdown.text_of(title).split()) or caption
            title.decompose()
        blocks = [block for block in self.blocks(tag) if block.strip()]
        if caption:
            blocks.insert(0, markdown.wrap(markdown.escape(caption), "*"))
        return "\n\n".join(blocks)

    def _simplelist(self, tag: Tag) -> str:
        """`table.simplelist` is a list, not a table (§5.6.7).

        192 of them, each a run of rows of one or two cells holding a link or a
        code span. A pipe table with no header row is not GFM, and the content is
        a list of names -- so it is emitted as one.
        """
        items: list[str] = []
        for cell in tag.find_all(["td", "th"]):
            text = self.inline_children(cell).strip()
            if text:
                items.append(f"- {markdown.escape_leading(text)}")
        return "\n".join(items)

    # -- inline ---------------------------------------------------------------

    def inline_override(self, tag: Tag) -> str | None:
        if tag.name == "a" and tag.get("name") and not tag.get("href"):
            # A referenced anchor that `_prune_anchors` kept. Emitted as HTML
            # because GFM has no anchor syntax, and as an `id` because that is
            # what a modern renderer resolves a fragment against.
            return f'<a id="{tag["name"]}"></a>'
        if tag.name != "span":
            return None
        for name in _raw_classes(tag):
            style = SPAN_TO_STYLE.get(name.lower())
            if style == "code":
                return code_transform.inline(markdown.text_of(tag))
            if style == "strong":
                return markdown.wrap(self.inline_children(tag), "**")
        return None

    # -- references (invariant 13) --------------------------------------------

    def link(self, tag: Tag) -> str | None:
        raw = str(tag.get("href") or "")
        reference = links.classify(raw)

        if reference.kind is links.ReferenceKind.FRAGMENT:
            # A bookmark into this same page -- 16 of the corpus's `div.toc` links.
            if reference.fragment in self.page.anchors:
                return f"#{reference.fragment}"
            self.engine.dropped_fragment(self.context, self.unit, self.source, reference.fragment)
            return None
        if reference.kind is links.ReferenceKind.ABSOLUTE:
            return raw.strip()
        if reference.kind is links.ReferenceKind.ROOTED:
            # `/cgi-bin/olink?sysid=…`: a cross-book olink the build baked in
            # against a CGI script that a static tree does not have. Broken at the
            # source and broken here; the text survives and the claim does not.
            self.engine.dangling_link(self.context, self.unit, self.source, raw.strip())
            return None
        if not reference.resolvable:
            return None
        if not links.is_topic(reference.path):
            return self._asset(reference.raw)

        resolved = links.resolve(self.page.relative.parent, reference.path)
        target = self.plan.targets.get(str(resolved).lower())
        if target is None:
            # Almost all of these are `../apidocs/…`: the API tree exists on disk
            # and has no converted counterpart, exactly as in DITA (§5.2.8).
            self.engine.dangling_link(self.context, self.unit, self.source, reference.path)
            return None
        fragment = self._fragment(target, reference.fragment)
        return links.emit(links.relative_to(self.output, target.output), fragment)

    def _fragment(self, target: "_Page", fragment: str) -> str:
        """The bookmark to keep, or `""`. 9 of 5,548 in the corpus name nothing."""
        if not fragment:
            return ""
        if fragment in target.anchors:
            return fragment
        self.engine.dropped_fragment(self.context, self.unit, self.source, fragment)
        return ""

    def image(self, tag: Tag) -> str | None:
        """2,003 `../images/…` and 116 in a subdirectory, all inside `html/`."""
        return self._asset(str(tag.get("src") or ""))

    def _asset(self, raw: str) -> str | None:
        """One non-topic reference, resolved and copied by the same call (§6.4)."""
        copier = self.context.assets
        if copier is None:  # pragma: no cover - the driver always sets one
            return None
        return copier.resolve(self.source, self.output, raw).url or None


# -- the plan ------------------------------------------------------------------


@dataclass
class _Entry:
    """One `dt` of a `div.toc`, with whatever the following `dd` nests under it."""

    label: str
    href: str = ""
    children: list["_Entry"] = field(default_factory=list)


@dataclass
class _Page:
    """One DocBook-generated page, as the plan pass sees it."""

    source: Path
    # Relative to the unit root, in source form: `authoring/typechecking.html`.
    relative: PurePosixPath
    # Where the Markdown goes. Mirrored, never slugged: the guide directory is the
    # only hierarchy this corpus has, and title collisions across guides are
    # routine (`index.html` alone is 24 of them).
    output: PurePosixPath
    # The first path segment, or `""` for a page at the unit root.
    guide: str = ""
    title: str = ""
    # Plain `a[name]` values this page defines. `a.ix` is never here.
    anchors: set[str] = field(default_factory=set)
    # This page's own `div.toc`, where it has one.
    toc: list[_Entry] = field(default_factory=list)
    # In-unit topic targets linked from the container but *not* from its `div.toc`,
    # in document order. The link-graph fallback of §5.6.5 walks these.
    outbound: list[PurePosixPath] = field(default_factory=list)


@dataclass
class _Plan:
    """What one unit will convert, settled before the first page is rewritten."""

    pages: list[_Page] = field(default_factory=list)
    # Unit-relative source path, case-folded -> page. What `link()` resolves against.
    targets: dict[str, _Page] = field(default_factory=dict)
    # Every fragment anything in the unit points at. An anchor outside this set is
    # not emitted: 10,753 are defined and 5,539 are ever named.
    referenced: set[str] = field(default_factory=set)
    # `p#mainhelp-navmenu`, as (label, unit-relative target).
    menu: list[tuple[str, PurePosixPath]] = field(default_factory=list)
    # `div#footer`'s `li` ids -> unit-relative target.
    footer: dict[str, PurePosixPath] = field(default_factory=dict)


# -- the engine ----------------------------------------------------------------


@register
class DocBookEngine(BaseEngine):
    """DocBook XSL Stylesheets V1.76.1, as published by StreamBase."""

    engine = SourceEngine.DOCBOOK

    def __init__(self) -> None:
        self._dropped = 0
        self._unfiled = 0

    def units(self, context: ConversionContext) -> list[Path]:
        """The one root, and a report line for every duplicate of it (§5.6.3).

        The duplicates are byte-identical copies of a guide already under `html/`
        and converting them would publish every affected guide twice. They are
        rejected by the root rule rather than here -- but a rejection nobody hears
        about is indistinguishable from not having looked, so each one is named.
        """
        roots = super().units(context)
        for duplicate in _duplicate_roots(context.tree, roots):
            context.record(
                "DOCSET_SKIPPED", path=_relative(context.tree, duplicate),
                message="byte-identical duplicate of the same directory under html/",
            )
        if not roots:
            context.record(
                "DOCSET_SKIPPED",
                message="DocBook tree with no directory whose pages link a stylesheet "
                        "inside it -- no unit of work could be located",
            )
        return roots

    # -- one unit --------------------------------------------------------------

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        unit = Unit(root=root, name=_relative(context.tree, root))
        plan = self._plan(context, unit, root)

        documents: dict[str, Document] = {}
        for page in plan.pages:
            document = self._convert(context, unit, plan, page)
            if document is not None:
                documents[str(document.relative)] = document

        unit.documents = list(documents.values())
        unit.nav = self._navigation(context, unit, plan, documents)
        self._landing(unit, plan, documents)
        self._tail(context, unit, plan, documents)
        return unit

    # -- what to convert -------------------------------------------------------

    def _plan(self, context: ConversionContext, unit: Unit, root: Path) -> _Plan:
        """Walks the unit once and classifies every HTML file it holds.

        The walk is over the whole subtree rather than the root's own files,
        because unlike DITA this engine's hierarchy *is* its directories -- 24
        guide directories under one root -- and unlike WebWorks the API tree is
        inside the unit rather than beside it.
        """
        plan = _Plan()
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _HTML_SUFFIXES:
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if is_skin_path(relative.parts, self.engine):
                continue
            if self.skips_api_references and is_api_reference(path, context.api_roots):
                unit.skip("api-reference")
                continue
            if not is_docbook_page(path):
                unit.skip(_foreign_reason(path))
                continue
            self._profile(context, unit, plan, path, relative)

        for page in plan.pages:
            plan.targets[str(page.relative).lower()] = page
        return plan

    def _profile(self, context: ConversionContext, unit: Unit, plan: _Plan,
                 path: Path, relative: PurePosixPath) -> None:
        """One page's title, anchors, TOC and outbound links, from one parse."""
        text = _read(path)
        if text is None:
            unit.skip("unreadable")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{relative}".lstrip("/"),
                           message="could not be read")
            return
        soup = markdown.parse(text)
        container = soup.find(id=CONTENT_ID)
        if not isinstance(container, Tag):
            unit.skip("no-content-container")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{relative}".lstrip("/"),
                           message=f"no #{CONTENT_ID}")
            return

        page = _Page(
            source=path,
            relative=relative,
            output=links.to_markdown(relative),
            guide=relative.parts[0] if len(relative.parts) > 1 else "",
            title=_document_title(soup),
        )
        base = relative.parent
        for anchor in container.find_all("a"):
            name = anchor.get("name")
            if name and not anchor.get("href") and "ix" not in _classes(anchor):
                page.anchors.add(str(name))
            href = anchor.get("href")
            if not href:
                continue
            reference = links.classify(str(href))
            if reference.fragment:
                plan.referenced.add(reference.fragment.lower())
            if _in_navigation(anchor):
                continue
            target = _in_unit_target(base, reference)
            if target is not None:
                page.outbound.append(target)

        listing = container.find("div", class_="toc")
        if isinstance(listing, Tag):
            page.toc = _read_toc(listing)
        plan.pages.append(page)

        if not plan.menu:
            plan.menu = _read_menu(soup, base)
        if not plan.footer:
            plan.footer = _read_footer(soup, base)

    # -- one page --------------------------------------------------------------

    def _convert(self, context: ConversionContext, unit: Unit, plan: _Plan,
                 page: _Page) -> Document | None:
        text = _read(page.source)
        if text is None:  # pragma: no cover - read once already in the plan pass
            unit.skip("unreadable")
            return None
        soup = markdown.parse(text)
        container = soup.find(id=CONTENT_ID)
        if not isinstance(container, Tag):  # pragma: no cover - checked in the plan pass
            unit.skip("no-content-container")
            return None

        _strip_comments(container)
        _unwrap_layout_tables(container)
        _unwrap_redundant_spans(container)
        emitted = _prune_anchors(container, plan.referenced)

        heading = container.find(_HEADINGS)
        if isinstance(heading, Tag) and heading.name != "h1":
            # 921 of the corpus's 11,689 pages open at `h2` rather than `h1`:
            # every `div.refentry`, whose visible title is an `h2` holding a
            # `span.refentrytitle`, and every generated index. In 921 of 921 that
            # heading's text is exactly `<title>`, so it *is* the page title and
            # is promoted -- prepending a second `#` above it would say the page
            # has two titles.
            heading.name = "h1"

        body = DocBookRenderer(self, context, unit, plan, page).render(container)
        if page.title and heading is None:
            # No heading anywhere in the container -- unmeasured in this corpus,
            # where all 11,689 pages carry at least one, but a page with prose and
            # no `#` is worse than one titled from `<title>` (§5.6.6).
            body = f"# {markdown.escape(page.title)}\n\n{body}".rstrip("\n")

        return Document(source=page.source, relative=page.output, title=page.title,
                        body=body, anchors=emitted)

    # -- navigation ------------------------------------------------------------

    def _navigation(self, context: ConversionContext, unit: Unit, plan: _Plan,
                    documents: dict[str, Document]) -> list[NavNode]:
        """One node per guide, in menu order, then everything the menu did not name.

        Three sources in one pass, in the order §5.6.5 measured them: the guide's
        own recursive `div.toc`, then a two-hop link graph for the three guides
        that ship no `div.toc` at all, then whatever is still unfiled -- 42 of
        1,178 pages, appended in source order rather than dropped.
        """
        filed: set[str] = set()
        self._dropped = 0
        self._unfiled = 0
        landing = plan.targets.get("index.html")
        if landing is not None:
            # Hoisted to `unit.landing`, so it is not also a node.
            filed.add(str(landing.output))

        nodes: list[NavNode] = []
        for guide, label, book in _guides(plan):
            node = self._guide_node(plan, documents, filed, guide, label, book)
            if node is not None:
                nodes.append(node)

        orphans = [document for key, document in documents.items() if key not in filed]
        unfiled = self._unfiled + len(orphans)
        if unfiled:
            # 42 of 1,178 in the survey (3.6%). Counted rather than merely placed:
            # the three sources are what navigation quality *is* for this engine,
            # and a run where the number jumps is a run where a `div.toc` stopped
            # parsing. The pages themselves are not in an "Unfiled" bucket unless
            # they belong to no guide at all -- their guide is where they belong.
            context.record("TOC_ORPHAN", path=unit.name, count=unfiled,
                           message=f"{unfiled} converted page(s) reached by no TOC entry "
                                   "and by no link from a book page")
        if orphans:
            nodes.append(NavNode(
                label="Unfiled",
                children=[NavNode(label=document.nav_label, document=document.relative)
                          for document in sorted(orphans, key=lambda d: str(d.relative))],
            ))
        if self._dropped:
            context.record("NAV_NODE_DROPPED", path=unit.name, count=self._dropped,
                           message=f"{self._dropped} TOC entry/entries naming no converted page")
        return nodes

    def _guide_node(self, plan: _Plan, documents: dict[str, Document], filed: set[str],
                    guide: str, label: str, book: _Page | None) -> NavNode | None:
        children: list[NavNode] = []
        document = None
        if book is not None:
            key = str(book.output)
            document = documents.get(key)
            if document is not None:
                filed.add(key)
            children.extend(self._toc_nodes(book, plan, documents, filed, 0))
            children.extend(self._graph_nodes(book, plan, documents, filed))

        for page in plan.pages:
            if page.guide != guide:
                continue
            key = str(page.output)
            if key in filed or key not in documents:
                continue
            filed.add(key)
            self._unfiled += 1
            children.append(NavNode(label=documents[key].nav_label, document=page.output))

        if document is None and not children:
            return None
        title = label or (document.title if document is not None else guide)
        return NavNode(label=title,
                       document=document.relative if document is not None else None,
                       children=children)

    def _toc_nodes(self, base: _Page, plan: _Plan, documents: dict[str, Document],
                   filed: set[str], depth: int) -> list[NavNode]:
        return [
            node for node in
            (self._toc_node(entry, base, plan, documents, filed, depth) for entry in base.toc)
            if node is not None
        ]

    def _toc_node(self, entry: _Entry, base: _Page, plan: _Plan,
                  documents: dict[str, Document], filed: set[str], depth: int) -> NavNode | None:
        """One `div.toc` entry, its nested entries, and the target's own TOC.

        The recursion is what closes the last 0% -- a book's TOC lists its parts
        and each part page carries a TOC of its own sections. The `filed` guard is
        what keeps it finite and non-duplicating: a part page's TOC is a copy of
        the slice the book already placed, so the second sighting adds nothing.
        """
        reference = links.classify(entry.href)
        target = None
        if entry.href:
            resolved = links.resolve(base.relative.parent, reference.path) if reference.path else base.relative
            target = plan.targets.get(str(resolved).lower())

        children = [
            node for node in
            (self._toc_node(child, base, plan, documents, filed, depth) for child in entry.children)
            if node is not None
        ]

        if target is None:
            if not children:
                self._dropped += 1
            return NavNode(label=entry.label, children=children) if children else None

        key = str(target.output)
        if key in filed:
            # A second sighting. Worth a node only when it names a section of a
            # page already placed, which is how `samplesinfo` publishes its
            # 200-entry contents list -- one page, many anchors.
            if reference.fragment and reference.fragment in target.anchors:
                return NavNode(label=entry.label, document=target.output,
                               anchor=reference.fragment)
            return NavNode(label=entry.label, children=children) if children else None

        filed.add(key)
        document = documents.get(key)
        if depth < _TOC_DEPTH:
            children.extend(self._toc_nodes(target, plan, documents, filed, depth + 1))
        if document is None:
            self._dropped += 1
            return NavNode(label=entry.label, children=children) if children else None
        return NavNode(label=entry.label or document.nav_label, document=target.output,
                       anchor=reference.fragment if reference.fragment in target.anchors else "",
                       children=children)

    def _graph_nodes(self, book: _Page, plan: _Plan, documents: dict[str, Document],
                     filed: set[str]) -> list[NavNode]:
        """The two-hop in-guide link graph (§5.6.5).

        `adaptersguide`, `samplesinfo` and `lv-reference` are generated lists whose
        book page links its members directly, with no `div.toc` to walk. Following
        the book page's own links and then theirs files 388 of the 430 pages that
        would otherwise be orphans, and costs nothing on the 21 guides whose TOC
        already covers everything -- there, every target is filed already.
        """
        out: list[NavNode] = []
        frontier = [book]
        seen = {book.relative}
        for _ in range(_GRAPH_HOPS):
            following: list[_Page] = []
            for page in frontier:
                for relative in page.outbound:
                    if relative in seen:
                        continue
                    seen.add(relative)
                    target = plan.targets.get(str(relative).lower())
                    if target is None or target.guide != book.guide:
                        continue
                    following.append(target)
                    key = str(target.output)
                    if key in filed or key not in documents:
                        continue
                    filed.add(key)
                    out.append(NavNode(label=documents[key].nav_label, document=target.output))
            frontier = following
        return out

    # -- the version's own pages ------------------------------------------------

    def _landing(self, unit: Unit, plan: _Plan, documents: dict[str, Document]) -> None:
        """`html/index.html`, which is a real page here and not a frameset stub."""
        page = plan.targets.get("index.html")
        if page is not None and str(page.output) in documents:
            unit.landing = page.output

    def _tail(self, context: ConversionContext, unit: Unit, plan: _Plan,
              documents: dict[str, Document]) -> None:
        """Support and legal, read from `div#footer`'s declared `li` ids (§5.6.9).

        Not from the label and not from the path. `is_legal_label` matches "third
        party", so a title search finds `apiguide/thirdpartylibs.html` -- a topic
        about packaging JARs -- before `welcome/legal-and-third-party-notices.html`
        and picks the wrong one. The footer says which pages these are.
        """
        for attribute, matches, label in (
            ("support", lambda key: key in FOOTER_SUPPORT_IDS, "support"),
            ("legal", is_legal_label, "legal"),
        ):
            found = None
            for key, relative in sorted(plan.footer.items()):
                if not matches(key):
                    continue
                page = plan.targets.get(str(relative).lower())
                found = documents.get(str(page.output)) if page is not None else None
                if found is not None:
                    break
            if found is None:
                context.record("TAIL_PAGE_MISSING", path=unit.name,
                               message=f"no {label} page declared in #{FOOTER_ID}")
                continue
            setattr(unit, attribute, found.relative)

    # -- findings the renderer raises -----------------------------------------

    def dangling_link(self, context: ConversionContext, unit: Unit, source: Path, raw: str) -> None:
        """A reference this run produced no page for. Usually `../apidocs/…`."""
        context.record("TOPIC_LINK_DANGLING", path=unit.name, count=1,
                       message=f"{source.name} -> {raw}")

    def dropped_fragment(self, context: ConversionContext, unit: Unit,
                         source: Path, fragment: str) -> None:
        """A bookmark naming no anchor in its target. The file link survives."""
        context.record("TOPIC_LINK_DANGLING", path=unit.name, count=1,
                       message=f"{source.name} -> #{fragment} (anchor absent; link kept, bookmark dropped)")


# -- DOM passes ----------------------------------------------------------------


def _strip_comments(container: Tag) -> None:
    for element in list(container.descendants):
        if isinstance(element, PreformattedString):
            element.extract()
    for element in container.find_all(["script", "style"]):
        element.decompose()


def _unwrap_layout_tables(container: Tag) -> None:
    """`div.mediaobject > table > tr > td > img` is centring, not tabulation.

    1,126 of them. Left alone they become a one-cell pipe table wrapped around an
    image, which no reader wants and `tables.py` would rightly refuse to make GFM.
    """
    for media in container.find_all("div", class_="mediaobject"):
        for table in media.find_all("table"):
            for element in table.find_all(["thead", "tbody", "tfoot", "tr", "td", "th"]):
                element.unwrap()
            table.unwrap()


def _unwrap_redundant_spans(container: Tag) -> None:
    """Removes the inner `strong`/`em` a mapped span already says (§5.6.7)."""
    for span in container.find_all("span"):
        if not {name.lower() for name in _raw_classes(span)} & set(SPAN_TO_STYLE):
            continue
        children = [child for child in span.children
                    if not (markdown.is_text(child) and not str(child).strip())]
        if len(children) == 1 and isinstance(children[0], Tag) \
                and children[0].name in REDUNDANT_WRAPPERS:
            children[0].unwrap()


def _prune_anchors(container: Tag, referenced: set[str]) -> set[str]:
    """Keeps the `a[name]` something points at; drops the rest and every `a.ix`.

    **No id pairing.** DITA needs one because 7,377 of its link targets are an
    element `id` with no `<a name>` beside it; here **0 of 5,548** referenced
    fragments resolve to an `id`, so pairing would insert markers nothing uses.
    """
    kept: set[str] = set()
    for anchor in container.find_all("a"):
        if anchor.get("href"):
            continue
        name = anchor.get("name")
        if "ix" in _classes(anchor):
            # A DocBook index marker: 3,347 defined, 0 referenced, and its `name`
            # is human-readable prose with spaces rather than an identifier.
            anchor.decompose()
            continue
        if not name:
            continue
        value = str(name)
        if value.lower() in referenced and value not in kept:
            kept.add(value)
        else:
            anchor.decompose()
    return kept


# -- the plan pass's readers ---------------------------------------------------


def _read_toc(listing: Tag) -> list[_Entry]:
    """A `div.toc` as a forest. `dl` of `dt` entries, each `dd` nesting the next.

    The corpus writes `dl`/`dt`/`dd` in every TOC measured; the `ul`/`li` flavour
    DocBook XSL can also emit does not appear, so it is not read for.
    """
    inner = listing.find("dl")
    return _entries(inner) if isinstance(inner, Tag) else []


def _entries(listing: Tag) -> list[_Entry]:
    out: list[_Entry] = []
    for child in listing.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "dt":
            anchor = child.find("a", href=True)
            label = _text(anchor if isinstance(anchor, Tag) else child)
            href = str(anchor["href"]).strip() if isinstance(anchor, Tag) else ""
            out.append(_Entry(label=label, href=href))
        elif child.name == "dd" and out:
            nested = child.find("dl")
            if isinstance(nested, Tag):
                out[-1].children.extend(_entries(nested))
    return out


def _read_menu(soup: Tag, base: PurePosixPath) -> list[tuple[str, PurePosixPath]]:
    """`p#mainhelp-navmenu` as (label, unit-relative target), in menu order."""
    menu = soup.find(id=MENU_ID)
    if not isinstance(menu, Tag):
        return []
    out: list[tuple[str, PurePosixPath]] = []
    for anchor in menu.find_all("a", href=True):
        target = _in_unit_target(base, links.classify(str(anchor["href"])))
        if target is not None:
            out.append((_text(anchor), target))
    return out


def _read_footer(soup: Tag, base: PurePosixPath) -> dict[str, PurePosixPath]:
    """`div#footer`'s `li` ids -> the page each one names."""
    footer = soup.find(id=FOOTER_ID)
    if not isinstance(footer, Tag):
        return {}
    out: dict[str, PurePosixPath] = {}
    for item in footer.find_all("li", id=True):
        anchor = item.find("a", href=True)
        if not isinstance(anchor, Tag):
            continue
        target = _in_unit_target(base, links.classify(str(anchor["href"])))
        if target is not None:
            out.setdefault(str(item["id"]).lower(), target)
    return out


def _guides(plan: _Plan) -> list[tuple[str, str, _Page | None]]:
    """Every guide directory as (name, menu label, book page), in menu order.

    The menu names 13 of the 24 and fixes their order and their short labels;
    the other 11 follow alphabetically under their own `<title>`. A page at the
    unit root that is not `index.html` -- `lvindex.html`, in every version --
    becomes a top-level node of its own, which is what the `""` guide is.
    """
    ordered: list[tuple[str, str, _Page | None]] = []
    seen: set[str] = set()
    for label, relative in plan.menu:
        book = plan.targets.get(str(relative).lower())
        guide = relative.parts[0] if len(relative.parts) > 1 else ""
        if guide in seen or (guide == "" and str(relative) == "index.html"):
            continue
        seen.add(guide)
        ordered.append((guide, label, book))

    remaining = sorted({page.guide for page in plan.pages} - seen)
    for guide in remaining:
        if guide == "":
            for page in sorted(plan.pages, key=lambda item: str(item.relative)):
                if page.guide == "" and str(page.relative) != "index.html":
                    ordered.append(("", page.title, page))
            continue
        book = plan.targets.get(f"{guide}/index.html")
        ordered.append((guide, book.title if book is not None else guide, book))
    return ordered


# -- small readers -------------------------------------------------------------


def _duplicate_roots(tree: Path, roots: list[Path]) -> list[Path]:
    """Top-level directories holding DocBook pages that no output root covers.

    All 42 in the corpus sit at depth 1 and duplicate a directory under `html/`,
    so one level is the whole search.
    """
    found: list[Path] = []
    try:
        children = sorted(child for child in tree.iterdir() if child.is_dir())
    except OSError:  # pragma: no cover - the tree was listed moments earlier
        return found
    for child in children:
        if any(child == root or root in child.parents for root in roots):
            continue
        try:
            pages = [item for item in sorted(child.iterdir())
                     if item.is_file() and item.suffix.lower() in _HTML_SUFFIXES]
        except OSError:  # pragma: no cover - unreadable directory
            continue
        if any(is_docbook_page(page) for page in pages[:5]):
            found.append(child)
    return found


def _foreign_reason(path: Path) -> str:
    """Why a non-DocBook page under the root was not converted."""
    try:
        with path.open("rb") as handle:
            head = handle.read(_HEAD_BYTES)
    except OSError:  # pragma: no cover - the file was listed moments earlier
        return "unreadable"
    for marker, _name in FOREIGN_MARKERS:
        if marker in head:
            return "foreign-generator"
    return "not-docbook"


def _in_unit_target(base: PurePosixPath, reference: links.Reference) -> PurePosixPath | None:
    """The unit-relative page a reference names, or None if it names something else."""
    if not reference.resolvable or not links.is_topic(reference.path):
        return None
    resolved = links.resolve(base, reference.path)
    return None if links.escapes(resolved) else resolved


def _in_navigation(node: Tag) -> bool:
    return any(parent.name == "div" and _classes(parent) & NAVIGATION_CLASSES
               for parent in node.parents)


def _document_title(soup: Tag) -> str:
    """`<title>`, which equals the titlepage heading on 1,094 of 1,178 pages."""
    title = soup.find("title")
    return _text(title) if isinstance(title, Tag) else ""


def _text(node: Tag) -> str:
    return " ".join(node.get_text(" ").split())


def _raw_classes(tag: Tag) -> list[str]:
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


def _classes(tag: Tag) -> set[str]:
    return {name.lower() for name in _raw_classes(tag)}


def _read(path: Path) -> str | None:
    """UTF-8, which 1,178 of 1,178 pages declare and are. Never raises."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:  # pragma: no cover - no corpus page reaches it
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    except OSError:
        return None


def _relative(tree: Path, path: Path) -> str:
    try:
        return path.relative_to(tree).as_posix()
    except ValueError:  # pragma: no cover - the driver walks from the tree
        return path.name


__all__ = [
    "ADMONITION_CLASSES",
    "CONTENT_ID",
    "DocBookEngine",
    "DocBookRenderer",
    "FOOTER_SUPPORT_IDS",
    "SPAN_TO_STYLE",
]
