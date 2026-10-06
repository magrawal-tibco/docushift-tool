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
scale: strip chrome, then fake lists, then list continuations, then icon tables
and text popups, then colspan splits. Its `fake_list_tables()`, `split_colspan_tables()` and `SPAN_TO_TAG`
vocabulary are taken; its `Home.htm` skip, its missing `div.topic-frame`, its
selector fallback chain and its hand-maintained `skip_path_segments` are not.

**One honest limit.** A cross-reference is checked against the set of topics this
run *planned* to convert, which is settled before the first file is parsed. A
topic that then fails the container check leaves a link pointing at a page that
was never written. That is 3 files in the sampled corpus, and the alternative --
holding 8,485 parsed DOMs to defer every link decision -- costs more than it buys.
`validate` (Phase 7) re-resolves the emitted links and would name the residue.
"""

import html
import os
import re
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning
from bs4.element import PreformattedString, ProcessingInstruction

from docushift.apiref import is_api_reference
from docushift.engines.base import (
    BaseEngine,
    ConversionContext,
    Document,
    NavNode,
    Unit,
    fold_same_page,
    is_legal_label,
    is_placeholder_whats_new,
    is_support_label,
    is_whats_new,
    register,
)
from docushift.engines.flare_toc import Manifest, Toc, TocNode, read_manifest, read_toc, tree_files
from docushift.engines.roots import find_output_roots, owning_root
from docushift.models import SourceEngine
from docushift.transforms import callouts, deflists, headings, links, markdown
from docushift.utils.longpath import long_path, walk_under

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
# The number a step is drawn with: `data-mc-autonum="3. "`.
_AUTONUM_NUMBER = re.compile(r"\s*(\d+)")
# Set on each list `_fake_list_tables` builds and removed once the merge pass is
# done, so that only those lists absorb their neighbours (R5-07). Never emitted.
_FAKE_LIST_MARK = "data-docushift-fake-list"
# `TableStyle-IconTable`: a callout drawn as a one-row table (R5-03).
_ICON_TABLE_CLASS = "icontable"
# Block children that a colspan heading's bold label cannot hold (R5-04).
_HEADING_BLOCKS = ("p", "div", "ul", "ol", "dl", "pre", "table", "blockquote",
                   "h1", "h2", "h3", "h4", "h5", "h6")
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
                 source: Path, output: PurePosixPath, topics: dict[str, str],
                 landing: bool = False):
        self.engine = engine
        self.context = context
        self.unit = unit
        self.source = source
        self.output = output
        # Every topic this run will write, case-folded root-relative path -> the
        # path as it is on disk. A cross-reference to anything else is a dangling
        # link, not a `.md` path.
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
                return self.code_span(tag)
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
        # Into a published API tree: the one link kind whose target is a real
        # file that this run deliberately does not convert (§10.7). The URL comes
        # from `ConversionContext.api_url`, which the driver resolved -- the engine
        # is told the publishing layout, never asked to work it out.
        #
        # Checked before the topic/asset split rather than inside one arm of it.
        # Every one of the 3,194 measured references is a topic-suffixed page, but
        # a repackaging that ships a PDF inside a Javadoc tree must not quietly
        # start dropping links again.
        api = self.context.api_url(self.source, reference.path, reference.fragment)
        if api is not None:
            return api
        if not links.is_topic(reference.path):
            return self._asset(reference.raw)

        resolved = links.resolve(self.base, reference.path)
        planned = None if links.escapes(resolved) else self.topics.get(str(resolved).lower())
        if planned is None:
            # Not this root's -- but perhaps a sibling's or a nested root's, which
            # is where 1,332 such links in 18 versions point (Phase 34, R5-08).
            # Emitted between the two published subtrees, and still a dangling
            # note when no unit of the version converts the target.
            across = self.engine.cross_root(
                self.context, self.unit, Path(os.path.normpath(self.unit.root / resolved))
            )
            if across is None:
                self.engine.dangling_link(self.context, self.unit, self.source, reference.path)
                return None
            here = PurePosixPath(self.unit.name) / self.output if self.unit.name else self.output
            return links.emit(links.relative_to(here, across), reference.fragment)
        # The file's letter case, not the href's (R5-06). Matched case-folded, the
        # way Windows resolves it, and emitted as written: `dsc-stat/14.1.0` links
        # `10-working-with-Statistica-query/` into a directory spelled in lower
        # case, which 404s on GitHub and AEM.
        target = links.to_markdown(PurePosixPath(planned))
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

    tocs: list[Toc] = field(default_factory=list)
    # Root-relative source paths, sorted. The landing page is not among them.
    topics: list[str] = field(default_factory=list)
    landing: str = ""
    # The What's New topic under `_templates/`, root-relative, where the root has
    # one *and it says something*. Blank otherwise -- including where the page is
    # there but unfilled, which is the case `placeholder` records.
    whats_new: str = ""
    # A What's New page that is still the authoring template, case-folded. Held
    # separately because it has to be rejected even when the source TOC references
    # it, which is true of 4 versions.
    placeholder: str = ""
    # `topics` plus `landing`, case-folded, each mapped to its on-disk spelling:
    # what a cross-reference may point at, and the path it is emitted as.
    planned: dict[str, str] = field(default_factory=dict)


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
        # `.flprj` insertion points dropped from the TOC, as "label (project)".
        self._subprojects: list[str] = []
        # Every unit of the version, and each one's plan once something has asked
        # for it -- its own conversion, or a link from another root into it
        # (Phase 34, R5-08). Planned once either way, so its findings are too.
        self._roots: list[Path] = []
        self._plans: dict[Path, tuple[Unit, _Plan]] = {}
        # Phase 41: what each root's built topics fill in for a shipped source
        # topic, read only once a root turns out to hold one, and what was done.
        self._terms: dict[Path, _SourceTerms] = {}
        self._sourced: dict[Path, _SourceTally] = {}

    def units(self, context: ConversionContext) -> list[Path]:
        roots = super().units(context)
        self._roots = list(roots)
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
        unit, plan = self._planned(context, root)

        documents: dict[str, Document] = {}
        bare: list[str] = []
        for relative in plan.topics:
            document = self._guarded(context, unit, root, relative, plan.planned, bare=bare)
            if document is not None:
                documents[relative.lower()] = document
        if bare:
            documents = self._bare_root(context, unit, root, plan, documents, bare)

        if plan.landing:
            landing = self._guarded(context, unit, root, plan.landing, plan.planned, landing=True)
            if landing is not None:
                documents[plan.landing.lower()] = landing
                unit.landing = landing.relative

        if plan.whats_new:
            found = documents.get(plan.whats_new.lower())
            if found is not None:
                unit.whats_new = found.relative

        tally = self._sourced.pop(root, None)
        if tally is not None:
            context.record("CONTENT_SOURCE_TOPIC", path=unit.name, count=tally.topics,
                           message=tally.message())

        unit.documents = list(documents.values())
        unit.nav = self._navigation(context, unit, plan, documents)
        self._tail(context, unit, plan, documents)
        return unit

    def _planned(self, context: ConversionContext, root: Path) -> tuple[Unit, _Plan]:
        if root not in self._plans:
            unit = Unit(root=root, name=context.subtree_name(root))
            self._plans[root] = (unit, self._plan(context, unit, root))
        return self._plans[root]

    def cross_root(self, context: ConversionContext, unit: Unit,
                   target: Path) -> PurePosixPath | None:
        """Where another unit of this version publishes `target`, version-relative.

        `None` when the innermost unit holding the file is the asking one -- a
        miss in its own plan is a real miss -- or when the unit that holds it
        does not convert it. The path keeps the planned file's own case.
        """
        owner = owning_root(target, self._roots)
        if owner is None or owner == unit.root:
            return None
        other, plan = self._planned(context, owner)
        key = target.relative_to(owner).as_posix().lower()
        if key not in plan.planned:
            return None
        name = next(
            (topic for topic in (*plan.topics, plan.landing) if topic and topic.lower() == key), key
        )
        published = links.to_markdown(PurePosixPath(name))
        return PurePosixPath(other.name) / published if other.name else published

    # -- what to convert -------------------------------------------------------

    def _plan(self, context: ConversionContext, unit: Unit, root: Path) -> _Plan:
        """Reads the manifest and the TOCs, then decides the file set.

        Both halves have to happen before any topic is parsed: `_templates/` is
        converted only where the TOC references it, and a cross-reference can only
        be rewritten against a set that is already known.
        """
        manifest = read_manifest(root)
        if manifest is None:
            # The file is there -- it is how the root was found -- and did not
            # parse. No declared TOC and no landing page follow, and before R5-12
            # only `TOC_ORPHAN` hinted at why.
            context.record("TOC_UNREADABLE", path=unit.name,
                           message="Data/HelpSystem.xml did not parse; no declared TOC, no landing page")
            manifest = Manifest()
        tocs = self._tocs(context, unit, root, manifest)
        referenced = {
            node.entry.path.lower()
            for toc in tocs for node in toc.walk() if node.entry.path
        }

        landing = manifest.default_url
        if landing and not (root / Path(*PurePosixPath(landing).parts)).is_file():
            landing = ""

        whats_new, placeholder = self._whats_new(context, unit, root, landing)
        if whats_new:
            # 74 roots have a real What's New that no TOC entry reaches, and
            # `_rejection` would discard it as `unreferenced-template`. Declaring it
            # referenced here -- rather than special-casing the rejection -- keeps
            # one answer to "what does this root convert".
            referenced.add(whats_new.lower())

        topics = self._topics(context, unit, root, referenced, landing, placeholder)
        planned = {name.lower(): name for name in topics}
        if landing:
            planned[landing.lower()] = landing
        return _Plan(tocs=tocs, landing=landing, topics=topics,
                     whats_new=whats_new, placeholder=placeholder, planned=planned)

    def _whats_new(self, context: ConversionContext, unit: Unit, root: Path,
                   landing: str) -> tuple[str, str]:
        """The root's What's New topic, and whether it is still the blank template.

        Returns `(real, placeholder)` -- at most one of them is set. Measured over
        903 Flare roots: 648 carry the file, 481 of those say something and 167 do
        not. The landing page is excluded from the search because a root whose
        `DefaultUrl` *is* the What's New page already has it first.
        """
        directory = root / TEMPLATES_DIRECTORY
        if not directory.is_dir():
            return "", ""
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() not in _HTML_SUFFIXES or not is_whats_new(path.name):
                continue
            relative = f"{TEMPLATES_DIRECTORY}/{path.name}"
            if relative.lower() == landing.lower():
                return "", ""
            text = _read(path)
            if text is None:  # pragma: no cover - reported by `_convert` if reached
                return "", ""
            container = markdown.parse(text).select_one(CONTENT_SELECTOR)
            if container is not None and not is_placeholder_whats_new(_text(container)):
                return relative, ""
            context.record("WHATS_NEW_PLACEHOLDER", path=unit.name,
                           message=f"{path.name} is the unfilled template; left out of the TOC")
            return "", relative.lower()
        return "", ""

    def _tocs(self, context: ConversionContext, unit: Unit, root: Path,
              manifest: Manifest) -> list[Toc]:
        """The declared tree first, then the others as sibling top-level nodes.

        Three corpus roots ship two trees and `Toc=` names one of them; in
        `bctcm/6.2.0` the declared tree covers 53 of 106 topics, so reading it
        alone loses half the navigation and globbing alphabetically picks the wrong
        file in all three.

        The declared tree is read even when it is not on disk, so that its absence
        is reported rather than skipped (R5-12); its place stays first either way.
        Any other file that does not read as a tree is a helper script or a chunk
        payload the pattern missed, and is passed over without a word.
        """
        files = tree_files(root)
        declared = root / Path(*PurePosixPath(manifest.toc).parts) if manifest.toc else None
        ordered = [declared] if declared is not None else []
        ordered += [path for path in files if path != declared]

        tocs: list[Toc] = []
        for path in ordered:
            toc = read_toc(path)
            if not toc.readable:
                if path != declared:
                    continue
                context.record("TOC_UNREADABLE", path=unit.name,
                               message=f"{manifest.toc} is missing or did not parse; "
                                       "every topic is filed under Unfiled")
            if toc.unmatched:
                context.record("NAV_NODE_DROPPED", path=unit.name, count=toc.unmatched,
                               message=f"{toc.unmatched} TOC id(s) with no payload entry in {path.name}")
            if toc.ragged:
                context.record("NAV_NODE_DROPPED", path=unit.name, count=toc.ragged,
                               message=f"{toc.ragged} ragged i/t/b array(s) in {path.name}")
            tocs.append(toc)
        return tocs

    def _topics(self, context: ConversionContext, unit: Unit, root: Path,
                referenced: set[str], landing: str, placeholder: str = "") -> list[str]:
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
        stubs = _project_stubs(root)
        # Another engine's unit inside this root -- BusinessConnect 7.4.0's WebWorks
        # book -- is the driver's to name, once (Phase 34, R4-02); fed to this
        # engine it was ~80 `CONTENT_MISSING` lines, one per page.
        foreign = [other for other in context.excluded_roots
                   if root in other.parents and other not in nested]
        found: list[str] = []
        for path in walk_under(root):
            if path.suffix.lower() not in _HTML_SUFFIXES:
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if str(relative).lower() == landing.lower():
                # Converted, by the landing-page path rather than this one. Not a
                # skip, and counting it as one would put a converted page in the
                # column that says nothing was written.
                continue
            if any(other in path.parents for other in foreign):
                unit.skip("other-engine-root")
                continue
            reason = self._rejection(path, relative, nested, context.api_roots,
                                     referenced, placeholder, stubs)
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
                   api_roots: list[Path], referenced: set[str], placeholder: str = "",
                   stubs: frozenset[str] = frozenset()) -> str:
        """Why this HTML file is not a topic, or `""` if it is one."""
        first = relative.parts[0].lower() if len(relative.parts) > 1 else ""
        if first in LOCALIZED_DIRECTORIES:
            return "localized-subtree"
        if first in GENERATED_DIRECTORIES:
            return "generated-directory"
        if path.name.lower() in STUB_FILENAMES:
            return "runtime-stub"
        if len(relative.parts) == 1 and path.name.lower() in stubs:
            return "runtime-stub"
        if any(root in path.parents for root in nested):
            return "nested-output-root"
        if self.skips_api_references and is_api_reference(path, api_roots):
            return "api-reference"
        key = str(relative).lower()
        if placeholder and key == placeholder:
            # Rejected whether or not a TOC entry reaches it, which is the one
            # place this overrules the source. 4 versions file the unfilled
            # template in their navigation; the rest never referenced it anyway.
            return "placeholder-template"
        if first == TEMPLATES_DIRECTORY and key not in referenced:
            return "unreferenced-template"
        return ""

    def _bare_root(self, context: ConversionContext, unit: Unit, root: Path, plan: _Plan,
                   documents: dict[str, Document], bare: list[str]) -> dict[str, Document]:
        """The topics with no container: a root's shape, or a stray file each.

        The Statistica LTS roots use a skin that puts content straight in
        `<body>` -- 292 of 293 topics in each 14.1.0 root, ~1,485 across 10 roots,
        each one dropped and reported on its own line (R5-09). §5.1.6's 99.9% is a
        per-topic figure and cannot see that shape. So where **no topic outside
        `_templates/`** has the container, a MadCap `Topic` file without it is
        converted from `<body>` and the root is reported once. The skin's own
        templates do not count -- 14.2.0's `Home.htm` has the container and its
        five topics do not. Anywhere else, a topic without the container is
        still `CONTENT_MISSING`: one stray file is not evidence about a skin,
        and the Javadoc page the fallback chain once converted carries no
        MadCap marker at all.

        The planned set is unchanged, so a cross-reference resolved against it
        stays right. Documents keep the plan's order.
        """
        contained = any(
            not key.startswith(f"{TEMPLATES_DIRECTORY}/") for key in documents
        )
        fallen = 0
        for relative in bare:
            document = self._guarded(context, unit, root, relative, plan.planned,
                                     body=not contained)
            if document is not None:
                documents[relative.lower()] = document
                fallen += 1
        if fallen:
            context.record("CONTENT_BODY_FALLBACK", path=unit.name, count=fallen,
                           message=f"no topic has {CONTENT_SELECTOR}; {fallen} converted from <body>")
        order = [relative.lower() for relative in plan.topics]
        return {key: documents[key] for key in order if key in documents}

    # -- one topic -------------------------------------------------------------

    def _guarded(self, context: ConversionContext, unit: Unit, root: Path, relative: str,
                 planned: dict[str, str], **options) -> Document | None:
        """`_convert`, with the base contract's "never raises" held per topic (R5-15).

        One topic that makes bs4 or the recursive renderer fail -- a
        `RecursionError` on deep nesting is the plausible one -- would otherwise
        abort every root of the version. None has in ~49,000 converted documents,
        which is why it is a skip and a report line rather than a design.
        """
        try:
            return self._convert(context, unit, root, relative, planned, **options)
        except Exception as error:  # noqa: BLE001 - reported, and the root goes on
            unit.skip("render-error")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{relative}".lstrip("/"),
                           message=f"could not be rendered: {type(error).__name__}: {error}")
            return None

    def _convert(self, context: ConversionContext, unit: Unit, root: Path, relative: str,
                 planned: dict[str, str], landing: bool = False, body: bool = False,
                 bare: list[str] | None = None) -> Document | None:
        """One topic. `body` is `_bare_root`'s fallback; `bare` defers a container miss.

        A topic with no container is appended to `bare` instead of reported when
        the caller passes one, because whether it is a stray file or the shape of
        the whole root is not known until every topic has been read.
        """
        source = root / Path(*PurePosixPath(relative).parts)
        text = _read(source)
        if text is None:
            unit.skip("unreadable")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{relative}".lstrip("/"),
                           message="could not be read")
            return None

        soup = _parse(text)
        container = soup.select_one(CONTENT_SELECTOR)
        if container is None and (landing or (body and _is_runtime_topic(soup))):
            # The landing page is the one place the invariant does not hold: 5
            # roots publish 3,444 characters of real prose in a plain `<body>`.
            # The other is a root whose skin never writes the container at all.
            container = soup.body
        if container is None and _is_source_topic(soup):
            container = self._source_body(unit, root, soup)
        if container is None and bare is not None:
            bare.append(relative)
            return None
        if container is None:
            unit.skip("no-content-container")
            context.record("CONTENT_MISSING", path=f"{unit.name}/{relative}".lstrip("/"),
                           message=f"no {CONTENT_SELECTOR}")
            return None

        output = links.to_markdown(PurePosixPath(relative))
        title = _title(container)

        _strip_chrome(container, landing=landing)
        _fake_list_tables(container)
        _merge_list_continuations(container)
        _icon_tables(container)
        _text_popups(container)
        _split_colspan_tables(container)

        context.recovered_terms += deflists.normalize(container)
        context.renumbered_headings += headings.normalize(container)

        renderer = FlareRenderer(self, context, unit, source, output, planned, landing=landing)
        body = renderer.render(container)
        context.flattened_links += renderer.flattened_links
        context.unrendered.update(renderer.unrendered)

        if landing:
            return self._landing_document(context, unit, soup, source, output, title, body)
        return Document(source=source, relative=output, title=title, body=body)

    def _source_body(self, unit: Unit, root: Path, soup: BeautifulSoup) -> Tag | None:
        """A shipped source topic's `<body>`, finished the way its build would have.

        Phase 41: 24 English pages in 11 ibi versions are the authored `.htm`, not
        the built one. Their variables are empty elements and their conditional
        text is all still there, so both are settled from what the root's built
        topics show before the page goes through the ordinary passes.
        """
        if root not in self._terms:
            plan = self._plans.get(root)
            self._terms[root] = _source_terms(root, plan[1].topics if plan else [])
        terms = self._terms[root]
        tally = self._sourced.setdefault(root, _SourceTally())
        tally.topics += 1

        for keyword in soup.find_all("madcap:keyword"):
            keyword.decompose()
        for element in soup.find_all(attrs={"madcap:conditions": True}):
            if element.decomposed:
                continue
            tags = _condition_tags(str(element["madcap:conditions"]))
            if tags & terms.kept:
                continue
            if tags & terms.known:
                element.decompose()
                tally.removed += 1
            else:
                # No built topic shows the tag, kept or dropped: removing the
                # element would delete text on a guess.
                tally.unknown.update(tags)
        for variable in soup.find_all("madcap:variable"):
            name = str(variable.get("name", ""))
            value = terms.variables.get(name)
            if value:
                variable.replace_with(value)
            else:
                tally.unresolved[name] += 1
                variable.decompose()
        for xref in soup.find_all("madcap:xref"):
            xref.name = "a"
        return soup.body

    def _landing_document(self, context: ConversionContext, unit: Unit, soup: BeautifulSoup,
                          source: Path, output: PurePosixPath, title: str, body: str) -> Document:
        """The landing page, with its two fallbacks and its hero-only stub.

        24 landing pages have no `h1` and only 2 of those a usable `<title>`, so
        the title falls back to the product variable in the banner and then to the
        catalog. 55 are hero-only: title and version and nothing else, which is a
        page with no content rather than a page that failed to convert.
        """
        if not title:
            variable = soup.select_one("span.productvar.productName, span.mc-variable.productName")
            title = _text(variable) if variable is not None else context.product_name

        body = _trim_portal(body)

        frontmatter: dict[str, object] = {}
        if len(_visible(body)) < _LANDING_MINIMUM:
            context.record("LANDING_PAGE_EMPTY", path=unit.name,
                           message=f"{source.name} has nothing past the hero; a stub was generated")
            body = ""
            frontmatter["generated"] = True
        if title and not body.lstrip().startswith("#"):
            body = f"# {markdown.escape(title)}\n\n{body}".rstrip("\n")
        return Document(source=source, relative=output, title=title, body=body,
                        frontmatter=frontmatter)

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
        self._folded = 0
        self._subprojects = []

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
        if self._folded:
            context.record("NAV_NODE_DROPPED", path=unit.name, count=self._folded,
                           message=f"{self._folded} child node(s) repeating the parent's "
                                   "page with no bookmark of their own, folded into it "
                                   "(same page)")
        if self._subprojects:
            # Counted apart from the drops above, because the cause is not a
            # missing page: the sub-project converts as a unit of its own (or is
            # not in this version) and only its place in this TOC is lost. The
            # file names do not match the unit names -- `control-tower.flprj` is
            # `Subsystems/platform-ct` -- so placing it is not attempted here.
            context.record("TOC_SUBPROJECT_UNPLACED", path=unit.name, count=len(self._subprojects),
                           message="merged-project TOC node(s) not placed: "
                                   + "; ".join(self._subprojects))
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
        # parent keeps the page and the child node goes, so the topic appears once
        # -- but only an exact repeat: a child with its own bookmark is a section
        # entry, and §5.3.4 keeps it (R7-01).
        children, folded = fold_same_page(
            children, document.relative if document is not None else None, node.entry.anchor
        )
        self._folded += folded

        if document is None and not children and node.entry.project:
            # A merged project's insertion point (R5-11): 121 keys over 937 roots.
            self._subprojects.append(f"{node.entry.label} ({node.entry.project})".lstrip())
            return None
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


def _orphan_targets(table: Tag) -> list[Tag]:
    """The table's *own* anchor targets, extracted, in document order.

    Flare writes one between `<col>` and `<thead>` -- in no cell, so a rewrite
    that carries the rows across leaves it on the element it is about to
    discard. 24 of the `ems` tree's missing anchors were exactly that (§5.7).
    A target inside a cell rides with its row and is deliberately not taken.
    """
    return [
        anchor.extract()
        for anchor in list(table.find_all("a"))
        if not anchor.get("href")
        and markdown.anchor_target(anchor)
        and anchor.find_parent(["td", "th"]) is None
    ]


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
        replacement[_FAKE_LIST_MARK] = ""
        start = _autonum_start(table) if ordered else 1
        if start != 1:
            # The step's drawn number. A procedure that a note or a paragraph
            # interrupts resumes at 3 in the source and, merged with nothing,
            # would restart at 1 here: 110 of 1,285 numbered items (R5-02).
            replacement["start"] = str(start)
        for row in rows:
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            item = _SOUP.new_tag("li")
            # The last cell, always: a two-column fake list puts the drawn bullet
            # or number in the first one.
            item.extend(list(cells[-1].children))
            replacement.append(item)
        for anchor in reversed(_orphan_targets(table)):
            table.insert_before(anchor)
        table.replace_with(replacement)


def _is_ordered(table: Tag, names: str) -> bool:
    for cell in table.find_all(["td", "th"]):
        raw = str(cell.get("data-mc-autonum") or "").strip()
        if not raw:
            continue
        if _AUTONUM_COUNTER.search(raw) or raw[:1].isdigit():
            return True
    return any(name in names for name in _ORDERED_CLASS)


def _autonum_start(table: Tag) -> int:
    """The number the first item is drawn with, or 1 where it is a counter token."""
    for cell in table.find_all(["td", "th"]):
        raw = str(cell.get("data-mc-autonum") or "")
        if raw.strip():
            match = _AUTONUM_NUMBER.match(raw)
            return int(match.group(1)) if match else 1
    return 1


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

    **Nothing merges across prose, and only a list `_fake_list_tables` built
    absorbs a `<pre>`** (R5-07). Prose between a list and the next block is the
    sentence that introduces it -- skipping over it nested an example inside the
    previous bullet and ahead of its explanation. And an authored `<ul>` was
    never split by MadCap, so a `<pre>` after it is the author's own block: in
    EMS it is the example for the whole list, not for its last bullet. A
    `p.ListContinue` still joins any list, because the class is the author
    saying so.
    """
    for parent in [container, *container.find_all(True)]:
        if not getattr(parent, "decomposed", False):
            _merge_within(parent)
    for built in container.find_all(attrs={_FAKE_LIST_MARK: True}):
        del built[_FAKE_LIST_MARK]


def _merge_within(parent: Tag) -> None:
    while _merge_once(parent):
        pass


def _merge_once(parent: Tag) -> bool:
    children = [child for child in parent.children if isinstance(child, Tag)]
    for node in children:
        if node.name not in ("ol", "ul"):
            continue
        items = node.find_all("li", recursive=False)
        if not items:
            continue
        sibling = _adjacent(node)
        if sibling is None:
            continue
        if (sibling.name == "pre" and node.has_attr(_FAKE_LIST_MARK)) or (
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


def _adjacent(node: Tag) -> Tag | None:
    """The next element sibling, or None when text other than whitespace comes first."""
    sibling = node.next_sibling
    while sibling is not None:
        if isinstance(sibling, Tag):
            return sibling
        if markdown.is_text(sibling) and str(sibling).strip():
            return None
        sibling = sibling.next_sibling
    return None


def _icon_tables(container: Tag) -> None:
    """`TableStyle-IconTable` is a callout drawn as a table (§5.1.10, R5-03).

    The label is a `data-mc-autonum` paragraph in the first cell and the text is
    in the second. As a table, the pipe path renders each cell inline, so the
    label -- which only `_labelled` re-emits, and only in block position -- is
    lost, and the note becomes a two-column table with an empty header. Rebuilt
    as `div.note` carrying the label, the callout path then maps it exactly as it
    maps any other note, including the report for a label outside the vocabulary.
    """
    for table in list(container.find_all("table")):
        if _ICON_TABLE_CLASS not in " ".join(_raw_classes(table)).lower():
            continue
        rows = _direct_rows(table)
        cells = rows[0].find_all(["td", "th"], recursive=False) if len(rows) == 1 else []
        if len(cells) != 2:
            continue
        labelled = cells[0].find(attrs={"data-mc-autonum": True})
        label = autonum_label(labelled) if isinstance(labelled, Tag) else ""
        callout = _SOUP.new_tag("div", attrs={"class": "note"})
        if label:
            callout["data-mc-autonum"] = label
        # The table's own targets, and any in the label cell, which is discarded.
        targets = _orphan_targets(table) + [
            anchor.extract() for anchor in list(cells[0].find_all("a"))
            if not anchor.get("href") and markdown.anchor_target(anchor)
        ]
        for anchor in targets:
            table.insert_before(anchor)
        callout.extend(list(cells[1].children))
        table.replace_with(callout)


def _text_popups(container: Tag) -> None:
    """A MadCap text popup becomes its trigger and a parenthetical (R5-13).

    `a.MCTextPopup` holds the trigger -- usually a footnote digit the skin
    superscripts -- and the popup body inside it, so walking it as a link that
    goes nowhere ran the two together with the word before: "PCA Apply1This
    operator is deprecated". The body is kept, in brackets, where it was.
    """
    for anchor in list(container.select("a.MCTextPopup")):
        body = anchor.find("span", class_="MCTextPopupBody")
        if not isinstance(body, Tag):
            continue
        body.extract()
        for arrow in body.select("span.MCTextPopupArrow"):
            arrow.decompose()
        trigger = _text(anchor)
        replacement: list[Tag | str] = []
        if trigger:
            superscript = "super" in str(anchor.get("style") or "").lower()
            if superscript and anchor.find("sup") is None:
                marker = _SOUP.new_tag("sup")
                marker.string = trigger
                replacement.append(marker)
            else:
                replacement.extend(list(anchor.children))
        if _text(body):
            _trim_edges(body)
            replacement.append(" (")
            replacement.extend(list(body.children))
            replacement.append(")")
        for node in replacement:
            anchor.insert_before(node)
        anchor.decompose()


def _trim_edges(tag: Tag) -> None:
    """Strips the source indentation at either end, which would sit inside the brackets."""
    children = list(tag.children)
    if children and markdown.is_text(children[0]):
        children[0].replace_with(str(children[0]).lstrip())
    children = list(tag.children)
    if children and markdown.is_text(children[-1]):
        children[-1].replace_with(str(children[-1]).rstrip())


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

        replacements: list[Tag] = list(_orphan_targets(table))
        caption = table.find("caption", recursive=False)
        if isinstance(caption, Tag) and _text(caption):
            # The table's title -- "Status Codes" -- goes ahead of the first
            # piece rather than with the table it was on: 35 of 175 split tables
            # in the families carried one, and lost it (R5-05).
            title = _SOUP.new_tag("p")
            strong = _SOUP.new_tag("strong")
            strong.extend(list(caption.children))
            title.append(strong)
            replacements.append(title)
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
    """A full-width row's cell as the label of the rows under it.

    A short, inline-only cell is an identifier and becomes one bold run. Its
    children are moved into the run rather than rebuilt from its text: rebuilding
    dropped the `<code>` in "Use the `/MT` compiler option" and the link in every
    EMS version's "Headers and Properties" row (R5-04). A cell holding a block --
    a heading word over a `<p>` of prose -- keeps its markup as it stands, which
    is what a long label always did.
    """
    paragraph = _SOUP.new_tag("p")
    text = _text(cell)
    if len(text) <= _SHORT_HEADING and cell.find(_HEADING_BLOCKS) is None:
        # The anchor targets Flare writes into these rows are carried over ahead
        # of the label they name, outside the bold run: 100 of the `ems` tree's
        # missing anchors were one of these (§5.7).
        for anchor in list(cell.find_all("a")):
            if not anchor.get("href") and markdown.anchor_target(anchor):
                paragraph.append(anchor.extract())
        strong = _SOUP.new_tag("strong")
        strong.extend(list(cell.children))
        # `<b>Receipt</b>` is the common cell; inside the run a second bold
        # would emit `****Receipt****`.
        for inner in strong.find_all(["b", "strong"]):
            inner.unwrap()
        # `<code>tibemsd </code>settings`: the code span trims its own padding,
        # which the text rebuild never had to care about, so the space that
        # separates the words is put back outside it.
        for code in strong.find_all("code"):
            inner_text = markdown.text_of(code)
            if inner_text[:1].isspace():
                code.insert_before(" ")
            if inner_text[-1:].isspace():
                code.insert_after(" ")
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


def _project_stubs(root: Path) -> frozenset[str]:
    """The runtime stubs Flare names after the build target (R5-10).

    `<stem>.htm` and `<stem>_CSH.htm` sit beside `<stem>.mcwebhelp` at the
    root -- `platform-ct.htm` in `tp/1.1.0` -- where `STUB_FILENAMES` only knows
    the `Default` spelling. 278 in 139 roots, none a topic, each a false
    `CONTENT_MISSING` until now.
    """
    try:
        stems = [path.stem.lower() for path in root.iterdir()
                 if path.suffix.lower() == ".mcwebhelp" and path.is_file()]
    except OSError:
        return frozenset()
    return frozenset(name for stem in stems for name in (f"{stem}.htm", f"{stem}_csh.htm"))


def _read(path: Path) -> str | None:
    """UTF-8, which 4,810 of 4,810 sampled topics are. Never raises.

    Through `long_path` (X2-08): a plain read of a topic past 260 characters
    fails, and that failure was reported as `CONTENT_MISSING`.
    """
    path = long_path(path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp1252", errors="replace")
        except OSError:  # pragma: no cover - vanished between the two reads
            return None
    except OSError:
        return None


def _parse(text: str) -> BeautifulSoup:
    """`markdown.parse`, quiet about a source topic's XML declaration (Phase 41).

    Reading one as HTML is the intended behaviour, so bs4's advice to switch to
    an XML parser is noise in every convert log that meets one.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        return markdown.parse(text)


def _is_source_topic(soup: BeautifulSoup) -> bool:
    """An authored Flare topic the build copied into its output (Phase 41).

    An XML declaration, the MadCap namespace on `<html>`, and no runtime marker.
    All 55 such files in `families/` qualify and no built topic does; a Javadoc
    page has no MadCap namespace, so §5.1.6's no-fallback rule still holds for it.
    """
    root = soup.find("html")
    if not isinstance(root, Tag) or root.get("data-mc-runtime-file-type"):
        return False
    if not any(str(name).lower() == "xmlns:madcap" for name in root.attrs):
        return False
    return any(
        isinstance(node, ProcessingInstruction) and str(node).lower().startswith("xml")
        for node in soup.contents
    )


@dataclass
class _SourceTerms:
    """What a root's built topics say its build filled in and kept (Phase 41)."""

    # Variable name -> the value its `span.mc-variable` shows most often.
    variables: dict[str, str] = field(default_factory=dict)
    # Condition tags some built element carries on its own: the build included them.
    kept: frozenset[str] = frozenset()
    # Every tag a built element carries. Known but not kept means excluded.
    known: frozenset[str] = frozenset()


@dataclass
class _SourceTally:
    """One root's source topics, for its single `CONTENT_SOURCE_TOPIC` row."""

    topics: int = 0
    removed: int = 0
    unresolved: Counter[str] = field(default_factory=Counter)
    unknown: Counter[str] = field(default_factory=Counter)

    def message(self) -> str:
        parts = [f"{self.topics} source topic(s) converted from <body>",
                 f"{self.removed} element(s) of excluded conditions removed"]
        if self.unresolved:
            parts.append(f"{sum(self.unresolved.values())} variable(s) unresolved: "
                         + ", ".join(sorted(self.unresolved)))
        if self.unknown:
            parts.append("condition tag(s) no built topic shows, left in: "
                         + ", ".join(sorted(self.unknown)))
        return "; ".join(parts)


_VARIABLE_SPAN = re.compile(
    r"""<span\b[^>]*\bclass=["']mc-variable\s+([^"'\s]+)[^"']*["'][^>]*>([^<]*)</span>""")
_CONDITIONS = re.compile(r"""data-mc-conditions=["']([^"']*)["']""")


def _condition_tags(raw: str) -> frozenset[str]:
    return frozenset(tag.strip() for tag in raw.split(",") if tag.strip())


def _source_terms(root: Path, topics: list[str]) -> _SourceTerms:
    """Reads the root's built topics as text; a source topic has no container."""
    values: dict[str, Counter[str]] = {}
    kept: set[str] = set()
    known: set[str] = set()
    for relative in topics:
        text = _read(root / Path(*PurePosixPath(relative).parts))
        if text is None or "mc-main-content" not in text:
            continue
        for name, value in _VARIABLE_SPAN.findall(text):
            value = " ".join(html.unescape(value).split())
            if value:
                values.setdefault(name, Counter())[value] += 1
        for raw in _CONDITIONS.findall(text):
            tags = _condition_tags(raw)
            known.update(tags)
            if len(tags) == 1:
                kept.update(tags)
    return _SourceTerms(
        variables={name: counts.most_common(1)[0][0] for name, counts in values.items()},
        kept=frozenset(kept), known=frozenset(known),
    )


def _is_runtime_topic(soup: BeautifulSoup) -> bool:
    """MadCap's own marker for a topic file, on `<html>`. A Javadoc page has none."""
    html = soup.find("html")
    return isinstance(html, Tag) and str(html.get("data-mc-runtime-file-type", "")) == "Topic"


def _title(container: Tag) -> str:
    """The `h1`, never `<title>` -- which is the truncated one in ~10% of topics."""
    heading = container.find(["h1"])
    return _text(heading) if heading is not None else ""


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ").split()) if node is not None else ""


# The doc-portal blocks a Flare landing page ends with. They are `docs.tibco.com`
# furniture -- a PDF shelf, a site-wide "most visited" list, links to sibling
# products -- and in a published version folder their targets are external or gone,
# so they render as bare text lists. Counts over 778 landing pages.
PORTAL_BLOCKS = frozenset({
    "release documents",              # 545
    "related product documentation",  # 537
    "related products documentation",  # 50, the same block spelled with the plural
    "most visited topics",            # 482
    "downloadable pdf guides",        # 457
    "downloadable pdf guide",         # 2
    "videos",                         # 49
    "key guides",                     # 27
    "recommended topics",             # 18
})

_HEADING_LINE = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")


def _trim_portal(body: str) -> str:
    """The landing page, cut at its first doc-portal block.

    Keeps the product overview and its Key New Features; drops the website
    furniture below. Over 778 landing pages this trims 688 and leaves 90 alone.

    **Cut at the block labels, not at "the section after Key New Features".** The
    obvious rule fails twice: 351 of the 778 have no Key New Features section at
    all and would go untrimmed, and 10 carry *genuine* feature subsections below it
    -- `Server Improvements`, `Governance & Security`, `Platform Support` -- which
    anchoring would delete. Cutting at a closed set of known labels keeps those,
    and over all 778 pages there is **no** page whose Key New Features section it
    removes.

    Read off the converted Markdown rather than the HTML, because in the HTML these
    labels are frequently not headings at all: `datasynapse`'s landing page has one
    `h1` and no `h2`, and Flare styles the block titles with classes. The Markdown
    is the form the rule is actually about.
    """
    lines = body.splitlines()
    for index, line in enumerate(lines):
        match = _HEADING_LINE.match(line)
        if match is None:
            continue
        label = re.sub(r"[^a-z0-9 ]+", "", match.group(1).lower()).strip()
        if label in PORTAL_BLOCKS:
            return "\n".join(lines[:index]).rstrip()
    return body


def _visible(body: str) -> str:
    """The body's text, minus its heading lines -- what the hero-only test counts."""
    return "".join(line for line in body.splitlines() if not line.startswith("#")).strip()


def _stem_label(stem: str) -> str:
    """A second TOC tree's name, from its file stem. `_HTML_gateway_server` -> ..."""
    name = stem.lstrip("_")
    if name.lower().startswith("html_"):
        name = name[5:]
    return " ".join(name.replace("_", " ").replace("-", " ").split()) or stem


__all__ = ["CONTENT_SELECTOR", "FlareEngine", "FlareRenderer", "autonum_label"]
