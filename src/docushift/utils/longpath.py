"""Windows's 260-character path limit, and the one prefix that lifts it.

Phase 14b, and found the hard way: `extract --family ems` failed on all six
versions with `FileNotFoundError`, on a machine where every extracted path was
*legal*. The arithmetic is the whole story. The deepest member of the EMS 10.5.1
package lands at **257 characters** under its final directory -- five under the
limit -- but extraction builds into a staging sibling named `<target>.part`
(`extractor/unpacker.py`), and those five extra characters put the same member at
**262**. The tree that could not be written is one that, once swapped into place,
fits. `HKLM\\...\\FileSystem\\LongPathsEnabled` reads `0x0` here, so the Win32
layer enforces the limit rather than the filesystem, which is what makes this a
call-site problem rather than a machine problem.

Prefixing a path with `\\\\?\\` tells Win32 to hand it to the filesystem
unparsed, and the limit becomes the filesystem's ~32,767. The cost is exactly
that "unparsed": the OS does no normalization at all, so `..`, a forward slash,
or a relative segment reaching such a path is not resolved but taken literally.
`long_path` therefore absolutizes and normalizes *before* prefixing, and never
after.

**The traversal refusal stays in front of this, not behind it.** `safe_unzip`
rejects an escaping member by name before any path is built, which has to remain
true: a `..` that reached a prefixed path would no longer be collapsed by the OS,
so the prefix makes the check more load-bearing rather than less.

Scoped deliberately to the two places that *write* a staged tree -- unpacking and
the swap. A final extracted path over 260 characters would still be unreadable to
every consumer downstream, and that is a condition to report rather than to paper
over one call site at a time.
"""

import os
from collections.abc import Iterator
from pathlib import Path

# Win32's escape from MAX_PATH. `\\?\UNC\server\share` is its form for a network
# path, whose `\\server\share` spelling the prefix cannot represent directly.
_PREFIX = "\\\\?\\"
_UNC_PREFIX = _PREFIX + "UNC" + os.sep


def long_path(path: "Path | str") -> Path:
    """The same location, spelled so Windows will accept it at any length.

    A no-op everywhere but Windows, and idempotent: a path that already carries
    the prefix is returned unchanged, so a helper may be applied twice without
    building `\\\\?\\C:\\...\\\\?\\C:\\...`.
    """
    if os.name != "nt":
        return Path(path)

    text = os.path.abspath(path)
    if text.startswith(_PREFIX):
        return Path(text)
    if text.startswith("\\\\"):
        return Path(_UNC_PREFIX + text[2:])
    return Path(_PREFIX + text)


def walk_files(root: Path) -> Iterator[tuple[Path, Path]]:
    """`(relative, absolute)` for every file under `root` -- including the long ones.

    Phase 15e, and the reason this is a helper rather than an `rglob` at each call
    site. `Path.rglob` reaches each directory through the *unprefixed* spelling, so
    on Windows it simply omits a file whose own path is over the limit, and it
    omits it **silently** -- no exception, no warning, a shorter list. Measured on
    one EMS API tree: 798 entries plain, **801** through the prefix.

    That silence is what made it a defect rather than an inconvenience. `sync`'s
    own ceiling check walked with `rglob`, so it could not see the three files that
    then broke the copy; `apirefs.measure` undercounted every tree by the same
    three, which would have made a published tree compare unequal to its source on
    every subsequent run.

    The `absolute` half carries the prefix, because that is the only spelling those
    files can be opened by. The `relative` half does not, and is what a caller
    should put in a message: `\\\\?\\` in a report is this tool's plumbing, not the
    reader's path.
    """
    base = long_path(root)
    for path in base.rglob("*"):
        try:
            if not path.is_file():
                continue
        except OSError:  # pragma: no cover - a file that vanished mid-walk
            continue
        yield path.relative_to(base), path


# Phase 15d. The ceiling a *published* path is measured against, and the one
# number in this module that is not about the machine `sync` happens to run on.
# The published tree is read on Windows by the documentation team whatever built
# it, so the limit is a property of the consumer; enforcing it only under
# `os.name == "nt"` would let a Linux runner write a tree its readers cannot
# open, and silently. 260 is the Win32 value, counted the way Win32 counts it --
# the whole absolute path, the drive letter included.
PUBLISHED_PATH_LIMIT = 260


def over_limit(destination: Path, source: Path, limit: int = PUBLISHED_PATH_LIMIT) -> tuple[Path, int] | None:
    """The first file in `source` whose published path would exceed the ceiling.

    Returns `(path, length)` for the offender, or `None` when the whole tree fits.
    Measured against where each file *will* land, not where it currently is: the
    extracted tree sits under a short workspace path and the published one under
    whatever root the user chose, so the source's own lengths say nothing.

    The ceiling is deliberately **not** lifted with `long_path`. This is a final
    path, not the transient staging overflow of Phase 14b: nothing downstream of
    `sync` -- including readers outside this tool -- could open what the prefix
    would let us write. See `architecture.md` §4.4.

    The *walk*, on the other hand, goes through the prefix (Phase 15e), and the
    two are not in tension: the prefix is how the source tree is read, and the
    limit is what the destination is held to. A check that could not see the
    longest files in the tree it was checking was the worst of both.
    """
    if not source.is_dir():
        return None
    base = len(str(destination))
    for relative, _ in walk_files(source):
        length = base + 1 + len(str(relative))
        if length > limit:
            return source / relative, length
    return None
