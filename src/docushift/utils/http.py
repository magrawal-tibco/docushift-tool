"""Shared HTTP session construction and request pacing.

Two callers, one policy: `discovery/client.py` fetches JSON from the docsite and
`downloader/fetcher.py` streams ZIPs from the same host. They need the same
`Retry` behaviour, the same `User-Agent`, and the same provenance -- every value
comes from `config/docsite.yaml`, so a moved endpoint or a changed politeness
floor is a config edit rather than a release (docs/architecture.md §2).

Keeping one builder is not tidiness. A second copy of the retry configuration is
how the crawler and the downloader end up disagreeing about what a 429 means,
and the disagreement would only show under load.
"""

import threading
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Transient by nature: 429 is the docsite rate-limiting us, the 5xx family is it
# failing. A 404 is not retried -- an absent archive index is a normal answer.
RETRY_STATUSES = (429, 500, 502, 503, 504)


def build_session(crawl: dict[str, Any], accept: str | None = None) -> requests.Session:
    """A `requests.Session` carrying the docsite's declared retry and identity policy.

    `accept` overrides the configured header, which is what the two callers differ
    on and the only thing they differ on: the crawler wants JSON, the downloader
    wants bytes.
    """
    session = requests.Session()
    retry = Retry(
        total=int(crawl.get("max_retries", 3)),
        backoff_factor=float(crawl.get("backoff_factor", 1.5)),
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": str(crawl.get("user_agent") or "DocuShift/0.1"),
            "Accept": accept or str(crawl.get("accept") or "application/json"),
        }
    )
    return session


class Throttle:
    """A hard floor on the interval between request *initiations*, shared across threads.

    A floor rather than a token bucket: a burst of 250 product lookups is exactly
    the shape of traffic this tool generates, and a bucket would let the whole
    burst through -- which is the one case politeness is for.

    It paces starts, not transfers. A download that streams for two minutes is one
    request, not four requests a second, so holding the lock for the duration would
    serialize the thread pool into a single worker and call it rate limiting.
    """

    def __init__(self, rate_per_second: float = 0.0):
        self._min_interval = 1.0 / rate_per_second if rate_per_second > 0 else 0.0
        self._last_at = 0.0
        self._lock = threading.Lock()

    @classmethod
    def from_crawl(cls, crawl: dict[str, Any]) -> "Throttle":
        return cls(float(crawl.get("rate_limit_per_second", 0) or 0))

    def wait(self) -> None:
        """Blocks until the next request is allowed to start."""
        if self._min_interval <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last_at
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_at = time.monotonic()
