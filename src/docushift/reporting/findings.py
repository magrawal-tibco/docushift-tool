"""The findings register: every deferred "report line" in the design, given a code.

Implements `docs/planning.md` §7.1, §7.2 and §7.5. Three rules carry the whole
design, and each of them is a rule about where a decision is *not* made:

- **`code` is the contract; `message` is prose.** Tests assert on codes, so a
  message can be reworded freely and an obligation that existed only as an English
  sentence becomes an enumerable thing.
- **Severity belongs to the code, not to the call site.** It is fixed once, in
  `REGISTRY` below. Two call sites reporting one condition at two severities would
  make the exit code depend on which of them fired.
- **Errors and warnings get a row each; notes are aggregated with a `count`.** You
  act on an error individually and only need the magnitude of a note -- and a
  per-file note would write hundreds of thousands of rows for `ASSET_ORPHANED`
  alone, which is 54.6% of Flare's images by design of the authoring tool.

The module is deliberately small and knows nothing about any stage. It was owed at
the start of Phase 4 (§7.7) and arrived in Phase 5a; the cost of that slip is
recorded in §7.7 rather than tidied away.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from docushift.state import StateStore


class Severity(StrEnum):
    """`planning.md` §7.2. Only `validate` gates, and only on `ERROR`."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


class Stage(StrEnum):
    """Which command discovers the condition. Not which one reports it."""

    CATALOG = "catalog"
    DOWNLOAD = "download"
    EXTRACT = "extract"
    CONVERT = "convert"
    REFRAME = "reframe"
    SYNC = "sync"
    VALIDATE = "validate"


@dataclass(frozen=True)
class Code:
    """One row of the §7.5 register."""

    code: str
    severity: Severity
    stage: Stage
    obligation: str
    # Where the promise was made. Kept so `report --explain` can cite the spec
    # rather than paraphrase it.
    specified_in: str


def _codes(*rows: Code) -> dict[str, Code]:
    registry: dict[str, Code] = {}
    for row in rows:
        if row.code in registry:  # pragma: no cover - a typo caught at import time
            raise ValueError(f"Duplicate finding code: {row.code}")
        registry[row.code] = row
    return registry


# The §7.5 register, in full, on the first commit that has a table to put it in.
# All twenty rows are here although Phase 5a can only reach three of them: the
# register is the deliverable, and a half-populated one cannot be audited. The
# test that asserts "every emitted code is registered and every registered code is
# reachable" names the unreachable ones rather than failing, so this stays a
# visible to-do list instead of a silent one.
REGISTRY: dict[str, Code] = _codes(
    Code("SCOPE_RULE_UNMATCHED", Severity.WARNING, Stage.CATALOG,
         "A scope.yaml rule matching no product", "design.md §8.2.5"),
    Code("EOS_ALIAS_STALE", Severity.WARNING, Stage.CATALOG,
         "An alias naming a product the active report lacks", "design.md §8.2"),
    Code("EOS_PRODUCT_EMPTIED", Severity.WARNING, Stage.CATALOG,
         "Retirement left a product with nothing to convert", "planning.md Phase 3.7"),
    Code("BATCH_NOT_ELIGIBLE", Severity.WARNING, Stage.CATALOG,
         "Tagged into a batch but not eligible", "design.md §8.2.2"),
    # Phase 25. A warning, not an error: 104 sheet slugs match nothing today and
    # the tool works perfectly well without them -- those rows simply carry no
    # verdict. But 91 of their rows say `Migrate`, so silence here would be a
    # request nobody ever sees. Cleared one alias at a time in
    # `docsite-migration.yaml`, exactly as the eos aliases were.
    Code("MIGRATE_SHEET_SLUG_UNMATCHED", Severity.WARNING, Stage.CATALOG,
         "A migration-sheet slug matching no catalogued product", "planning.md Phase 25"),
    Code("MIGRATE_ALIAS_STALE", Severity.WARNING, Stage.CATALOG,
         "An alias naming a slug the active export lacks", "planning.md Phase 25"),
    # The conflict the phase exists to surface: a verdict and an eligibility flag
    # that disagree. Deliberately a warning on the *version* rather than anything
    # blocking -- resolving it is a human's call, and 376 rows carry it today
    # (458 on the first apply; 94 were hand-resolved the same day).
    Code("MIGRATE_DECISION_CONFLICT", Severity.WARNING, Stage.CATALOG,
         "migrate_decision disagrees with convert_eligible", "planning.md Phase 25"),
    # Phase 14a, and the register's first `download` row -- the stage had never
    # had one, because until the template was corrected the stage had never run.
    # A warning rather than an error: 7 of 35 sampled products publish their
    # package under a directory segment no pattern predicts (`1.0.0_october_2004`
    # for version `1.0`), and `download --from-file` exists for exactly that.
    # Gating on a condition whose remedy is a hand-supplied file would stop a
    # 200-version batch over a known, bounded residue.
    Code("ZIP_URL_UNRESOLVED", Severity.WARNING, Stage.DOWNLOAD,
         "No ZIP endpoint could be derived for an active version; supply it with "
         "download --from-file", "planning.md Phase 14a"),
    Code("CSH_SOURCE_EMPTY", Severity.NOTE, Stage.EXTRACT,
         "CSH source present but empty -- no csh.yml written", "architecture.md §5.4.2"),
    Code("CSH_SOURCE_UNPARSED", Severity.WARNING, Stage.EXTRACT,
         "Source located but failed to parse; _has_csh still set", "design.md §6.2"),
    # Phase 34 (R3-04). A partial walk already wrote no columns; what it did not
    # do was say so, or clear the previous package's counts, so the row read as
    # measured. A warning: the tree is on disk and converts, but its footprint is
    # unknown until a re-run reads every directory.
    Code("INVENTORY_PARTIAL", Severity.WARNING, Stage.EXTRACT,
         "A directory in the extracted tree could not be read; the inventory columns "
         "were left blank", "design.md §6.1"),
    Code("ENGINE_UNKNOWN", Severity.WARNING, Stage.CONVERT,
         "auto, or a named engine with no handler -- skipped, not guessed",
         "design.md invariant 7"),
    Code("DOCSET_SKIPPED", Severity.WARNING, Stage.CONVERT,
         "A file-named doc-set reaching the engine guard", "architecture.md §5.2"),
    Code("NAV_NODE_DROPPED", Severity.NOTE, Stage.CONVERT,
         "A navigation node with no page and no children -- DITA's lof/lot/ix, "
         "Flare's childless headless node -- or a Flare/WebWorks child repeating "
         "its parent's page with no bookmark of its own",
         "planning.md Phase 5"),
    Code("OUTPUT_ROOT_MISSING", Severity.WARNING, Stage.CONVERT,
         "Engine detected and no unit of work found -- a partial output",
         "architecture.md §5.1.1"),
    Code("CONTENT_MISSING", Severity.WARNING, Stage.CONVERT,
         "A topic with no content container -- not converted, never guessed at",
         "architecture.md §5.1.6"),
    Code("CONTENT_BODY_FALLBACK", Severity.NOTE, Stage.CONVERT,
         "A Flare root whose skin writes no content container: its MadCap topics "
         "were converted from <body>, reported once per root",
         "Phase 34 (R5-09)"),
    Code("CONTENT_SOURCE_TOPIC", Severity.NOTE, Stage.CONVERT,
         "A Flare root shipping authored source topics: each converted from <body>, "
         "its variables and conditions settled from the root's built topics, "
         "reported once per root",
         "Phase 41"),
    Code("TOC_UNREADABLE", Severity.WARNING, Stage.CONVERT,
         "A Flare root's HelpSystem.xml or declared TOC is missing or did not parse, "
         "or a WebWorks book's runtime file (files.js, toc.js, title.js, context.js) "
         "is present and could not be read or yields nothing; its topics are filed "
         "under an Unfiled node, or the book loses what that file named",
         "Phase 34 (R5-12, R7-09)"),
    Code("TOC_SUBPROJECT_UNPLACED", Severity.NOTE, Stage.CONVERT,
         "A merged-project TOC node (*.flprj) marking where a sub-project's TOC "
         "goes; the node is dropped and the sub-guide loses its place",
         "Phase 34 (R5-11)"),
    Code("TOC_ORPHAN", Severity.NOTE, Stage.CONVERT,
         "Converted topics in no TOC entry, kept out of toc.yml and unmerged under "
         "unfiled/ -- 5.9% for Flare; left in an Unfiled node only when the version "
         "has no other TOC entry",
         "architecture.md §5.1.4, Phase 43"),
    Code("TOPIC_LINK_DANGLING", Severity.NOTE, Stage.CONVERT,
         "A cross-reference to a topic this run did not produce; text kept, link dropped",
         "architecture.md §5.1.3"),
    Code("ALERT_LABEL_UNMAPPED", Severity.WARNING, Stage.CONVERT,
         "An admonition label outside the five GitHub renders; rendered as NOTE",
         "transforms/callouts.py"),
    Code("ANCHOR_DROPPED", Severity.WARNING, Stage.CONVERT,
         "A referenced anchor the engine kept and then did not emit; its links now dangle",
         "planning.md Phase 19"),
    Code("LANDING_PAGE_EMPTY", Severity.NOTE, Stage.CONVERT,
         "A landing page with nothing past its hero -- a stub was generated",
         "architecture.md §5.1.5"),
    Code("WHATS_NEW_PLACEHOLDER", Severity.NOTE, Stage.CONVERT,
         "A What's New page still holding the unfilled authoring template; not published",
         "planning.md Phase 11a"),
    Code("TAIL_PAGE_MISSING", Severity.WARNING, Stage.CONVERT,
         "No support or no legal page in the TOC -- nothing is synthesized",
         "architecture.md §5.1.5"),
    # Phase 34 (R4-02). One engine converts a version; a unit of work another
    # convertible engine owns used to be fed to the first engine page by page, or
    # never looked at. A warning with a row each, because each is a book that
    # publishes nowhere until two-engine conversion exists.
    Code("ENGINE_ROOT_UNCONVERTED", Severity.WARNING, Stage.CONVERT,
         "A unit of work for a second convertible engine, in a version converted "
         "by another; not converted", "Phase 34 (R4-02)"),
    Code("LOCALIZED_TREE_SKIPPED", Severity.NOTE, Stage.CONVERT,
         "A localized subtree inside an English unit, not converted",
         "architecture.md §5.1.9"),
    # Phase 34 (R5-01). A whole output root built for another language, which the
    # subtree note above never saw: 24 in the corpus, converted into the English
    # tree. A warning with a row each, because each names a build that publishes
    # nowhere until the `loc-` tree exists -- a note would fold them into one line.
    Code("LOCALIZED_ROOT_SKIPPED", Severity.WARNING, Stage.CONVERT,
         "An output root built for another locale, not converted into this locale's tree",
         "Phase 34 (R5-01)"),
    Code("ASSET_ORPHANED", Severity.NOTE, Stage.CONVERT,
         "Unreferenced asset -- 54.6% is normal for Flare", "architecture.md §5.5.7"),
    Code("REFERENCE_UNRESOLVED", Severity.ERROR, Stage.CONVERT,
         "A reference producing neither link nor copy", "design.md invariant 13"),
    Code("REFERENCE_PAGE_SEGMENT_DROPPED", Severity.NOTE, Stage.CONVERT,
         "A reference naming a page as a folder (`a.htm/b.png`), resolved without that segment",
         "planning.md Phase 47"),
    Code("CSH_UNRESOLVED", Severity.WARNING, Stage.CONVERT,
         "Identifier matched no produced topic", "planning.md Phase 6 contract"),
    Code("CSH_AMBIGUOUS", Severity.NOTE, Stage.CONVERT,
         "Identifier claimed by 2+ doc-sets; first ordered doc-set wins",
         "planning.md Phase 6 contract"),
    Code("DOC_REFERENCE_MISSING", Severity.WARNING, Stage.SYNC,
         "Escape pointing at a document the ZIP never shipped", "architecture.md §5.5.8"),
    Code("VERSION_NOT_NUMERIC", Severity.WARNING, Stage.SYNC,
         "Non-numeric version string sorted last in version.yml",
         "planning.md Phase 6 contract"),
    Code("VERSION_UNDATED", Severity.NOTE, Stage.SYNC,
         "Active version with no release_date; title loses its bracket",
         "planning.md Phase 6 contract"),
    # CONVERT rather than SYNC, corrected in 6a: the homepage figures live in
    # `Unit.metadata`, which exists only while the engine's unit is in hand, so
    # conversion is the stage that *discovers* the disagreement even though the
    # keys it used to feed belong to sync's `metadata.yml`.
    Code("METADATA_MISMATCH", Severity.WARNING, Stage.CONVERT,
         "SuiteHelp release-version / release-date disagreeing with the catalog",
         "planning.md Phase 6 contract"),
    # 6c's one new code, and the only one this phase needed. A note rather than a
    # warning: the file is published and titled from its filename, so nothing is
    # lost -- but a damaged deliverable that nobody names is shipped silently. It
    # earns a code by being rare: 7 of the corpus's 5,007 PDFs, in 4 filenames. A
    # *blank* `/Title` is deliberately not reported at all; 27.9% of the corpus is
    # blank, and a note firing 1,396 times describes the corpus, not a defect.
    Code("DOCUMENT_UNREADABLE", Severity.NOTE, Stage.SYNC,
         "PDF whose Info dictionary would not parse; titled from its filename",
         "design.md §10.5"),
    # 6d's one new code, and the first one whose condition is a *configuration*
    # rather than a document. Raised once per version that places an api-reference
    # tree while `publish_base_url` is empty: the copy is published, but the help
    # topics that point into it keep relative links that cannot span two
    # repositories. A warning rather than an error because empty is the shipped,
    # supported state -- the AEM host is not known yet -- and rather than a note
    # because it is a human decision pending, not a property of the corpus.
    Code("PUBLISH_BASE_URL_UNSET", Severity.WARNING, Stage.SYNC,
         "api-references placed with no publish_base_url; cross-tree links have no host",
         "architecture.md §6.4"),
    # Phase 15d, and `sync`'s first `error`. An **error** rather than a warning,
    # against the precedent `ZIP_URL_UNRESOLVED` set three phases of a day
    # earlier: that one has a remedy a user can apply at run time
    # (`download --from-file`) and this one has none, nothing downstream can read
    # what would have been written, and a partially copied API tree published as
    # though it were whole is the failure this register exists to make loud.
    # It outlives the wrapper-directory fix that removes its only known
    # occurrence: the ceiling is a property of the target filesystem and of the
    # publishing root the user picks, and a deeper root puts other products over
    # the line with no wrapper involved.
    Code("PUBLISHED_PATH_TOO_LONG", Severity.ERROR, Stage.SYNC,
         "a file's published path exceeds 260 characters; the tree was not copied",
         "planning.md Phase 15d"),
    # 6e's one new code, and a note for the reason 6c's is: nobody acts on one
    # rewritten link and everybody wants the magnitude. Notes aggregate into a
    # single row with a count (§7.1), which is the shape this needs -- because the
    # failure it guards against is silent. A version with an API tree and **zero**
    # rewritten links is either a product whose help genuinely never references its
    # API (8 of the 49 in-scope versions) or a predicate that stopped matching, and
    # a count of 0 is the only thing that tells those apart.
    Code("API_LINK_REWRITTEN", Severity.NOTE, Stage.CONVERT,
         "Link into an api-reference tree pointed at its published -resources URL",
         "design.md §10.7"),
    # Phase 8's one new code. The phase taught the walk to keep the links inside a
    # code *span*; a code *fence* is a different matter, because GFM gives it no
    # way to hold a link at all -- the only alternative is emitting the whole block
    # as HTML, which trades a copy-pasteable code block for a decorative type
    # cross-reference in a C signature. Measured over all 13 in-scope products:
    # 4,964 of 13,126 swallowed references are inside a `<pre>`.
    #
    # A note, because nobody acts on one of them and the residue is a magnitude.
    # It exists at all because the defect this phase fixed was invisible for six
    # phases -- the reference was never classified, so no dangling link was raised
    # either -- and leaving a remainder behind with the same silence would repeat
    # exactly the mistake the phase was called to correct.
    Code("CODE_LINK_FLATTENED", Severity.NOTE, Stage.CONVERT,
         "Link inside a code block kept its words and lost its target; a GFM fence "
         "cannot hold a link",
         "planning.md Phase 8"),
    # Phase 34 (R8-13), a note for `CODE_LINK_FLATTENED`'s reason: a magnitude per
    # version, by tag. An `<iframe>` of a video reached the output as nothing and
    # nobody was told; none turned up in the five families measured, so this is
    # the count that says whether one ever does.
    Code("ELEMENT_UNRENDERED", Severity.NOTE, Stage.CONVERT,
         "Embedded media with no Markdown form (iframe, video, svg ...); an absolute "
         "URL became a link, anything else kept only its fallback text",
         "Phase 34 (R8-13)"),
    # Phase 27's two, both notes and both for `CODE_LINK_FLATTENED`'s reason: they
    # are magnitudes, not incidents. Nobody opens a ticket about one renumbered
    # heading -- but a structural rewrite of somebody else's document with no
    # number attached cannot be checked against the next corpus, and both of these
    # were invisible until a reader found them in published output.
    #
    # A note and *not* a warning, deliberately, even though each one means the
    # source was malformed. 612 of 24,781 pages skip a heading level; a warning
    # would fire on 2.5% of every convert run forever, on a fault the authoring
    # team has no plan to fix and the tool has just finished repairing.
    # Phase 30's pair, and they are two halves of one measurement. The platform
    # generates anchors from heading text and ignores `<a id>`, so every
    # cross-reference the converter emitted pointed at something that would
    # never exist: 5,670 of 5,670 on one Streaming version, ~50,000 published.
    # The first counts what was repaired, the second what could not be.
    Code("FRAGMENT_RETARGETED", Severity.NOTE, Stage.CONVERT,
         "Cross-references pointed at a heading instead of an inert anchor marker "
         "the platform does not honour",
         "planning.md Phase 30"),
    # A warning rather than an error: the link still goes to the right *page*,
    # and the remedy is a heading the source does not have -- which is an
    # authoring decision this tool may name and must not make.
    Code("FRAGMENT_UNPLACEABLE", Severity.WARNING, Stage.CONVERT,
         "A cross-reference naming an anchor with no heading behind it; left as "
         "written and will not resolve",
         "planning.md Phase 30"),
    Code("HEADING_LEVEL_NORMALIZED", Severity.NOTE, Stage.CONVERT,
         "Headings renumbered to close a level the source skipped; depth and order "
         "are unchanged",
         "planning.md Phase 27"),
    Code("DEFINITION_TERM_RECOVERED", Severity.NOTE, Stage.CONVERT,
         "Definition terms marked up as class=\"dt\" rather than <dt>, retagged so "
         "they publish as terms instead of as prose",
         "planning.md Phase 27"),
    # Phase 13's one new code, and it exists because the failure has already
    # shipped once: 7b found `navigation._free` comparing a generated container
    # page's path case-sensitively, so on Windows the page was written *over* a
    # converted topic and three versions published with content silently replaced.
    # Counting the output tree turns that class of defect into arithmetic -- the
    # engines reported N documents, the disk holds fewer -- which is the only
    # way a write landing on another write is visible from outside the run.
    Code("OUTPUT_COUNT_MISMATCH", Severity.WARNING, Stage.CONVERT,
         "Fewer Markdown files on disk than documents converted; two writes "
         "resolved to one path",
         "planning.md Phase 13"),
    # Phase 20a's two codes, both about the stage refusing to guess.
    #
    # A TOC whose shape has no adapter is an **error** rather than a skip. Reframe
    # rebuilds `toc.yml` from the tree it parsed, so a shape it half-understands
    # does not produce a worse merge -- it produces a merge that silently loses
    # whichever branch the parser did not recognise, and the page count looks
    # plausible either way. The one doc set measured (EMS 10.5.1, 1,441 paths) is
    # `items`/`title`/`path`/`children`; the second set is the risk, and this is
    # the code that makes it arrive as a failure instead of a quiet shortfall.
    Code("REFRAME_TOC_SCHEMA_UNKNOWN", Severity.ERROR, Stage.REFRAME,
         "No TOC adapter matches this version's toc.yml; refusing to merge a tree "
         "that was only partly understood",
         "REFRAME-INTEGRATION-PLAN.md §4 Phase 0"),
    # R1.4. A note since Phase 42: an unpinned multi-version doc set is now pinned
    # automatically to its newest eligible version, so the versions stay diffable.
    # What is left to say is that the pin is the tool's choice, and a newer
    # version arriving will re-cut the older ones until a writer freezes it.
    Code("REFRAME_LAYOUT_UNPINNED", Severity.NOTE, Stage.REFRAME,
         "More than one eligible version of this doc set and no pin in reframe.yaml; "
         "laid out on the newest eligible version, chosen automatically",
         "REFRAME-REQUIREMENTS.md R1.4"),
    # The other half of R1.4, and an error where the one above is a warning. There
    # the pin is missing and the stage has no instruction; here it has one and
    # cannot carry it out, so the only alternatives are to refuse or to pack the
    # version unpinned. Refusing, because an unpinned fallback writes a tree that
    # looks merged, passes the audit, and has boundaries nothing else in the set
    # shares -- the exact drift the pin exists to prevent, arrived at silently.
    Code("REFRAME_PIN_UNAVAILABLE", Severity.ERROR, Stage.REFRAME,
         "The version named by pin_layout_to cannot be laid out, so the versions "
         "pinned to it are refused rather than merged on their own boundaries",
         "REFRAME-REQUIREMENTS.md R1.4"),
    # 20e. A writer's decision that silently did nothing looks exactly like a
    # writer's decision that was applied, which is the one way this file can be
    # wrong without anybody finding out. A warning and not an error: a path stops
    # matching legitimately when a version drops the topic, and failing there would
    # let one version's deletion break every other version's merge.
    Code("REFRAME_KEEP_SEPARATE_UNMATCHED", Severity.WARNING, Stage.REFRAME,
         "A keep_separate path in reframe.yaml matches no topic in this version",
         "planning.md §20e"),
    # Requirements §6: "Reframe must self-validate and fail the stage if any check
    # fails." One row per failed check, because the eight checks fail for eight
    # unrelated reasons and a single "the audit failed" row would send a reader
    # back to the code to find out which. The stage refuses the swap when this is
    # emitted -- §1's "Reframe cannot be re-run to fix a bad boundary" is what makes
    # a merged tree that only mostly passed worse than no merged tree at all.
    Code("REFRAME_SELF_CHECK_FAILED", Severity.ERROR, Stage.REFRAME,
         "A requirements §6 acceptance check failed; the merged tree was discarded "
         "rather than swapped in",
         "REFRAME-REQUIREMENTS.md §6"),
    # R4's "leave unchanged and count them", kept distinct from the error above
    # because §8 says so: a relative target that pointed at nothing *before* the
    # merge is Stage 6a's defect, and failing Reframe on it would block a doc set on
    # a fault this stage can neither cause nor repair. Measured on EMS 10.5.1: 92,
    # all of them `.html` links into a sibling resources tree that is published
    # separately and is genuinely not there at merge time.
    Code("REFRAME_LINK_UNRESOLVED", Severity.WARNING, Stage.REFRAME,
         "Relative references pointing outside the converted tree, left exactly as "
         "written; present before the merge",
         "REFRAME-REQUIREMENTS.md R4, §8"),
    # A `.md` file Stage 6a wrote and `toc.yml` never listed. Reframe carries it
    # through as a single-topic page rather than dropping it, because Stage 7
    # publishes the whole tree and a navigation gap is not a licence to delete
    # content -- but it is a gap, and the writer is the only one who can say whether
    # the topic wants a TOC node or wants deleting. Two on the corpus, both in
    # `tibco-runtime-agent@5.13.0`, one of them the target of a live link.
    Code("REFRAME_TOPIC_UNTOCKED", Severity.WARNING, Stage.REFRAME,
         "Topics absent from toc.yml, carried through unmerged and unreachable from "
         "navigation",
         "REFRAME-REQUIREMENTS.md R3"),
    # A **note**, not a warning, and one row per version rather than per page.
    # R6's queue is the expected output of a *successful* merge -- Reframe declines
    # these judgments on purpose -- so a warning would fire on every version of
    # every run and stop being read, which is the argument 20a made for counting
    # non-Flare rows instead of naming them. The count and the flag breakdown go in
    # the message, because the number is the thing a human acts on.
    # Phase 29. A note, and the one row in the register that reports the tool
    # *not* deciding something: a name here came from a human, and the run says
    # how many so that a reviewer can tell a stable tree from one that happened
    # to recompute the same answer.
    Code("RENAME_MAP_APPLIED", Severity.NOTE, Stage.REFRAME,
         "Page names taken from rename-map.csv rather than recomputed, so a "
         "published URL does not move when a title is edited",
         "planning.md Phase 29"),
    # Phase 34, R9-05. The other half of the row above: a name in the map that
    # was *not* used, because another page ends up at that path and two pages at
    # one path is a page lost. A warning, not a note -- somebody chose that name
    # and the run kept a different one, which is `keep_separate`'s case exactly:
    # a decision that silently did nothing looks like one that was applied.
    Code("RENAME_MAP_REFUSED", Severity.WARNING, Stage.REFRAME,
         "Page names in rename-map.csv that another page already holds (letter "
         "case aside), or that are not a page path inside the tree; the computed "
         "name was kept",
         "planning.md Phase 29"),
    # Phase 34, X2-02 / X3-02. The map lived only inside the tree a swap replaces,
    # so a failed or killed swap lost it and the next run recomputed every name
    # without a word. A warning whether or not a copy rescued the names: the file a
    # writer edits is gone, and published URLs move if no copy survived.
    # Phase 34, X1-07. A pin is keyed on its leading topic's converted path; a
    # re-convert or a boundary change can retire that path, and the row was then
    # neither applied nor refused, and erased from the rewritten map in silence.
    Code("RENAME_MAP_UNMATCHED", Severity.WARNING, Stage.REFRAME,
         "Rows in rename-map.csv whose source topic no longer leads a page; their "
         "names were not used and the rows are dropped, each one named",
         "planning.md §7.5"),
    Code("RENAME_MAP_MISSING", Severity.WARNING, Stage.REFRAME,
         "rename-map.csv is gone from a merged tree that had one; the names came "
         "from the copy kept in state.db, or were recomputed if none survived",
         "planning.md §7.5"),
    Code("REFRAME_REVIEW_QUEUED", Severity.NOTE, Stage.REFRAME,
         "Merged pages needing an editorial decision, listed in review-queue.csv",
         "REFRAME-REQUIREMENTS.md R6"),
    # Phase 22. A genuinely new condition rather than a broadened old one: this is
    # neither a broken link nor an unparsed artifact, it is *the tool declining to
    # guess a URL*. A warning and not an error, because an undeclared product is
    # the expected state for every product but the pilot, and the run that names
    # it has done nothing wrong.
    #
    # The severity is the argument in reverse from 20d.1's "no new code for the
    # empty base". An empty `publish_base_url` is a property of the whole run and
    # the shipped state, so a warning would fire on every correct run; this is a
    # property of one version, is actionable by one line in `origin-urls.yaml`,
    # and goes away for good once answered.
    # Stage CONVERT since Phase 35: `convert` is now the first command to write
    # `301.yml`, so it discovers these. Reframe reports them again for the merged
    # tree; the run's command column says which.
    Code("ORIGIN_TEMPLATE_UNDECLARED", Severity.WARNING, Stage.CONVERT,
         "No verified docsite URL template for this product, so no 301.yml was "
         "written; a guessed origin URL is a redirect to a page that never existed",
         "planning.md Phase 22"),
    # Phase 33. The Coveo sitemap is the second source of verified origin URLs,
    # and these are the three things it can say that Phase 22 could not.
    # MISSING is a warning for the reason UNDECLARED is: no 301.yml, actionable.
    # UNLISTED is a note -- one row withheld out of hundreds written is the check
    # working, not a fault. UNMAPPED is a warning because each one is a live page
    # whose reader gets a 404 at cutover, and nothing else in the tree counts them.
    Code("ORIGIN_SITEMAP_MISSING", Severity.WARNING, Stage.CONVERT,
         "No Coveo sitemap page list for this version and no declared template, so "
         "no 301.yml was written",
         "planning.md Phase 33"),
    Code("ORIGIN_URL_UNLISTED", Severity.NOTE, Stage.CONVERT,
         "Converted topics whose origin URL the docsite sitemap does not list; a "
         "derived row is withheld rather than written unproven",
         "planning.md Phase 33"),
    Code("ORIGIN_PAGE_UNMAPPED", Severity.WARNING, Stage.CONVERT,
         "Live docsite pages no 301.yml row starts from -- API reference, PDFs, "
         "help-system frames -- each a 404 at cutover unless redirected elsewhere",
         "planning.md Phase 33"),
    # Phase 34 (R1-07). Both split out of conditions that were silent or
    # mislabelled. A refused declaration used to read exactly like no declaration,
    # so the one person able to fix it -- whoever wrote it -- was never told; a
    # warning, because the remedy is one line in `origin-urls.yaml`. Sources too
    # short for `drop_segments` used to be counted as one UNDECLARED; each is a
    # topic with no 301 row, so the count is per source and the severity matches
    # ORIGIN_PAGE_UNMAPPED's.
    Code("ORIGIN_TEMPLATE_REJECTED", Severity.WARNING, Stage.CONVERT,
         "A declared docsite URL template failed validation and was ignored; the "
         "version fell back to the sitemap, or wrote no 301.yml without one",
         "planning.md Phase 34"),
    Code("ORIGIN_PATH_TOO_SHORT", Severity.WARNING, Stage.CONVERT,
         "Converted topics whose source path is shorter than the template's "
         "drop_segments, so they have no 301.yml row",
         "planning.md Phase 34"),
    Code("LINK_BROKEN", Severity.ERROR, Stage.VALIDATE,
         "Relative link resolving to nothing", "design.md §8.4"),
    # Phase 43. The link resolves in the tree and breaks on AEM, which does not
    # publish `unfiled/`. A note: the user let these break; this is the record.
    Code("LINK_TO_UNFILED", Severity.NOTE, Stage.VALIDATE,
         "A listed page links to an orphan under unfiled/, which AEM does not publish; "
         "listed in that version's unfiled/inbound-links.csv",
         "planning.md Phase 43"),
    # Phase 34 (R11-06). `sync`'s `PUBLISHED_PATH_TOO_LONG` read back from the
    # shelf, for a tree synced before that guard or by something else. An error
    # for the reason that one is: nothing downstream can open the file. And it
    # can gate, because its clean answer is knowable -- the longest path in
    # either published tree is 236 characters.
    Code("PATH_TOO_LONG", Severity.ERROR, Stage.VALIDATE,
         "A published file whose absolute path exceeds 260 characters; Windows "
         "readers cannot open it", "planning.md Phase 34 (R11-06)"),
    # Emitted from Phase 7c, and a warning on arithmetic rather than on taste, the
    # same way 7b's six were. Measured over the whole cache: 51 of 317 adjacent
    # version pairs (16.1%) drop at least one identifier -- 11.9% even when the
    # comparison is restricted to same-major upgrades, and 69.6% across a major
    # bump, where a product re-keys its help wholesale. A gate at that rate is a
    # gate nobody leaves switched on.
    #
    # **One row per version, with the magnitude in `count`.** §7.1's "errors and
    # warnings get a row each" is intact, because the condition is *this version
    # dropped identifiers against its predecessor* and that is one condition per
    # version. Per-identifier rows would be 784 over the cache, of which 376 come
    # from two pairs -- burying the 30 pairs that dropped between one and five,
    # which are the ones that are a regression rather than a redesign.
    Code("CSH_IDENTIFIER_DROPPED", Severity.WARNING, Stage.VALIDATE,
         "Present in the prior version, absent here", "planning.md §7.6"),
    # 7b's six. Every one of them was an obligation `planning.md` §7.4 or
    # `design.md` §9.6 already carried in English; none had a code, because until
    # `validate` existed nothing could raise one. Their severities are the phase's
    # central decision and each was measured before it was chosen (Phase 7b's
    # "Measured 2026-09-16" table), on the principle that a gating command may only
    # gate on checks whose clean answer is knowable in advance.
    #
    # A warning, not an error. It was chosen on arithmetic -- 1,626 of the
    # sample's 14,055 resolving fragments, 11.6%, named an anchor that was not
    # there -- and that arithmetic no longer holds: after Phases 16, 19 and 30,
    # p35 misses 65 of about 68,900 page fragments (0.09%). It stays a warning
    # because of what the 65 are (Phase 34, R11-03): footnote, GUID and marker
    # fragments with no heading behind them, the residue convert already
    # reports as `FRAGMENT_UNPLACEABLE`. Their remedy is a heading the source
    # does not have, and a gate on a defect nobody here can fix is a gate
    # people switch off. A Help-button anchor meant as a section is
    # `CSH_ANCHOR_MISSING` now.
    Code("ANCHOR_MISSING", Severity.WARNING, Stage.VALIDATE,
         "A #fragment naming no heading in the file it resolves to (an id= or "
         "name= attribute is not an anchor since Phase 29)",
         "planning.md §7.4"),
    # The network is not the output. A proxy, an outage or a host that dislikes
    # HEAD would otherwise decide an exit code, and an exit code that depends on
    # the network is one nobody trusts. Only reachable under `--check-external`.
    # Phase 34 (R11-02). R9-01's defect, which existence-only matching passed: on
    # a merged page `#import` resolves to the first topic's Import heading, not
    # the renumbered `import-1` beside the link. A warning, like `ANCHOR_MISSING`:
    # the link works, it just goes somewhere wrong, and the rule is a heuristic
    # -- exact on p35 (3 hits, all real), but not a fact a gate can rest on.
    Code("ANCHOR_WRONG_HEADING", Severity.WARNING, Stage.VALIDATE,
         "A same-page #fragment resolving to an earlier topic's heading: a heading "
         "with the same title, renumbered, sits between the target and the link",
         "planning.md Phase 34 (R11-02)"),
    Code("LINK_EXTERNAL_DEAD", Severity.WARNING, Stage.VALIDATE,
         "An absolute URL that did not respond, under --check-external",
         "planning.md §7.4"),
    # Phase 34 (R11-03). A `csh.yml` anchor that names no heading: the Help button
    # opens the page top instead of its section. Split out of `ANCHOR_MISSING`,
    # where 318 of these (R8-04's TRA 5.12.x markers) were indistinguishable from
    # 154 harmless identifier-echo fragments. A warning for now, and that is a
    # decision left open rather than made: the 318 are a known, unfixed defect,
    # so a gate would fail every run over p35 until R8-04 lands -- re-measure
    # then, when the clean answer is knowable.
    Code("CSH_ANCHOR_MISSING", Severity.WARNING, Stage.VALIDATE,
         "A csh.yml anchor naming no heading on its page; the Help button opens "
         "the page top instead of the section", "planning.md Phase 34 (R11-03)"),
    # Phase 34 (R11-01). The same guide published twice: sibling `toc.yml` entries
    # with one title opening different pages whose bodies are identical (SFAS
    # 1.2.0's two copies of every guide, Streaming's `index.md`/`lvindex.md`). A
    # warning: every link works, the reader just meets everything twice, and
    # which copy to drop is a decision about the source, not a gate. Narrow on
    # purpose -- p35 has 33 sibling groups sharing a title and only the identical
    # ones are provably duplicates.
    Code("TOC_ENTRY_DUPLICATED", Severity.WARNING, Stage.VALIDATE,
         "Sibling toc.yml entries with one title opening different pages with "
         "identical bodies; the same page or guide published twice",
         "planning.md Phase 34 (R11-01)"),
    # `transforms/csh.py` writes the map and the frontmatter in one pass, so a
    # disagreement is a regression -- but it breaks one Help button rather than the
    # page, and the page is what an error should be about.
    Code("CSH_FRONTMATTER_MISMATCH", Severity.WARNING, Stage.VALIDATE,
         "csh.yml and a topic's frontmatter disagree about an identifier",
         "design.md §9.6"),
    # An error, because `metadata.yml` is the AEM contract's one required file and
    # a version folder without a usable `csg-version` does not publish.
    Code("METADATA_INVALID", Severity.ERROR, Stage.VALIDATE,
         "metadata.yml missing, unshaped, or with an empty csg-product/csg-version",
         "architecture.md §6.2"),
    # A warning, because `sync` deliberately preserves drop-down rows it does not
    # own (`sync/versions.py`) and failing a run over somebody's intentional
    # hand-edit is how a tool teaches people to stop running it.
    Code("DROPDOWN_INCONSISTENT", Severity.WARNING, Stage.VALIDATE,
         "version.yml disagrees with the version folders beside it",
         "architecture.md §6.6"),
    # Separate from any artifact being *wrong*: the file is unreadable, so no field
    # check ran at all, and every other finding about that folder would be unsound.
    Code("ARTIFACT_UNPARSED", Severity.ERROR, Stage.VALIDATE,
         "An AEM YAML artifact that would not parse; its field checks were skipped",
         "planning.md §7.4"),
    # A note, and the only 7b code that is not about correctness. A failed `sync`
    # leaves its staging sibling on the shelf -- two in the sample. The swap did its
    # job, so nothing half-published exists; what is left is litter from a failure
    # that may have gone unnoticed, and the folder itself is skipped.
    Code("SYNC_RESIDUE", Severity.NOTE, Stage.VALIDATE,
         "A .part staging folder left by a sync that did not finish",
         "planning.md §7.4"),
    # Phase 20d. A doc set with `publish: true` in `reframe.yaml` and no usable
    # merged tree -- either none built, or one older than the conversion under it.
    # A warning and not an error, because the doc set is mid-flight rather than
    # broken: the sign-off landed and the merge has not been re-run. What it must
    # not do is fall back to `output/`, which would republish 1,441 unmerged topics
    # over URLs a merge already took, so the version publishes nothing and says so.
    Code("SYNC_MERGE_UNAVAILABLE", Severity.WARNING, Stage.SYNC,
         "A product set to publish merged has no current reframed tree",
         "planning.md §20d"),
    # Phase 20d, and found by measuring EMS rather than by reading R5: a redirect
    # whose `from` still resolves to a published file can never fire. All five on
    # the reference corpus differ from their target only in case
    # (`_templates/Home.md` -> `_templates/home.md#home`), which is a necessary
    # redirect on a case-sensitive host and a 301 loop on a case-insensitive one.
    # The tool does not know which host it publishes to, so it names them and a
    # human decides once per platform.
    Code("REDIRECT_SHADOWED", Severity.WARNING, Stage.VALIDATE,
         "A redirect whose source path still exists in the published tree",
         "REFRAME-REQUIREMENTS.md R5"),
    # Phase 10b, and the reverse of `LINK_BROKEN`: not a link with no file, but a
    # file with no link. A note, and expected to find nothing -- `render_index` is
    # handed the same routed list that decides what gets copied, so every published
    # artifact is linked by construction. That is exactly why the check is worth
    # having and why it must not gate: it guards an invariant that holds today and
    # is one refactor away from being silently false, and a gate that fires on
    # correct output is a gate people switch off.
    Code("INDEX_UNLINKED", Severity.NOTE, Stage.VALIDATE,
         "A published file in a generated doc-class folder that index.md links to nowhere",
         "planning.md Phase 10b"),
    # X3-11. A `current` re-run records nothing about the version, so `report
    # --run last` stopped showing the errors and warnings the unchanged tree
    # still has. A note pointing at the run that built the tree, rather than a
    # copy of its rows: a copied error would make a `current` reframe exit 1.
    Code("CONVERT_FINDINGS_IN_EARLIER_RUN", Severity.NOTE, Stage.CONVERT,
         "A current version's tree was built by an earlier run, which holds its "
         "errors and warnings; the note names that run",
         "reports/review X3-11"),
    Code("REFRAME_FINDINGS_IN_EARLIER_RUN", Severity.NOTE, Stage.REFRAME,
         "A current version's merged tree was built by an earlier run, which holds "
         "its errors and warnings; the note names that run",
         "reports/review X3-11"),
)

# The register's remaining debt, stated as the *complement* of what is written.
#
# Through Phase 6e this was an eight-deep chain of `REACHABLE_IN_PHASE_*` unions,
# one per sub-phase, each naming what its predecessor could reach plus what it
# added. That shape had two faults. It grew a constant per phase while answering
# one question, and it was asserted as a **subset** -- so a code that quietly
# started being emitted never showed up, and the list could only ever overstate
# the debt. Phase 7a replaces the chain with one frozenset asserted **equal**: a
# code that starts firing fails the test until it is removed from here, and a code
# that stops firing fails it until it is added back.
#
# One left. `DOC_REFERENCE_MISSING` belongs to the document router's escape check
# (§10.7's class 2), which is the one remaining debt that belongs to no sub-phase
# yet. Before 7a there were nine, four of them in stages -- `catalog fetch`,
# `catalog eos`, `extract` -- that computed their findings, printed them, and
# opened no run to record them in. `LINK_BROKEN` left the set in 7b and
# `CSH_IDENTIFIER_DROPPED` in 7c, both by hand, which is the whole point of
# asserting this equal rather than as a subset.
#
# The count was briefly believed to be twenty, and how that happened is the reason
# the companion test scans for a quoted literal rather than for a call: the earlier
# count came from grepping `record("CODE"`, which misses every continuation-line
# and every variable call site. The scan that replaces it proves a code is
# *written*, not that it fires -- which is a real limit, and why this set is
# curated by hand rather than derived.
NOT_YET_EMITTED = frozenset({"DOC_REFERENCE_MISSING"})


class UnregisteredCode(KeyError):
    """Raised at the call site, which is the only place that can fix it.

    The one condition in this module that *is* an exception rather than a finding:
    an unregistered code is a programming error, and reporting it as a finding
    would need a code of its own.
    """


@dataclass
class Finding:
    """One row, before it reaches `state.db`."""

    code: str
    slug: str = ""
    version: str = ""
    path: str = ""
    message: str = ""
    count: int = 1

    @property
    def registered(self) -> Code:
        return REGISTRY[self.code]

    @property
    def severity(self) -> Severity:
        return self.registered.severity

    @property
    def stage(self) -> Stage:
        return self.registered.stage

    def row(self) -> tuple[str, str, str, str, str, str, str, int]:
        """The tuple `StateStore.record_findings` takes."""
        return (
            str(self.stage), str(self.severity), self.code,
            self.slug, self.version, self.path, self.message, self.count,
        )


@dataclass
class FindingsRun:
    """Buffers findings for one command run and flushes them to `state.db`.

    Buffered rather than written straight through, because §7.1 requires findings
    to land inside the stage's existing transaction: the caller flushes once per
    version, so a crash on version 200 keeps the first 199 and loses only the
    partial one. A run with no store buffers and never flushes, which is what lets
    a `--dry-run` and a unit test exercise the same code path.
    """

    command: str
    batch: str = ""
    store: "StateStore | None" = None
    run_id: int = 0
    pending: list[Finding] = field(default_factory=list)
    # Notes are folded on the way in, so the buffer cannot grow to one row per
    # orphaned image. Keyed on the aggregation identity, not on the message.
    _notes: dict[tuple[str, str, str], Finding] = field(default_factory=dict)
    recorded: list[Finding] = field(default_factory=list)

    def start(self) -> "FindingsRun":
        if self.store is not None and not self.run_id:
            self.run_id = self.store.start_run(self.command, self.batch)
        return self

    def record(
        self,
        code: str,
        slug: str = "",
        version: str = "",
        path: str = "",
        message: str = "",
        count: int = 1,
    ) -> Finding:
        """Records one finding. Severity comes from the registry, never from here."""
        if code not in REGISTRY:
            raise UnregisteredCode(
                f"{code} is not in the §7.5 register; add it to REGISTRY with a severity"
            )
        finding = Finding(code, slug, version, path, message, count)
        if finding.severity is Severity.NOTE:
            key = (code, slug, version)
            existing = self._notes.get(key)
            if existing is not None:
                existing.count += count
                # The first message stands. A note's prose describes the class of
                # thing, and the count is what the reader acts on.
                return existing
            self._notes[key] = finding
        self.pending.append(finding)
        return finding

    def flush(self) -> None:
        """Writes the buffer. Called by the stage, inside its own transaction."""
        if not self.pending:
            return
        if self.store is not None and self.run_id:
            self.store.record_findings(self.run_id, [f.row() for f in self.pending])
        self.recorded.extend(self.pending)
        self.pending.clear()
        self._notes.clear()

    def point_back(self, code: str, slug: str, version: str, built_in: str) -> None:
        """On a `current` re-run, a note naming the run that built the tree (X3-11).

        The building run's errors and warnings still describe the tree, and the
        report defaults to the last run, which has none of them. Only when there
        is something to point at: a run id recorded, still holding error or
        warning rows for this version. `report --prune` can still drop those rows,
        and then there is nothing to say.
        """
        if self.store is None or not built_in.isdigit() or int(built_in) == self.run_id:
            return
        run_id = int(built_in)
        tally = {Severity.ERROR: 0, Severity.WARNING: 0}
        for row in self.store.query_findings(run_id, slug=slug):
            severity = Severity(row["severity"])
            if row["version"] == version and severity in tally:
                tally[severity] += 1
        parts = [f"{n} {severity}{'s' if n != 1 else ''}" for severity, n in tally.items() if n]
        if parts:
            self.record(code, slug=slug, version=version, message=(
                f"unchanged since run {run_id}, which recorded {' and '.join(parts)} for it; "
                f"`docushift report --run {run_id} --slug {slug}`"))

    def finish(self, exit_code: int = 0) -> None:
        self.flush()
        if self.store is not None and self.run_id:
            self.store.finish_run(self.run_id, exit_code)

    # -- reading back ---------------------------------------------------------

    @property
    def all(self) -> list[Finding]:
        """Everything recorded this run, flushed or not, in record order."""
        return [*self.recorded, *self.pending]

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.all if f.severity is severity]

    def counts(self) -> dict[Severity, int]:
        """Rows per severity -- notes counted as rows, not as occurrences.

        The magnitude of a note lives in its `count` column; what a summary line
        needs is how many distinct things were noted.
        """
        tally = {severity: 0 for severity in Severity}
        for finding in self.all:
            tally[finding.severity] += 1
        return tally

    def summary(self) -> str:
        """One line for the end of a run report. Empty when there is nothing to say."""
        tally = self.counts()
        parts = [
            f"{tally[severity]} {severity}{'s' if tally[severity] != 1 else ''}"
            for severity in Severity if tally[severity]
        ]
        return ", ".join(parts)

    def __iter__(self) -> Iterator[Finding]:
        return iter(self.all)


def unreachable_codes(emitted: Iterable[str]) -> list[str]:
    """Registered codes that no supplied code path reaches. For the §7.5 test."""
    return sorted(set(REGISTRY) - set(emitted))
