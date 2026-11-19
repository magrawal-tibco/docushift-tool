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
import logging
import os
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import requests

from docushift.utils.http import Throttle, build_session
from docushift.utils.swap import replace_file

log = logging.getLogger(__name__)

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

    @property
    def refused(self) -> bool:
        """The site turned the request away (Phase 85): it says nothing about the page."""
        return self.status in REFUSED


#: Answers that say nothing about the page (Phase 85): rate limited, server trouble, or
#: no answer at all (0, a dropped connection). Never cached; waited out and retried.
REFUSED = frozenset({0, 429, 500, 502, 503, 504})


class Fetcher:
    def __init__(self, cache_dir: Path, crawl: dict[str, Any], refresh: bool = False,
                 workers: int = 1, sleep: Callable[[float], None] = time.sleep) -> None:
        self.cache_dir = cache_dir
        self.timeout = float(crawl.get("timeout_seconds", 30))
        self.throttle = Throttle.from_crawl(crawl)
        self.refresh = refresh
        self.workers = max(1, int(workers or 1))
        self.requests = 0
        #: Pages still refused after every round, and the cool-downs taken (Phase 85).
        self.refused = 0
        self.cooldowns = 0
        self._rounds = int(crawl.get("refusal_rounds", 6))
        self._first_wait = float(crawl.get("refusal_wait_seconds", 30))
        self._max_wait = float(crawl.get("refusal_max_wait_seconds", 300))
        self._sleep = sleep
        self._cool_until = 0.0
        self._strikes = 0
        self._slowed = False
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
                if int(meta["status"]) not in REFUSED:  # one stored before Phase 85: ask again
                    return Fetched(url, int(meta["status"]), body_path.read_bytes(),
                                   meta.get("content_type", ""))
            except (OSError, ValueError, KeyError):
                pass  # an unreadable entry is fetched again, not a crash
        for _ in range(max(1, self._rounds)):
            fetched, retry_after = self._request(url)
            if not fetched.refused:
                break
            self._cool_down(url, fetched.status, retry_after)
        else:
            with self._lock:
                self.refused += 1
            log.warning("verify: %s still refused (HTTP %s) after %d round(s)", url, fetched.status,
                        self._rounds)
            return fetched  # not cached: it says nothing about the page
        with self._lock:
            self._strikes = 0
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        # The body first, then the meta that says the entry is there.
        _write_atomic(body_path, fetched.body)
        _write_atomic(meta_path, json.dumps({"url": url, "status": fetched.status,
                                             "content_type": fetched.content_type}).encode("utf-8"))
        with self._lock:
            self._fresh.add(url)
        return fetched

    def _request(self, url: str) -> tuple[Fetched, float | None]:
        """One GET after the shared cool-down and the throttle; with `Retry-After` if sent."""
        while True:  # every thread honours a cool-down another one started
            with self._lock:
                left = self._cool_until - time.monotonic()
            if left <= 0:
                break
            self._sleep(left)
        self.throttle.wait()
        with self._lock:
            self.requests += 1
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            return Fetched(url, 0, str(exc).encode("utf-8")), None
        fetched = Fetched(url, response.status_code, response.content,
                          response.headers.get("Content-Type", ""))
        return fetched, _retry_after(response.headers.get("Retry-After"))

    def _cool_down(self, url: str, status: int, retry_after: float | None) -> None:
        """Pause every thread: `Retry-After` if given, else 30 s doubling to 5 min; and,
        once per run, halve the request rate."""
        with self._lock:
            wait = retry_after if retry_after is not None else min(
                self._first_wait * (2 ** self._strikes), self._max_wait)
            self._strikes += 1
            self.cooldowns += 1
            until = time.monotonic() + wait
            if until > self._cool_until:
                self._cool_until = until
            slow, self._slowed = not self._slowed, True
        if slow:
            self.throttle.slow_down()
        log.warning("verify: staging refused %s (HTTP %s); pausing %.0f s", url, status, wait)


def _retry_after(value: str | None) -> float | None:
    """`Retry-After` in seconds (a number of seconds or an HTTP date), or None."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        from datetime import datetime, timezone
        return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


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
