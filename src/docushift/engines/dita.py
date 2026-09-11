"""The SDL DITA engine: 353 doc-sets, 67,406 topics, and one selector.

`architecture.md` §5.2, measured on 2026-09-08 and re-measured on 2026-09-11
against the `html-to-md` cache. The second-largest engine after Flare, and the
one whose source is *semantic*: DITA's `@class` survives into the HTML, so where
Flare needs heuristics this engine reads a vocabulary. What the corpus decided:

- **The unit of work is the doc-set**, a directory holding `GUID-*.html`. It sits
  at `html`, `doc/html`, `html_v3` or `en-US` depending on the product, and 23 of
  319 versions ship several. `engines/roots.py` already locates it.
- **Content is `<article>`** -- 3,742 of 3,742 sampled topics, and the only rule
  that spans the corpus's two skins. Chrome lives *inside* it and comes out after.
- **Titles come from the topic, structure from `suitehelp_topic_list.html`.** The
  two TOC files disagree on 4% of shared entries and the crawler is the stale one.
- **`DC.Relation` is not a parent pointer.** 42% of topics sit in a mutual pair
  and all 65 doc-sets tested contain a cycle; it is DITA's *related-links*
  relation. `test_dita.py` pins this, because it is the tempting wrong answer.
- **Output is flat and the slug collides.** 15 of 22 sampled doc-sets contain a
  title collision, so ties break by GUID with `-2`/`-3` and the hierarchy is
  carried by `toc.yml` rather than by directories.
- **The callout label is a `span` that must be deleted** -- the exact mirror of
  Flare, which recovers its label from an attribute the CSS draws (§5.1.8).

Four things this file does that §5.2's tables do not say, each measured on
2026-09-11 and recorded in `planning.md` beside the checklist:

1. **The class table is mostly redundant, and honouring it would be wrong.**
   SuiteHelp already emits the semantic tag: `topictitle1` is an `h1`,
   `sectiontitle` an `h2` (922) or `h3` (4), `codeph` a `<samp>`, `varname` a
   `<var>`, `userinput` a `<kbd>`, `codeblock` a `<pre>`, `stepexpand` an `<li>`.
   §5.2.5 maps `sectiontitle` to `###`; the tag says `##`, and forcing the class
   would demote every section heading and break the four that are `h3`. So the
   tag rules the level and `CLASS_TO_STYLE` below covers only the classes whose
   tag carries no meaning -- the `<span>`s and the `<div>`s.
2. **Half the anchors are not `<a name>`.** 8,056 id-bearing elements pair with
   an `<a name>` of the same value and **7,377 do not**, so pruning anchors by
   looking at `<a>` alone would drop half the link targets in the corpus.
3. **`menucascade` must not be bolded.** It holds at least one `uicontrol` child
   in 2,618 of 2,619 observed -- two on average -- and `uicontrol` is already
   bold, so bolding the wrapper too emits `** **File** > **Save** **`.
4. **There is no landing page to hoist.** `index.html` redirects to the
   `-homepage.html` -- which §5.2.7 makes metadata, not a topic -- and the TOC is
   a forest of 2 to 10 top-level nodes in 23 of 23 sampled doc-sets, never one.
   `unit.landing` therefore stays `None`, as it does for WebWorks (§5.3.5), and
   Phase 6 synthesizes the version root. That is the engine's normal shape and
   not an absence to report.

**Two reads per topic, and no held DOM.** The plan pass reads each file as text
and takes its identity, its title and its anchor set by regular expression; the
convert pass reads it again and parses it. A doc-set runs to 6,152 topics, and
both halves of the plan -- which slug a GUID gets, and which anchors anything
points at -- have to be settled before the first link is rewritten. Two cheap
reads is what buys that without holding 6,152 parse trees.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from bs4 import BeautifulSoup, Tag
from bs4.element import PreformattedString

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
from docushift.engines.detector import GUID_HTML_NAME
from docushift.models import SourceEngine
from docushift.transforms import callouts, links, markdown
from docushift.transforms import code as code_transform
from docushift.utils.slug import slugify

# The one selector (§5.2.4). Both skins wrap their content in it -- the Bootstrap
# `navbar-fixed-top` layout (89%) and the legacy `#leftbar` one (11%) -- and they
# share almost nothing else, so a per-skin selector list would be two rules where
# the corpus has one.
CONTENT_SELECTOR = "article"

# Chrome that lives *inside* `<article>`, which is why extraction does not end at
# the selector. `div.familylinks` is dropped whole rather than partly converted:
# it holds publisher-generated `ulchildlink`/`previouslink`/`nextlink` navigation
# that `toc.yml` reproduces correctly and Markdown must not duplicate.
CHROME_SELECTORS = ("div#copyright", "noscript", "div#thumbnailDialog", "div.familylinks")

# Structure, in preference order (§5.2.3). `suitehelp_topic_list.html` is present
# in 314 of 353 doc-sets and `toc_crawler.html` in 54; where both exist they
# disagree on 86 of 2,409 shared entries and the crawler is the stale one, so it
# is a fallback and never a supplement. Titles come from the topic either way.
TOC_SOURCES = ("suitehelp_topic_list.html", "toc_crawler.html")

# `GUID-<uuid>-homepage.html`: publication metadata, not a topic (§5.2.7).
HOMEPAGE_MARKER = "-homepage"

# The three divs its `<article>` holds, and nothing else. Present in all 314
# doc-sets that ship a homepage, and in 20 of 20 re-sampled on 2026-09-11.
HOMEPAGE_KEYS = ("publication-title", "release-version", "release-date")

# The admonition classes the corpus ships: note 1,674, tip 42, important 15,
# warning 13, remember 8, attention 8, caution 3, restriction 1. Unlike Flare's
# open `div.note<Kind>` convention (§5.1.7) this set is genuinely closed -- DITA's
# `@class` comes from the DTD, so an unlisted name is a different vocabulary and
# not a project stylesheet's invention. It is still checked against
# `transforms/callouts.py` rather than assumed, which is what keeps
# `ALERT_LABEL_UNMAPPED` reachable here.
CALLOUT_CLASSES = frozenset({
    "note", "tip", "important", "warning", "caution", "remember", "attention", "restriction",
})

# §5.2.5, minus everything SuiteHelp already says with a tag. What is left is the
# `<span>`s: 3,050 `uicontrol`, 350 `filepath`, 265 `wintitle`, 213 `parmname` in
# 853 sampled topics. `codeph`/`varname`/`userinput`/`term` are listed anyway --
# their tags (`samp`, `var`, `kbd`, `dfn`) render as code, *italic*, code and
# *italic*, and DITA means code, code, code and bold -- so for two of the four
# this table is the correction and for the other two it is the belt.
#
# `menucascade` is deliberately absent: see the module docstring.
CLASS_TO_STYLE = {
    "codeph": "code", "msgph": "code", "filepath": "code", "varname": "code",
    "parmname": "code", "cmdname": "code", "apiname": "code", "userinput": "code",
    "sysout": "code", "option": "code",
    "uicontrol": "strong", "wintitle": "strong", "term": "strong",
}

# `cellrowborder`, `tablenoborder`, `choicetableborder`, `tablecap` and
# `tablecaption` are border styling and are ignored -- which is the default path,
# so they are named here and nowhere else.

_HTML_SUFFIXES = (".htm", ".html")

# A `<meta name="DC.Identifier">` and friends, matched **case-insensitively**:
# SuiteHelp writes `DC.Type` and the file-named flavour writes `DC.type`, and a
# case-sensitive match silently drops 66 versions (§7.2).
_META = re.compile(
    r"""<meta\b[^>]*\bname\s*=\s*["']?(?P<name>dc\.[a-z]+)["']?[^>]*>""",
    re.IGNORECASE,
)
_CONTENT = re.compile(r"""\bcontent\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_TITLE_TAG = re.compile(r"<title\b[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# The plan pass's two readers. Restricted to the `<article>` slice so that the
# skin's own ids -- `search_form`, `toc_pane`, `crumb_home` -- cannot make a
# fragment resolve against chrome that conversion already removed.
_ARTICLE = re.compile(r"<article\b.*</article\s*>", re.IGNORECASE | re.DOTALL)
_ANCHOR_ATTR = re.compile(r"""\b(?:id|name)\s*=\s*"([^"]+)\"""")
_HREF_ATTR = re.compile(r"""<a\b[^>]*\bhref\s*=\s*"([^"]*)\"""", re.IGNORECASE)

# `GUID-…ADE1E_unique_1`: SDL republishing one topic at a second TOC position.
# The suffix lands on the identifier and on every id and `<a name>` inside the
# file, so it is stripped from both -- anchored at the end for the identifier,
# unanchored for a fragment, where `GUID-X_unique_1__STEP_9` carries it mid-string.
_UNIQUE_SUFFIX = re.compile(r"_unique_\d+$", re.IGNORECASE)
_UNIQUE_ANY = re.compile(r"_unique_\d+", re.IGNORECASE)

_SOUP = BeautifulSoup("", "html.parser")


# -- the renderer --------------------------------------------------------------


class DitaRenderer(markdown.Renderer):
    """SuiteHelp's vocabulary, over `transforms/markdown.py`'s walk."""

    def __init__(self, engine: "DitaEngine", context: ConversionContext, unit: Unit,
                 plan: "_Plan", topic: "_Topic"):
        self.engine = engine
        self.context = context
        self.unit = unit
        self.plan = plan
        self.topic = topic
        self.source = topic.source
        self.output = topic.output

    # -- blocks ---------------------------------------------------------------

    def block_override(self, tag: Tag) -> str | None:
        if tag.name in ("script", "style"):
            return ""
        if tag.name != "div":
            return None
        classes = _classes(tag)
        name = _callout_kind(tag, classes)
        if name:
            return self._callout(tag, name)
        if "figcap" in classes:
            # `fignone` needs no override -- a `div` is transparent and the `<img>`
            # inside it becomes a paragraph of its own. Only the caption does,
            # because GFM has no `<figcaption>` and italic is what AEM renders.
            caption = self.inline_children(tag).strip()
            return markdown.wrap(caption, "*") if caption else ""
        return None

    def _callout(self, tag: Tag, name: str) -> str:
        """One admonition, with its label span deleted (§5.2.5).

        **Every callout carries its own label span**, 1:1 in every kind measured:
        364 `span.notetitle` for 364 `div.note`, 9 `tiptitle` for 9 `tip`, and so
        on through `warning`, `important`, `attention` and `remember`. GFM renders
        the label itself, so leaving the span emits `> [!NOTE]` and then
        `**Note:** Note: …`. It is matched as `span.<kind>title` and never as
        `span[class$=title]`, which would also delete the 265 `wintitle` spans in
        the same sample -- those are content, and window names at that.
        """
        label = ""
        for span in tag.find_all("span", class_=f"{name}title"):
            label = " ".join(markdown.text_of(span).split()) or label
            span.decompose()

        kind = callouts.alert_for(name)
        if kind is None:
            self.engine.unmapped_alert(self.context, self.unit, name)
            kind = callouts.Alert.NOTE

        blocks = self.blocks(tag)
        # `remember`, `attention` and `restriction` have no GitHub alert of their
        # own and collapse onto NOTE and IMPORTANT. Their authored label is kept
        # as the first bolded run so the collapse loses the rendering, not the word.
        if label and str(kind).lower() != name:
            blocks = _prefixed(f"**{markdown.escape(label)}**", blocks)
        return callouts.render(kind, "\n\n".join(blocks))

    # -- inline ---------------------------------------------------------------

    def inline_override(self, tag: Tag) -> str | None:
        if tag.name == "a" and tag.get("name") and not tag.get("href"):
            # A referenced anchor: `_prune_anchors` already removed the rest, and
            # all 7,786 of them in the sample are empty, so nothing is lost with
            # the tag. Emitted as HTML because GFM has no anchor syntax.
            return f'<a id="{tag["name"]}"></a>'
        for name in _raw_classes(tag):
            style = CLASS_TO_STYLE.get(name)
            if style == "code":
                return code_transform.inline(markdown.text_of(tag))
            if style == "strong":
                return markdown.wrap(self.inline_children(tag), "**")
            if style == "em":  # pragma: no cover - no class maps here today
                return markdown.wrap(self.inline_children(tag), "*")
        return None

    # -- references (invariant 13) --------------------------------------------

    def link(self, tag: Tag) -> str | None:
        raw = str(tag.get("href") or "")
        reference = links.classify(raw)

        if reference.kind is links.ReferenceKind.FRAGMENT:
            anchor = self._fragment(self.topic, reference.fragment)
            return f"#{anchor}" if anchor else None
        if reference.kind in (links.ReferenceKind.ABSOLUTE, links.ReferenceKind.ROOTED):
            return raw.strip()
        if not reference.resolvable:
            return None

        guid = _guid_of(reference.path)
        if guid is None:
            if links.is_topic(reference.path):
                # `javadoc/index.html` and friends: 0.4% of hrefs, a cross-repo
                # link into the `-resources` tree that this run does not produce.
                # Reported and unlinked rather than handed to the copier, which
                # would resolve it and copy an HTML page into the Markdown output.
                self.engine.dangling_link(self.context, self.unit, self.source, reference.path)
                return None
            return self._asset(reference.raw)

        target = self.plan.targets.get(guid)
        if target is None:
            self.engine.dangling_link(self.context, self.unit, self.source, reference.path)
            return None
        anchor = self._fragment(target, reference.fragment)
        return links.emit(links.relative_to(self.output, target.output), anchor)

    def _fragment(self, target: "_Topic", fragment: str) -> str:
        """The bookmark to keep, or `""`. Three outcomes, all of them measured.

        **Most fragments are redundant** -- `GUID-X.html#GUID-X` names the target
        topic's own id and adds nothing: 12,153 of 16,604 in the 18,542-topic scan
        (73%). Of the 3,648 that name a real sub-anchor and can be checked, 793
        resolve against nothing (22%), and in a smaller doc-set-level sample
        **27 of 34 spell it `…__missing-elem-id--GUID-…`**: SDL's own marker for a
        cross-reference it could not resolve at publish time. Those are source
        defects, concentrated in a few doc-sets rather than spread evenly, so the
        link keeps its target file and loses only the bookmark.
        """
        if not fragment:
            return ""
        value = _UNIQUE_ANY.sub("", fragment)
        if value.lower() == target.guid:
            return ""
        if value in target.anchors:
            return value
        self.engine.dropped_fragment(self.context, self.unit, self.source, fragment)
        return ""

    def image(self, tag: Tag) -> str | None:
        """Content images keep their source filename (§5.2.6).

        The predecessor renames an image from its `alt` text and falls back to the
        GUID; 8,723 of 9,519 scanned `<img>` have no `alt` at all (92%), so the
        fallback fires almost always and the strategy is abandoned rather than
        inherited. `static/` icons are chrome and `engines/roots.SKIN_PREFIXES`
        already drops them before the existence test.
        """
        return self._asset(str(tag.get("src") or ""))

    def _asset(self, raw: str) -> str | None:
        """One non-topic reference, resolved and copied by the same call (§6.4)."""
        copier = self.context.assets
        if copier is None:  # pragma: no cover - the driver always sets one
            return None
        return copier.resolve(self.source, self.output, raw).url or None


def _prefixed(label: str, blocks: list[str]) -> list[str]:
    """A run-in label where the body is one paragraph, its own line where it is not."""
    if not blocks:
        return [label]
    if len(blocks) == 1 and _is_prose(blocks[0]):
        return [f"{label} {blocks[0]}"]
    return [label, *blocks]


def _is_prose(block: str) -> bool:
    return not block.startswith(("- ", "1. ", "|", "```", ">", "#", "<"))


def _guid_of(path: str) -> str | None:
    """The GUID a reference names, case-folded, or None if it names something else.

    **Matched on the GUID, not on the suffix.** Extensionless `GUID-2D166F0A-…`
    hrefs are 4 of 43,353 in the 18,542-topic scan and 17 of 2,663 in a
    small-doc-set re-sample -- somewhere between 0.01% and 0.6%, and clustered
    rather than spread. Rare either way, and a rewriter keyed on the suffix drops
    every one of them silently, which is the failure this avoids.
    """
    name = PurePosixPath(path).name
    stem = PurePosixPath(name).stem if links.is_topic(name) else name
    return stem.lower() if GUID_HTML_NAME.match(f"{stem.lower()}.html") else None


def _callout_kind(tag: Tag, classes: set[str]) -> str:
    """Which admonition a `<div>` is, or `""` where it is not one.

    **The class is `note tip`, not `tip`** -- DITA-OT writes the family and then
    the type, so `note` is present on every admonition in the corpus and picking
    the first match in any fixed order silently renders half the vocabulary as a
    plain NOTE. The type is identified by its own **label span**, which SDL emits
    1:1 with the kind in every kind measured (364 `notetitle` for 364 `note`,
    9 `tiptitle` for 9 `tip`, and so on), so the markup that has to be deleted is
    also the markup that says what to delete it as.

    That also lets a type outside the DTD's eight -- `fastpath`, say -- be seen
    rather than swallowed: it is reported and collapses onto NOTE with its label,
    which is what keeps `ALERT_LABEL_UNMAPPED` reachable in this engine.
    """
    if not classes & CALLOUT_CLASSES:
        return ""
    for candidate in sorted(classes):
        if tag.find("span", class_=f"{candidate}title") is not None:
            return candidate
    specific = sorted((classes & CALLOUT_CLASSES) - {"note"})
    return specific[0] if specific else "note"


def _raw_classes(tag: Tag) -> list[str]:
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


def _classes(tag: Tag) -> set[str]:
    return {name.lower() for name in _raw_classes(tag)}


# -- the plan ------------------------------------------------------------------


@dataclass
class _Topic:
    """One `GUID-*.html`, as the plan pass sees it. No DOM."""

    source: Path
    # The filename stem, case-folded. What every href in the doc-set names.
    stem: str
    # `DC.Identifier` with `_unique_N` removed, case-folded: the topic's *content*
    # identity, which a republished duplicate shares with its original.
    guid: str
    title: str
    # True where `DC.Identifier` -- **not** the filename -- carried `_unique_N`.
    # The distinction is the whole trap: `GUID-…ADE1E_unique_1` lives in
    # `GUID-…ADE1E1.html`, so the stem gains a bare digit and matches no
    # `_unique` pattern at all. Filtering on the stem puts both halves of a pair
    # in the originals map, where the second silently overwrites the first.
    republished: bool = False
    anchors: set[str] = field(default_factory=set)
    # Every `#fragment` this topic points at, case-folded and de-uniqued. Taken in
    # the same read as the anchors, because whether topic A emits an anchor
    # depends on whether topic Z references it and a third pass over the doc-set
    # buys nothing the first one could not have collected.
    fragments: set[str] = field(default_factory=set)
    # Where the Markdown goes, relative to the doc-set's subtree. Flat (§5.2.2).
    output: PurePosixPath = PurePosixPath()
    # True where this file is a republished copy of another topic in the doc-set.
    # It is never converted; its stem points at the original's output path.
    duplicate: bool = False


@dataclass
class _Plan:
    """What one doc-set will convert, settled before the first file is parsed."""

    # Converted, in slug order. Duplicates are not here.
    topics: list[_Topic] = field(default_factory=list)
    # Every stem in the doc-set, duplicates included -> the topic whose file is
    # written. What `link()` resolves against.
    targets: dict[str, _Topic] = field(default_factory=dict)
    # De-uniqued, case-folded fragment values anything in the doc-set points at.
    # An anchor not in here is not emitted: the surface is ~8.6 per topic and
    # 27,990 `GUID__…` values corpus-wide, against 2,192 that are ever referenced.
    referenced: set[str] = field(default_factory=set)
    nav: list["_Entry"] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class _Entry:
    """One `<li>` of a SuiteHelp TOC file."""

    label: str
    href: str = ""
    children: list["_Entry"] = field(default_factory=list)


def read_toc(path: Path) -> list[_Entry]:
    """A SuiteHelp TOC file as a forest. Never raises; a bad file reads as empty.

    Both TOC sources are the same shape -- nested `<ul><li id="toc-GUID-…"><a
    href="GUID-….html">Label</a>` -- so one reader covers the primary and the
    fallback. The `data-audience` attribute on every `<li>` reads `NONE` in 4,994
    of 4,994 sampled and is therefore not a filter.
    """
    text = _read(path)
    if text is None:
        return []
    soup = markdown.parse(text)
    body = soup.body or soup
    return [_entry(item) for item in _child_items(body)]


def _entry(item: Tag) -> _Entry:
    anchor = _own_anchor(item)
    # A node with no link of its own is a section, and its label is its own text.
    label = " ".join(anchor.get_text(" ").split()) if anchor is not None else _own_label(item)
    href = str(anchor["href"]).strip() if anchor is not None else ""
    children: list[_Entry] = []
    for nested in item.find_all(["ul", "ol"], recursive=False):
        children.extend(_entry(child) for child in _child_items(nested))
    return _Entry(label=label, href=href, children=children)


def _own_anchor(item: Tag) -> Tag | None:
    """The `<a href>` an `<li>` owns, never one belonging to a list nested in it.

    A plain recursive `find` would give a container node its first child's target,
    which reads as a working link and points a section at one of its own pages.
    """
    for child in item.children:
        if not isinstance(child, Tag) or child.name in ("ul", "ol"):
            continue
        if child.name == "a" and child.has_attr("href"):
            return child
        found = child.find("a", href=True)
        if found is not None:
            return found
    return None


def _own_label(item: Tag) -> str:
    """An `<li>`'s own text, with every nested list's text left out of it."""
    parts: list[str] = []
    for child in item.children:
        if isinstance(child, Tag):
            if child.name not in ("ul", "ol"):
                parts.append(child.get_text(" "))
        elif not isinstance(child, PreformattedString):
            parts.append(str(child))
    return " ".join(" ".join(parts).split())


def _child_items(node: Tag) -> list[Tag]:
    """The `<li>` children of the first list under `node`, at one level only."""
    if node.name in ("ul", "ol"):
        return [child for child in node.children if isinstance(child, Tag) and child.name == "li"]
    listing = node.find(["ul", "ol"])
    return _child_items(listing) if listing is not None else []


# -- the engine ----------------------------------------------------------------


@register
class DitaEngine(BaseEngine):
    """SDL (Trisoft) SuiteHelp."""

    engine = SourceEngine.DITA

    def __init__(self) -> None:
        self._alerts: set[str] = set()
        self._dropped = 0

    def units(self, context: ConversionContext) -> list[Path]:
        """The SuiteHelp doc-sets, and a report line for anything else (§5.2.1).

        The guard, not the deferral it started as. The corpus's 371 DITA versions
        are 316 SuiteHelp and ~55 **file-named** -- `administrator_roles.html` in
        a nested `topics/`, `article[role='article']`, lowercase `DC.*` -- and
        every product publishing the second flavour is on the §3.10 exclusion
        list, so it has no in-scope population at all. The branch can now only
        fire if a product is readmitted; without it a bare-`article` doc-set would
        run the SuiteHelp path and produce plausible-looking wrong output instead
        of a report line.
        """
        roots = super().units(context)
        kept = [root for root in roots if _is_suitehelp(root)]
        for root in roots:
            if root not in kept:
                context.record(
                    "DOCSET_SKIPPED", path=_relative(context.tree, root),
                    message="no GUID-*.html -- not SDL SuiteHelp, not converted",
                )
        if not kept:
            context.record(
                "DOCSET_SKIPPED",
                message="DITA tree with no GUID-*.html doc-set -- the file-named "
                        "flavour is out of scope and is never converted",
            )
        return kept

    # -- one doc-set -----------------------------------------------------------

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        unit = Unit(root=root, name=_relative(context.tree, root))
        plan = self._plan(context, unit, root)
        unit.metadata = plan.metadata

        documents: dict[str, Document] = {}
        for topic in plan.topics:
            document = self._convert(context, unit, plan, topic)
            if document is not None:
                documents[str(document.relative)] = document

        unit.documents = list(documents.values())
        unit.nav = self._navigation(context, unit, plan, documents)
        self._tail(context, unit, plan, documents)
        return unit

    # -- what to convert -------------------------------------------------------

    def _plan(self, context: ConversionContext, unit: Unit, root: Path) -> _Plan:
        """Reads every file as text, then settles identity, slugs and anchors.

        The doc-set is **flat** -- 297 of 353 have exactly one subdirectory and it
        is `static/` -- so this enumerates the root's own files and never
        descends. That is also why no API-reference predicate runs here: an API
        tree is a subdirectory, and a subdirectory is not a topic by construction.
        """
        plan = _Plan()
        found: list[_Topic] = []
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not GUID_HTML_NAME.match(name):
                if path.suffix.lower() in _HTML_SUFFIXES:
                    # `index.html`, the two TOC files: consumed or discarded, and
                    # counted either way (§5.2.7).
                    unit.skip("not-a-topic")
                continue
            text = _read(path)
            if text is None:
                unit.skip("unreadable")
                context.record("CONTENT_MISSING", path=f"{unit.name}/{path.name}".lstrip("/"),
                               message="could not be read")
                continue
            if HOMEPAGE_MARKER in name:
                unit.skip("publication-homepage")
                _read_metadata(text, plan.metadata)
                continue
            found.append(_profile(path, text))

        self._deduplicate(context, unit, found, plan)
        _assign_slugs(plan.topics)
        for topic in plan.topics:
            plan.targets[topic.stem] = topic

        plan.nav = self._toc(root)
        plan.referenced = _referenced(found)
        return plan

    def _deduplicate(self, context: ConversionContext, unit: Unit,
                     found: list[_Topic], plan: _Plan) -> None:
        """`_unique_N` topics are republished duplicates, not new topics (§5.2.2).

        402 of 18,542 scanned topics (2.2%) carry an identifier ending
        `_unique_N`, and in **402 of 402** the stripped identifier names another
        file in the same doc-set -- so the collapse never orphans anything. The
        pair is byte-identical but for the suffix on every id and `<a name>`:
        SDL publishing one topic at a second TOC position. Converting both yields
        near-duplicate Markdown and a spurious `-2` slug, so one file is written
        and both TOC positions point at it.

        The pairing is by identifier and never by filename, for the reason
        `_Topic.republished` records. A further 2 topics of the 18,542 have an
        identifier that is neither their stem nor a `_unique_N` of one; they pair
        with nothing and convert normally, which is what falling through does.
        """
        originals = {topic.guid: topic for topic in found if not topic.republished}
        duplicates: list[tuple[_Topic, _Topic]] = []
        for topic in found:
            original = originals.get(topic.guid)
            if original is not None and original is not topic:
                topic.duplicate = True
                duplicates.append((topic, original))
                continue
            plan.topics.append(topic)
        for topic, original in duplicates:
            plan.targets[topic.stem] = original
            # Counted as a skip and not as a finding: both TOC positions survive,
            # so nothing was dropped and a `NAV_NODE_DROPPED` row would be a
            # report of something that did not happen.
            unit.skip("republished-duplicate")

    def _toc(self, root: Path) -> list[_Entry]:
        for name in TOC_SOURCES:
            path = root / name
            if path.is_file():
                entries = read_toc(path)
                if entries:
                    return entries
        return []

    # -- one topic -------------------------------------------------------------

    def _convert(self, context: ConversionContext, unit: Unit, plan: _Plan,
                 topic: _Topic) -> Document | None:
        text = _read(topic.source)
        if text is None:  # pragma: no cover - read once already in the plan pass
            unit.skip("unreadable")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{topic.source.name}".lstrip("/"),
                           message="could not be read")
            return None

        soup = markdown.parse(text)
        container = soup.select_one(CONTENT_SELECTOR)
        if container is None:
            unit.skip("no-content-container")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{topic.source.name}".lstrip("/"),
                           message=f"no <{CONTENT_SELECTOR}>")
            return None

        _strip_chrome(container)
        emitted = _prune_anchors(container, plan.referenced)
        title = _title(container) or topic.title

        body = DitaRenderer(self, context, unit, plan, topic).render(container)
        if title and not body.lstrip().startswith("#"):
            # The `h1` is inside `<article>` in 853 of 853 sampled topics, so this
            # fires on none of them. It stands for the unsampled remainder: a page
            # with no heading is a page whose title exists only in `toc.yml`.
            body = f"# {markdown.escape(title)}\n\n{body}".rstrip("\n")

        return Document(source=topic.source, relative=topic.output, title=title,
                        body=body, anchors=emitted)

    # -- navigation ------------------------------------------------------------

    def _navigation(self, context: ConversionContext, unit: Unit, plan: _Plan,
                    documents: dict[str, Document]) -> list[NavNode]:
        """The TOC as nodes, plus the orphans. A forest, not a tree.

        23 of 23 sampled doc-sets have between 2 and 10 top-level entries, so
        there is no single root to hoist and `unit.landing` stays unset. Coverage
        is high but never complete -- mean 97% for the primary source, complete in
        2 of 314 and complete in 36 of 353 even taking both files -- so the
        remainder goes under an explicit "Unfiled" node and is counted. A 2-3%
        orphan rate is normal here and must not read as a failure; it must not be
        a silence either.
        """
        filed: set[str] = set()
        self._dropped = 0
        nodes = [
            node for node in (self._node(entry, plan, documents, filed) for entry in plan.nav)
            if node is not None
        ]

        orphans = [document for key, document in documents.items() if key not in filed]
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

    def _node(self, entry: _Entry, plan: _Plan, documents: dict[str, Document],
              filed: set[str]) -> NavNode | None:
        """One TOC entry, with its children. None when the node cannot be kept.

        A duplicate's entry resolves to the original's document, which is the
        whole point of §5.2.2's collapse: two positions, one file. Flare's
        same-page-child rule is deliberately *not* applied -- there the repetition
        is an accident of the TOC and here it is what the author published.
        """
        guid = _guid_of(entry.href) if entry.href else None
        target = plan.targets.get(guid) if guid else None
        document = documents.get(str(target.output)) if target is not None else None
        if document is not None:
            filed.add(str(document.relative))

        children = [
            child for child in (self._node(child, plan, documents, filed) for child in entry.children)
            if child is not None
        ]
        if document is None and not children:
            self._dropped += 1
            return None

        # The topic is authoritative for its own title (§5.2.2): `h1` equals
        # `DC.Title` in 3,675 of 3,675, while the two TOC files disagree with each
        # other on 4% of shared entries. The TOC label is kept as the *nav* label,
        # which is the distinction `Document` carries two strings for.
        label = entry.label or (document.title if document is not None else "")
        return NavNode(label=label,
                       document=document.relative if document is not None else None,
                       children=children)

    def _tail(self, context: ConversionContext, unit: Unit, plan: _Plan,
              documents: dict[str, Document]) -> None:
        """Which converted topic is support and which is legal, from the TOC.

        The same predicates Flare uses, and from the TOC for the same reason: the
        heading is `TIBCO Documentation and Support Services` in most doc-sets and
        the filename is a GUID, so there is nothing in the path to match on.
        """
        for attribute, matches, label in (
            ("support", is_support_label, "support"),
            ("legal", is_legal_label, "legal"),
        ):
            found = None
            for entry in _walk_entries(plan.nav):
                if not entry.href or not matches(entry.label):
                    continue
                guid = _guid_of(entry.href)
                target = plan.targets.get(guid) if guid else None
                found = documents.get(str(target.output)) if target is not None else None
                if found is not None:
                    break
            if found is None:
                context.record("TAIL_PAGE_MISSING", path=unit.name,
                               message=f"no {label} page in the TOC")
                continue
            setattr(unit, attribute, found.relative)

    # -- findings the renderer raises -----------------------------------------

    def unmapped_alert(self, context: ConversionContext, unit: Unit, label: str) -> None:
        """One row per distinct label, not per occurrence."""
        if label in self._alerts:
            return
        self._alerts.add(label)
        context.record("ALERT_LABEL_UNMAPPED", path=unit.name,
                       message=f"{label!r} is outside the alert vocabulary; rendered as NOTE")

    def dangling_link(self, context: ConversionContext, unit: Unit, source: Path, raw: str) -> None:
        """A cross-reference to a topic this run did not produce.

        Rare here and that is the point: 17,043 of 17,046 GUID links resolve on
        disk (0.02% broken), against Flare's 22% dangling alias links. A count
        that climbs means the run skipped something, not that the source is bad.
        """
        context.record("TOPIC_LINK_DANGLING", path=unit.name, count=1,
                       message=f"{source.name} -> {raw}")

    def dropped_fragment(self, context: ConversionContext, unit: Unit,
                         source: Path, fragment: str) -> None:
        """A bookmark naming no anchor in its target. The file link survives."""
        context.record("TOPIC_LINK_DANGLING", path=unit.name, count=1,
                       message=f"{source.name} -> #{fragment} (anchor absent; link kept, bookmark dropped)")


# -- DOM passes ----------------------------------------------------------------


def _strip_chrome(container: Tag) -> None:
    """§5.2.4's four selectors, then scripts and comments."""
    for selector in CHROME_SELECTORS:
        for element in container.select(selector):
            element.decompose()
    for element in container.find_all(["script", "style"]):
        element.decompose()
    for element in list(container.descendants):
        if isinstance(element, PreformattedString):
            element.extract()


def _prune_anchors(container: Tag, referenced: set[str]) -> set[str]:
    """Keeps the anchors something points at and drops the rest. Returns the kept.

    **The id half is not optional.** 8,056 id-bearing elements in the sample pair
    with an `<a name>` of the same value and **7,377 do not**, so an
    implementation that only looks at `<a>` keeps under half the link targets and
    turns the other half into dropped bookmarks. Where the pair is missing, a
    marker is inserted so that the renderer has one thing to emit rather than two.
    """
    kept: set[str] = set()
    for anchor in container.find_all("a"):
        name = anchor.get("name")
        if not name or anchor.get("href"):
            continue
        if str(name).lower() in referenced and str(name) not in kept:
            kept.add(str(name))
        else:
            anchor.decompose()
    for element in list(container.find_all(id=True)):
        value = str(element["id"])
        if value.lower() in referenced and value not in kept:
            kept.add(value)
            marker = _SOUP.new_tag("a")
            marker["name"] = value
            element.insert(0, marker)
    return kept


# -- the plan pass's readers ---------------------------------------------------


def _profile(path: Path, text: str) -> _Topic:
    """One topic's identity, title and anchor set, by regular expression.

    The title is `DC.Title` and then `<title>`, both of which the head carries as
    plain text. It is the *slug's* source and not the page's: `h1` equals
    `DC.Title` in 18,351 of 18,542 scanned topics (99.0%) and `<title>` equals
    `h1` in 3,675 of 3,675, so the two agree in all but a handful -- and the slug
    has to
    exist before any DOM does, because a cross-reference cannot be rewritten
    against a filename that has not been chosen yet.
    """
    meta = _meta(text)
    article = _article(text)
    stem = path.stem.lower()
    identifier = meta.get("dc.identifier") or path.stem
    title = meta.get("dc.title") or _tag_title(text)
    return _Topic(
        source=path,
        stem=stem,
        guid=_UNIQUE_SUFFIX.sub("", identifier).lower(),
        title=title,
        republished=bool(_UNIQUE_SUFFIX.search(identifier)),
        anchors=_anchor_values(article),
        fragments=_fragment_values(article),
    )


def _meta(text: str) -> dict[str, str]:
    """Every `DC.*` meta, keyed lowercase. Case-insensitive by §7.2's rule."""
    found: dict[str, str] = {}
    for match in _META.finditer(text):
        content = _CONTENT.search(match.group(0))
        if content:
            found.setdefault(match.group("name").lower(), (content.group(1) or content.group(2) or "").strip())
    return found


def _tag_title(text: str) -> str:
    match = _TITLE_TAG.search(text)
    return " ".join(markdown.parse(match.group(1)).get_text(" ").split()) if match else ""


def _article(text: str) -> str:
    match = _ARTICLE.search(text)
    return match.group(0) if match else ""


def _anchor_values(article: str) -> set[str]:
    return {value for value in _ANCHOR_ATTR.findall(article) if value}


def _fragment_values(article: str) -> set[str]:
    """The bookmarks this topic points at, case-folded and de-uniqued.

    De-uniqued on the way in for the same reason `_fragment` de-uniques on the way
    out: a link to a republished duplicate carries `_unique_1` in its bookmark and
    the file that gets written is the original, whose anchors do not.
    """
    values: set[str] = set()
    for href in _HREF_ATTR.findall(article):
        _, separator, fragment = href.strip().partition("#")
        if separator and fragment:
            values.add(_UNIQUE_ANY.sub("", fragment).lower())
    return values


def _referenced(found: list[_Topic]) -> set[str]:
    """Every anchor anything in the doc-set points at. Case-folded.

    A topic's own id is what 73% of fragments name, and it is never emitted as an
    anchor -- the file itself is the target. Removed here so that `_prune_anchors`
    does not keep one useless anchor at the top of nearly every page.
    """
    values: set[str] = set()
    for topic in found:
        values |= topic.fragments
    return values - {topic.guid for topic in found} - {topic.stem for topic in found}


def _assign_slugs(topics: list[_Topic]) -> None:
    """Title slugs, flat, with a deterministic tie-break (§5.2.2).

    **A title-derived filename is not unique by construction.** The survey found
    a collision in 44% of 140 doc-sets; two re-samples bracket that at 6 of 30 and
    15 of 22, so the rate is a property of the doc-set and not of the corpus, and
    every doc-set has to be treated as colliding. Ties break by GUID rather than
    by iteration order, so that re-running the
    conversion -- or running it on another machine, where `pathlib` sorts case
    differently -- produces the same filenames.
    """
    grouped: dict[str, list[_Topic]] = {}
    for topic in topics:
        grouped.setdefault(slugify(topic.title) or topic.stem, []).append(topic)
    for slug, group in grouped.items():
        for index, topic in enumerate(sorted(group, key=lambda item: item.guid), start=1):
            topic.output = PurePosixPath(f"{slug}.md" if index == 1 else f"{slug}-{index}.md")
    topics.sort(key=lambda item: str(item.output))


def _read_metadata(text: str, into: dict[str, str]) -> None:
    """`publication-title`, `release-version`, `release-date` from a homepage.

    All three are present in 314 of 314 doc-sets that ship one, and in 20 of 20
    re-sampled. They no longer feed `metadata.yml` -- AEM specified that file as
    `csg-*` keys only -- so they become a **cross-check** against the catalog's
    `display_name` and `release_date` in Phase 6, where a disagreement is a
    `METADATA_MISMATCH` report line rather than a failure. 5 doc-sets ship more
    than one homepage and 39 ship none; the first read wins and an absent one
    leaves the dict empty, which invariant 11 makes a blank rather than a zero.
    """
    soup = markdown.parse(text)
    container = soup.select_one(CONTENT_SELECTOR) or soup
    for key in HOMEPAGE_KEYS:
        element = container.find(class_=key)
        value = " ".join(element.get_text(" ").split()) if element is not None else ""
        if value:
            into.setdefault(key, value)


# -- small readers -------------------------------------------------------------


def _is_suitehelp(directory: Path) -> bool:
    try:
        return any(GUID_HTML_NAME.match(child.name.lower())
                   for child in directory.iterdir() if child.is_file())
    except OSError:  # pragma: no cover - the root was listed moments earlier
        return False


def _read(path: Path) -> str | None:
    """UTF-8, which 3,742 of 3,742 sampled topics are. Never raises."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:  # pragma: no cover - no corpus doc-set reaches it
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    except OSError:
        return None


def _title(container: Tag) -> str:
    """The `h1`, which is inside `<article>` in 853 of 853 sampled topics."""
    heading = container.find("h1")
    return " ".join(heading.get_text(" ").split()) if heading is not None else ""


def _walk_entries(entries: list[_Entry]):
    for entry in entries:
        yield entry
        yield from _walk_entries(entry.children)


def _relative(tree: Path, path: Path) -> str:
    try:
        return path.relative_to(tree).as_posix()
    except ValueError:  # pragma: no cover - the driver walks from the tree
        return path.name


__all__ = [
    "CALLOUT_CLASSES",
    "CLASS_TO_STYLE",
    "CONTENT_SELECTOR",
    "DitaEngine",
    "DitaRenderer",
    "read_toc",
]
