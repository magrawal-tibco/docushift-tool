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
  engine-neutral and are applied once, by the synthesizer, in Phase 6.
- **A failure is a returned outcome, never an exception** -- the rule
  `PackageDownloader` and `PackageExtractor` already state, so all three stage
  drivers read alike.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

from docushift.engines.roots import find_output_roots
from docushift.models import SourceEngine
from docushift.reporting.findings import FindingsRun
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
    # roots. Phase 6 generates a page for the 158 that have children and drops the
    # 7 that do not; the engine reports the fact rather than deciding.
    document: PurePosixPath | None = None
    children: list["NavNode"] = field(default_factory=list)

    def walk(self) -> Iterator["NavNode"]:
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class Unit:
    """One unit of work, converted: a Flare output root, a DITA doc-set, a WebWorks book.

    `name` is the unit's path relative to the extracted tree, and it becomes the
    unit's subtree in the output -- which is why the flat `csh.yml` can drop
    `doc_set` without loss (`architecture.md` §1576): the doc-set is already the
    first segment of every value.
    """

    root: Path
    name: str
    documents: list[Document] = field(default_factory=list)
    nav: list[NavNode] = field(default_factory=list)
    # The version's landing page, which Phase 6 moves to first. Flare resolves one
    # in 676 of 676 roots and it is *absent* from the TOC in 55 of 60 sampled.
    landing: PurePosixPath | None = None
    # Support and legal, in that order, reported by name and never constanted --
    # the support heading is `TIBCO` in 565 roots, `ibi` in 49, `Spotfire` in 45.
    support: PurePosixPath | None = None
    legal: PurePosixPath | None = None
    # HTML the engine looked at and did not convert, with why. A count, not a
    # silence: `_globalpages/`, `Default.htm` stubs, framesets, generated indexes.
    skipped: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str, count: int = 1) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + count


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
    api_roots: list[Path] = field(default_factory=list)
    output_roots: list[Path] = field(default_factory=list)
    findings: FindingsRun | None = None
    # The copier for the unit currently being converted, set by the driver before
    # each `convert_unit`. Per-unit state on a per-version object, and deliberately:
    # invariant 13 says the link and the copy come out of the same call, so the
    # engine has to resolve *while* it emits -- but if the engine constructed its
    # own copier it would also be deriving the destination, which is the driver's
    # answer and must not exist twice.
    assets: AssetCopier | None = None

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
        """The units of work in this tree, outermost first."""
        if context.output_roots:
            return list(context.output_roots)
        return find_output_roots(context.tree, self.engine)

    @abstractmethod
    def convert_unit(self, context: ConversionContext, root: Path) -> Unit:
        """Converts one unit. Never raises -- a failure is a reported outcome."""


# -- the registry -------------------------------------------------------------
#
# An empty registry is a valid state, and in Phase 5a it is the *only* state. That
# is why dispatch tests "is a handler registered" rather than "is the engine in
# `CONVERTIBLE_ENGINES`": `docbook`, which is convertible-by-policy and unwritten,
# and any engine at all in 5a take the same path and produce the same
# `ENGINE_UNKNOWN` finding, instead of two ways of saying "nothing happened".

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
