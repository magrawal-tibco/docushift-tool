"""Unpacking a documentation ZIP without trusting it.

Landed with Phase 4a rather than 4b (docs/planning.md) because
`docushift archive download --extract` needs it, and because it is the one piece
of extraction that is a *safety rule* rather than an inventory walk: the rule has
to exist before the first thing that could violate it runs. Phase 4b's extractor
consumes it unchanged.

The rule is `design.md` §6.1 step 2 -- refuse any member whose resolved path
escapes the target directory, and any absolute member path. A documentation ZIP
has no legitimate reason to contain either, so this raises rather than skipping:
a package that carries one is not a package we understand, and unpacking the
other 4,000 members of it would leave a tree nobody can reason about.

Phase 34 (R3-01, R3-07) extends the same refusal to names Windows cannot hold
faithfully. They are written through `long_path`, which hands the name to the
filesystem unparsed, so nothing else stops them: a `:` is a drive or an
alternate data stream, a trailing dot or space makes a file no unprefixed reader
can find, and two members that differ only in case are one file on NTFS. None
occurs in the 54 real packages, which is why refusing costs nothing.
"""

import shutil
import zipfile
from pathlib import Path, PurePosixPath

from docushift.utils.longpath import long_path


class UnsafeArchiveError(Exception):
    """A ZIP member would have been written outside the target directory, or
    under a name Windows cannot hold as written (Phase 34)."""


# What Win32 refuses in a file name, beyond the separators. `:` is not here
# because `_is_unsafe` refuses it first, as an escape rather than a bad name.
_RESERVED = frozenset('<>"|?*') | frozenset(chr(code) for code in range(32))


def _is_unsafe(member: str) -> bool:
    """Whether a member name escapes its target directory.

    Checked on the *name* rather than on a resolved filesystem path, deliberately:
    resolving means touching the disk, and a symlinked target directory would then
    decide the answer. `zipfile` writes members with `/` separators regardless of
    the platform that wrote them, so `PurePosixPath` is the right reader -- but a
    Windows-authored archive can still carry a backslash or a drive letter, and
    both are normalized here before the test rather than after.
    """
    name = member.replace("\\", "/")
    path = PurePosixPath(name)
    if path.is_absolute() or name.startswith("/"):
        return True
    # A Windows drive letter (`C:/x`) is not absolute to PurePosixPath -- and
    # not only at the start (Phase 34, R3-01): `root.joinpath("w", "C:x")` is
    # drive-relative, and that segment replaces the root, so `w/C:x` was written
    # to the working directory on C:. A `:` anywhere in a segment is refused.
    return any(part == ".." or ":" in part for part in path.parts)


def _unwritable(member: str) -> str | None:
    """Why Windows cannot hold this member's name as written, if it cannot.

    Phase 34 (R3-07). Per segment, because a directory named `doc.` is as
    unreadable as a file named so.
    """
    for part in PurePosixPath(member.replace("\\", "/")).parts:
        if _RESERVED & set(part):
            return f"a character Windows reserves in {part!r}"
        if part.endswith((".", " ")):
            return f"a trailing dot or space in {part!r}"
    return None


def safe_extract(zip_path: Path, target_dir: Path) -> int:
    """Unpacks `zip_path` into `target_dir`, refusing escaping members.

    Returns the number of files written. Directories are not counted -- the number
    that matters downstream is the file count the inventory will walk.

    Raises `UnsafeArchiveError` naming the offending member, and `zipfile.BadZipFile`
    for an archive that is not readable. Neither is caught here: the caller decides
    whether one bad package fails a run or becomes a report line.
    """
    root = long_path(target_dir)
    root.mkdir(parents=True, exist_ok=True)
    written = 0
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.namelist()
        # Every member is checked *before* any is written, so a malicious archive
        # cannot leave half a tree on disk before being refused. This runs on the
        # raw names and stays ahead of `long_path` on purpose: `\\?\` suppresses
        # the OS's own path normalization, so a `..` that got past here would no
        # longer be collapsed by anything (see `utils/longpath.py`).
        seen: dict[str, str] = {}
        for member in members:
            if _is_unsafe(member):
                raise UnsafeArchiveError(
                    f"{zip_path.name} contains a member that escapes the target directory: {member!r}"
                )
            if (reason := _unwritable(member)) is not None:
                raise UnsafeArchiveError(f"{zip_path.name} contains {reason}: {member!r}")
            if member.endswith("/"):
                continue
            # Two members on one case-insensitive path: the second would overwrite
            # the first and `written` would count both (R3-07). Directories may
            # differ in case -- they merge -- so only the whole file path counts.
            key = member.replace("\\", "/").casefold()
            if key in seen:
                raise UnsafeArchiveError(
                    f"{zip_path.name} holds two members Windows would write to one file: "
                    f"{seen[key]!r} and {member!r}"
                )
            seen[key] = member
        for member in members:
            if member.endswith("/"):
                continue
            # Written here rather than by `ZipFile.extract`, which joins the
            # member onto an unprefixed target of its own making and so puts the
            # 260-character limit back. The member is already proven safe, and
            # `extract`'s sanitizer is the only thing being given up.
            destination = root.joinpath(*PurePosixPath(member.replace("\\", "/")).parts)
            # The backstop the name checks above should make unreachable (R3-01):
            # a join that is not under the root is refused, never written.
            if root not in destination.parents:
                raise UnsafeArchiveError(
                    f"{zip_path.name} contains a member that escapes the target directory: {member!r}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            written += 1
    return written
