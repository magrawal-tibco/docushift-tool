"""Polite, cached GETs for `verify`: throttled, retried, and never fetched twice.

Cached under `cache/verify/` by URL, status included, so a re-run of a version
costs no request and a 404 stays a 404 without asking again. `--refresh` is how
a re-published page is fetched anew -- once per run: a URL already fetched in
this run (the menu page, an icon on every page) is read back from the cache.

**Concurrent** (verify speed-up, 2026-11-14): the checks hand their work to
`fan_out`, which runs it on `workers` threads and returns the results in the order
given, so findings come out exactly as a one-thread run records them. The
throttle is the crawler's floor, shared by every thread: more workers overlap the
waiting on each response, they do not raise the request rate past the configured
one. Each thread has its own `requests.Session`; each cache entry is written to a
temporary file and renamed into place, body first, so a reader -- another thread,
or another `docushift` process -- sees a whole entry or none.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import requests

from docushift.utils.http import Throttle, build_session
from docushift.utils.swap import replace_file

#: Threads per run when neither `--workers` nor `verify.max_concurrent_requests` says.
DEFAULT_WORKERS = 6

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class Fetched:
    url: str
    status: int
    body: bytes
    content_type: str = ""

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    @property
    def ok(self) -> bool:
        return self.status == 200


class Fetcher:
    def __init__(self, cache_dir: Path, crawl: dict[str, Any], refresh: bool = False,
                 workers: int = 1) -> None:
        self.cache_dir = cache_dir
        self.timeout = float(crawl.get("timeout_seconds", 30))
        self.throttle = Throttle.from_crawl(crawl)
        self.refresh = refresh
        self.workers = max(1, int(workers or 1))
        self.requests = 0
        self._crawl = dict(crawl)
        self._local = threading.local()
        self._lock = threading.Lock()
        # URLs fetched in this run: read back from the cache after, `--refresh` or not.
        self._fresh: set[str] = set()

    @property
    def session(self) -> requests.Session:
        """This thread's session: `requests.Session` is not documented as thread-safe."""
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._local.session = build_session(self._crawl, accept="*/*")
        return session

    def _paths(self, url: str) -> tuple[Path, Path]:
        name = hashlib.sha1(url.encode("utf-8")).hexdigest()
        folder = self.cache_dir / name[:2]
        return folder / f"{name}.json", folder / f"{name}.bin"

    def get(self, url: str) -> Fetched:
        meta_path, body_path = self._paths(url)
        with self._lock:
            from_cache = not self.refresh or url in self._fresh
        if from_cache and meta_path.is_file() and body_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                return Fetched(url, int(meta["status"]), body_path.read_bytes(), meta.get("content_type", ""))
            except (OSError, ValueError, KeyError):
                pass  # an unreadable entry is fetched again, not a crash
        self.throttle.wait()
        with self._lock:
            self.requests += 1
        try:
            response = self.session.get(url, timeout=self.timeout)
            fetched = Fetched(url, response.status_code, response.content,
                              response.headers.get("Content-Type", ""))
        except requests.RequestException as exc:
            # Not cached: a network failure says nothing about the page.
            return Fetched(url, 0, str(exc).encode("utf-8"))
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        # The body first, then the meta that says the entry is there.
        _write_atomic(body_path, fetched.body)
        _write_atomic(meta_path, json.dumps({"url": url, "status": fetched.status,
                                             "content_type": fetched.content_type}).encode("utf-8"))
        with self._lock:
            self._fresh.add(url)
        return fetched


def _write_atomic(path: Path, data: bytes) -> None:
    """`data` at `path` through a temporary sibling and a rename: whole or not at all.

    The temporary name is this process's and this thread's own, so two writers of
    one URL never share it; the later rename wins, with the same bytes.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(data)
        replace_file(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def fan_out(fetcher: Any, fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
    """`[fn(item) for item in items]` on the fetcher's `workers` threads, in the given order.

    A fetcher without `workers` (the tests' fakes) runs them one at a time, as before.
    """
    todo = list(items)
    workers = min(int(getattr(fetcher, "workers", 1) or 1), len(todo))
    if workers <= 1:
        return [fn(item) for item in todo]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="verify") as pool:
        return list(pool.map(fn, todo))
