"""`csh.yml` retargeted onto the merged pages (planning.md 20f).

A context-sensitive help map is `{identifier: path/to/topic.md#anchor}`, written
by `transforms/csh.py` at conversion time and read by the product itself: an F1
keypress resolves an identifier to a URL. Merging moves the topic into a section
of a larger page, so the map has to move with it or every Help button in the
application lands on a file that is no longer there.

**Every value gets its topic's section anchor (Phase 29)**, the same answer
`toc.retarget` and `redirects.yml` give. It used to keep the identifier's own
fragment, on the reasoning that it named an `<a id="…">` marker which travels
into the merged page with the topic body and is a more precise landing point
than the section heading. The platform ignores those markers and anchors on
heading text only, so a kept fragment resolved nowhere -- 0 of 154 -- and
`_value` below explains the change. A value with no fragment at all gets the
same section anchor. Measured on the merged corpus: all 154 values equal their
source topic's section anchor (R9-13). Since convert retargets the map onto
headings (R8-04), a fragment naming a heading of its topic keeps that heading
instead (X1-04).

An identifier whose topic the packer never placed keeps its value untouched and
is reported by the audit, which is `toc.retarget`'s rule for the same condition:
this module does not decide what to do about a broken map, it only declines to
invent a destination.
"""

from pathlib import Path, PurePosixPath
from typing import Any

import yaml

#: The file `transforms/csh.py` writes and this module rewrites. Same name in the
#: converted tree and the merged one -- a consumer holding a URL to it should not
#: have to know which stage produced the tree behind it.
CSH_FILE = "csh.yml"

CSH_HEADER = (
    "# Context-sensitive help map -- retargeted onto the merged pages by\n"
    "# `docushift reframe` (planning.md 20f). Each identifier points at the\n"
    "# section its topic became: the merged page and that section's anchor.\n"
)


class Unreadable(Exception):
    """The converted tree has a `csh.yml` this stage cannot parse.

    Distinct from having none, and deliberately not swallowed. The three
    alternatives are all worse: writing nothing deletes every Help button from
    the merged tree with no record, copying the file through republishes the
    pre-merge paths this module exists to fix, and guessing at a half-parsed map
    silently loses whichever identifiers were on the far side of the error.
    Reframe already treats an unreadable `toc.yml` as a failure rather than a
    skip, and this is the same file class and the same argument -- the run fails,
    nothing is swapped, and the previous merge stands.
    """


def load(root: Path) -> dict[str, str] | None:
    """The converted tree's map, or `None` when it has none. Raises `Unreadable`.

    Values are stringified rather than validated: a map whose shape is wrong in
    some subtler way is `validate`'s to report against the tree that shipped, and
    two implementations of that judgement would be two answers to one question.
    """
    path = root / CSH_FILE
    if not path.is_file():
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as error:
        raise Unreadable(f"{path} does not parse: {error}") from error
    if not isinstance(loaded, dict):
        raise Unreadable(f"{path} is not a mapping of identifier to path")
    return {str(key): str(value) for key, value in loaded.items()}


def retarget(mapping: dict[str, str], located: dict[PurePosixPath, tuple[Any, str]]) -> dict[str, str]:
    """The map with every value pointed at the page its topic became a section of.

    Insertion order is the source map's, so a reviewer diffing the converted file
    against the merged one reads one changed value per line rather than a
    reordering. Identifier text is never touched -- §9.6's rule is that a Help
    button may move and may never disappear.
    """
    return {identifier: _value(value, located) for identifier, value in mapping.items()}


def _value(value: str, located: dict[PurePosixPath, tuple[Any, str]]) -> str:
    """One identifier's new target: the merged page, and the section it became.

    **The identifier's own fragment is dropped (Phase 29).** It used to be kept
    where the source map had one, on the reasoning that a help author who named a
    precise spot meant it. The spot was a Flare alias -- `aa.advisory.helpurl` --
    backed by an `<a id>` marker, and the platform generates anchors from heading
    text and ignores markers entirely. Measured on the merged corpus the moment
    that was confirmed: **0 of 154 identifiers resolved.** Every Help button in
    every published set landed nowhere.

    So a marker fragment becomes the section anchor. A reader arrives at the
    topic's own heading instead of at a spot part-way down it, which is less
    precise than the author asked for and is the whole of what the platform can
    express. §9.6's rule is that a Help button may move and may never disappear;
    keeping an unreachable fragment was the disappearing case.

    **A fragment that names a heading is kept, renumbered as the merge renumbers
    it (X1-04).** Since R8-04 convert writes the heading a marker belongs to
    rather than the marker, so the fragment is now reachable and is the section
    the Help button means. Dropping it put all eight of TRA Runtime Agent
    5.13.0's `aa.txcontrolpool.*` on one section, and 27 of its 108 identifiers
    lost theirs. The same lookup a link's fragment takes (`pages._retarget`,
    R9-02).
    """
    target, _separator, fragment = value.partition("#")
    found = located.get(PurePosixPath(target))
    if found is None:
        return value
    page, anchor = found
    if fragment:
        anchor = page.heading(PurePosixPath(target), fragment) or anchor
    return f"{page.path}#{anchor}"


def by_topic(mapping: dict[str, str]) -> dict[PurePosixPath, list[str]]:
    """`{source topic -> its identifiers, sorted}`, for §9.5's frontmatter mirror.

    Sorted rather than left in map order because the merged page unions several
    topics' lists and `reframe` is byte-deterministic (C5); map order would make
    the frontmatter depend on how `transforms/csh.py` happened to walk the source.
    """
    grouped: dict[PurePosixPath, list[str]] = {}
    for identifier, value in mapping.items():
        grouped.setdefault(PurePosixPath(value.partition("#")[0]), []).append(identifier)
    return {topic: sorted(identifiers) for topic, identifiers in grouped.items()}
