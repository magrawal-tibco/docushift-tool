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
