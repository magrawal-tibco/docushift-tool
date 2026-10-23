"""`reports/verify-<name>.csv` and its HTML summary (Phase 55).

The CSV is the evidence: one row per old page, what it became, and what was
found. The HTML is for the spot-check -- the lowest-scoring pages first, each
with its old and new link, so a reviewer opens the two side by side.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from docushift.utils.csvio import write_rows
from docushift.verify.driver import COLUMNS

SUMMARY_ROWS = 40


def write(reports: Path, name: str, rows: list[dict[str, str]], totals: dict[str, int]) -> tuple[Path, Path]:
    reports.mkdir(parents=True, exist_ok=True)
    csv_path = reports / f"verify-{name}.csv"
    write_rows(csv_path, COLUMNS, rows)
    html_path = reports / f"verify-{name}.html"
    html_path.write_text(_html(name, rows, totals), encoding="utf-8", newline="\n")
    return csv_path, html_path


def _score(row: dict[str, str]) -> tuple[float, int]:
    try:
        percent = float(row.get("text_percent") or 100)
    except ValueError:
        percent = 100.0
    problems = sum(1 for column in ("published_status",) if row.get(column) not in ("", "ok"))
    return (percent, -problems)


def _html(name: str, rows: list[dict[str, str]], totals: dict[str, int]) -> str:
    worst = sorted((r for r in rows if not r.get("skip_reason")), key=_score)[:SUMMARY_ROWS]
    tally = "".join(f"<li><code>{escape(c)}</code>: {n}</li>" for c, n in sorted(totals.items()))

    def link(url: str, label: str) -> str:
        return f'<a href="{escape(url)}">{label}</a>' if url else ""

    body = "".join(
        "<tr>"
        f"<td>{escape(r['slug'])} {escape(r['version'])}</td>"
        f"<td>{escape(r['new_path'])}</td>"
        f"<td>{escape(r['text_percent'])}</td>"
        f"<td>{escape(r['images_found'])}/{escape(r['images_expected'])}</td>"
        f"<td>{escape(r['published_status'])}</td>"
        f"<td>{link(r['old_url'], 'old')} {link(r['staging_url'], 'staging')}</td>"
        f"<td>{escape(r['missing_sentences'][:400])}</td>"
        "</tr>"
        for r in worst
    )
    return (
        f"<!doctype html><meta charset='utf-8'><title>verify {escape(name)}</title>"
        "<style>body{font-family:sans-serif;margin:2em}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccc;padding:4px 8px;vertical-align:top;font-size:13px}</style>"
        f"<h1>verify: {escape(name)}</h1><p>{len(rows)} old page(s) checked.</p>"
        f"<h2>Findings</h2><ul>{tally or '<li>none</li>'}</ul>"
        f"<h2>Lowest-scoring pages</h2><table><tr><th>version</th><th>new page</th><th>text %</th>"
        "<th>images</th><th>staging</th><th>links</th><th>missing sentences</th></tr>"
        f"{body}</table>"
    )
