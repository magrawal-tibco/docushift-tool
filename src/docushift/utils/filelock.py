"""An exclusive lock between processes (and threads), held on a small file.

For writers of a shared file that each read it whole and write it back: the
catalog CSVs, which two `docushift` runs at once used to overwrite with each
other's stale copy. The lock is the OS's own -- `msvcrt.locking` on Windows,
`fcntl.flock` elsewhere -- so a run that dies lets go with its process, and a lock
file left behind locks nothing.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":  # pragma: no cover - one branch per platform
    import msvcrt

    def _try_lock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:  # pragma: no cover
    import fcntl

    def _try_lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


class LockTimeout(TimeoutError):
    """The lock was held by someone else for longer than the caller would wait."""


@contextmanager
def exclusive(path: Path, timeout: float = 300.0, poll: float = 0.05) -> Iterator[None]:
    """Holds `path` exclusively for the `with` block; waits up to `timeout` seconds for it.

    Each call opens its own handle, so two threads of one process exclude each
    other as two processes do.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                _try_lock(fd)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"{path} held for over {timeout:.0f}s") from None
                time.sleep(poll)
        try:
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
