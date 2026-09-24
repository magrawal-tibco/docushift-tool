"""`csh.yml` retargeted onto the merged pages (planning.md 20f).

A context-sensitive help map is `{identifier: path/to/topic.md#anchor}`, written
by `transforms/csh.py` at conversion time and read by the product itself: an F1
keypress resolves an identifier to a URL. Merging moves the topic into a section
of a larger page, so the map has to move with it or every Help button in the
application lands on a file that is no longer there.

**It is not `toc.yml` and it is not `redirects.yml`, and the difference is the
fragment.** A TOC node *is* the section it points at, so `toc.retarget` gives it
the section anchor; `redirects.yml` does the same, because a reader following an
old topic URL wants the section that replaced it. A CSH identifier points at its
**own** `<a id="…">` marker, which `transforms/csh.py` wrote into the topic body
and which travels into the merged page with that body -- measured at 108 of 108
on `tibco-runtime-agent@5.13.0`. That marker is a more precise landing point than
the section heading, so only the path half is rewritten. Which is why the
redirect map, the obvious source for a rewrite that turns old paths into new
ones, is the wrong one to use here.

A value with no fragment at all falls back to the section anchor, because the
alternative is a Help button that opens a twelve-section page at the top. None of
the Flare sets measured has one; `tibco-runtime-agent@5.12.2` has 18 of 108, so
the shape is real in this corpus and merely belongs to another engine.

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
    "# `docushift reframe` (planning.md 20f). Each identifier keeps its own\n"
    "# anchor; only the page it lives on has changed.\n"
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
    target, separator, fragment = value.partition("#")
    found = located.get(PurePosixPath(target))
    if found is None:
        return value
    page, anchor = found
    return f"{page.path}#{fragment if separator else anchor}"


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
