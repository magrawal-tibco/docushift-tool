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

`download` stages one *file* and keeps `os.replace` directly: a single-file
rename over an existing name is atomic, and routing it through here would trade
that guarantee -- the one that stops a killed run leaving a truncated ZIP at the
canonical path -- for a retry it does not need.
"""

import shutil
import time
from pathlib import Path

# Five attempts, 0.1s apart and growing: 1.0s of patience in total. Long enough
# for a scanner to let go of a freshly written tree, short enough that a real
# permission problem is still reported inside one heartbeat of the run.
ATTEMPTS = 5
DELAY = 0.1


def remove(path: Path, attempts: int = ATTEMPTS, delay: float = DELAY) -> None:
    """Removes a file or a whole tree, retrying the scanner race. Raises on the last try."""
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


def swap(staging: Path, target: Path, attempts: int = ATTEMPTS, delay: float = DELAY) -> None:
    """Moves `staging` onto `target`, replacing whatever is there.

    Not atomic on Windows -- remove, then rename -- so an interrupted run can
    leave the target missing and the staging directory present. That is the
    same window the callers already documented; the retry narrows it rather
    than closing it.
    """
    for attempt in range(attempts):
        try:
            remove(target, attempts=1)
            target.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(target)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay * (attempt + 1))
