"""The four AEM artifacts, checked field by field rather than for existence.

This replaces `design.md` §8.4's original "existence and well-formedness only"
rule, and both of that rule's grounds are gone: the shapes stopped being guesses
when the AEM contract landed on 2026-09-10, and Stage 6 now writes all four from
templates, so a field that is wrong is a regression rather than a surprise.

Three decisions the sample tree of 2026-09-16 forced, all of them about **not**
checking something:

- **Only `metadata.yml` is required, and which key it must carry depends on where
  it sits.** A global required-set would raise around sixty findings against
  correct output: `online-help` carries a root `index.md` in 2 of its 17 folders
  and a `csh.yml` in 4, `api-references` carries `metadata.yml` and nothing else
  (§6.2.1), and `archives/` has no version segment at all. So `toc.yml`,
  `index.md`, `csh.yml` and `version.yml` are checked *if present* and never
  demanded, and the per-doc-class table below says which of `csg-product` and
  `csg-version` the one required file must hold.
- **A `version.yml` disagreement is a warning.** `sync` deliberately preserves
  rows it does not own (`sync/versions.py`), and failing a run over somebody's
  intentional hand-edit is how a tool teaches people to stop running it.
- **A `toc.yml` path is a link and gets `LINK_BROKEN`.** Giving the TOC its own
  code would mean two codes for one condition and a `report --code LINK_BROKEN`
  that misses half the broken links. `archives/toc.yml` points at absolute
  download URLs, which classify as external and are not resolved -- the same rule
  the page checker follows, reached through the same `transforms/links.py`.

A file that will not parse is reported once as `ARTIFACT_UNPARSED` and the rest of
that file's checks are skipped: the action is different -- nothing can be read at
all -- and continuing would make every further finding about it unsound.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from docushift.reporting.findings import Finding
from docushift.sync import API_REFERENCES, ARCHIVES, DOCUMENT_DOC_CLASSES
from docushift.sync import redirects as redirect_map
from docushift.sync import versions as version_file
from docushift.sync.distributor import STAGING_SUFFIX
from docushift.transforms import links as refs
from docushift.utils.csvio import natural_version_key
from docushift.utils.slug import is_numeric_version
from docushift.validation import references as md
from docushift.validation.links import FolderIndex
from docushift.validation.tree import ProductFolder, VersionFolder

METADATA = "metadata.yml"
TOC = "toc.yml"
VERSION_FILE = "version.yml"
#: Reframe's 301 map, present only in a merged tree (20d).
REDIRECTS = "redirects.yml"

PRODUCT_KEY = "csg-product"
VERSION_KEY = "csg-version"

# Which key a folder's `metadata.yml` must carry. `archives/` takes the product
# key although it sits at doc-class level, because the folder is the product's
# whole history rather than one version of it -- which is what Stage 6 writes.
_METADATA_KEY: dict[str, str] = {ARCHIVES: PRODUCT_KEY}


@dataclass(frozen=True)
class _Loaded:
    """A YAML file read, or the finding that says it could not be."""

    document: object = None
    failure: Finding | None = None


def _load(path: Path, slug: str, version: str, where: str) -> _Loaded:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:  # pragma: no cover - the file was just listed
        return _Loaded(failure=Finding(
            "ARTIFACT_UNPARSED", slug=slug, version=version, path=where, message=str(error)
        ))
    try:
        return _Loaded(document=yaml.safe_load(text))
    except yaml.YAMLError as error:
        detail = str(error).splitlines()[0] if str(error) else "invalid YAML"
        return _Loaded(failure=Finding(
            "ARTIFACT_UNPARSED", slug=slug, version=version, path=where, message=detail
        ))


# -- metadata.yml ---------------------------------------------------------------


def _check_metadata(path: Path, slug: str, version: str, where: str, key: str) -> list[Finding]:
    loaded = _load(path, slug, version, where)
    if loaded.failure is not None:
        return [loaded.failure]
    document = loaded.document
    if not isinstance(document, dict):
        return [Finding("METADATA_INVALID", slug=slug, version=version, path=where,
                        message="is not a YAML mapping")]
    value = document.get(key)
    if value is None:
        return [Finding("METADATA_INVALID", slug=slug, version=version, path=where,
                        message=f"has no {key}")]
    if not str(value).strip():
        return [Finding("METADATA_INVALID", slug=slug, version=version, path=where,
                        message=f"{key} is empty")]
    return []


def check_product(product: ProductFolder) -> list[Finding]:
    """The product-level `metadata.yml`, in the docs tree only.

    **Not checked in the `-resources` sibling**, and the omission is deliberate:
    all ten resources-tree product directories in the sample have no
    `metadata.yml`, because `sync` writes that file in the docs tree only, and
    nothing in `architecture.md` §6.2 says whether AEM wants one there. A gating
    command that enforces a guess about somebody else's contract is worse than one
    that stays quiet, so the gap is recorded in `planning.md` Phase 7b instead.
    """
    if product.is_resources:
        return []
    where = (product.relative / METADATA).as_posix()
    path = product.path / METADATA
    if not path.is_file():
        return [Finding("METADATA_INVALID", slug=product.slug, path=where, message="is missing")]
    return _check_metadata(path, product.slug, "", where, PRODUCT_KEY)


# -- toc.yml --------------------------------------------------------------------


def _toc_paths(node: object) -> list[str]:
    """Every `path` in a `toc.yml`, depth-first, whatever else the node carries.

    Shape-tolerant on purpose: `online-help` writes `{title, path, children}` and
    `archives` writes `{version, released, available, path}`. Both are DocuShift's
    own output, and a checker that insisted on one of them would report the other
    as malformed.
    """
    found: list[str] = []
    if isinstance(node, dict):
        value = node.get("path")
        if isinstance(value, str) and value.strip():
            found.append(value.strip())
        for key in ("items", "children"):
            found.extend(_toc_paths(node.get(key)))
    elif isinstance(node, list):
        for child in node:
            found.extend(_toc_paths(child))
    return found


def _check_toc(folder: VersionFolder, index: FolderIndex) -> list[Finding]:
    path = folder.path / TOC
    if not path.is_file():
        return []
    where = (folder.relative / TOC).as_posix()
    loaded = _load(path, folder.slug, folder.segment, where)
    if loaded.failure is not None:
        return [loaded.failure]

    findings: list[Finding] = []
    for raw in _toc_paths(loaded.document):
        reference = refs.classify(raw)
        if reference.kind is not refs.ReferenceKind.RELATIVE:
            continue
        # A `toc.yml` path is written from the version folder's root, not from the
        # file that carries it -- there is only one such file, and it is at the root.
        target = str(refs.resolve(PurePosixPath("."), reference.path))
        if target not in index.present:
            actual = index.actual_case(target)
            detail = (
                f"differs only in case from {actual}" if actual
                else "is not in this version folder"
            )
            findings.append(Finding("LINK_BROKEN", slug=folder.slug, version=folder.segment,
                                    path=where, message=f"{raw} {detail}"))
        elif reference.fragment and PurePosixPath(target).suffix.lower() == ".md":
            if reference.fragment.lower() not in index.anchors(target):
                findings.append(Finding(
                    "ANCHOR_MISSING", slug=folder.slug, version=folder.segment, path=where,
                    message=f"#{reference.fragment} is not an anchor in {target}",
                ))
    return findings


# -- redirects.yml, where Reframe published one ------------------------------------


def _check_redirects(folder: VersionFolder, index: FolderIndex) -> list[Finding]:
    """R5 at the gate: one 301 per source topic, zero dangling, none unreachable.

    Phase 20d. Reframe audits its own redirect map before it swaps a tree in, and
    that is the right place for it -- but the map it audits is the one it believes
    it wrote, against a set it built in memory. This checks the file that actually
    shipped against the folder that actually shipped, which is the only version of
    the question a published URL cares about. Checked *if present*, like every
    other artifact here: only a merged tree has one.

    Same codes as `_check_toc`, for the reason its docstring gives -- a dangling
    redirect is a broken link that happens to live in a different file, and two
    codes for one condition would make `report --code LINK_BROKEN` miss half of
    them. `REDIRECT_SHADOWED` is the one genuinely new condition; see below.
    """
    path = folder.path / REDIRECTS
    if not path.is_file():
        return []
    where = (folder.relative / REDIRECTS).as_posix()
    loaded = _load(path, folder.slug, folder.segment, where)
    if loaded.failure is not None:
        return [loaded.failure]

    document = loaded.document
    entries = document.get("redirects") if isinstance(document, dict) else None
    findings: list[Finding] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("from") or "").strip()
        raw = str(entry.get("to") or "").strip()
        if not raw:
            continue
        reference = refs.classify(raw)
        if reference.kind is not refs.ReferenceKind.RELATIVE:
            continue
        target = str(refs.resolve(PurePosixPath("."), reference.path))
        if target not in index.present:
            findings.append(Finding(
                "LINK_BROKEN", slug=folder.slug, version=folder.segment, path=where,
                message=f"{raw} is not in this version folder",
            ))
            continue
        if (
            reference.fragment
            and PurePosixPath(target).suffix.lower() == ".md"
            and reference.fragment.lower() not in index.anchors(target)
        ):
            findings.append(Finding(
                "ANCHOR_MISSING", slug=folder.slug, version=folder.segment, path=where,
                message=f"#{reference.fragment} is not an anchor in {target}",
            ))
        findings.extend(_shadowed(folder, index, where, source, target))
    return findings


def _shadowed(
    folder: VersionFolder, index: FolderIndex, where: str, source: str, target: str
) -> list[Finding]:
    """A redirect whose `from` still resolves to a published file.

    It can never fire, and the interesting half is *why*. A page's own leader
    redirects to itself -- `a.md -> a.md#a`, 108 of EMS 10.5.1's 1,441 -- which is
    expected and excluded. What is left is a source path that differs from its
    target only in case: five on that corpus, `_templates/Home.md` pointing at
    `_templates/home.md#home` among them, because the packer lowercases page
    filenames and the source topic was capitalised.

    Those five are a **necessary** redirect on a case-sensitive host and a **301
    loop** on a case-insensitive one. Nothing in this tool knows which host it
    publishes to, so the check names them with the distinction in the message and
    a human decides once per platform rather than once per redirect.
    """
    if not source or source == target:
        return []
    actual = source if source in index.present else index.actual_case(source)
    if actual is None:
        return []
    reason = (
        "differs from its target only in case, so it is a 301 loop on a "
        "case-insensitive host" if source.lower() == target.lower()
        else "still exists, so the redirect can never fire"
    )
    return [Finding("REDIRECT_SHADOWED", slug=folder.slug, version=folder.segment, path=where,
                    message=f"{source} -> {target}: the source {reason}")]


# -- index.md, in the folders DocuShift writes one for -----------------------------

INDEX = "index.md"

# The files Stage 6 generates into a doc-class folder. They are the page and its
# furniture, not artifacts the index is supposed to link, so they are never
# unlinked. `version.yml` sits a level up but is listed for the same reason.
_GENERATED = frozenset({INDEX, TOC, METADATA, VERSION_FILE, "csh.yml"})

# Where an `index.md` is a *complete* list of the folder's files. `online-help` is
# excluded and must stay excluded: its pages are a converted tree whose navigation
# is `toc.yml`, and its index -- where there is one -- is a landing page rather
# than a manifest, so every topic and every image in it would be reported here.
_INDEXED_DOC_CLASSES = frozenset(DOCUMENT_DOC_CLASSES) | {ARCHIVES}


def _check_index(folder: VersionFolder) -> list[Finding]:
    """Files in a generated doc-class folder that `index.md` links to nowhere.

    The reverse of `LINK_BROKEN`, and the direction nothing checked: a link with no
    file is an error, a file with no link is this. Phase 9 moved the artifact list
    out of `toc.yml` and into `index.md`, and `validate` already follows it --
    renaming a published PDF raises `LINK_BROKEN` from the page checker, tested
    rather than assumed. What that leaves is a file the index simply never named,
    which is unreachable and reported by nobody.

    Expected to find nothing. `render_index` is handed the same routed list that
    decides what gets copied, so the invariant holds by construction; the value is
    that it would stop holding silently otherwise.
    """
    if folder.doc_class not in _INDEXED_DOC_CLASSES:
        return []
    index = folder.path / INDEX
    if not index.is_file():
        return []
    try:
        text = index.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - the file was just listed
        return []

    linked: set[str] = set()
    for raw in md.references(text):
        reference = refs.classify(raw.raw)
        if reference.kind is refs.ReferenceKind.RELATIVE:
            linked.add(str(refs.resolve(PurePosixPath("."), reference.path)).lower())

    findings: list[Finding] = []
    for child in sorted(folder.path.iterdir()):
        if not child.is_file() or child.name in _GENERATED:
            continue
        if child.name.lower() not in linked:
            findings.append(Finding(
                "INDEX_UNLINKED", slug=folder.slug, version=folder.segment,
                path=(folder.relative / child.name).as_posix(),
                message=f"{child.name} is published here but {INDEX} links to it nowhere",
            ))
    return findings


# -- version.yml ----------------------------------------------------------------


def check_dropdown(product: ProductFolder, doc_class: Path) -> list[Finding]:
    """`{slug}/{doc-class}/version.yml` against the version folders beside it.

    Three questions, all of them about the *set* rather than about one row: does
    every row DocuShift could have written name a directory that is there, does
    every directory have a row, and are the rows in numeric-descending order. Rows
    this tool is not entitled to own -- an absolute URL, a multi-segment path --
    are excluded from all three, exactly as `sync/versions.merge` excludes them.
    """
    path = doc_class / VERSION_FILE
    if not path.is_file():
        return []
    where = (product.relative / doc_class.name / VERSION_FILE).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover
        return []
    rows = version_file.parse(text)
    if rows is None:
        return [Finding("ARTIFACT_UNPARSED", slug=product.slug, path=where,
                        message="is not the version.yml contract; sync leaves it alone")]

    present = {
        child.name for child in doc_class.iterdir()
        if child.is_dir() and not child.name.endswith(STAGING_SUFFIX)
    }
    owned = [row for row in rows if _bare_segment(row.path)]
    named = [_bare_segment(row.path) or "" for row in owned]

    findings: list[Finding] = []
    for segment in named:
        if segment not in present:
            findings.append(Finding(
                "DROPDOWN_INCONSISTENT", slug=product.slug, version=segment, path=where,
                message=f"row /{segment} names no folder beside this file",
            ))
    seen: set[str] = set()
    for segment in named:
        if segment in seen:
            findings.append(Finding(
                "DROPDOWN_INCONSISTENT", slug=product.slug, version=segment, path=where,
                message=f"row /{segment} appears more than once",
            ))
        seen.add(segment)
    for segment in sorted(present - seen):
        findings.append(Finding(
            "DROPDOWN_INCONSISTENT", slug=product.slug, version=segment, path=where,
            message=f"{segment}/ is published but has no drop-down row",
        ))

    # Numeric rows descending, non-numeric ones after them -- `generated_rows`'
    # order, checked rather than re-derived, so a hand-inserted row in the wrong
    # place is named without the checker claiming to know what the list should be.
    numeric = [segment for segment in named if is_numeric_version(segment.replace("-", "."))]
    ordered = sorted(numeric, key=lambda s: natural_version_key(s.replace("-", ".")), reverse=True)
    if numeric != ordered:
        findings.append(Finding(
            "DROPDOWN_INCONSISTENT", slug=product.slug, path=where,
            message=f"rows are not newest-first: {', '.join(numeric)}",
        ))
    return findings


def check_redirect_map(product: ProductFolder, doc_class: Path, target: Path,
                       trees: set[str]) -> list[Finding]:
    """`{slug}/{doc-class}/redirects.yml` -- the published 301 map (20d.1).

    One question, and it is the only one this file can be asked here: does every
    `to` name a file the target actually holds. These are the entries a reader is
    301'd through, so a dangling one is `LINK_BROKEN` and an error, the same code
    and the same severity the per-version map and `toc.yml` already use.

    Anchors are not checked here and are checked by the per-version map, which has
    the folder index to check them against. Two checkers reporting one dangling
    anchor twice would make `report --code ANCHOR_MISSING` a count of how many
    views of the map exist rather than of how many anchors are missing.

    A row whose `to` does not start at a published tree is not resolved: it is a
    hand-added redirect out of this target, which `sync` carries through verbatim
    precisely so that nothing here has to adjudicate it.
    """
    path = doc_class / redirect_map.REDIRECTS
    if not path.is_file():
        return []
    where = (product.relative / doc_class.name / redirect_map.REDIRECTS).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover
        return []
    rows = redirect_map.parse(text)
    if rows is None:
        return [Finding("ARTIFACT_UNPARSED", slug=product.slug, path=where,
                        message="is not the redirects.yml contract; sync leaves it alone")]

    findings: list[Finding] = []
    for row in rows:
        to = str(row.get("to", ""))
        resolved = redirect_map.relative_path(to, trees)
        if resolved is not None and not (target / resolved).exists():
            findings.append(Finding(
                "LINK_BROKEN", slug=product.slug, path=where,
                message=f"{row.get('from', '')} redirects to {to}, which this target does not hold",
            ))
    return findings


def _bare_segment(path: str) -> str | None:
    """`/10-4-0` -> `10-4-0`. Anything else -> `None`, meaning "not ours"."""
    text = str(path).strip().rstrip("/")
    if not text.startswith("/"):
        return None
    body = text[1:]
    return body if body and "/" not in body and "://" not in body else None


# -- the folder ------------------------------------------------------------------


def check(folder: VersionFolder, index: FolderIndex) -> list[Finding]:
    """Every artifact check that belongs to one published version folder."""
    where = (folder.relative / METADATA).as_posix()
    path = folder.path / METADATA
    key = _METADATA_KEY.get(folder.doc_class, VERSION_KEY)
    if not path.is_file():
        findings = [Finding("METADATA_INVALID", slug=folder.slug, version=folder.segment,
                            path=where, message="is missing")]
    else:
        findings = _check_metadata(path, folder.slug, folder.segment, where, key)

    if folder.doc_class == API_REFERENCES:
        # Copied Javadoc. `metadata.yml` is ours and is checked above; everything
        # else in there belongs to somebody else's generator (§6.2.1).
        return findings
    return findings + _check_toc(folder, index) + _check_redirects(folder, index) + _check_index(folder)
