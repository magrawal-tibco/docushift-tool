"""C: a sample of docs.tibco.com pages, against the copy that was downloaded (Phase 55).

Everything A checks starts from the downloaded package. This is the check on that
starting point: if a page on the live site says more than the copy, either the
page was updated after the download or the package was not what readers saw.

The sample is the version's `301.yml` origin URLs, spread evenly rather than taken
from the top, so one guide does not supply all twenty. A page that answers with
the docsite's sign-in interstitial (served as HTTP 200, `discovery/client.py`) is
counted as not checkable -- it says nothing about the content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from docushift.discovery.client import _looks_like_auth_page
from docushift.verify import text as texts
from docushift.verify.fetch import Fetcher


def origins(path: Path) -> list[tuple[str, str]]:
    """`(live URL, new path)` from a `301.yml`; empty when there is none."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    rows = document.get("redirects") if isinstance(document, dict) else None
    return [(str(r.get("from") or ""), str(r.get("to") or "")) for r in rows or []
            if isinstance(r, dict) and r.get("from") and r.get("to")]


def sample(rows: list[tuple[str, str]], size: int) -> list[tuple[str, str]]:
    """`size` rows spread evenly across `rows`, in order; all of them when fewer."""
    if size <= 0 or not rows:
        return []
    if len(rows) <= size:
        return list(rows)
    step = len(rows) / size
    return [rows[int(i * step)] for i in range(size)]


@dataclass
class LiveCheck:
    url: str
    status: str = "ok"       # ok | drift | uncheckable
    missing: list[str] = field(default_factory=list)


def check(fetcher: Fetcher, url: str, local: texts.Text | None, selector: str,
          chrome: tuple[str, ...] = ()) -> LiveCheck:
    """One live page against the local copy's text (`local`, the same container)."""
    fetched = fetcher.get(url)
    if not fetched.ok or _looks_like_auth_page(fetched.text) or local is None:
        return LiveCheck(url, "uncheckable")
    live = texts.html_text(fetched.text, selector, chrome) or texts.html_text(fetched.text, "body", chrome)
    if live is None:
        return LiveCheck(url, "uncheckable")
    cover = texts.coverage(live, local)
    return LiveCheck(url, "drift" if cover.missing else "ok", cover.missing)
