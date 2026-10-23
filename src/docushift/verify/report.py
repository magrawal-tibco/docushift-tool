"""Verify's evidence, kept per run, and the index a reader opens (Phase 58).

- `reports/verify/<bu>/<slug>/<version>-<date>.csv` -- one row per old page: what
  it became and what was found. Kept, not overwritten: a later run of the same
  version on another day is a second file, so a version that got worse shows.
- `.html` beside it -- the lowest-scoring pages first, each with its old and new
  link, for the spot-check.
- `reports/verify/INDEX.csv` and `INDEX.html` -- every published version and its
  `_verify_status`, verified or not, so the rollout's progress is one page.
"""

from __future__ import annotations

import contextlib
from collections import Counter
from html import escape
from pathlib import Path

from docushift.utils.csvio import write_rows
from docushift.verify.driver import COLUMNS, VersionResult

SUMMARY_ROWS = 40
INDEX_COLUMNS = ["bu", "family", "slug", "version", "verify_status", "verify_date", "scope", "pages",
                 "errors", "warnings", "explained", "findings", "commit", "report"]


def version_paths(root: Path, bu: str, slug: str, version: str, day: str) -> tuple[Path, Path]:
    folder = root / "verify" / bu / slug
    return folder / f"{version}-{day}.csv", folder / f"{version}-{day}.html"


def write_version(root: Path, bu: str, result: VersionResult, day: str) -> Path:
    csv_path, html_path = version_paths(root, bu, result.folder.slug, result.version, day)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_rows(csv_path, COLUMNS, result.rows)
    name = f"{result.folder.slug} {result.version}"
    html_path.write_text(_html(name, result.rows, dict(result.codes), result.outcome),
                         encoding="utf-8", newline="\n")
    return csv_path


def write_index(root: Path, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    """`rows` are `INDEX_COLUMNS` dicts, one per published version."""
    folder = root / "verify"
    folder.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: (r["bu"], r["family"], r["slug"], r["version"]))
    csv_path, html_path = folder / "INDEX.csv", folder / "INDEX.html"
    write_rows(csv_path, INDEX_COLUMNS, ordered)
    html_path.write_text(_index_html(ordered), encoding="utf-8", newline="\n")
    return csv_path, html_path


def _score(row: dict[str, str]) -> tuple[float, int]:
    try:
        percent = float(row.get("text_percent") or 100)
    except ValueError:
        percent = 100.0
    return (percent, -len((row.get("findings") or "").split()))


_STYLE = ("<style>body{font-family:sans-serif;margin:2em}table{border-collapse:collapse}"
          "td,th{border:1px solid #ccc;padding:4px 8px;vertical-align:top;font-size:13px}"
          ".lost{color:#b00020;font-weight:bold}.issues{color:#a15c00}.stale{color:#666}</style>")


def _html(name: str, rows: list[dict[str, str]], totals: dict[str, int], outcome: str) -> str:
    worst = sorted((r for r in rows if not r.get("skip_reason")), key=_score)[:SUMMARY_ROWS]
    tally = "".join(f"<li><code>{escape(c)}</code>: {n}</li>" for c, n in sorted(totals.items()))

    def link(url: str, label: str) -> str:
        return f'<a href="{escape(url)}">{label}</a>' if url else ""

    body = "".join(
        "<tr>"
        f"<td>{escape(r['new_path'])}</td>"
        f"<td>{escape(r['text_percent'])}</td>"
        f"<td>{escape(r['images_found'])}/{escape(r['images_expected'])}</td>"
        f"<td>{escape(r['published_status'])}</td>"
        f"<td>{escape(r['findings'])}</td><td>{escape(r['triage'])}</td>"
        f"<td>{link(r['old_url'], 'old')} {link(r['staging_url'], 'staging')}</td>"
        f"<td>{escape(r['missing_sentences'][:400])}</td>"
        "</tr>"
        for r in worst
    )
    return (
        f"<!doctype html><meta charset='utf-8'><title>verify {escape(name)}</title>{_STYLE}"
        f"<h1>verify: {escape(name)} &mdash; <span class='{outcome}'>{outcome}</span></h1>"
        f"<p>{len(rows)} old page(s) checked.</p>"
        f"<h2>Findings</h2><ul>{tally or '<li>none</li>'}</ul>"
        "<h2>Lowest-scoring pages</h2><table><tr><th>new page</th><th>text %</th><th>images</th>"
        "<th>staging</th><th>findings</th><th>triage</th><th>links</th><th>missing sentences</th></tr>"
        f"{body}</table>"
    )


def _index_html(rows: list[dict[str, str]]) -> str:
    by_status = Counter(r["verify_status"] or "not-verified" for r in rows)
    summary = ", ".join(f"{n} {s}" for s, n in sorted(by_status.items()))

    def report(r: dict[str, str]) -> str:
        if not r["report"]:
            return ""
        # Stored relative to the project root (`reports/verify/...`); the index sits
        # in `reports/verify/`, so its links drop that prefix.
        href = Path(r["report"]).with_suffix(".html")
        with contextlib.suppress(ValueError):
            href = href.relative_to("reports/verify")
        return f'<a href="{escape(href.as_posix())}">report</a>'

    body = "".join(
        f"<tr><td>{escape(r['bu'])}</td><td>{escape(r['family'])}</td><td>{escape(r['slug'])}</td>"
        f"<td>{escape(r['version'])}</td><td class='{escape(r['verify_status'])}'>{escape(r['verify_status'])}</td>"
        f"<td>{escape(r['verify_date'])}</td><td>{escape(r['scope'])}</td><td>{escape(r['pages'])}</td>"
        f"<td>{escape(r['errors'])}</td><td>{escape(r['warnings'])}</td><td>{escape(r['explained'])}</td>"
        f"<td>{escape(r['findings'])}</td><td>{report(r)}</td></tr>"
        for r in rows
    )
    return (
        f"<!doctype html><meta charset='utf-8'><title>verify index</title>{_STYLE}"
        f"<h1>verify: every published version</h1><p>{len(rows)} version(s): {escape(summary)}.</p>"
        "<table><tr><th>bu</th><th>family</th><th>product</th><th>version</th><th>status</th><th>date</th>"
        "<th>scope</th><th>pages</th><th>lost</th><th>warnings</th><th>explained</th><th>findings</th>"
        f"<th></th></tr>{body}</table>"
    )
