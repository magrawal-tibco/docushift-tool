"""The engine contract, and the document model the four engines produce.

Written in Phase 5a against *three* already-specified engines rather than against
the first one built, because the three disagree in ways a single-engine
generalization would miss. Flare recovers a callout's label from a
`data-mc-autonum` attribute the skin's CSS renders; DITA has the same label as a
`span` that must be *deleted* (`architecture.md` §5.1.8 vs §5.2.5). Flare mirrors
its source tree because filename stems collide 6.0% within one root; DITA is flat
because its doc-set has no hierarchy to mirror. WebWorks ships 3.5 books per
version where Flare ships 1.1 output roots. Anything the contract fixes that these
three do differently is a contract written against a coincidence.

So the contract fixes only what all of them share:

- **The engine names its own unit of work.** Output root, doc-set, book -- located
  by content and never by a configured path (`engines/roots.py`, already built).
- **A topic becomes a `Document`**, with *two* title strings, because all three
  engines have two and in all three they differ.
- **Navigation is a node list, not rendered YAML.** The engine reports the tree,
  the landing page and the support/legal tail; §10's three node rules are
  engine-neutral and are applied once, by `converter/navigation.py` (Phase 6a),
  which also decides how several units become one version's `toc.yml`.
- **A failure is a returned outcome, never an exception** -- the rule
  `PackageDownloader` and `PackageExtractor` already state, so all three stage
  drivers read alike.
"""

import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar
from urllib.parse import quote

from docushift.config import DEFAULT_LOCALE
from docushift.engines.roots import find_output_roots, root_locale, same_language
from docushift.models import SourceEngine
from docushift.reporting.findings import FindingsRun
from docushift.transforms import links
from docushift.transforms.assets import AssetCopier


@dataclass
class Document:
    """One converted topic: everything needed to write one Markdown file.

    Held rather than written as it is produced, so that CSH identifiers reach the
    topic's **first and only write** (`design.md` §9.5) instead of a second
    read-modify-write pass over the whole output tree.
    """

    # Absolute path of the HTML this came from. The key of the §9.3 output map.
    source: Path
    # Where it goes, relative to its unit's subtree in the output. Always `.md`.
    relative: PurePosixPath
    # The page title -- Flare's `h1`, DITA's `h1`/`DC.Title`, WebWorks' `files.js`
    # label. Not `<title>`, which is the truncated one in ~10% of Flare topics.
    title: str = ""
    # The navigation entry. Equal to `title` in 2,429 of 2,512 sampled Flare
    # topics; the rest are deliberate short labels, and both are kept.
    nav_label: str = ""
    body: str = ""
    # Anchors this topic defines, so a link into it can be checked without
    # re-parsing the Markdown.
    anchors: set[str] = field(default_factory=set)
    # CSH identifiers this topic owns (§9.5). Filled by `transforms/csh.py`
    # before the write, never after it.
    csh: list[str] = field(default_factory=list)
    # Extra frontmatter keys. `generated: true` marks a page the tool synthesized,
    # so a re-run replaces it rather than treating it as authored.
    frontmatter: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.nav_label:
            self.nav_label = self.title


@dataclass
class NavNode:
    """One navigation entry. A tree, not a rendered `toc.yml`."""

    label: str
    # None for a headless container -- Flare's `'___'` sentinel, 165 per 60 output
    # roots. `converter/navigation.py` generates a page for the 158 that have
    # children and drops the 7 that do not; the engine reports the fact.
    document: PurePosixPath | None = None
    # The bookmark within `document`, without its `#`. 12.1% of Flare's TOC entries
    # carry one and several entries routinely share a page; discarding it collapses
    # them onto one navigation target and loses the distinction the author drew.
    anchor: str = ""
    children: list["NavNode"] = field(default_factory=list)

    def walk(self) -> Iterator["NavNode"]:
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class Unit:
    """One unit of work, converted: a Flare output root, a DITA doc-set, a WebWorks book.

    `name` is the unit's subtree in the *output* -- `subtree_name(root)`, which is
    `""` for a lone output root and drops the source prefix for the rest (§5.1.3).
    It is **not** the unit's path relative to the extracted tree, and the two
    differ for most WebWorks versions; reading it as the latter is what put
    3,862 links in the wrong space (`planning.md` Phase 17a). `root` is the
    tree-side answer. That `name` is the output subtree is why the flat `csh.yml`
    can drop `doc_set` without loss (`architecture.md` §1576): the doc-set is
    already the first segment of every value.
    """

    root: Path
    name: str
    # What to call this unit where a version ships more than one -- 90.1% of
    # WebWorks versions, against 9.6% of Flare's. Filled by the engine and not
    # inferred by the synthesizer, because the engine is where the answer already
    # is: WebWorks has `books.xml`'s book title, DITA has the homepage's
    # `publication-title`, and a second guesser would drift from the first. Blank
    # where the engine has no name for it, which `converter/navigation.py` falls
    # back from rather than papers over -- the raw stem reads `tib_adas400_concepts`.
    title: str = ""
    documents: list[Document] = field(default_factory=list)
    nav: list[NavNode] = field(default_factory=list)
    # The version's landing page, which the synthesizer moves to first. Flare
    # resolves one in 676 of 676 roots; it is *absent* from the TOC in 55 of 60.
    landing: PurePosixPath | None = None
    # Support and legal, in that order, reported by name and never constanted --
    # the support heading is `TIBCO` in 565 roots, `ibi` in 49, `Spotfire` in 45.
    support: PurePosixPath | None = None
    legal: PurePosixPath | None = None
    # The What's New topic, which the synthesizer moves to *second* -- after the
    # landing page, which stays the entry point. Set only where the page says
    # something: 167 of 648 Flare roots ship the authoring template unfilled, and
    # those are not converted at all (`is_placeholder_whats_new`).
    whats_new: PurePosixPath | None = None
    # HTML the engine looked at and did not convert, with why. A count, not a
    # silence: `_globalpages/`, `Default.htm` stubs, framesets, generated indexes.
    skipped: dict[str, int] = field(default_factory=dict)
    # What the source says about itself, where it says anything: DITA's
    # `-homepage.html` carries `publication-title`, `release-version` and
    # `release-date` (§5.2.7). It does *not* become `metadata.yml`, whose keys AEM
    # fixed as `csg-*`; the driver reads it as a cross-check against the catalog and
    # a disagreement is a `METADATA_MISMATCH` line. Empty where the engine has no
    # such file, which invariant 11 makes a blank rather than a zero.
    metadata: dict[str, str] = field(default_factory=dict)

    def skip(self, reason: str, count: int = 1) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + count


def is_legal_label(label: str, path: str = "") -> bool:
    """Whether a nav node is the legal notice. Matched, never constanted.

    Lives here rather than in an engine because `Unit` has the slot and more than
    one engine has to fill it -- Phase 5c moved it out of `flare.py` the moment
    the second caller appeared, rather than growing a second spelling of one
    question. The `path` half is optional for the same reason DITA needs it to be:
    a Flare page is `legal_notices.htm` and a DITA topic is a GUID, so there the
    label is the only evidence.

    `copyrigh` earns its place from WebWorks, where the page is `copyrigh.htm` --
    truncated, so `copyright` would not match it -- and titled `Important
    Information` in 99 of 101 books. The title is the same boilerplate Flare files
    under `legal_notices.htm`: the licence, the trademarks and the third-party
    notices. Matching the title instead would take every topic a writer called
    `Important Information` with it, so the filename is the evidence used.

    **A legal notice, not a word** (Phase 36). Bare `third party` and bare `legal`
    are topic subjects, and the callers take the *first* match in TOC order, so
    either one hands the legal slot to a content topic that precedes the real page
    and moves it out of its chapter. Over the 953 Flare TOCs in the predecessor's
    cache the bare words did that in 65 roots -- `Third-Party Licenses for the
    Container Image`, `Required Third-Party Products`, `Using the ActiveSpaces JDBC
    Driver With Third-Party Tools` -- and `legal` alone also matches `Legal
    Characters`, `addLegal()` and `CLIENT.ILLEGAL_PUBLISH`. `legal` therefore needs
    `notice` or `third party` beside it; `third party notice` stands on its own.
    And `copyrigh` is read where the paragraph above says it is evidence -- the
    filename -- or at the very start of a label, since a DITA GUID has no name to
    read. Anywhere in a label it took `Customizing the Company Logo and Copyright`
    in 4 roots.
    """
    def fold(value: str) -> str:
        return value.lower().replace("-", " ").replace("_", " ").strip()

    name, title = fold(PurePosixPath(path).stem), fold(label)
    if "copyrigh" in name or title.startswith("copyright"):
        return True
    text = f"{title} {name}"
    if "third party notice" in text:
        return True
    return "legal" in text and ("notice" in text or "third party" in text)


def is_support_label(label: str, path: str = "") -> bool:
    """Whether a nav node is the support page. See `is_legal_label`.

    The heading is `TIBCO Documentation and Support Services` in 565 Flare roots,
    `ibi` in 49 and `Spotfire` in 45, which is why the brand is not in the test.
    """
    text = f"{label} {PurePosixPath(path).stem}".lower().replace("-", " ").replace("_", " ")
    return "support services" in text or "documentation and support" in text


def is_whats_new(path: str) -> bool:
    """Whether this file is the What's New topic. Matched on the stem, folded.

    The filename is not stable across the corpus -- `Whats-New.htm` dominates, with
    `Whats-New.html` (12), `What_s-New.htm` (9), `Whats_New.htm` (6) and
    `What's-New.htm` (5) behind it -- so every separator and apostrophe is removed
    before the comparison and the four spellings become one.

    The per-component variants are deliberately **not** matched: `Whats-New-old.htm`
    (5), `-client` (4) and `-server` (4) fold to `whatsnewold` and friends. Which of
    a pair is the version's What's New is a judgement the filename does not settle,
    and promoting the wrong one to second in the navigation is worse than leaving
    both where the source TOC put them.
    """
    return re.sub(r"[^a-z0-9]+", "", PurePosixPath(path).stem.lower()) == "whatsnew"


_BRACKETED = re.compile(r"\[[^\]]*\]")
_NAVIGATION_CHROME = re.compile(r"open topic with navigation", re.I)
_WHATS_NEW_HEADING = re.compile(r"^\s*what\W*s\s+new\b", re.I)


def is_placeholder_whats_new(text: str) -> bool:
    """Whether a What's New page is still the unfilled authoring template.

    167 of 648 Flare roots ship it as written by MadCap, its whole body a set of
    bracketed instructions to the author: *"[Provide list of update made to the
    product documentation...] [Feature Name] [Use sections with h2 styles...]"*.
    Publishing that as the first topic a reader meets is worse than publishing no
    What's New at all.

    `text` is the main content. Drop every `[...]` span, the navigation chrome, and
    the leading heading; strip all non-alphanumerics; a page with nothing left said
    nothing.

    **There is no threshold here, and that is the point.** Across 654 files the
    residue is 0 for 167 and 60+ for 467, with twenty between 20 and 59 and
    **nothing at all between 1 and 19**. The twenty in the middle are genuine short
    releases -- "No new features have been added in this release." -- and a cutoff
    picked anywhere in that gap behaves identically, which is what makes `== 0`
    trustworthy rather than tuned. Of the 167, five have empty main content and 162
    are the stub.
    """
    residue = _BRACKETED.sub(" ", text)
    residue = _NAVIGATION_CHROME.sub(" ", residue)
    residue = _WHATS_NEW_HEADING.sub("", residue.strip())
    return not re.sub(r"[^a-z0-9]+", "", residue.lower())


@dataclass
class ConversionContext:
    """What an engine is given. Everything an engine may not work out for itself.

    `api_roots` in particular is *read back* from `version_metadata`, where Stage 4
    recorded it -- never re-walked. §6.3 is explicit that Stages 4, 5 and 7 share
    one recorded answer, and a second walk here could disagree with the counts
    already written into `versions.csv`.
    """

    tree: Path
    output: Path
    engine: SourceEngine
    slug: str = ""
    version: str = ""
    # The catalog's display name. The last fallback for a page title, used where a
    # landing page has neither an `h1` nor a product variable -- which is 22 of the
    # corpus's 676 Flare roots, and inventing a title there would be worse.
    product_name: str = ""
    api_roots: list[Path] = field(default_factory=list)
    # Each of those roots paired with the URL its content is published at, from
    # `sync/apirefs.url_map` (6e). Empty for a version with no API tree, for a
    # non-primary locale, and in any test that does not pass one -- and empty means
    # the rewrite does not fire, not that it fires with a broken address.
    api_urls: dict[Path, str] = field(default_factory=dict)
    output_roots: list[Path] = field(default_factory=list)
    # Each unit's output subtree name, from `roots.subtree_names`. Set by the
    # driver once the unit list is in hand, because a unit's name depends on how
    # many units the version has -- a lone root publishes at the version root.
    # Empty until then, and `subtree_name` falls back to the tree-relative path,
    # which is both the old behaviour and the right answer for a single unit whose
    # root *is* the tree.
    subtrees: dict[Path, str] = field(default_factory=dict)
    # The run's locale. A unit root named for another language is a localized
    # build and is not converted into this locale's tree (Phase 34, R5-01).
    locale: str = DEFAULT_LOCALE
    # Roots that were located and deliberately not converted -- a localized build
    # (R5-01), another engine's unit of work (R4-02) -- so that nothing else
    # converts their files or resolves their help identifiers into this version:
    # Flare skips their files inside its own root, and the driver drops their CSH
    # sources, which would otherwise be reported unresolved one at a time.
    excluded_roots: list[Path] = field(default_factory=list)
    findings: FindingsRun | None = None
    # The copier for the unit currently being converted, set by the driver before
    # each `convert_unit`. Per-unit state on a per-version object, and deliberately:
    # invariant 13 says the link and the copy come out of the same call, so the
    # engine has to resolve *while* it emits -- but if the engine constructed its
    # own copier it would also be deriving the destination, which is the driver's
    # answer and must not exist twice.
    assets: AssetCopier | None = None
    # How many links this version's conversion sent into the `-resources` tree.
    # Counted rather than recorded one by one: nobody acts on a single rewritten
    # link and everybody wants the magnitude, so the driver reports one note per
    # version at the end (§7.1).
    api_links: int = 0
    # How many links this version's conversion flattened into a code fence, which
    # GFM will not let hold a link (Phase 8). Accumulated from each renderer after
    # its walk and reported as one note per version, for `api_links`' reason and
    # one more: it is the residue the code-span fix deliberately does not take, and
    # a residue nobody counts is the silence the fix exists to end.
    flattened_links: int = 0
    # Phase 27, and counted for `flattened_links`' reason: both are structural
    # repairs to what the author wrote, nobody acts on a single one of them, and a
    # rewrite with no magnitude attached is unfalsifiable on the next corpus.
    # How many headings this version's pages had renumbered to close a skipped
    # level, and how many definition terms were recovered from `class="dt"`.
    renumbered_headings: int = 0
    recovered_terms: int = 0
    # Embedded media the shared walk has no Markdown for, by tag (Phase 34,
    # R8-13). Accumulated from each renderer for `flattened_links`' reason: an
    # element reduced to its fallback text, or to nothing, was a loss nobody
    # counted.
    unrendered: Counter[str] = field(default_factory=Counter)

    def subtree_name(self, root: Path) -> str:
        """Where this unit's output goes, relative to the version folder.

        The one definition, read by all four engines *and* by the driver's asset
        copier. Two of them would be two answers, and two answers here put a
        topic's pages and that topic's images in different subtrees -- every image
        on the version 404s and nothing reports it, because each half is
        internally consistent.

        Once the lookup is set, a root it does not hold is refused rather than
        answered with `""` (Phase 34, R4-14): `""` is the version root, so an engine
        that derived a unit root differently from the list it returned would have
        written that unit's pages and images over it without a word. Raised, and
        the driver turns any exception into a `failed` version.
        """
        if self.subtrees:
            if root not in self.subtrees:
                raise ValueError(f"{root} is not a unit of this version")
            return self.subtrees[root]
        try:
            return root.relative_to(self.tree).as_posix() if root != self.tree else ""
        except ValueError:  # pragma: no cover - a root outside its own tree
            return root.name

    def api_url(self, source: Path, path: str, fragment: str = "") -> str | None:
        """The published URL for a reference into an API tree, or `None`.

        The one thing conversion is *told* about the publishing layout rather than
        deriving. §10.7 assigned this rewrite to Stage 7 because "conversion does
        not know where things get published", which remains true: the driver hands
        over a resolved map, exactly as it already hands over `api_roots` rather
        than letting an engine walk for them.

        `None` for anything that is not a file inside a published API tree --
        including a path that *looks* like one but is not on disk. That is
        `apiref.py`'s rule applied to the link side: a marker decides and a name
        never does. Emitting a URL for a page the copy will not contain would trade
        a reported dangling link for a silent 404.
        """
        if not self.api_urls:
            return None
        absolute = Path(os.path.normpath(source.parent / path))
        # Deepest first: nothing in the corpus nests one API root inside another,
        # but the shallower root would win the containment test if one ever did.
        for root, url in sorted(self.api_urls.items(), key=lambda item: -len(item[0].parts)):
            if absolute != root and not absolute.is_relative_to(root):
                continue
            if not absolute.exists():
                return None
            tail = absolute.relative_to(root).as_posix()
            target = f"{url}/{links.encode(tail)}" if tail != "." else url
            self.api_links += 1
            return f"{target}#{quote(fragment, safe='')}" if fragment else target
        return None

    def record(self, code: str, path: str = "", message: str = "", count: int = 1) -> None:
        """Records a finding against this version, or does nothing without a run."""
        if self.findings is not None:
            self.findings.record(
                code, slug=self.slug, version=self.version,
                path=path, message=message, count=count,
            )


class BaseEngine(ABC):
    """What every converter engine implements.

    Two methods, because the corpus says there are two questions: *what are the
    units of work in this tree*, and *what does one unit convert to*. The default
    answer to the first is `engines/roots.find_output_roots`, which Phase 4b-1
    already built and whose answers Stage 4 already recorded -- an engine overrides
    it only where its unit is not an output root.
    """

    engine: ClassVar[SourceEngine]
    # Whether an API-reference tree inside a unit is skipped. True everywhere so
    # far; it is a class attribute rather than a constant so that the one shared
    # `is_api_reference()` predicate stays the only thing that decides *which*
    # trees, and this stays the only thing that decides *whether*.
    skips_api_references: ClassVar[bool] = True

    def units(self, context: ConversionContext) -> list[Path]:
        """The units of work in this tree, outermost first, localized builds left out."""
        roots = list(context.output_roots) or find_output_roots(context.tree, self.engine)
        return _without_localized(context, roots)

    @abstractmethod
    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        """Converts one unit. Never raises -- a failure is a reported outcome."""


def _without_localized(context: ConversionContext, roots: list[Path]) -> list[Path]:
    """Leaves out every root that is a build for another language, and names each.

    Phase 34 (R5-01). A localized Flare build is an output root in its own right
    -- 24 of them in the corpus, `ja-jp` alone converting 2,779 Japanese topics
    of `wf-wf/9.3.5` into the English tree -- and the old guard only looked at the
    first segment *inside* a root. Skipped and reported rather than converted:
    publishing them belongs to the `loc-` tree, a later phase.

    A root nested inside a skipped one goes with it, so that `sfire-dsc/7.1.0`'s
    `doc/html/ja` cannot come back through a sub-root. The skipped roots stay in
    `context.output_roots`, which is what keeps an outer root from claiming
    their files as its own.
    """
    skipped: list[Path] = []
    kept: list[Path] = []
    for root in roots:
        tag = root_locale(root)
        inside = next((other for other in skipped if other in root.parents), None)
        if inside is None and (not tag or same_language(tag, context.locale)):
            kept.append(root)
            continue
        skipped.append(root)
        relative = _relative_to(context.tree, root)
        context.record(
            "LOCALIZED_ROOT_SKIPPED", path=relative,
            message=(f"output root for locale {tag!r} not converted into the {context.locale} tree"
                     if inside is None else
                     f"output root inside the localized root {_relative_to(context.tree, inside)}"),
        )
    context.excluded_roots.extend(skipped)
    return kept


def _relative_to(tree: Path, path: Path) -> str:
    try:
        return path.relative_to(tree).as_posix()
    except ValueError:  # pragma: no cover - a root outside its own tree
        return path.name


# -- the registry -------------------------------------------------------------
#
# An empty registry is a valid state, and in Phase 5a it was the *only* state. That
# is why dispatch tests "is a handler registered" rather than "is the engine in
# `CONVERTIBLE_ENGINES`": an engine that is convertible-by-policy and unwritten, and
# any engine at all in 5a, take the same path and produce the same `ENGINE_UNKNOWN`
# finding, instead of two ways of saying "nothing happened". All four convertible
# engines are written as of Phase 5e, so the registry is now full -- and the test
# still has to pass with it empty, because that is what a fifth one starts as.

_REGISTRY: dict[SourceEngine, type[BaseEngine]] = {}


def register(engine_cls: type[BaseEngine]) -> type[BaseEngine]:
    """Registers a handler. Usable as a decorator on the engine class."""
    _REGISTRY[engine_cls.engine] = engine_cls
    return engine_cls


def unregister(engine: SourceEngine) -> None:
    """Removes a handler. Exists for tests that register a fake one."""
    _REGISTRY.pop(engine, None)


def engine_for(engine: SourceEngine) -> type[BaseEngine] | None:
    """The registered handler, or None -- which is `ENGINE_UNKNOWN`, not an error."""
    return _REGISTRY.get(engine)


def registered_engines() -> list[SourceEngine]:
    return sorted(_REGISTRY, key=str)
