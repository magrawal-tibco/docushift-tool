"""`reports/repairs/INDEX.csv` and `.html`: versions against repairs (Phase 59).

One row per version that any census has measured, one column per repair, each cell
the state and what is left: `needed (1404)`, `fixed`, `confirmed`, `none`. The page
is rebuilt from `state.db` after every census and apply, so it is never older than
the last measurement.
"""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from docushift.repairs import Repair
from docushift.utils.csvio import write_rows


def cell(row: dict | None) -> str:
    if row is None:
        return ""
    return f"needed ({row['remaining']})" if row["state"] == "needed" else row["state"]


def write_index(root: Path, repairs: list[Repair], status: dict, catalog) -> tuple[Path, Path]:
    """`status` is `StateStore.repair_rows()`; `catalog` gives each product's bu and family."""
    keys = sorted({(slug, version) for slug, version, _ in status})
    rows = []
    for slug, version in keys:
        product = catalog.products.get(slug)
        row = {"bu": product.bu if product else "", "family": product.family if product else "",
               "slug": slug, "version": version}
        for repair in repairs:
            row[repair.id] = cell(status.get((slug, version, repair.id)))
        rows.append(row)
    rows.sort(key=lambda r: (r["bu"], r["family"], r["slug"], r["version"]))
    folder = root / "repairs"
    folder.mkdir(parents=True, exist_ok=True)
    columns = ["bu", "family", "slug", "version", *(r.id for r in repairs)]
    csv_path, html_path = folder / "INDEX.csv", folder / "INDEX.html"
    write_rows(csv_path, columns, rows)
    html_path.write_text(_html(rows, repairs), encoding="utf-8", newline="\n")
    return csv_path, html_path


def _html(rows: list[dict[str, str]], repairs: list[Repair]) -> str:
    summary = "".join(
        f"<li><b>{escape(r.id)}</b> {escape(r.title)} ({escape(r.ticket)}): "
        + escape(", ".join(f"{n} {s}" for s, n in sorted(
            Counter(row[r.id].split(" ")[0] for row in rows if row[r.id]).items())))
        + "</li>"
        for r in repairs
    )
    head = "".join(f"<th>{escape(r.id)}</th>" for r in repairs)
    body = "".join(
        f"<tr><td>{escape(row['bu'])}</td><td>{escape(row['family'])}</td><td>{escape(row['slug'])}</td>"
        f"<td>{escape(row['version'])}</td>"
        + "".join(f"<td class='{escape(row[r.id].split(' ')[0])}'>{escape(row[r.id])}</td>" for r in repairs)
        + "</tr>"
        for row in rows
    )
    return (
        "<!doctype html><meta charset='utf-8'><title>repairs</title>"
        "<style>body{font-family:sans-serif;margin:2em}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccc;padding:4px 8px;font-size:13px}.needed{color:#b00020}"
        ".fixed{color:#a15c00}.confirmed{color:#1b5e20}.none{color:#888}</style>"
        f"<h1>Repairs: every published version</h1><ul>{summary}</ul>"
        f"<table><tr><th>bu</th><th>family</th><th>product</th><th>version</th>{head}</tr>{body}</table>"
    )
