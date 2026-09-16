"""`csh.yml` and the frontmatter that mirrors it, checked against each other.

`design.md` §9.6 has four verification rules and this is where three of them are
enforced. The fourth -- an identifier present in the prior version and absent here
-- needs two converted versions of one product on disk and is Phase 7c's.

**CSH is checked as link integrity, because that is what it is.** A `csh.yml`
value is `path/to/topic.md#anchor`: the file half gets `LINK_BROKEN` and the
anchor half gets `ANCHOR_MISSING`, the same two codes and the same two severities
the page checker uses, for the same reason. Inventing a `CSH_TARGET_MISSING`
would mean two codes for one condition and a `report --code LINK_BROKEN` that
misses the help buttons.

The sample tree of 2026-09-16 split exactly where the design predicted: over 215
entries in 4 files, **0 file parts missing and 33 of 47 anchors missing**. The
half `transforms/csh.py` controls is perfect; the half that depends on an anchor
surviving conversion is not. That is the whole argument for the severity split,
measured rather than asserted.

The third rule is the round trip. `transforms/csh.py` writes the map and the
frontmatter in one pass, so a disagreement between them is a regression -- but it
breaks one Help button rather than the page, which is why
`CSH_FRONTMATTER_MISMATCH` is a warning.

**The fourth rule is §7.6's, and it arrived in Phase 7c.** A dropped identifier is
the one defect in this tool that cannot be seen from inside a version: 6.10.0's map
is correct and 6.11.0's map is correct, and the product's Help button still breaks
on upgrade. `diff` is the only thing in the tool that computes a CSH difference --
`validate`, `csh validate` and `csh report --since` all call it -- because two
implementations of one comparison is two answers to "did this Help button survive".
"""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import yaml

from docushift.reporting.findings import Finding
from docushift.utils.csvio import natural_version_key
from docushift.validation import references
from docushift.validation.links import FolderIndex
from docushift.validation.tree import ProductFolder, VersionFolder

CSH_FILE = "csh.yml"
# The frontmatter key `transforms/csh.py::frontmatter_value` writes (§9.5).
FRONTMATTER_KEY = "csh"

# How many dropped identifiers the finding's message names before it counts the
# rest. The full list is `csh report --since`'s job: the register carries the
# magnitude and the command carries the detail, which is the same split §7.1 makes
# for a note's `count`.
NAMED_IN_MESSAGE = 5


def _identifiers(text: str) -> list[str]:
    """The `csh:` list out of one page's frontmatter. `[]` when there is none."""
    block = references.frontmatter(text)
    if not block or FRONTMATTER_KEY not in block:
        return []
    try:
        document = yaml.safe_load(block)
    except yaml.YAMLError:
        # Not reported here. A page whose frontmatter will not parse is a
        # conversion defect, and claiming it as a CSH mismatch would name the
        # wrong stage -- `ARTIFACT_UNPARSED` is about the four YAML artifacts.
        return []
    if not isinstance(document, dict):
        return []
    value = document.get(FRONTMATTER_KEY)
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


@dataclass(frozen=True)
class MapFile:
    """One version folder's `csh.yml`, read once and shared by every surface.

    `absent` and `unparsed` are different facts and the tool has always treated
    them so: a version with no help source gets no file at all (§9.4), which is
    the common case, while a file that will not load is an `ARTIFACT_UNPARSED`
    error. Both come back with an empty `entries`, so a caller that only wants
    the identifiers needs no branch.
    """

    folder: VersionFolder
    entries: dict[str, str] = field(default_factory=dict)
    present: bool = False
    # Why it would not load. Empty when it loaded, or when there is no file.
    unparsed: str = ""

    @property
    def where(self) -> str:
        return (self.folder.relative / CSH_FILE).as_posix()

    @property
    def targets(self) -> set[str]:
        """The distinct pages the map opens, anchors stripped."""
        return {value.partition("#")[0] for value in self.entries.values()}


def load(folder: VersionFolder) -> MapFile:
    """Reads one folder's `csh.yml`. Never raises, and never reports."""
    path = folder.path / CSH_FILE
    if not path.is_file():
        return MapFile(folder)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        detail = str(error).splitlines()[0] if str(error) else "invalid YAML"
        return MapFile(folder, present=True, unparsed=detail)
    if document is None:
        document = {}
    if not isinstance(document, dict):
        return MapFile(folder, present=True,
                       unparsed="is not the flat identifier map §9.4 specifies")
    return MapFile(
        folder,
        entries={str(key): str(value) for key, value in document.items()},
        present=True,
    )


def check(folder: VersionFolder, index: FolderIndex) -> list[Finding]:
    """One version folder's CSH, or nothing at all if it has none.

    A folder with no `csh.yml` is not a finding: 13 of the sample's 17
    `online-help` folders have none, because the source package shipped no help
    mapping, and §9.4 is explicit that an empty map gets no file rather than an
    empty one.
    """
    return check_map(load(folder), index)


def check_map(found: MapFile, index: FolderIndex) -> list[Finding]:
    """The three single-version rules, over a map somebody has already read."""
    folder = found.folder
    pages = _frontmatter_index(folder, index)
    if not found.present:
        return _orphan_frontmatter(folder, pages, mapping={})

    where = found.where
    if found.unparsed:
        return [Finding("ARTIFACT_UNPARSED", slug=folder.slug, version=folder.segment,
                        path=where, message=found.unparsed)]

    mapping = found.entries
    findings: list[Finding] = []
    for identifier, value in sorted(mapping.items()):
        target, _, anchor = value.partition("#")
        if target not in index.present:
            actual = index.actual_case(target)
            detail = (
                f"differs only in case from {actual}" if actual
                else "is not in this version folder"
            )
            findings.append(Finding("LINK_BROKEN", slug=folder.slug, version=folder.segment,
                                    path=where, message=f"{identifier} -> {target} {detail}"))
            continue
        anchored = anchor and PurePosixPath(target).suffix.lower() == ".md"
        if anchored and anchor.lower() not in index.anchors(target):
            findings.append(Finding(
                "ANCHOR_MISSING", slug=folder.slug, version=folder.segment, path=where,
                message=f"{identifier} -> #{anchor} is not an anchor in {target}",
            ))
        # The identifier must also be on the page it names (§9.5's mirror).
        if identifier not in pages.get(target, ()):
            findings.append(Finding(
                "CSH_FRONTMATTER_MISMATCH", slug=folder.slug, version=folder.segment, path=where,
                message=f"{identifier} maps to {target}, whose frontmatter does not list it",
            ))
    return findings + _orphan_frontmatter(folder, pages, mapping)


def _frontmatter_index(folder: VersionFolder, index: FolderIndex) -> dict[str, set[str]]:
    """`{relative page -> identifiers in its frontmatter}`, for pages that have any.

    Only pages carrying the key are read into the map, so the round-trip check
    costs one frontmatter parse per Markdown file and nothing else. The files were
    already opened by the link checker; this is the one pass that cannot reuse
    that, because the link checker keeps anchors rather than text.
    """
    found: dict[str, set[str]] = {}
    for relative in sorted(index.present):
        if not relative.endswith(".md"):
            continue
        identifiers = _identifiers(_read(folder.path / relative))
        if identifiers:
            found[relative] = set(identifiers)
    return found


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover
        return ""


def _orphan_frontmatter(
    folder: VersionFolder, pages: dict[str, set[str]], mapping: dict[str, str]
) -> list[Finding]:
    """Identifiers a page claims that `csh.yml` does not carry -- the other direction.

    One finding per page rather than per identifier: a page owning six identifiers
    that all vanished is one conversion going wrong, and six rows would bury the
    five other pages it happened to.
    """
    known = set(mapping)
    findings: list[Finding] = []
    for relative, identifiers in sorted(pages.items()):
        missing = sorted(identifiers - known)
        if not missing:
            continue
        findings.append(Finding(
            "CSH_FRONTMATTER_MISMATCH", slug=folder.slug, version=folder.segment,
            path=(folder.relative / relative).as_posix(),
            message=f"frontmatter claims {', '.join(missing)}, absent from {CSH_FILE}",
        ))
    return findings


# -- §7.6, the cross-version regression ---------------------------------------


@dataclass(frozen=True)
class Diff:
    """What changed between one version's help map and its predecessor's."""

    prior: MapFile
    current: MapFile
    dropped: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    # Identifiers in both, opening a different page. **Not a finding.** Measured
    # over the cache, 1,084 of 8,425 survivors (12.9%) retarget between adjacent
    # versions, in 81 of 317 pairs -- that is pages being renamed between
    # releases, and the Help button still works. Carried so `csh report --since`
    # can show it, and read by nothing that records.
    retargeted: tuple[str, ...] = ()

    @property
    def wholesale(self) -> bool:
        """Did more than 90% of the predecessor's map go?

        15 of the cache's 51 dropping pairs did, two of them losing 188 of 188.
        That is a product re-keying its help, usually across a major version --
        a redesign rather than a regression. It changes nothing about the
        finding; it is why the message names both versions, so a reader can tell
        the two apart without opening either file.
        """
        return bool(self.prior.entries) and (
            len(self.dropped) / len(self.prior.entries) > 0.9
        )


def diff(prior: MapFile, current: MapFile) -> Diff:
    """The comparison, and **the only place in the tool that computes one.**

    `validate` records from it, `csh validate` records from it and
    `csh report --since` prints from it. Byte-exact on the identifier, never
    case-folded: `GatewayInstances` and `gatewayInstances` are two live help
    targets in TIBCO BC 7.4/7.5 (§9.1), and folding them here would hide a drop
    behind a survivor.
    """
    before, after = prior.entries, current.entries
    return Diff(
        prior=prior,
        current=current,
        dropped=tuple(sorted(set(before) - set(after))),
        added=tuple(sorted(set(after) - set(before))),
        retargeted=tuple(sorted(
            identifier for identifier in set(before) & set(after)
            if before[identifier] != after[identifier]
        )),
    )


def pairs(entry: ProductFolder) -> list[tuple[VersionFolder, VersionFolder]]:
    """`(predecessor, version)` for each version folder that has one.

    **The predecessor is the immediate next-lower folder in the same doc-class,
    and nothing cleverer.** Ordered by `natural_version_key` over the dashed
    published segment, which sorts correctly among segments because the key
    splits on digit runs and compares them numerically -- `10-4-0` above `9-3-0`.
    §4.1's point that the dashed form does not round-trip back to a dotted
    version is about parsing, and this is ordering.

    Skipping back to the last version that *had* a map sounds more thorough and
    is worse: a product whose map vanishes in 6.11.0 would report the same 123
    identifiers again in 6.12.0 and every version after it, so one defect becomes
    an unbounded row count and the version that actually lost the map stops being
    identifiable. Under the rule as written a vanished map fires exactly once.
    """
    by_class: dict[str, list[VersionFolder]] = {}
    for folder in entry.versions:
        if folder.segment:
            by_class.setdefault(folder.doc_class, []).append(folder)
    found: list[tuple[VersionFolder, VersionFolder]] = []
    for folders in by_class.values():
        ordered = sorted(folders, key=lambda f: natural_version_key(f.segment))
        found.extend(zip(ordered, ordered[1:], strict=False))
    return found


def check_regression(entry: ProductFolder) -> list[Finding]:
    """§7.6 over one product folder. One warning per version, never per identifier.

    **The magnitude is in `count` and a sample is in the message.** §7.1 says
    errors and warnings get a row each and only notes fold, and that rule is
    intact: the condition is *this version dropped identifiers relative to its
    predecessor*, which is one condition per version. The measurement is what
    forbids the other reading -- 784 per-identifier rows over the cache, of which
    376 come from two pairs, would bury the 30 pairs that dropped between one and
    five, and those are the ones that are a regression rather than a re-key.

    A product's oldest version gets nothing. §7.6 asked for a note there; its
    intent was *do not fail on a first conversion*, and writing no row honours it
    while writing one would add 150 rows over the cache to a check that produces
    51 real ones. The absence shows in `csh report`'s coverage table, where it is
    a column rather than a finding.
    """
    findings: list[Finding] = []
    for before, after in pairs(entry):
        prior = load(before)
        if not prior.entries:
            # Nothing to regress against. An unparseable predecessor is already
            # an `ARTIFACT_UNPARSED` error against its own folder; claiming a
            # drop from a file nobody could read would be a guess.
            continue
        change = diff(prior, load(after))
        if not change.dropped:
            continue
        findings.append(Finding(
            "CSH_IDENTIFIER_DROPPED",
            slug=after.slug,
            version=after.segment,
            path=(after.relative / CSH_FILE).as_posix(),
            message=_dropped_message(before.segment, change),
            count=len(change.dropped),
        ))
    return findings


def _dropped_message(prior_segment: str, change: Diff) -> str:
    named = ", ".join(change.dropped[:NAMED_IN_MESSAGE])
    rest = len(change.dropped) - NAMED_IN_MESSAGE
    if rest > 0:
        named = f"{named} and {rest} more"
    total = len(change.prior.entries)
    scale = (
        f"{len(change.dropped)} of {prior_segment}'s {total}"
        if not change.wholesale
        else f"{len(change.dropped)} of {prior_segment}'s {total} -- the map was re-keyed"
    )
    return f"{scale}: {named}"


# -- what `csh report` counts --------------------------------------------------


@dataclass(frozen=True)
class Coverage:
    """One product's CSH, as the shelf has it.

    Computed here rather than in the command so it can be tested without a
    terminal, and so `csh report` and any later reader cannot disagree about what
    "covered" means.
    """

    slug: str
    tree: str
    published: int = 0
    mapped: int = 0
    identifiers: int = 0
    pages: int = 0
    dropped: int = 0
    maps: tuple[MapFile, ...] = ()
    diffs: tuple[Diff, ...] = ()

    @property
    def comparable(self) -> int:
        """Version pairs where the predecessor had a map to compare against."""
        return len(self.diffs)


def coverage(entry: ProductFolder) -> Coverage:
    """Reads every `csh.yml` under one product and tallies it."""
    maps = [load(folder) for folder in entry.versions if folder.segment]
    loaded = {found.folder.path: found for found in maps}
    diffs = []
    for before, after in pairs(entry):
        prior = loaded[before.path]
        if prior.entries:
            diffs.append(diff(prior, loaded[after.path]))
    identifiers: set[str] = set()
    pages: set[str] = set()
    for found in maps:
        identifiers |= set(found.entries)
        pages |= found.targets
    return Coverage(
        slug=entry.slug,
        tree=entry.tree,
        published=len(maps),
        mapped=sum(1 for found in maps if found.entries),
        identifiers=len(identifiers),
        pages=len(pages),
        dropped=sum(len(change.dropped) for change in diffs),
        maps=tuple(maps),
        diffs=tuple(diffs),
    )
