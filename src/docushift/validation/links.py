"""Does every link in a published version folder point at something?

`design.md` §8.4, measured. The checker is a pure function over one folder: it
takes a `VersionFolder` and a context and hands back findings, and it holds no
`CatalogManager`, no `StateStore` and no `FindingsRun` -- the driver records what
it returns. That is what makes it testable against a fixture directory in three
lines, and it is the separation `sync/` already keeps between `router.py` and
`distributor.py`.

Four rules decide what is a defect, and the sample tree of 2026-09-16 decided
three of them:

- **A reference whose raw first segment names a published tree is a host-less
  URL, and it resolves against the target root.** This is the highest-value rule
  in the phase. With `publish_base_url` empty -- the shipped state -- a rewritten
  API link is a tree-rooted path with no host (`architecture.md` §6.4.2), which
  `links.classify()` rightly calls RELATIVE. Resolve it against the citing page's
  own directory and you get `html/apiguide/en-us-…-resources/…`, which exists
  nowhere: **121 of the sample's 123 broken links were exactly that mistake.**
  The test has to run on the *raw* path, before `resolve()`, because afterwards
  the tree name is buried behind the page's directory and the rule cannot fire.
  Resolving rather than merely skipping is the bonus -- it catches help pointing
  into an API tree nobody synced, which nothing else in the tool would notice.
- **Resolution is case-sensitive, on every platform.** The target is published to
  Linux. A link differing from its file only in case resolves on the developer's
  Windows machine and 404s in production, which is precisely the defect class a
  linter is for. Where a case-insensitive match exists the message names the file
  that is actually there, so the fix is one rename rather than a search.
- **A missing file is an error; a missing anchor is a warning.** 1,626 of the
  sample's 14,055 fragments do not resolve -- 11.6% -- and an 11.6% rate cannot
  gate. They are still worth raising: spot-checks say these are anchors the
  conversion genuinely dropped rather than slug-algorithm disagreement, which
  makes `ANCHOR_MISSING` the first measurement of a defect nobody had counted.
- **Absolute URLs are skipped and counted; only `--check-external` puts them on
  the wire.** 1,676 in the sample, and after §10.7 every link into an API
  reference on a configured host is one of these. An exit code that depends on the
  network is an exit code nobody trusts, so `LINK_EXTERNAL_DEAD` is a warning.

`api-references/` is not walked here at all -- see `driver.py`. It is copied
Javadoc, not this tool's output.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from docushift.reporting.findings import Finding
from docushift.transforms import links as refs
from docushift.validation import references
from docushift.validation.tree import VersionFolder

# Only a Markdown target can have its anchors computed. A fragment onto a `.html`
# in a copied API tree is not this tool's output and is not read.
_ANCHORED = (".md",)


@dataclass
class LinkContext:
    """Everything the checker needs that is not the folder itself."""

    target: Path
    # Top-level directory names in `--target-dir`. A raw reference starting with
    # one of these is a host-less published URL (§6.4.2).
    trees: set[str] = field(default_factory=set)
    # Absolute URLs seen this run, deduplicated. Populated whether or not
    # `--check-external` is set, because the count is worth reporting either way
    # and the set is what the flag would work through.
    external: set[str] = field(default_factory=set)


@dataclass
class LinkReport:
    """One folder's findings, plus the counts a run report prints."""

    findings: list[Finding] = field(default_factory=list)
    files: int = 0
    references: int = 0
    html: int = 0
    absolute: int = 0
    tree_rooted: int = 0
    fragments: int = 0
    anchors_matched: int = 0

    def extend(self, other: "LinkReport") -> None:
        self.findings.extend(other.findings)
        for name in ("files", "references", "html", "absolute", "tree_rooted",
                     "fragments", "anchors_matched"):
            setattr(self, name, getattr(self, name) + getattr(other, name))


class FolderIndex:
    """One version folder's files, read once.

    Three indexes over one `rglob`, because the checker asks three questions of
    every reference and re-walking for each would turn an 84-second run into a
    three-hour one. The anchor cache is the same bargain one level down: a page
    cited by two hundred siblings is parsed once.
    """

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.present: set[str] = set()
        self._folded: dict[str, str] = {}
        self._anchors: dict[str, set[str]] = {}
        for path in folder.rglob("*"):
            if path.is_file():
                relative = path.relative_to(folder).as_posix()
                self.present.add(relative)
                # First writer wins. Two files differing only in case cannot both
                # exist on Windows, and on Linux either one proves the reference
                # is resolvable in *some* casing, which is all this index claims.
                self._folded.setdefault(relative.lower(), relative)

    def actual_case(self, relative: str) -> str | None:
        """The file that is there, when only its casing differs. `None` otherwise."""
        return self._folded.get(relative.lower())

    def anchors(self, relative: str) -> set[str]:
        cached = self._anchors.get(relative)
        if cached is None:
            try:
                text = (self.folder / relative).read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - the file was just listed
                text = ""
            cached = references.anchors(text)
            self._anchors[relative] = cached
        return cached


def check(
    folder: VersionFolder,
    context: LinkContext,
    index: FolderIndex | None = None,
) -> LinkReport:
    """Every Markdown file in one version folder, checked against what is there."""
    index = index if index is not None else FolderIndex(folder.path)
    report = LinkReport()
    for path in sorted(folder.path.rglob("*.md")):
        report.extend(_check_file(folder, context, index, path))
    return report


def _check_file(
    folder: VersionFolder, context: LinkContext, index: FolderIndex, path: Path
) -> LinkReport:
    report = LinkReport(files=1)
    relative = path.relative_to(folder.path).as_posix()
    base = PurePosixPath(relative).parent
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover
        return report

    def issue(code: str, line: int, message: str) -> None:
        report.findings.append(
            Finding(
                code,
                slug=folder.slug,
                version=folder.segment,
                path=f"{folder.rel(path)}:{line}",
                message=message,
            )
        )

    for reference in references.references(text):
        report.references += 1
        report.html += reference.syntax == "html"
        classified = refs.classify(reference.raw)

        if classified.kind is refs.ReferenceKind.EMPTY:
            continue
        if classified.kind is refs.ReferenceKind.ABSOLUTE:
            report.absolute += 1
            context.external.add(reference.raw.strip())
            continue
        if classified.kind is refs.ReferenceKind.ROOTED:
            # `/foo/bar` cannot be resolved inside an output root and
            # `transforms/links.py` already treats it as external. Counted with
            # the absolute ones so the report's arithmetic closes.
            report.absolute += 1
            continue
        if classified.kind is refs.ReferenceKind.FRAGMENT:
            report.fragments += 1
            if classified.fragment.lower() in index.anchors(relative):
                report.anchors_matched += 1
            else:
                issue(
                    "ANCHOR_MISSING",
                    reference.line,
                    f"#{classified.fragment} is not an anchor in this page",
                )
            continue

        head = PurePosixPath(classified.path).parts[0] if classified.path else ""
        if head in context.trees:
            report.tree_rooted += 1
            if not (context.target / classified.path).exists():
                issue(
                    "LINK_BROKEN",
                    reference.line,
                    f"{classified.path} names a published tree this target does not hold",
                )
            continue

        resolved = refs.resolve(base, classified.path)
        if refs.escapes(resolved):
            issue(
                "LINK_BROKEN",
                reference.line,
                f"{reference.raw} climbs out of the published version folder",
            )
            continue

        target = str(resolved)
        if target not in index.present:
            actual = index.actual_case(target)
            if actual is not None:
                issue(
                    "LINK_BROKEN",
                    reference.line,
                    f"{target} differs only in case from {actual}, which will 404 on Linux",
                )
            else:
                issue("LINK_BROKEN", reference.line, f"{target} is not in this version folder")
            continue

        if classified.fragment:
            report.fragments += 1
            if PurePosixPath(target).suffix.lower() not in _ANCHORED:
                continue
            if classified.fragment.lower() in index.anchors(target):
                report.anchors_matched += 1
            else:
                issue(
                    "ANCHOR_MISSING",
                    reference.line,
                    f"#{classified.fragment} is not an anchor in {target}",
                )
    return report


# -- the external pass ---------------------------------------------------------

# `(url) -> reachable`. Injected rather than imported so a test can assert the
# default path makes no call at all by handing in one that raises.
Fetcher = Callable[[str], bool]


def check_external(urls: set[str], fetch: Fetcher) -> list[Finding]:
    """`--check-external`: one request per distinct URL, for the whole run.

    Deduplicated across every folder rather than per folder, because a boilerplate
    support link appears in all 10,190 pages of the sample and checking it ten
    thousand times is a denial-of-service attack on a colleague's web server.
    """
    findings: list[Finding] = []
    for url in sorted(urls):
        if not url.lower().startswith(("http://", "https://")):
            # `mailto:`, `data:`, `javascript:` and the rest have nothing to
            # request. Skipped silently: they are not defects and never were.
            continue
        if not fetch(url):
            findings.append(
                Finding("LINK_EXTERNAL_DEAD", path=url, message="did not respond to HEAD or GET")
            )
    return findings
