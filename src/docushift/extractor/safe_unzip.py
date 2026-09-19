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
"""

import shutil
import zipfile
from pathlib import Path, PurePosixPath

from docushift.utils.longpath import long_path


class UnsafeArchiveError(Exception):
    """A ZIP member would have been written outside the target directory."""


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
    # A Windows drive letter (`C:/x`) is not absolute to PurePosixPath.
    if len(name) > 1 and name[1] == ":":
        return True
    return any(part == ".." for part in path.parts)


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
        for member in members:
            if _is_unsafe(member):
                raise UnsafeArchiveError(
                    f"{zip_path.name} contains a member that escapes the target directory: {member!r}"
                )
        for member in members:
            if member.endswith("/"):
                continue
            # Written here rather than by `ZipFile.extract`, which joins the
            # member onto an unprefixed target of its own making and so puts the
            # 260-character limit back. The member is already proven safe, and
            # `extract`'s sanitizer is the only thing being given up.
            destination = root.joinpath(*PurePosixPath(member.replace("\\", "/")).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            written += 1
    return written
