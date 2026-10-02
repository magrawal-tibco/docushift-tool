"""The effective Reframe policy for one product, and the key that invalidates it.

Separated from `ConfigManager` on the same line `load_scope` draws: the manager
reads and shapes files, and the per-row resolution lives with the stage that has
the row in hand. It also keeps the currency key next to the values it is a digest
of, which is the pairing that goes wrong when they drift apart.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
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
_NOT_OUTPUT = frozenset({"publish"})

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
_ALGORITHM = 4


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
        payload = json.dumps(shaping, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def policy_for(reframe: dict[str, Any], slug: str) -> ReframePolicy:
    """Resolves `ConfigManager.load_reframe()` down to one product's policy.

    Default-then-override, key by key, so a product block naming only
    `pin_layout_to` keeps the shipped `max_words` rather than falling back to the
    dataclass's -- the two agree today and a silent divergence when they stop
    agreeing is the kind of thing that is only noticed as a page-count change.
    """
    values: dict[str, Any] = dict(reframe.get("defaults") or {})
    values.update((reframe.get("products") or {}).get(slug) or {})

    return ReframePolicy(
        max_words=int(values.get("max_words") or ReframePolicy.max_words),
        toc_schema=str(values.get("toc_schema") or "").strip(),
        pin_layout_to=str(values.get("pin_layout_to") or "").strip(),
        publish=bool(values.get("publish") or False),
        keep_separate=_paths(values.get("keep_separate")),
    )


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
    cleaned = {_one(entry) for entry in value}
    return tuple(sorted(path for path in cleaned if path))


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
