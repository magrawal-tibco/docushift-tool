"""Build reports/conversion-status.html: the conversion status page for a business audience.

A reader, never a writer: it reads config/products.csv, config/versions.csv,
cache/state.db and the published tree, and embeds what it found into the page.
Where each version stands is read from versions.csv's `_status` and `_sync_status`
columns (Phase 38), which the tool derives with the same rules as `docushift
status`, so the page, the sheet and the command cannot disagree. Standard library
only, so it runs without the tool installed.

    python scratch/build_conversion_status.py
"""

import argparse
import collections
import csv
import datetime as dt
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BU_NAMES = {"tibco": "TIBCO", "ibi": "IBI", "spotfire": "Spotfire", "datasynapse": "DataSynapse", "onebx": "EBX"}
ENGINE_NAMES = {"flare": "MadCap Flare", "webworks": "WebWorks", "docbook": "DocBook", "dita": "DITA (SuiteHelp)"}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validation_summary(db_path: Path) -> dict | None:
    db = sqlite3.connect(db_path)
    run = db.execute(
        "SELECT run_id, started_at FROM runs WHERE command='validate' ORDER BY run_id DESC LIMIT 1"
    ).fetchone()
    if run is None:
        return None
    codes = db.execute(
        "SELECT severity, code, SUM(count) FROM findings WHERE run_id=? GROUP BY 1, 2", (run[0],)
    ).fetchall()
    return {
        "date": run[1][:10],
        "errors": sum(n for sev, _, n in codes if sev == "error"),
        "warnings": sum(n for sev, _, n in codes if sev == "warning"),
        "codes": {code: n for _, code, n in codes},
    }


# `_status` -> the page's stage. A converted or merged version counts as published
# once `sync` has placed it (`out-of-date` is still placed, just rebuilt since).
STAGE_OF = {
    "out-of-scope": "out_of_scope", "retired": "retired", "not-selected": "not_selected",
    "not-started": "not_started", "downloaded": "in_progress", "extracted": "in_progress",
    "download-failed": "blocked_download", "format-unknown": "blocked_format", "pdf-only": "pdf_only", "pdf-ready": "pdf_only",
    "extract-failed": "blocked_failed", "convert-failed": "blocked_failed",
    "merge-failed": "blocked_failed", "converted": "converted", "merged": "converted",
}


def build() -> dict:
    products = {row["slug"]: row for row in read_csv(ROOT / "config/products.csv")}
    versions = read_csv(ROOT / "config/versions.csv")
    if versions and "_status" not in versions[0]:
        raise SystemExit("versions.csv has no _status column; run `docushift catalog refresh` first.")

    gates = collections.Counter()
    rows = []  # one per catalogued version, packed for the page's filters
    families: dict[str, dict] = {}
    converted_detail = []
    blocked = collections.defaultdict(lambda: {"versions": [], "reason": ""})

    for v in versions:
        product = products[v["slug"]]
        bu = product["bu"]
        fam_key = f"{bu}/{product['family']}"
        families.setdefault(fam_key, {
            "bu": BU_NAMES.get(bu, bu),
            "name": product["_family_name"] or product["family"],
            "products": set(),
            "in_scope": set(),
        })["products"].add(v["slug"])
        if product["in_scope"] == "true":
            families[fam_key]["in_scope"].add(v["slug"])

        if v["_status"] not in STAGE_OF:
            # A value this page does not know is a new status the tool learned; counting
            # it as anything would misreport it, so stop and say which.
            raise SystemExit(f"Unknown _status '{v['_status']}' on {v['slug']}@{v['version']}; "
                             f"add it to STAGE_OF in this script.")
        stage = STAGE_OF[v["_status"]]
        if stage == "converted" and v["_sync_status"] in ("synced", "out-of-date"):
            stage = "published"
        gates[stage] += 1

        if stage in ("published", "converted"):
            converted_detail.append({
                "product": product["display_name"],
                "slug": v["slug"],
                "family": fam_key,
                "version": v["version"],
                "engine": ENGINE_NAMES.get(v["engine"], v["engine"]),
                "topics": int(v["_md_files"] or 0),
                "pages": int(v["_reframed_md_files"] or 0),
                "published": stage == "published",
                "built": v["_status_date"],
                "sync": v["_sync_status"],
                "synced": v["_sync_date"],
            })
        if stage.startswith("blocked_"):
            entry = blocked[(product["display_name"], stage)]
            entry["versions"].append(v["version"])
            entry.setdefault("dates", []).append(v["_status_date"])
            entry["family"] = fam_key

        # Packed for size: the page filters 5,181 of these. The last four are the
        # sheet's own status columns, verbatim, so the page speaks the sheet's words.
        rows.append([
            fam_key,
            stage,
            v["migrate_decision"],
            v["_status"],
            v["_status_date"],
            v["_sync_status"],
            v["_sync_date"],
        ])

    family_list = [
        {"key": k, "bu": f["bu"], "name": f["name"], "products": len(f["products"]),
         "inScope": len(f["in_scope"])}
        for k, f in families.items()
    ]
    blocked_list = [
        {"product": name, "kind": kind, "family": e["family"], "versions": e["versions"],
         "last": max(e["dates"])}
        for (name, kind), e in sorted(blocked.items(), key=lambda kv: (-len(kv[1]["versions"]), kv[0][0]))
    ]
    in_scope_products = sum(1 for p in products.values() if p["in_scope"] == "true")
    return {
        "asOf": dt.date.today().isoformat(),
        "productsTotal": len(products),
        "productsInScope": in_scope_products,
        "families": family_list,
        "rows": rows,
        "converted": converted_detail,
        "blocked": blocked_list,
        "validation": validation_summary(ROOT / "cache/state.db"),
        "gates": dict(gates),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "reports/conversion-status.html")
    args = parser.parse_args()
    data = build()
    template = (ROOT / "scratch/conversion_status_template.html").read_text(encoding="utf-8")
    page = template.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out}  {data['gates']}")


if __name__ == "__main__":
    main()
