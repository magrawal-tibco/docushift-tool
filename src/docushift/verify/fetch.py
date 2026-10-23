"""Polite, cached GETs for `verify`: throttled, retried, and never fetched twice.

Cached under `cache/verify/` by URL, status included, so a re-run of a version
costs no request and a 404 stays a 404 without asking again. `--refresh` is how
a re-published page is fetched anew.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from docushift.utils.http import Throttle, build_session


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
    def __init__(self, cache_dir: Path, crawl: dict[str, Any], refresh: bool = False) -> None:
        self.cache_dir = cache_dir
        self.timeout = float(crawl.get("timeout_seconds", 30))
        self.throttle = Throttle.from_crawl(crawl)
        self.session = build_session(crawl, accept="*/*")
        self.refresh = refresh
        self.requests = 0

    def _paths(self, url: str) -> tuple[Path, Path]:
        name = hashlib.sha1(url.encode("utf-8")).hexdigest()
        folder = self.cache_dir / name[:2]
        return folder / f"{name}.json", folder / f"{name}.bin"

    def get(self, url: str) -> Fetched:
        meta_path, body_path = self._paths(url)
        if not self.refresh and meta_path.is_file() and body_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return Fetched(url, int(meta["status"]), body_path.read_bytes(), meta.get("content_type", ""))
        self.throttle.wait()
        self.requests += 1
        try:
            response = self.session.get(url, timeout=self.timeout)
            fetched = Fetched(url, response.status_code, response.content,
                              response.headers.get("Content-Type", ""))
        except requests.RequestException as exc:
            # Not cached: a network failure says nothing about the page.
            return Fetched(url, 0, str(exc).encode("utf-8"))
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(fetched.body)
        meta_path.write_text(json.dumps({"url": url, "status": fetched.status,
                                         "content_type": fetched.content_type}), encoding="utf-8")
        return fetched
