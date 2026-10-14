"""One resolution, two outputs: the copy set *is* what the Markdown references.

`design.md` §6.4 steps 3-7 and invariant 13. The whole module exists to make one
sentence structurally true: **a relative asset link exists in the output if and
only if that asset was copied.** Both come out of the same call, in the pass that
emits the topic -- or neither does, plus a counted failure.

The failure being designed out is the predecessor's, and it is worth naming
because it is not an obvious bug. `html-to-md` copies assets in one pass and
rewrites links in another, each re-deriving the destination from a URL and a cache
layout; the two disagree on 7,231 of 23,172 image links, 7,223 of them in a single
product, and nothing anywhere says so (`architecture.md` §5.5.9). Two passes over
one question is the defect; a second pass that is *careful* would still be one.

Five branches, in the order §6.4 step 3 fixes, and the order matters:

1. External or `data:` -- emitted unchanged, never copied.
2. Normalize: strip `#fragment`/`?query`, percent-decode, `\\` -> `/`. Skipping this
   reports 1,872 WebWorks references as missing that are not.
3. Resolve against the topic's own directory.
4. Escape check: a resolved path starting `..` leaves the output root and is handed
   to Stage 7 with its absolute source path (§10.7), not emitted.
5. **Skin check before the existence test**, whole-segment, against
   `engines/roots.SKIN_PREFIXES`. A `.gif` in `Skins/` is chrome and must be
   dropped rather than reported missing.

§6.4 step 3 lists the skin check ahead of the escape check; here they are the other
way round, which is the same algorithm. The two branches cannot both match -- a
path leading with `..` matches no root-relative skin prefix -- so the order between
them is free, and only their position *before* the existence test carries meaning.

Then step 4's two outputs, step 5's per-root counts, step 6's case check --
corrected to the file's spelling since Phase 52 (399 in one version), and still
counted -- and step 7's orphans, which
are reported and never copied: 54.6% of Flare's images and 673 MB.
"""

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath

from docushift.engines.roots import is_skin_path
from docushift.models import SourceEngine
from docushift.transforms import links
from docushift.utils.longpath import PUBLISHED_PATH_LIMIT, long_path

# Files the copy set never contains and the orphan count never mentions: they are
# either the input to conversion or the output of it.
_NOT_AN_ASSET = frozenset({".htm", ".html", ".xhtml", ".md"})


class AssetOutcome(StrEnum):
    """What happened to one reference. Every reference gets exactly one."""

    RESOLVED = "resolved"
    # Engine chrome. Dropped, not copied, and explicitly *not* counted as missing.
    SKIN = "skin"
    # Left the output root. Handed to Stage 7 with its resolved source path.
    ESCAPED = "escaped"
    # Resolved to nothing on disk. Neither link nor copy, and counted.
    DANGLING = "dangling"
    # http/https/mailto/data, or a server-absolute path. Emitted verbatim.
    EXTERNAL = "external"
    # `#anchor` or an empty href. Not an asset at all.
    NOT_A_REFERENCE = "not-a-reference"


@dataclass
class Resolution:
    """The answer to one reference, and everything the caller may emit from it."""

    outcome: AssetOutcome
    # The URL to put in the Markdown, or "" when there must not be one.
    url: str = ""
    # The file to copy, absolute. Set only on RESOLVED.
    source: Path | None = None
    # Where it goes, relative to the unit's subtree. The *same* relative path it
    # had in the source -- never flattened, and renamed only when that path could
    # not be published at all (Phase 49, `shortened`).
    target: PurePosixPath | None = None
    # Resolved, but the reference spells it differently from the file. Works on
    # this Windows cache and 404s after publishing. 14 corpus-wide.
    case_mismatch: bool = False

    @property
    def emits(self) -> bool:
        return bool(self.url)


@dataclass
class Counts:
    """§6.4 step 5, per output root."""

    resolved: int = 0
    skin: int = 0
    escaped: int = 0
    dangling: int = 0
    external: int = 0
    case_mismatch: int = 0
    orphan_files: int = 0
    orphan_bytes: int = 0
    # Dangling references by **top path segment**, because a total hides the
    # corpus's actual failure shape: 2,706 of Flare's 2,905 come from one tree
    # that is broken in its own source and the remaining rate is 0.37%.
    dangling_by_segment: dict[str, int] = field(default_factory=dict)
    #: Resolved only after dropping a page-named folder segment (Phase 47).
    page_segment_dropped: int = 0


class AssetCopier:
    """Resolves references for one unit of work, and copies exactly what resolved.

    Constructed per unit rather than per version, because the copy set, the counts
    and the orphan sweep are all "inside this output root" questions -- and because
    Flare's roots overlap: 30,736 relative paths are shared between two roots of
    the same version and ~15% of them are genuinely different content, so a shared
    copy set would silently pick one release's file for both.
    """

    def __init__(self, root: Path, engine: SourceEngine, destination: Path, published: int = 0):
        self.root = root
        self.engine = engine
        self.destination = destination
        # Phase 49. The length of the folder this unit publishes to, the way
        # `published_length` counts it; 0 when it is not known, which renames
        # nothing.
        self.published = published
        # Source path -> the shorter target it was given, for the few assets whose
        # source path would publish past the limit.
        self.renamed: dict[PurePosixPath, PurePosixPath] = {}
        self.counts = Counts()
        # target -> source. A dict, so two topics referencing one image copy it
        # once; keyed on the target, so a collision is impossible by construction.
        self.copy_set: dict[PurePosixPath, Path] = {}
        # Resolved absolute source paths of references that left the root, with
        # the topic that made them. Stage 7 routes these (§10.7).
        self.escaped: list[tuple[Path, Path]] = []
        self._listings: dict[Path, dict[str, str]] = {}

    # -- one reference ---------------------------------------------------------

    def resolve(self, topic: Path, topic_output: PurePosixPath, raw: str) -> Resolution:
        """Resolves one raw `src`/`href` from `topic`. Never raises.

        `topic` is the absolute source HTML path; `topic_output` is where that
        topic will be written, relative to the unit's subtree, because the emitted
        URL is the path *from the emitted topic to the emitted asset* and neither
        end is the source layout.
        """
        reference = links.classify(raw)
        if reference.kind in (links.ReferenceKind.ABSOLUTE, links.ReferenceKind.ROOTED):
            self.counts.external += 1
            return Resolution(AssetOutcome.EXTERNAL, url=reference.raw.strip())
        if not reference.resolvable:
            return Resolution(AssetOutcome.NOT_A_REFERENCE)

        base = PurePosixPath(topic.parent.relative_to(self.root).as_posix())
        resolved = links.resolve(base, reference.path)

        if links.escapes(resolved):
            self.counts.escaped += 1
            absolute = Path(os.path.normpath(topic.parent / reference.path))
            self.escaped.append((absolute, topic))
            return Resolution(AssetOutcome.ESCAPED)

        # Skin *before* existence: chrome that is missing is still chrome, and
        # reporting it as a dangling reference would put 76.2% of WebWorks'
        # references into the failure column.
        if is_skin_path(resolved.parts, self.engine):
            self.counts.skin += 1
            return Resolution(AssetOutcome.SKIN)

        candidate = self.root / Path(*resolved.parts)
        # `long_path` (X2-08): an asset past 260 characters is on disk, and the
        # plain spelling would count it dangling.
        if not long_path(candidate).is_file():
            retry = links.without_page_segments(resolved)
            if retry is not None and long_path(self.root / Path(*retry.parts)).is_file():
                self.counts.page_segment_dropped += 1
                resolved, candidate = retry, self.root / Path(*retry.parts)
        if not long_path(candidate).is_file():
            self.counts.dangling += 1
            segment = resolved.parts[0] if len(resolved.parts) > 1 else "."
            self.counts.dangling_by_segment[segment] = (
                self.counts.dangling_by_segment.get(segment, 0) + 1
            )
            return Resolution(AssetOutcome.DANGLING)

        # Phase 52: published under the file's own spelling, as page links are
        # (R5-06). Product and Service Catalog 5.1.0 links `html-opd/` 399 times
        # into `html-OPD/`, which Windows resolves and AEM 404s.
        actual = self._on_disk(resolved)
        mismatch = actual is not None and actual != resolved
        if mismatch:
            self.counts.case_mismatch += 1
            resolved = actual
        self.counts.resolved += 1
        target = self._publishable(resolved)
        self.copy_set[target] = candidate
        return Resolution(
            AssetOutcome.RESOLVED,
            url=links.emit(links.relative_to(topic_output, target), reference.fragment),
            source=candidate,
            target=target,
            case_mismatch=mismatch,
        )

    # -- a path too long to publish (Phase 49) ----------------------------------

    def _publishable(self, resolved: PurePosixPath) -> PurePosixPath:
        """`resolved`, or a shorter name in the same folder when it cannot be published.

        The one exception to "never renamed": `sync` refuses a whole version over a
        single file past `PUBLISHED_PATH_LIMIT`, and an image, unlike a page, has no
        `rename-map.csv`. The name is cut to fit and given the first 8 hex digits of
        the SHA-256 of the source path, so a re-run writes the same name and two
        cut names cannot collide. Decided here, in the one resolution that writes
        both the link and the copy, so the two cannot disagree (invariant 13).
        """
        if resolved in self.renamed:
            return self.renamed[resolved]
        length = self.published + 1 + len(str(resolved))
        if not self.published or length <= PUBLISHED_PATH_LIMIT:
            return resolved
        tag = "-" + hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:8]
        name = PurePosixPath(resolved.name)
        keep = len(name.stem) - (length - PUBLISHED_PATH_LIMIT) - len(tag)
        stem = name.stem[:max(keep, 0)].rstrip(" .-_")
        shorter = resolved.with_name((stem + tag if stem else tag[1:]) + name.suffix)
        # A folder too long on its own leaves nothing to cut. The source name is
        # kept, and `sync` names the file when it refuses the version.
        if len(str(shorter)) >= len(str(resolved)):
            return resolved
        self.renamed[resolved] = shorter
        return shorter

    # -- case, checked and corrected (§6.4 step 6, Phase 52) ---------------------

    def _on_disk(self, resolved: PurePosixPath) -> PurePosixPath | None:
        """`resolved` as the filesystem spells it, or None when a segment is not listed.

        Walked segment by segment against real directory listings, because the
        extracted cache is on Windows: `candidate.is_file()` succeeds on the wrong
        casing, and the mismatch only shows up as a 404 after publishing.
        """
        current = self.root
        spelled: list[str] = []
        for part in resolved.parts:
            actual = self._listing(current).get(part.lower())
            if actual is None:
                return None
            spelled.append(actual)
            current = current / actual
        return PurePosixPath(*spelled)

    def _listing(self, directory: Path) -> dict[str, str]:
        cached = self._listings.get(directory)
        if cached is None:
            try:
                cached = {entry.name.lower(): entry.name for entry in os.scandir(directory)}
            except OSError:
                cached = {}
            self._listings[directory] = cached
        return cached

    # -- the copy (§6.4 step 4) -------------------------------------------------

    def copy(self) -> int:
        """Copies the set. Returns how many files landed.

        Run after the topic loop rather than per reference, so that one image
        referenced by 400 topics is read once -- and so that a run that failed
        mid-conversion has written no assets for a tree it did not finish.
        """
        written = 0
        for target, source in sorted(self.copy_set.items()):
            landing = long_path(self.destination / Path(*target.parts))
            try:
                landing.parent.mkdir(parents=True, exist_ok=True)
                # Both ends prefixed (X2-08): a plain `copy2` of a long source
                # failed and was counted as a dangling reference.
                shutil.copy2(long_path(source), landing)
            except OSError:
                # A copy that fails is a dangling link by invariant 13, and the
                # emitted Markdown already claims otherwise. Counted here so the
                # report says so rather than the reader discovering it.
                self.counts.resolved -= 1
                self.counts.dangling += 1
                continue
            written += 1
        return written

    # -- orphans (§6.4 step 7) --------------------------------------------------

    def orphans(self) -> list[tuple[PurePosixPath, int]]:
        """Assets on disk inside the root that the copy set does not contain.

        Topics and Markdown are excluded -- they are conversion's input and output,
        not assets -- and so is chrome, which was never a candidate. What is left
        is the honest orphan population: 54.6% of Flare's images by count and
        673 MB by size, which is the authoring tool's design and not a defect,
        which is exactly why it is a `note` and never copied.
        """
        found: list[tuple[PurePosixPath, int]] = []
        stack = [self.root]
        while stack:
            current = stack.pop()
            try:
                entries = list(os.scandir(current))
            except OSError:
                continue
            for entry in entries:
                path = Path(entry.path)
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(path)
                        continue
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
                relative = PurePosixPath(path.relative_to(self.root).as_posix())
                if path.suffix.lower() in _NOT_AN_ASSET:
                    continue
                if is_skin_path(relative.parts, self.engine):
                    continue
                if relative in self.copy_set or relative in self.renamed:
                    continue
                found.append((relative, size))
        found.sort()
        self.counts.orphan_files = len(found)
        self.counts.orphan_bytes = sum(size for _, size in found)
        return found
