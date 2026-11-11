"""Link targets into a page's sections, checked on staging (Phase 58, staging pilots).

The tool names a heading's anchor by its own rule (`utils/anchors.anchor_run`). The
TIBCO staging site writes heading ids its own way (punctuation kept, `_` as `-`, no
number on a repeat; 2026-11-11), so a `page.md#anchor` can open the page and miss
the section. Until the AEM team confirms the rule, every such target is an issue,
and all of them are kept in one list, `reports/verify/anchor-targets.csv`, since
`toc.yml`, `301.yml` and links inside the pages point at the same anchors.

- **differs**: the page has the heading, under another id (recorded).
- **missing**: no heading on the served page slugs to the anchor.
"""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from docushift.utils.anchors import anchor_run
from docushift.utils.csvio import read_rows, write_rows
from docushift.verify.published import PageCheck
from docushift.verify.toc import Node, is_section

FILE = "anchor-targets.csv"
COLUMNS = ["bu", "slug", "version", "page", "anchor", "served_id", "outcome", "old_url", "old_url_is",
           "staging_url", "sources", "example", "date"]
# `](target#anchor)` or `](#anchor)`; a URL or a rooted path is not this version's page.
_LINK = re.compile(r"\]\(([^)\s#]*)#([^)\s]+)\)")
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Target:
    page: str
    anchor: str
    sources: Counter = field(default_factory=Counter)
    example: str = ""
    outcome: str = ""
    served_id: str = ""
    #: The docs.tibco.com page a reader of this section came from, from `301.yml`:
    #: the section's own row (`section`), else the row of the topic holding it (`topic`),
    #: else the page's own row, for a page that was one old page (`page`).
    old_url: str = ""
    old_url_is: str = ""

    def cite(self, source: str, example: str) -> None:
        self.sources[source] += 1
        self.example = self.example or example

    @property
    def key(self) -> str:
        return f"{self.page}#{self.anchor}"


def gather(toc: Node, redirects: list[tuple[str, str]], folder: Path, pages: set[str]) -> dict[str, Target]:
    """Every `page.md#anchor` of the version whose page is in `pages`, with its sources."""
    found: dict[str, Target] = {}

    def add(page: str, anchor: str, source: str, example: str) -> None:
        anchor = unquote(anchor)
        if page in pages and anchor:
            found.setdefault(f"{page}#{anchor}", Target(page, anchor)).cite(source, example)

    for row, _ in toc.walk():
        if is_section(row):
            page, _, anchor = str(row.key).partition("#")
            add(page, anchor, "toc", row.title)
    for old, new in redirects:
        page, _, anchor = new.partition("#")
        add(page, anchor, "301", old)
    for page in sorted(pages):
        try:
            text = (folder / page).read_text(encoding="utf-8")
        except OSError:
            continue
        for target, anchor in _LINK.findall(text):
            if "://" in target or target.startswith(("/", "mailto:")):
                continue
            to = posixpath.normpath(posixpath.join(posixpath.dirname(page), unquote(target))) if target else page
            add(to, anchor, "link", page)
    _old_urls(found, redirects, folder)
    return found


def _old_urls(found: dict[str, Target], redirects: list[tuple[str, str]], folder: Path) -> None:
    """Fill each target's old URL: its own `301.yml` row, else the nearest heading above
    it on the page that has one (the merged topic the section came from), else the
    page's own row (an unmerged page, such as WebWorks)."""
    old_of: dict[str, str] = {}
    for old, new in redirects:
        old_of.setdefault(unquote(new), old)
    order: dict[str, list[str]] = {}
    for target in found.values():
        if target.key in old_of:
            target.old_url, target.old_url_is = old_of[target.key], "section"
            continue
        if target.page not in order:
            order[target.page] = _page_anchors(folder / target.page)
        run = order[target.page]
        above = run[:run.index(target.anchor)] if target.anchor in run else []
        for anchor in reversed(above):
            old = old_of.get(f"{target.page}#{anchor}")
            if old:
                target.old_url, target.old_url_is = old, "topic"
                break
        if not target.old_url and target.page in old_of:
            target.old_url, target.old_url_is = old_of[target.page], "page"


def _page_anchors(path: Path) -> list[str]:
    """The page's heading anchors in order, by the tool's own rule."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    titles, fenced = [], False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (m := _HEADING.match(line)):
            titles.append(m.group(1))
    return anchor_run(titles)


def classify(target: Target, check: PageCheck) -> None:
    """Sets `outcome` (`ok`, `differs`, `missing`) and the served id of a `differs`."""
    if target.anchor in check.anchors:
        target.outcome = "ok"
        return
    run = anchor_run([text for text, _ in check.headings])
    if run[:1] == [target.anchor] and not check.headings[0][1]:
        # The page's own title: staging gives it no id, but an unknown fragment opens
        # the page at its top, which is the title. The reader lands where meant.
        target.outcome = "ok"
        return
    if target.anchor in run:
        target.outcome, target.served_id = "differs", check.headings[run.index(target.anchor)][1]
    else:
        target.outcome = "missing"


def _staging(url: str, served_id: str) -> str:
    """The staging page, at the section's served id when it has one (opens on the heading)."""
    return f"{url}#{served_id}" if url and served_id else url


def sources(target: Target) -> str:
    return " ".join(f"{name}:{count}" for name, count in sorted(target.sources.items()))


def write_list(root: Path, bu: str, slug: str, version: str, targets: list[Target],
               urls: dict[str, str], day: str) -> Path:
    """Replace this version's rows in the list; keep every other version's."""
    path = root / "verify" / FILE
    kept = [r for r in read_rows(path) if (r.get("slug"), r.get("version")) != (slug, version)] \
        if path.is_file() else []
    rows = [{"bu": bu, "slug": slug, "version": version, "page": t.page, "anchor": t.anchor,
             "served_id": t.served_id, "outcome": t.outcome, "old_url": t.old_url, "old_url_is": t.old_url_is,
             "staging_url": _staging(urls.get(t.page, ""), t.served_id), "sources": sources(t),
             "example": t.example, "date": day}
            for t in sorted(targets, key=lambda t: (t.page, t.anchor)) if t.outcome != "ok"]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_rows(path, COLUMNS, sorted(kept + rows, key=lambda r: (r["bu"], r["slug"], r["version"],
                                                                  r["page"], r["anchor"])))
    return path
