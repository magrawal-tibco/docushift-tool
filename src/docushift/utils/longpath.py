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

It began scoped to the two places that *write* a staged tree -- unpacking and the
swap -- and now also reaches the readers and copiers of what those wrote,
including final writes such as `sync`'s published copy. So the prefix is no
longer what keeps a published path under 260: `over_limit` below is, run by
`sync` before every published folder is copied (Phase 34, `architecture.md`
§4.4). A final path over 260 characters is unreadable to every consumer
downstream, and that is a condition to report rather than to paper over.
"""

import os
import re
import shutil
from collections.abc import Collection, Iterator
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


def walk_under(root: Path, skip: Collection[str] = ()) -> Iterator[Path]:
    """Every file under `root`, long ones included, spelled under the plain `root`.

    The engines' walk (X2-08): through the prefix, because extract writes past 260
    characters and a plain `os.walk` omits such a file, so whether a topic converted
    depended on how long the workspace root was. Yielded under `root` rather than
    the prefixed spelling `walk_files` hands back, so every caller's
    `relative_to(root)` holds. Files in name order within a directory; a directory
    whose lowercased name is in `skip` is not descended into, and the rest are then
    visited in name order too.
    """
    base = long_path(root)
    for directory, names, files in os.walk(base):
        if skip:
            names[:] = [name for name in sorted(names) if name.lower() not in skip]
        here = root / Path(directory).relative_to(base)
        for name in sorted(files):
            yield here / name


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
    for relative, _ in walk_files(source):
        length = published_length(destination, relative)
        if length > limit:
            return source / relative, length
    return None


def published_length(destination: Path, relative: "Path | str") -> int:
    """How many characters `destination / relative` is, the way Win32 counts it.

    Phase 34 (R1-08): absolutized first. `--target-dir` reaches here as typed, so
    `../aem` used to be measured as six characters and every file under it came
    out short by the length of the working directory -- the margin that let a
    261-to-285-character path pass the check and then be written through
    `long_path`.
    """
    return len(os.path.abspath(destination)) + 1 + len(str(relative))


# What Win32 refuses in a file name, beyond the separators, and the device names
# it resolves wherever they appear in a path, with or without an extension:
# `aux.htm` written through the prefix is a file, but every plain reader opens
# the device instead (Phase 34, X2-10).
_RESERVED = frozenset('<>"|?*') | frozenset(chr(code) for code in range(32))
_DEVICES = re.compile(r"(?i)^(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(\..*)?$")


def is_device_name(part: str) -> bool:
    """Whether Windows reads this path segment as a device (`NUL`, `com1.txt`)."""
    return bool(_DEVICES.match(part.rstrip(" ")))


def segment_problem(part: str) -> str | None:
    """Why one value cannot be used as a single folder or file name, or `None`.

    Phase 34 (X2-10, X2-11). A value read from a file -- a catalog cell, a
    sitemap `<loc>` -- and joined onto a path as one segment must stay one
    segment: `..` made a swap delete a whole family folder, and `D:evil.xml`
    is relative to drive D's working directory. A trailing dot is not refused
    here, because a real catalog version (`6.0.1.`) has one; `safe_unzip`
    refuses it for member names, where nothing depends on it.
    """
    if part.strip() in ("", ".", ".."):
        return f"{part!r} is not a name"
    if "/" in part or "\\" in part:
        return f"a path separator in {part!r}"
    if ":" in part:
        return f"a drive or stream colon in {part!r}"
    if _RESERVED & set(part):
        return f"a character Windows reserves in {part!r}"
    if is_device_name(part):
        return f"a Windows device name in {part!r}"
    return None


def path_segment(value: str, what: str) -> str:
    """`value`, checked to be one safe path segment; raises `ValueError` naming it if not."""
    problem = segment_problem(value)
    if problem is not None:
        raise ValueError(f"{what} {value!r} cannot be used as a folder name: {problem}")
    return value


# Phase 46. The prefix above reaches only the call sites that use it, and a site
# that forgets it does not fail: `is_file()` and `iterdir()` report a long path as
# absent. Adapter for Files 1.3.0 converted nothing that way, and 49 other versions
# lost files, all without a message. With Windows long-path support turned on, an
# unprefixed path works at any length, so a run checks that once and refuses to
# start without it.
_PROBE_DEPTH = 300
LONG_PATHS_OFF = (
    "Windows long-path support is off, so files at 260+ characters would be skipped "
    "without a warning. Turn it on (admin PowerShell):\n"
    '  New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" '
    "-Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force\n"
    'or the Group Policy "Enable Win32 long paths", then start a new shell.'
)


def long_paths_enabled(scratch: Path) -> bool:
    """Can this process read and write a path past 260 characters without the prefix?

    A probe rather than a registry read: what matters is what the running Python
    can do, and that also depends on its manifest. It writes one file under
    `scratch` through the *plain* spelling, reads it back, and removes it through
    the prefix, so a failed probe leaves nothing behind. Always true off Windows.
    """
    if os.name != "nt":
        return True
    base = Path(os.path.abspath(scratch)) / f"longpath-probe-{os.getpid()}"
    filler = "x" * 100
    probe = base
    while len(str(probe)) < _PROBE_DEPTH:
        probe = probe / filler
    probe = probe / "probe.txt"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        return probe.read_text(encoding="utf-8") == "ok"
    except OSError:
        return False
    finally:
        shutil.rmtree(long_path(base), ignore_errors=True)
