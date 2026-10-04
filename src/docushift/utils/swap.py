"""Build-and-swap, made to survive a virus scanner.

`extract` and `convert` both build a tree beside its destination and rename it
into place. On Windows that rename fails with `PermissionError: [WinError 5]`
whenever *any* handle to the directory or its contents is still open -- and a
handle nobody asked for is the normal case there, because the search indexer
and the on-access scanner open files moments after they are written.

Measured while building Stage 5: roughly one run in seven of a 21-test suite,
on a tree of nine files, failed at exactly this call. A 250-version batch
writing millions of files would hit it many times per run. What makes it worth
handling rather than reporting is *where* it lands: the tree is complete and
correct, and the last syscall lost a race with a scanner. Reporting that as a
failed extract would send someone to look for a corrupt package.

So the swap retries with a short backoff -- about a second in total -- and only
then raises, which leaves the genuine failures (a full disk, a denied
directory, a target open in an editor) reported exactly as before. On POSIX the
first attempt succeeds and the loop is never entered.

**The live tree is moved aside, never deleted first** (Phase 34, X2-01). The
swap used to `rmtree` the target and then rename: `rmtree` deletes file by file
and stops at the first locked one, so a `rename-map.csv` open in Excel left a
199-file merged tree holding 6 files, and a kill inside the delete left a tree
the next run called `current`. Now the target is renamed to `<target>.old`, the
staging tree is renamed in, and only then is `.old` deleted. A locked file makes
the first rename fail with nothing touched; a failed second rename puts `.old`
back. The window with no target is two renames wide, and `recover` closes even
that on the next visit.

Single files go through `replace_file`, the same atomic `os.replace` with the
scanner retry -- the downloader's ZIP included since X2-14.
"""

import contextlib
import shutil
import time
from pathlib import Path

from docushift.utils.longpath import long_path

# Five attempts, 0.1s apart and growing: 1.0s of patience in total. Long enough
# for a scanner to let go of a freshly written tree, short enough that a real
# permission problem is still reported inside one heartbeat of the run.
ATTEMPTS = 5
DELAY = 0.1


def remove(path: Path, attempts: int = ATTEMPTS, delay: float = DELAY) -> None:
    """Removes a file or a whole tree, retrying the scanner race. Raises on the last try.

    Long-path spelled (Phase 14b): a `.part` tree that Windows refused to *create*
    at full length is equally one it will refuse to walk, so a failed extract
    would otherwise leave litter that nothing could clean up.
    """
    path = long_path(path)
    for attempt in range(attempts):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay * (attempt + 1))


#: The sibling the live tree is renamed to while its replacement moves in (X2-01).
ASIDE_SUFFIX = ".old"

#: The sibling every stage builds in before the swap.
STAGING_SUFFIX = ".part"


def aside_of(target: Path) -> Path:
    """`<target>.old`: where the live tree waits while the new one is renamed in."""
    return target.with_name(target.name + ASIDE_SUFFIX)


def staging_of(target: Path) -> Path:
    """`<target>.part`: where a stage builds the tree that replaces `target`."""
    return target.with_name(target.name + STAGING_SUFFIX)


def swap(staging: Path, target: Path, attempts: int = ATTEMPTS, delay: float = DELAY) -> None:
    """Moves `staging` onto `target`, replacing whatever is there.

    Rename the target aside, rename staging in, delete what was set aside
    (X2-01). Nothing is deleted until the new tree is in place: a file held open
    in the old tree fails the first rename and leaves the old tree whole, and a
    failed second rename renames the old tree back before raising. A run killed
    between the two renames leaves `<target>.old` and no target, which `recover`
    puts back on the next visit.

    Both ends are long-path spelled (Phase 14b). The staging tree is the longer
    of the two by the width of `.part`, which is the whole reason the limit is
    reachable here at all.
    """
    staging, target = long_path(staging), long_path(target)
    old = long_path(aside_of(target))
    # Beside a live target, a `.old` is residue of a run killed after its swap.
    # Beside a missing one it is the last good tree, kept until the new one is in.
    if old.exists() and target.exists():
        remove(old)
    for attempt in range(attempts):
        try:
            if target.exists():
                target.replace(old)
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                staging.replace(target)
            except OSError:
                _restore(old, target)
                raise
            break
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay * (attempt + 1))
    # The new tree is in and the stage has succeeded; a scanner still holding a
    # file of the old one costs residue, not the run. `recover` sweeps it.
    with contextlib.suppress(OSError):
        remove(old)


def _restore(old: Path, target: Path) -> None:
    """Puts the set-aside tree back after a failed rename-in. Best effort.

    If this rename loses a race too, the old tree is still whole at `.old`, and
    `recover` renames it back on the next visit; raising here would only hide the
    error that matters.
    """
    if old.exists() and not target.exists():
        with contextlib.suppress(OSError):
            old.replace(target)


def recover(target: Path, keep_orphan_staging: bool = False) -> None:
    """Undoes what an interrupted run left beside `target`, before a stage looks at it.

    Every stage calls this first, `current` included (X3-09): a run killed while
    building left `<target>.part`, and a `current` decision used to leave it
    there until a forced rebuild -- 715 files in `extracted/`, and in the
    published tree a folder whose `301.yml` rows were served.

    * a `.old` with no target is the last good tree, from a run killed between
      `swap`'s two renames: renamed back, so the target is exactly as it was;
    * a `.old` beside a target is residue of a run killed after its swap: removed;
    * a `.part` is an unfinished build: removed -- unless `keep_orphan_staging`
      and there is no target, which is the state an older tool's interrupted
      swap left, and Reframe reads its pins out of that `.part` first (X3-02).

    Raises only when the old tree cannot be put back; residue that will not go
    is left for the next visit, and the stage's own `remove(staging)` before a
    build still raises on it.
    """
    target = long_path(target)
    old = long_path(aside_of(target))
    if old.is_dir() and not target.exists():
        old.replace(target)
    if keep_orphan_staging and not target.exists():
        return
    for residue in (old, long_path(staging_of(target))):
        with contextlib.suppress(OSError):
            remove(residue)


def replace_file(staging: Path, target: Path, attempts: int = ATTEMPTS, delay: float = DELAY) -> None:
    """`os.replace` for one file, retrying the scanner race. Still atomic per attempt.

    A single-file rename was once thought to need no retry; the Coveo sitemap
    cache disproved that (Phase 33): rewriting `manifest.json` once per product,
    ~500 times in a row, lost to `[WinError 32]` on a file the indexer had just
    opened. Each attempt is the same atomic `os.replace`, so the guarantee the
    downloader relies on -- no truncated ZIP at the canonical path -- is not
    traded away; only the race is retried (X2-14).
    """
    for attempt in range(attempts):
        try:
            staging.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay * (attempt + 1))
