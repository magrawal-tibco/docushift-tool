"""The MadCap Flare engine: 676 output roots, 422,267 topics, and one selector.

`architecture.md` §5.1, measured on 2026-09-08 against the `html-to-md` cache. The
largest engine in the corpus by six times, and the first real consumer of Phase
5a's contract. What the corpus decided, and what each decision costs to get wrong:

- **The unit of work is the output root**, located by `Data/HelpSystem.xml`. 51 of
  595 versions ship several and 153 nest inside another; the innermost owns a file.
- **Output mirrors the source tree**, so a cross-reference is a `.htm` -> `.md`
  suffix substitution. Stems collide 6.0% within one root, so a flat layout is not
  an option and a title slug is not either (2.6%).
- **The TOC is JavaScript** (`flare_toc.py`), declared by `Toc=`, and 85.9%
  complete. The remainder are orphans, filed under an explicit "Unfiled" node and
  counted -- 14% is normal here and silently dropping 59,000 topics would not be.
- **Content is `div[role='main']#mc-main-content`, and there is no fallback
  chain.** It matches 4,656 of 4,660 MadCap topics; the predecessor's three extra
  selectors convert *non-Flare* files instead of reporting them, which is how a
  Javadoc page reaches the Markdown output.
- **The chrome that matters is inside the container**, and `#feedback-survey`
  alone is 47.7% of every raw `href` in the corpus. It goes first, before any link
  is looked at.
- **Flare's semantics live in `data-mc-autonum`**, an attribute the skin's CSS
  renders. The engine recovers the label and re-emits it; DITA is the mirror image
  (§5.2.5), where the same label is a `span` that must be deleted.

The ordering of the DOM passes is inherited from the predecessor's
`scripts/lib/preprocessor.py` (§5.1.10), which is its main pipeline and has run at
scale: strip chrome, then fake lists, then list continuations, then colspan
splits. Its `fake_list_tables()`, `split_colspan_tables()` and `SPAN_TO_TAG`
vocabulary are taken; its `Home.htm` skip, its missing `div.topic-frame`, its
selector fallback chain and its hand-maintained `skip_path_segments` are not.

**One honest limit.** A cross-reference is checked against the set of topics this
run *planned* to convert, which is settled before the first file is parsed. A
topic that then fails the container check leaves a link pointing at a page that
was never written. That is 3 files in the sampled corpus, and the alternative --
holding 8,485 parsed DOMs to defer every link decision -- costs more than it buys.
`validate` (Phase 7) re-resolves the emitted links and would name the residue.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from bs4 import BeautifulSoup, Tag
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
from docushift.engines.flare_toc import Manifest, Toc, TocNode, read_manifest, read_toc, tree_files
from docushift.engines.roots import find_output_roots
from docushift.models import SourceEngine
from docushift.transforms import callouts, links, markdown
from docushift.transforms import code as code_transform

# The one selector (§5.1.6). Not a list, and deliberately.
CONTENT_SELECTOR = "div[role='main']#mc-main-content"

# Removed in this order. `#feedback-survey` is first because it is 95% of topics
# and 47.7% of every raw href, so every link statistic taken before it is wrong by
# half; `div.topic-frame` is unwrapped rather than removed, because it wraps the
# real content in 88% of topics -- the omission from the predecessor's list.
CHROME_SELECTORS = (
    "div#feedback-survey",
    "div.MCBreadcrumbsBox_0",
    "div.MCMiniTocBox_0",
    "div.topicToolbarProxy",
    "p.MCWebHelpFramesetLink",
    "div.breadcrumbs",
    "div.toolbar",
    "div#prdnm",
    "p.Copyright",
    "a.codeSnippetCopyButton",
    "div.codeSnippetCaption",
    "a.MCHelpControl-Related",
    "noscript",
)

# Generated hero furniture on the landing page (§5.1.5). The banner itself is
# *not* here: it holds the `h1` and the product description, which is the content
# 91.9% of landing pages have.
LANDING_CHROME = ("div#release-info", "div.download-button", "div#redirect", "select")

# Top-level directories holding no convertible topic (§5.1.9). `_templates/` is
# **not** among them -- the landing page and 1,737 TOC-referenced paths live there.
GENERATED_DIRECTORIES = frozenset({"skins", "resources", "_globalpages", "microcontent", "data"})

# The corpus's only localized subtree: 8,004 files, no `zh`/`de`/`fr`/`es` anywhere.
LOCALIZED_DIRECTORIES = frozenset({"ja"})

TEMPLATES_DIRECTORY = "_templates"

# The predecessor's `skip_filenames`, minus `Home.htm` -- which is the `DefaultUrl`
# landing page in 644 of 676 roots, and skipping it is why its output has none.
STUB_FILENAMES = frozenset({"default.htm", "default_csh.htm", "index.htm", "index.html",
                            "index_csh.htm", "default.js"})

# `div.note*` and friends (§5.1.7). Note 1,574, Warning 30, Tip 28, Important 21.
#
# **Detection is deliberately wider than the mapping.** Flare's authoring
# convention is `div.note<Kind>`, where the kind is whatever the project's
# stylesheet defines, so the set of class names is open even though the corpus's
# own is closed -- a scan of 2,174 sampled topics finds exactly six (`note`,
# `noteNote`, `noteImportant`, `noteCaution`, `noteTip`, `noteWarning`) and the
# vocabulary maps all six. Matching only those would mean a `div.noteBestPractice`
# in the unsampled remainder rendering as unmarked prose with its admonition lost
# and nothing said; matching the prefix makes it a NOTE with a reported label.
CALLOUT_PREFIX = "note"
CALLOUT_CLASSES = frozenset({"warning", "caution", "tip", "important"})

# The predecessor's map, which matches the vocabulary this survey observed.
SPAN_TO_TAG = {
    "uicontrol": "strong", "wintitle": "strong", "option": "strong",
    "filepath": "code", "codeph": "code", "userinput": "code",
    "varname": "em", "parmname": "em", "term": "em",
}

_HTML_SUFFIXES = (".htm", ".html")
# `{b}`, `{/b}`, `{n+}`: Flare's autonumber format tokens. The counter cannot be
# evaluated without the whole numbering context, so the label keeps its words and
# loses its format codes rather than emitting a literal `{n+}` into the prose.
_AUTONUM_TOKEN = re.compile(r"\{[^}]*\}")
_AUTONUM_COUNTER = re.compile(r"\{[^}]*n[^}]*\}", re.IGNORECASE)
_ORDERED_CLASS = ("_number", "_step", "_procedure", "_numbered")
_FAKE_LIST_CLASS = "autonumber_p_"
# A colspan section header longer than this keeps its markup as a paragraph; a
# short one is an identifier and becomes a bold label. The predecessor's number.
_SHORT_HEADING = 60
# `architecture.md` §5.1.5's hero-only tier: 55 of 676 roots, which get a stub.
_LANDING_MINIMUM = 100

_SOUP = BeautifulSoup("", "html.parser")


def autonum_label(tag: Tag) -> str:
    """The prose inside a `data-mc-autonum`, with its format codes removed.

    The attribute holds markup in a minority of topics -- 5 of 2,174 sampled carry
    a `<b><span class="mcFormatSize">Note: </span></b>` where the others carry
    `Note:` -- so the tags come off before the format codes do. Left in, the label
    is re-emitted into the prose as literal HTML inside a `**bold**` run.
    """
    raw = str(tag.get("data-mc-autonum") or "")
    if "<" in raw:
        raw = markdown.parse(raw).get_text(" ")
    return " ".join(_AUTONUM_TOKEN.sub(" ", raw).split())


# -- the renderer --------------------------------------------------------------


class FlareRenderer(markdown.Renderer):
    """MadCap's vocabulary, over `transforms/markdown.py`'s walk."""

    def __init__(self, engine: "FlareEngine", context: ConversionContext, unit: Unit,
                 source: Path, output: PurePosixPath, topics: set[str], landing: bool = False):
        self.engine = engine
        self.context = context
        self.unit = unit
        self.source = source
        self.output = output
        # Case-folded root-relative paths of every topic this run will write. A
        # cross-reference to anything else is a dangling link, not a `.md` path.
        self.topics = topics
        self.landing = landing
        self.base = PurePosixPath(source.parent.relative_to(self.unit.root).as_posix())

    # -- blocks ---------------------------------------------------------------

    def block_override(self, tag: Tag) -> str | None:
        if tag.name in ("script", "style"):
            return ""
        classes = _classes(tag)
        kind = self._callout(tag, classes)
        if kind is not None:
            return callouts.render(kind, "\n\n".join(self.blocks(tag)))
        if self.landing and "mcdropdown" in classes:
            return self._dropdown(tag)
        label = autonum_label(tag)
        if label:
            return self._labelled(tag, label)
        return None

    def _callout(self, tag: Tag, classes: set[str]) -> callouts.Alert | None:
        """Which alert this `div` is, or None if it is not one.

        `data-mc-autonum` wins over the class name, because the class is ambiguous
        -- `div.note` carrying an autonum of `Warning:` is a warning.
        """
        if tag.name != "div":
            return None
        matched = sorted(
            name for name in classes
            if name in CALLOUT_CLASSES or name.startswith(CALLOUT_PREFIX)
        )
        if not matched:
            return None
        label = autonum_label(tag)
        kind = callouts.alert_for(label) if label else None
        if kind is None:
            for name in matched:
                kind = callouts.alert_for(_callout_kind(name))
                if kind is not None:
                    break
        if kind is None:
            self.engine.unmapped_alert(self.context, self.unit, label or matched[0])
            kind = callouts.Alert.NOTE
        return kind

    def _labelled(self, tag: Tag, label: str) -> str:
        """Re-emits a `data-mc-autonum` label the skin's CSS would have drawn.

        A run-in where the labelled element is one paragraph of prose (`Before you
        begin`, `Result`), a bold line of its own where it introduces a structure
        (`Procedure` over a list of steps). Not a heading either way: the label
        sits under the topic's `h1` and would compete with the topic's own
        sections in the page outline.
        """
        blocks = self._block(tag)
        if not blocks:
            return f"**{label}**"
        if len(blocks) == 1 and _is_prose(blocks[0]):
            return f"**{label}** {blocks[0]}"
        return "\n\n".join([f"**{label}**", *blocks])

    def _dropdown(self, tag: Tag) -> str:
        """One `MCDropDown` as an `##` section (§5.1.5, landing pages only).

        457 of the 459 files in the corpus that use the construct are this page,
        where the dropdowns carry the whole structure. In a content topic the
        generic unwrap path handles it -- there is exactly one such topic.
        """
        head = tag.find(class_="MCDropDownHead")
        body = tag.find(class_="MCDropDownBody")
        label = " ".join(head.get_text(" ").split()) if isinstance(head, Tag) else ""
        blocks = self.blocks(body) if isinstance(body, Tag) else []
        if not label:
            return "\n\n".join(blocks)
        return "\n\n".join([f"## {markdown.escape(label)}", *blocks])

    # -- inline ---------------------------------------------------------------

    def inline_override(self, tag: Tag) -> str | None:
        """The `SPAN_TO_TAG` vocabulary, plus the two spans that are not mappings."""
        if tag.name == "code" and "CodeItalic" in _raw_classes(tag):
            # A MadCap italic placeholder inside code. Left as `<code>` it emits a
            # second backtick run against its neighbour and both stop being code.
            return markdown.wrap(self.inline_children(tag), "*")
        if tag.name != "span":
            return None
        classes = _classes(tag)
        if "menucascade" in classes:
            return markdown.wrap(" ".join(tag.get_text(" ").split()), "**")
        if "autonumber" in classes:
            # The label the skin draws from `data-mc-autonum`, already in the DOM.
            # Recovered from the attribute by `_labelled`, so leaving it here emits
            # it twice.
            return ""
        for name in _raw_classes(tag):
            mapped = SPAN_TO_TAG.get(name)
            if mapped == "strong":
                return markdown.wrap(self.inline_children(tag), "**")
            if mapped == "em":
                return markdown.wrap(self.inline_children(tag), "*")
            if mapped == "code":
                return code_transform.inline(markdown.text_of(tag))
        return None

    # -- references (invariant 13) --------------------------------------------

    def link(self, tag: Tag) -> str | None:
        raw = str(tag.get("href") or "")
        reference = links.classify(raw)
        if reference.kind is links.ReferenceKind.FRAGMENT:
            return f"#{reference.fragment}" if reference.fragment else None
        if reference.kind in (links.ReferenceKind.ABSOLUTE, links.ReferenceKind.ROOTED):
            # `javascript:void(0)` is a skin button, not a link. It is 47.7% of the
            # corpus's raw hrefs and nearly all of it is inside `#feedback-survey`,
            # which is already gone by the time anything gets here.
            return None if raw.strip().lower().startswith("javascript:") else raw.strip()
        if not reference.resolvable:
            return None
        if not links.is_topic(reference.path):
            return self._asset(reference.raw)

        resolved = links.resolve(self.base, reference.path)
        if links.escapes(resolved) or str(resolved).lower() not in self.topics:
            self.engine.dangling_link(self.context, self.unit, self.source, reference.path)
            return None
        target = links.to_markdown(resolved)
        return links.emit(links.relative_to(self.output, target), reference.fragment)

    def image(self, tag: Tag) -> str | None:
        return self._asset(str(tag.get("src") or ""))

    def _asset(self, raw: str) -> str | None:
        """One non-topic reference, resolved and copied by the same call (§6.4)."""
        copier = self.context.assets
        if copier is None:  # pragma: no cover - the driver always sets one
            return None
        return copier.resolve(self.source, self.output, raw).url or None


def _callout_kind(name: str) -> str:
    """`noteWarning` -> `warning`, `note` -> `note`. The class minus its prefix."""
    if name.startswith(CALLOUT_PREFIX) and len(name) > len(CALLOUT_PREFIX):
        return name[len(CALLOUT_PREFIX):]
    return name


def _is_prose(block: str) -> bool:
    return not block.startswith(("- ", "1. ", "|", "```", ">", "#", "<"))


def _raw_classes(tag: Tag) -> list[str]:
    value = tag.get("class") or []
    return value if isinstance(value, list) else str(value).split()


def _classes(tag: Tag) -> set[str]:
    return {name.lower() for name in _raw_classes(tag)}


# -- the engine ----------------------------------------------------------------


@dataclass
class _Plan:
    """What one root will convert, settled before the first file is parsed."""

    manifest: Manifest
    tocs: list[Toc] = field(default_factory=list)
    # Root-relative source paths, sorted. The landing page is not among them.
    topics: list[str] = field(default_factory=list)
    landing: str = ""
    # `topics` plus `landing`, case-folded: what a cross-reference may point at.
    planned: set[str] = field(default_factory=set)


@register
class FlareEngine(BaseEngine):
    """MadCap Flare WebHelp2."""

    engine = SourceEngine.FLARE

    def __init__(self) -> None:
        # Per-version state. The driver builds one engine per version, so the
        # alert vocabulary is deduplicated across a version's output roots --
        # which is the scope the finding is reported at.
        self._alerts: set[str] = set()
        self._dropped = 0

    def units(self, context: ConversionContext) -> list[Path]:
        roots = super().units(context)
        if not roots:
            # The 5 partial outputs: MadCap topics, no runtime manifest, so no TOC,
            # no CSH and no reliable root boundary. Reported for triage (§5.1.1).
            context.record(
                "OUTPUT_ROOT_MISSING",
                message="Flare tree with no Data/HelpSystem.xml -- partial output, not converted",
            )
        return roots

    # -- one output root -------------------------------------------------------

    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        unit = Unit(root=root, name=_relative(context.tree, root))
        plan = self._plan(context, unit, root)

        documents: dict[str, Document] = {}
        for relative in plan.topics:
            document = self._convert(context, unit, root, relative, plan.planned)
            if document is not None:
                documents[relative.lower()] = document

        if plan.landing:
            landing = self._convert(context, unit, root, plan.landing, plan.planned, landing=True)
            if landing is not None:
                documents[plan.landing.lower()] = landing
                unit.landing = landing.relative

        unit.documents = list(documents.values())
        unit.nav = self._navigation(context, unit, plan, documents)
        self._tail(context, unit, plan, documents)
        return unit

    # -- what to convert -------------------------------------------------------

    def _plan(self, context: ConversionContext, unit: Unit, root: Path) -> _Plan:
        """Reads the manifest and the TOCs, then decides the file set.

        Both halves have to happen before any topic is parsed: `_templates/` is
        converted only where the TOC references it, and a cross-reference can only
        be rewritten against a set that is already known.
        """
        manifest = read_manifest(root) or Manifest()
        tocs = self._tocs(context, unit, root, manifest)
        referenced = {
            node.entry.path.lower()
            for toc in tocs for node in toc.walk() if node.entry.path
        }

        landing = manifest.default_url
        if landing and not (root / Path(*PurePosixPath(landing).parts)).is_file():
            landing = ""

        topics = self._topics(context, unit, root, referenced, landing)
        planned = {name.lower() for name in topics}
        if landing:
            planned.add(landing.lower())
        return _Plan(manifest=manifest, tocs=tocs, landing=landing, topics=topics, planned=planned)

    def _tocs(self, context: ConversionContext, unit: Unit, root: Path,
              manifest: Manifest) -> list[Toc]:
        """The declared tree first, then the others as sibling top-level nodes.

        Three corpus roots ship two trees and `Toc=` names one of them; in
        `bctcm/6.2.0` the declared tree covers 53 of 106 topics, so reading it
        alone loses half the navigation and globbing alphabetically picks the wrong
        file in all three.
        """
        files = tree_files(root)
        declared = root / Path(*PurePosixPath(manifest.toc).parts) if manifest.toc else None
        ordered = [path for path in files if declared is not None and path == declared]
        ordered += [path for path in files if path not in ordered]
        if declared is not None and not ordered:
            ordered = [declared]

        tocs: list[Toc] = []
        for path in ordered:
            toc = read_toc(path)
            if toc.unmatched:
                context.record("NAV_NODE_DROPPED", path=unit.name, count=toc.unmatched,
                               message=f"{toc.unmatched} TOC id(s) with no payload entry in {path.name}")
            if toc.ragged:
                context.record("NAV_NODE_DROPPED", path=unit.name, count=toc.ragged,
                               message=f"{toc.ragged} ragged i/t/b array(s) in {path.name}")
            tocs.append(toc)
        return tocs

    def _topics(self, context: ConversionContext, unit: Unit, root: Path,
                referenced: set[str], landing: str) -> list[str]:
        """Every HTML file under `root` that is a topic, root-relative and sorted.

        Everything rejected is counted rather than passed over in silence -- the
        skip tallies are 2,339 generated pages, 1,295 runtime stubs, 8,078 API
        files and the 8,004-file `ja` tree, and each of those numbers is a claim
        the report has to be able to make.
        """
        nested = [
            other for other in (context.output_roots or find_output_roots(context.tree, self.engine))
            if other != root and root in other.parents
        ]
        found: list[str] = []
        for path in _walk_files(root):
            if path.suffix.lower() not in _HTML_SUFFIXES:
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if str(relative).lower() == landing.lower():
                # Converted, by the landing-page path rather than this one. Not a
                # skip, and counting it as one would put a converted page in the
                # column that says nothing was written.
                continue
            reason = self._rejection(path, relative, nested, context.api_roots, referenced)
            if reason:
                unit.skip(reason)
                continue
            found.append(str(relative))
        if unit.skipped.get("localized-subtree"):
            context.record("LOCALIZED_TREE_SKIPPED", path=unit.name,
                           count=unit.skipped["localized-subtree"],
                           message=f"{unit.skipped['localized-subtree']} file(s) in a localized subtree")
        return sorted(found)

    def _rejection(self, path: Path, relative: PurePosixPath, nested: list[Path],
                   api_roots: list[Path], referenced: set[str]) -> str:
        """Why this HTML file is not a topic, or `""` if it is one."""
        first = relative.parts[0].lower() if len(relative.parts) > 1 else ""
        if first in LOCALIZED_DIRECTORIES:
            return "localized-subtree"
        if first in GENERATED_DIRECTORIES:
            return "generated-directory"
        if path.name.lower() in STUB_FILENAMES:
            return "runtime-stub"
        if any(root in path.parents for root in nested):
            return "nested-output-root"
        if self.skips_api_references and is_api_reference(path, api_roots):
            return "api-reference"
        key = str(relative).lower()
        if first == TEMPLATES_DIRECTORY and key not in referenced:
            return "unreferenced-template"
        return ""

    # -- one topic -------------------------------------------------------------

    def _convert(self, context: ConversionContext, unit: Unit, root: Path, relative: str,
                 planned: set[str], landing: bool = False) -> Document | None:
        source = root / Path(*PurePosixPath(relative).parts)
        text = _read(source)
        if text is None:
            unit.skip("unreadable")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{relative}".lstrip("/"),
                           message="could not be read")
            return None

        soup = markdown.parse(text)
        container = soup.select_one(CONTENT_SELECTOR)
        if container is None:
            # The landing page is the one place the invariant does not hold: 5
            # roots publish 3,444 characters of real prose in a plain `<body>`.
            container = soup.body if landing else None
        if container is None:
            unit.skip("no-content-container")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{relative}".lstrip("/"),
                           message=f"no {CONTENT_SELECTOR}")
            return None

        output = links.to_markdown(PurePosixPath(relative))
        anchors = _anchors(container)
        title = _title(container)

        _strip_chrome(container, landing=landing)
        _fake_list_tables(container)
        _merge_list_continuations(container)
        _split_colspan_tables(container)

        renderer = FlareRenderer(self, context, unit, source, output, planned, landing=landing)
        body = renderer.render(container)

        if landing:
            return self._landing_document(context, unit, soup, source, output, title, body, anchors)
        return Document(source=source, relative=output, title=title, body=body, anchors=anchors)

    def _landing_document(self, context: ConversionContext, unit: Unit, soup: BeautifulSoup,
                          source: Path, output: PurePosixPath, title: str, body: str,
                          anchors: set[str]) -> Document:
        """The landing page, with its two fallbacks and its hero-only stub.

        24 landing pages have no `h1` and only 2 of those a usable `<title>`, so
        the title falls back to the product variable in the banner and then to the
        catalog. 55 are hero-only: title and version and nothing else, which is a
        page with no content rather than a page that failed to convert.
        """
        if not title:
            variable = soup.select_one("span.productvar.productName, span.mc-variable.productName")
            title = _text(variable) if variable is not None else context.product_name

        frontmatter: dict[str, object] = {}
        if len(_visible(body)) < _LANDING_MINIMUM:
            context.record("LANDING_PAGE_EMPTY", path=unit.name,
                           message=f"{source.name} has nothing past the hero; a stub was generated")
            body = ""
            frontmatter["generated"] = True
        if title and not body.lstrip().startswith("#"):
            body = f"# {markdown.escape(title)}\n\n{body}".rstrip("\n")
        return Document(source=source, relative=output, title=title, body=body,
                        anchors=anchors, frontmatter=frontmatter)

    # -- navigation ------------------------------------------------------------

    def _navigation(self, context: ConversionContext, unit: Unit, plan: _Plan,
                    documents: dict[str, Document]) -> list[NavNode]:
        """The TOC as nodes, plus the orphans, minus the nodes AEM cannot use.

        Three of §5.1.5's rules are applied here because they need the source TOC:
        a headless node with no children is dropped, a container pointing at the
        same page as one of its children loses the child, and a topic in no TOC
        entry is filed under "Unfiled". The other two -- hoisting the landing page
        and moving the support/legal tail -- are reported, not applied: they are
        engine-neutral and Phase 6's synthesizer owns them.
        """
        filed: set[str] = set()
        nodes: list[NavNode] = []
        self._dropped = 0

        for index, toc in enumerate(plan.tocs):
            converted = [
                node for node in (self._node(child, documents, filed) for child in toc.nodes)
                if node is not None
            ]
            if not converted:
                continue
            if index == 0:
                nodes.extend(converted)
            else:
                nodes.append(NavNode(label=_stem_label(toc.name), children=converted))

        orphans = [
            document for key, document in documents.items()
            if key not in filed and document.relative != unit.landing
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

    def _node(self, node: TocNode, documents: dict[str, Document],
              filed: set[str]) -> NavNode | None:
        """One TOC node, with its children. None when the node cannot be kept."""
        key = node.entry.path.lower()
        document = documents.get(key)
        if document is not None:
            filed.add(key)

        children = [
            child for child in (self._node(child, documents, filed) for child in node.children)
            if child is not None
        ]
        # 30 containers point at the same page as one of their own children. The
        # parent keeps the page and the child node goes, so the topic appears once.
        if document is not None:
            children = [child for child in children if child.document != document.relative]

        if document is None and not children:
            # A label with nothing under it: 7 headless nodes corpus-wide, plus any
            # node whose page was skipped. Dropped, and counted.
            self._dropped += 1
            return None

        label = node.entry.label or (document.title if document is not None else "")
        return NavNode(
            label=label,
            document=document.relative if document is not None else None,
            anchor=node.entry.anchor,
            children=children,
        )

    def _tail(self, context: ConversionContext, unit: Unit, plan: _Plan,
              documents: dict[str, Document]) -> None:
        """Which converted topic is support and which is legal (§5.1.5).

        Picked from the **TOC**, never by filename: 49 roots ship two or more
        support pages and 5 ship two or more legal pages, and in all 54 the TOC
        references exactly one. Absence is reported and nothing is synthesized --
        7 roots ship no legal page and 8 no support page, and unlike a headless
        container, a missing legal page breaks nothing.
        """
        for attribute, matches, label in (
            ("support", is_support_label, "support"),
            ("legal", is_legal_label, "legal"),
        ):
            found = None
            for toc in plan.tocs:
                for node in toc.walk():
                    if node.entry.path and matches(node.entry.label, node.entry.path):
                        found = documents.get(node.entry.path.lower())
                        break
                if found is not None:
                    break
            if found is None:
                context.record("TAIL_PAGE_MISSING", path=unit.name,
                               message=f"no {label} page in the TOC")
                continue
            setattr(unit, attribute, found.relative)

    # -- findings the renderer raises -----------------------------------------

    def unmapped_alert(self, context: ConversionContext, unit: Unit, label: str) -> None:
        """One row per distinct label, not per occurrence.

        The vocabulary is closed and the point of the finding is *which* label was
        seen; a row per occurrence would say the same unknown word 400 times.
        """
        if label in self._alerts:
            return
        self._alerts.add(label)
        context.record("ALERT_LABEL_UNMAPPED", path=unit.name,
                       message=f"{label!r} is outside the alert vocabulary; rendered as NOTE")

    def dangling_link(self, context: ConversionContext, unit: Unit, source: Path, raw: str) -> None:
        """A cross-reference to a topic this run did not produce.

        A note and not an error: 1.7% of the corpus's topic links already point at
        nothing in the *source*, and the finding is aggregated per version rather
        than emitted per occurrence.
        """
        context.record("TOPIC_LINK_DANGLING", path=unit.name, count=1,
                       message=f"{source.name} -> {raw}")


# -- DOM passes, in the predecessor's order (§5.1.10) --------------------------


def _strip_chrome(container: Tag, landing: bool = False) -> None:
    """Chrome first, and `#feedback-survey` first of all (§5.1.6)."""
    selectors = CHROME_SELECTORS + (LANDING_CHROME if landing else ())
    for selector in selectors:
        for element in container.select(selector):
            element.decompose()
    for element in container.find_all(["script", "style"]):
        element.decompose()
    for element in list(container.descendants):
        if isinstance(element, PreformattedString):
            # Comments and CDATA. bs4 makes both `NavigableString` subclasses, so a
            # renderer that tests for text alone emits the contents of every one.
            element.extract()
    for element in container.find_all(_is_toolbar_proxy):
        element.decompose()
    # 88% of topics: a layout wrapper around the real content, and the omission
    # from the predecessor's chrome list.
    for element in container.select("div.topic-frame"):
        element.unwrap()


def _is_toolbar_proxy(tag: Tag) -> bool:
    """`MadCap:topicToolbarProxy`, however the parser spelled it."""
    return bool(tag.name) and tag.name.lower().endswith("topictoolbarproxy")


def _fake_list_tables(container: Tag) -> None:
    """`AutoNumber_p_*` single-column tables are lists (§5.1.7).

    1,321 of them in 7% of sampled topics, against 1,809 real `<ul>`. Left as
    tables they emit a one-column pipe table where a list belongs.
    `data-mc-autonum` on the content cell decides ordered versus bulleted -- the
    class name alone does not, since `Step` and `Bullet` both appear with and
    without numbering.
    """
    for table in container.find_all("table"):
        names = " ".join(_raw_classes(table)).lower()
        if _FAKE_LIST_CLASS not in names:
            continue
        rows = _direct_rows(table)
        if not rows:
            continue
        ordered = _is_ordered(table, names)
        replacement = _SOUP.new_tag("ol" if ordered else "ul")
        for row in rows:
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            item = _SOUP.new_tag("li")
            # The last cell, always: a two-column fake list puts the drawn bullet
            # or number in the first one.
            item.extend(list(cells[-1].children))
            replacement.append(item)
        table.replace_with(replacement)


def _is_ordered(table: Tag, names: str) -> bool:
    for cell in table.find_all(["td", "th"]):
        raw = str(cell.get("data-mc-autonum") or "").strip()
        if not raw:
            continue
        if _AUTONUM_COUNTER.search(raw) or raw[:1].isdigit():
            return True
    return any(name in names for name in _ORDERED_CLASS)


def _direct_rows(table: Tag) -> list[Tag]:
    rows: list[Tag] = []
    for child in table.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "tr":
            rows.append(child)
        elif child.name in ("thead", "tbody", "tfoot"):
            rows.extend(row for row in child.children if isinstance(row, Tag) and row.name == "tr")
    return rows


def _merge_list_continuations(container: Tag) -> None:
    """One `<ol>` per step is what `_fake_list_tables` leaves behind.

    MadCap emits each numbered step as its own table, and the step's code block
    and continuation paragraph as *siblings* of it rather than inside it.
    Un-merged, every step restarts at 1 and every code block falls out of its
    step. Two absorptions only -- a `<pre>` and a `p.ListContinue` -- and a merge
    of adjacent lists of the same kind; anything wider starts swallowing lists the
    author meant to keep apart.
    """
    for parent in [container, *container.find_all(True)]:
        if not getattr(parent, "decomposed", False):
            _merge_within(parent)


def _merge_within(parent: Tag) -> None:
    while _merge_once(parent):
        pass


def _merge_once(parent: Tag) -> bool:
    children = [child for child in parent.children if isinstance(child, Tag)]
    for index, node in enumerate(children[:-1]):
        if node.name not in ("ol", "ul"):
            continue
        items = node.find_all("li", recursive=False)
        if not items:
            continue
        sibling = children[index + 1]
        if sibling.name == "pre" or (
            sibling.name == "p" and "listcontinue" in _classes(sibling)
        ):
            items[-1].append(sibling.extract())
            return True
        if sibling.name == node.name:
            for item in sibling.find_all("li", recursive=False):
                node.append(item.extract())
            sibling.decompose()
            return True
    return False


def _split_colspan_tables(container: Tag) -> None:
    """A full-width `colspan` row is a section heading, not a row (§5.1.7).

    Each becomes a label and the rows under it a table of their own, so that what
    was one ragged table -- which GFM cannot carry at all -- becomes several that
    it can.
    """
    for table in list(container.find_all("table")):
        rows = _direct_rows(table)
        width = _width(rows)
        if width < 2 or not any(_is_full_width(row, width) for row in rows):
            continue

        groups: list[tuple[Tag | None, list[Tag]]] = []
        heading: Tag | None = None
        current: list[Tag] = []
        for row in rows:
            if _is_full_width(row, width):
                groups.append((heading, current))
                heading = row.find(["td", "th"])
                current = []
            else:
                current.append(row)
        groups.append((heading, current))
        if groups and groups[0][0] is None and not groups[0][1]:
            groups = groups[1:]

        replacements: list[Tag] = []
        for label, body in groups:
            if label is not None:
                replacements.append(_heading_paragraph(label))
            if body:
                copy = _SOUP.new_tag("table")
                for row in body:
                    copy.append(row.extract())
                replacements.append(copy)
        for replacement in reversed(replacements):
            table.insert_after(replacement)
        table.decompose()


def _heading_paragraph(cell: Tag) -> Tag:
    paragraph = _SOUP.new_tag("p")
    text = _text(cell)
    if len(text) <= _SHORT_HEADING:
        strong = _SOUP.new_tag("strong")
        strong.string = text
        paragraph.append(strong)
    else:
        paragraph.extend(list(cell.children))
    return paragraph


def _width(rows: list[Tag]) -> int:
    widths = [
        sum(_span(cell) for cell in row.find_all(["td", "th"], recursive=False))
        for row in rows
    ]
    return max(widths, default=0)


def _is_full_width(row: Tag, width: int) -> bool:
    cells = row.find_all(["td", "th"], recursive=False)
    return len(cells) == 1 and _span(cells[0]) >= width > 1


def _span(cell: Tag) -> int:
    try:
        return max(1, int(str(cell.get("colspan", "1")).strip()))
    except (TypeError, ValueError):
        return 1


# -- small readers -------------------------------------------------------------


def _walk_files(root: Path):
    for directory, _, names in os.walk(root):
        for name in sorted(names):
            yield Path(directory) / name


def _read(path: Path) -> str | None:
    """UTF-8, which 4,810 of 4,810 sampled topics are. Never raises."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp1252", errors="replace")
        except OSError:  # pragma: no cover - vanished between the two reads
            return None
    except OSError:
        return None


def _title(container: Tag) -> str:
    """The `h1`, never `<title>` -- which is the truncated one in ~10% of topics."""
    heading = container.find(["h1"])
    return _text(heading) if heading is not None else ""


def _anchors(container: Tag) -> set[str]:
    found = {str(tag["id"]) for tag in container.find_all(id=True)}
    found |= {str(tag["name"]) for tag in container.find_all("a", attrs={"name": True})}
    return {anchor for anchor in found if anchor}


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ").split()) if node is not None else ""


def _visible(body: str) -> str:
    """The body's text, minus its heading lines -- what the hero-only test counts."""
    return "".join(line for line in body.splitlines() if not line.startswith("#")).strip()


def _stem_label(stem: str) -> str:
    """A second TOC tree's name, from its file stem. `_HTML_gateway_server` -> ..."""
    name = stem.lstrip("_")
    if name.lower().startswith("html_"):
        name = name[5:]
    return " ".join(name.replace("_", " ").replace("-", " ").split()) or stem


def _relative(tree: Path, path: Path) -> str:
    try:
        return path.relative_to(tree).as_posix()
    except ValueError:  # pragma: no cover - the driver walks from the tree
        return path.name


__all__ = ["CONTENT_SELECTOR", "FlareEngine", "FlareRenderer", "autonum_label"]
