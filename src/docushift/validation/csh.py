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
"""

from pathlib import Path, PurePosixPath

import yaml

from docushift.reporting.findings import Finding
from docushift.validation import references
from docushift.validation.links import FolderIndex
from docushift.validation.tree import VersionFolder

CSH_FILE = "csh.yml"
# The frontmatter key `transforms/csh.py::frontmatter_value` writes (§9.5).
FRONTMATTER_KEY = "csh"


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


def check(folder: VersionFolder, index: FolderIndex) -> list[Finding]:
    """One version folder's CSH, or nothing at all if it has none.

    A folder with no `csh.yml` is not a finding: 13 of the sample's 17
    `online-help` folders have none, because the source package shipped no help
    mapping, and §9.4 is explicit that an empty map gets no file rather than an
    empty one.
    """
    path = folder.path / CSH_FILE
    pages = _frontmatter_index(folder, index)
    if not path.is_file():
        return _orphan_frontmatter(folder, pages, mapping={})

    where = (folder.relative / CSH_FILE).as_posix()
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        detail = str(error).splitlines()[0] if str(error) else "invalid YAML"
        return [Finding("ARTIFACT_UNPARSED", slug=folder.slug, version=folder.segment,
                        path=where, message=detail)]
    if document is None:
        document = {}
    if not isinstance(document, dict):
        return [Finding("ARTIFACT_UNPARSED", slug=folder.slug, version=folder.segment,
                        path=where, message="is not the flat identifier map §9.4 specifies")]

    mapping = {str(key): str(value) for key, value in document.items()}
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
