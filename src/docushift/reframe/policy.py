"""The effective Reframe policy for one product, and the key that invalidates it.

Separated from `ConfigManager` on the same line `load_scope` draws: the manager
reads and shapes files, and the per-row resolution lives with the stage that has
the row in hand. It also keeps the currency key next to the values it is a digest
of, which is the pairing that goes wrong when they drift apart.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from typing import Any

# Only the keys that change the output belong in the digest. A comment edit or a
# reordered mapping must not re-merge 113 pages, and an added field that does
# change the output must not be forgotten -- so this is the dataclass's own fields,
# derived, rather than a second list to keep in step.

#: The exception to that, and it has to argue for itself. `publish` decides whether
#: Stage 7 picks the merged tree up; it does not change a byte of it. In the digest
#: it would re-merge a whole doc set on a sign-off commit -- and invalidate every
#: tree already built, because the field's arrival changes the digest of every
#: policy that does not name it. The default stays "every field counts".
#: `toc_folders` is the same kind of switch: it decides whether an unmerged version
#: goes through the stage at all, not what the stage writes when it does.
_NOT_OUTPUT = frozenset({"publish", "toc_folders"})

#: The packer's boundary rule, versioned. Bumped whenever a *code* change moves a
#: page boundary or a heading level.
#:
#: The digest below is built from config fields, and that is a hole the config
#: cannot see: change the algorithm without touching `reframe.yaml` and every
#: merged tree on disk still reports CURRENT, keeps its old layout for good, and
#: only a `--force` anybody happens to remember will re-cut it. A constant here
#: closes it. Not a `reframe.yaml` field -- a config that could select an
#: algorithm would be two packers to keep alive.
#:
#: 1 = greedy sibling runs (Phase 20). 2 = parent-leads subtrees (Phase 28).
#: 3 = anchors predicted from heading text, no `<a id>` markers (Phase 29).
#: 4 = a title is not replaced by a source stem that truncates it, and a name
#: that does not carry its title queues for review (Phase 34, R1-03). Neither
#: moves a boundary, but both change the tree, and a CURRENT tree would keep
#: the old answer for good.
#: 5 = a link keeps the heading its fragment names when the merge renumbers
#: repeated headings (Phase 34, R9-01, R9-02). Links only, no boundary. The
#: same bump covers R9-03: a page the TOC never lists is named in the folder it
#: is written to, which it now borrows from its guide, so its path moves.
#: 6 = the outer link of a linked image, `[![alt](src)](href)`, is re-pathed
#: (Phase 44). Links only.
#: 7 = a title-only page whose TOC row has children lists them, one link per
#: immediate child (Phase 63). No boundary moves; blank parents gain a body.
#: 8 = a topic opening on its only `##`/`###` keeps that heading as its title
#: instead of gaining a synthesized copy, and no heading skips a level below a
#: synthesized one (Phase 76). Headings and anchors only; no boundary moves.
_ALGORITHM = 8


@dataclass(frozen=True)
class ReframePolicy:
    """What Stage 6b will do to one product, after defaults and overrides."""

    #: The cap a join may not cross (R1.2). Never splits a topic to respect it.
    max_words: int = 3000
    #: Forced TOC dialect, or empty for detection.
    toc_schema: str = ""
    #: R1.4 -- the version whose page layout every other version reuses. Empty means
    #: each version is laid out on its own, which is only safe for a single-version
    #: doc set and raises `REFRAME_LAYOUT_UNPINNED` otherwise.
    pin_layout_to: str = ""
    #: Whether Stage 7 publishes this product's *merged* tree instead of its Stage 6
    #: one. Off by default and left off for every product: opting in is the writer
    #: sign-off the integration plan calls the point of the whole thing (§4 Phase 4),
    #: and a commit to this file is the only form of it the tool can enforce.
    publish: bool = False
    #: 20e. Source paths a writer has taken back out of the merge: a topic at or
    #: under one of these is never joined to anything, so that subtree keeps the
    #: layout Stage 6 gave it. Prefixes, matched on path parts. Held sorted, so
    #: reordering the list in the file is not a re-merge -- the currency key reads
    #: this field, unlike `publish`, because it changes every byte downstream.
    keep_separate: tuple[str, ...] = ()
    #: Phase 76. `keep_separate` entries written with `versions:`, as sorted
    #: `(path, versions)` pairs. Folded into `keep_separate` by `for_version` before
    #: a version is laid out, so a doc set whose versions are shaped differently can
    #: split one of them without the split being projected onto the others.
    keep_separate_in: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: Phase 63. Off for a doc set published unmerged by decision: every TOC row
    #: becomes its own page, and the stage still names pages, lays the folders out
    #: as the TOC and writes the redirects -- the part AEM needs whatever the merge.
    merge: bool = True
    #: Phase 63's rollout switch, per family. On, a version the stage does not merge
    #: -- `merge: false`, or a WebWorks or DocBook one -- is laid out here and
    #: `publish` holds it to that tree; off, it is skipped and publishes its
    #: converted tree, as before the phase. Moves to `defaults` when every family
    #: has rolled out.
    toc_folders: bool = False
    #: Phase 69. A guide's computed top-level name -> the one it publishes under, as
    #: sorted pairs. Its page and its folder move together, before Phase 63's cut, so
    #: the cut works on the short name. Product level only: the names are the ones a
    #: product's own TOC produced.
    guide_names: tuple[tuple[str, str], ...] = ()

    @property
    def key(self) -> str:
        """A short digest of the policy, for currency.

        Stage 6b is current when its input tree is unchanged **and** the policy that
        shaped the output is unchanged. Convert learned the same lesson at
        `convert_api_prefix`: keying on the source alone means a config edit leaves a
        stale tree looking up to date, and the boundary rules here are expected to be
        tuned repeatedly, so that failure would be the common case rather than a
        corner of it.
        """
        shaping: dict[str, Any] = {"algorithm": _ALGORITHM}
        shaping.update({k: v for k, v in asdict(self).items() if k not in _NOT_OUTPUT})
        # Only when off: a field arriving at its default must not change the digest
        # of every policy that does not name it, which would re-cut every merged tree.
        if self.merge:
            del shaping["merge"]
        if not self.guide_names:
            del shaping["guide_names"]
        if not self.keep_separate_in:
            del shaping["keep_separate_in"]
        payload = json.dumps(shaping, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


    def for_version(self, number: str) -> ReframePolicy:
        """This policy as one version sees it: its scoped `keep_separate` entries
        joined to the unscoped ones, and the scoped list then cleared, so a version
        no scoped entry names keeps the digest it would have without them."""
        if not self.keep_separate_in:
            return self
        scoped = {path for path, versions in self.keep_separate_in if number in versions}
        return replace(self, keep_separate=tuple(sorted(set(self.keep_separate) | scoped)),
                       keep_separate_in=())


def policy_for(
    reframe: dict[str, Any], slug: str, bu: str = "", family: str = ""
) -> ReframePolicy:
    """Resolves `ConfigManager.load_reframe()` down to one product's policy.

    Default-then-override, key by key, so a product block naming only
    `pin_layout_to` keeps the shipped `max_words` rather than falling back to the
    dataclass's -- the two agree today and a silent divergence when they stop
    agreeing is the kind of thing that is only noticed as a page-count change.

    Four levels, outside in: defaults, the BU, the family, the product (Phase 42).
    A family block is keyed by the family name alone, so `streaming` would also
    match an IBI family of that name -- none exists, and keying by `bu/family`
    would make the common case harder to read for a collision nobody has.
    """
    values: dict[str, Any] = dict(reframe.get("defaults") or {})
    if bu:
        values.update((reframe.get("bus") or {}).get(bu) or {})
    if family:
        values.update((reframe.get("families") or {}).get(family) or {})
    own: dict[str, Any] = (reframe.get("products") or {}).get(slug) or {}
    values.update(own)

    return ReframePolicy(
        max_words=int(values.get("max_words") or ReframePolicy.max_words),
        toc_schema=str(values.get("toc_schema") or "").strip(),
        pin_layout_to=str(values.get("pin_layout_to") or "").strip(),
        publish=bool(values.get("publish") or False),
        keep_separate=_paths(values.get("keep_separate")),
        keep_separate_in=_scoped(values.get("keep_separate")),
        merge=values.get("merge") is not False,
        toc_folders=bool(values.get("toc_folders") or False),
        guide_names=_names(own.get("guide_names")),
    )


def _names(value: Any) -> tuple[tuple[str, str], ...]:
    """The `guide_names` mapping as sorted `(computed, wanted)` pairs.

    Sorted because the digest reads it; blank or non-string entries are dropped
    rather than guessed at. A `.md` typed on either side is the same name.
    """
    if not isinstance(value, dict):
        return ()
    pairs = {(str(old).strip().removesuffix(".md"), str(new).strip().removesuffix(".md"))
             for old, new in value.items()}
    return tuple(sorted((old, new) for old, new in pairs if old and new and old != new))


def _paths(value: Any) -> tuple[str, ...]:
    """The `keep_separate` list, normalized: POSIX, no slashes at either end, sorted.

    De-duplicated and sorted because the digest reads it, and a writer moving a
    line to group it with its neighbours is not a layout change. A single string
    is accepted as a one-entry list -- YAML makes that mistake easy and the intent
    is never ambiguous.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return ()
    cleaned = {_one(entry) for entry in value if not isinstance(entry, dict)}
    return tuple(sorted(path for path in cleaned if path))


def _scoped(value: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """`keep_separate` entries written as `{path: ..., versions: [...]}` (Phase 76).

    Sorted for the digest. An entry with no usable `versions` is dropped rather
    than widened to every version: a writer who scoped a split did not ask for it
    everywhere.
    """
    if not isinstance(value, list):
        return ()
    pairs: dict[str, set[str]] = {}
    for entry in value:
        if not isinstance(entry, dict):
            continue
        path = _one(entry.get("path", ""))
        versions = entry.get("versions")
        if isinstance(versions, (str, int, float)):
            versions = [versions]
        named = {str(v).strip() for v in versions or [] if str(v).strip()}
        if path and named:
            pairs.setdefault(path, set()).update(named)
    return tuple(sorted((path, tuple(sorted(named))) for path, named in pairs.items()))


def _one(entry: Any) -> str:
    """One path, spelled the way `sections[].source` spells it.

    Windows separators, surrounding whitespace, a leading `/` and a copied-in
    `./` are all the same path written differently, so they are normalized away
    rather than warned about. A bare stem is not: `users-guide/monitor` names a
    directory and never `monitor.md`, because guessing there would mean the same
    line taking out different topics depending on what is on disk.
    """
    path = str(entry).strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.strip("/")
