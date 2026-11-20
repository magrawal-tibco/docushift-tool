"""Build reports/conversion-status.html: where the migration stands, for a business audience.

A reader, never a writer: it reads config/products.csv, config/versions.csv,
cache/state.db and the DOCOPS snapshot (reports/jira/docops-snapshot.json, written by
fetch_docops.py), and embeds what it found into the page. Its first tab, "Where we
stand" (closeout plan §8b), also reads config/status-areas.yaml (hand-kept),
reports/verify/INDEX.csv and ISSUES.csv, the Karan change list and the plan's
decisions table, and writes the same status as reports/status-latest.md. Where each version stands
is read from versions.csv's `_status`, `_sync_status`, `_verify_status` and
`_repairs_pending` columns, which the tool derives with the same rules as `docushift
status`, so the page, the sheet and the command cannot disagree. Standard library
only, so it runs without the tool installed.

    python scratch/fetch_docops.py
    python scratch/build_conversion_status.py

`--data-root` reads the catalog, state and reports from another checkout (a worktree
builds from the main tree's live data); outputs and the areas file stay in this one.
"""

import argparse
import collections
import csv
import datetime as dt
import json
import sqlite3
from pathlib import Path

import read_xlsx
import status_page

ROOT = Path(__file__).resolve().parents[1]
# The user's .xlsx download of the UAT sheet, all tabs (20 Nov; gcloud cannot read Sheets).
UAT_XLSX = "cache/TIbco_IBI_Spotfire UAT Sheet.xlsx"
UAT_URL = "https://docs.google.com/spreadsheets/d/1lcMg602HoTxxvMTQnrzEt2i4Ft2Z4ch0dwmmIlZo6eg/edit?usp=sharing"
# Business units handed over and not ours to report (user, 20 Nov: Spotfire belongs to
# Digital Platform since the 19 Nov hand-over). Left out of every tab of the page.
NOT_OURS = {"spotfire"}
BU_NAMES = {"tibco": "TIBCO", "ibi": "IBI", "spotfire": "Spotfire", "datasynapse": "DataSynapse", "onebx": "EBX"}
ENGINE_NAMES = {"flare": "MadCap Flare", "webworks": "WebWorks", "docbook": "DocBook", "dita": "DITA (SuiteHelp)"}
# The epics this tool's work is logged under (docs/jira.md); DOCOPS also holds other teams' issues.
WORK_EPICS = {"DOCOPS-5", "DOCOPS-74", "DOCOPS-75", "DOCOPS-139", "DOCOPS-153", "DOCOPS-170"}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validation_summary(db_path: Path) -> dict | None:
    if not db_path.exists():
        return None
    db = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
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


# `_status` values that keep a version out of the migration; anything else is in it.
OUT_OF_MIGRATION = {"out-of-scope", "retired", "not-selected"}
# `_status` -> (furthest step reached before placing, attention reason or None).
BUILD_STEP = {
    "not-started": ("not_started", None), "download-failed": ("not_started", "blocked-download"),
    "downloaded": ("downloaded", None), "extracted": ("downloaded", None),
    "format-unknown": ("downloaded", "blocked-format"), "extract-failed": ("downloaded", "blocked-failed"),
    "convert-failed": ("downloaded", "blocked-failed"), "merge-failed": ("built", "blocked-failed"),
    "converted": ("built", None), "merged": ("built", None), "pdf-only": ("built", None), "pdf-ready": ("built", None),
}
PLACED = {"synced", "out-of-date"}
SYNC_KNOWN = PLACED | {"sync-failed", ""}
VERIFY_KNOWN = {"", "not-verified", "stale", "clean", "explained", "logged", "issues", "lost"}
# A check result in which every finding is understood: nothing lost, explained, or
# each kind logged in Jira to be fixed later (Phase 77).
VERIFY_UNDERSTOOD = ("clean", "explained", "logged")


def place(v: dict) -> tuple[str | None, list[str]]:
    """The ladder step a version has reached, and why it needs a person, if it does.

    Steps: not_started -> downloaded -> built -> fixes_pending -> placed -> checked.
    A version outside the migration has no step; it only needs attention when `sync`
    placed it before it was deselected or retired.
    """
    status, sync, verify = v["_status"], v["_sync_status"], v["_verify_status"]
    # A value this page does not know is something the tool learned since; placing it
    # anywhere would misreport it, so stop and say which.
    for value, known, col in ((sync, SYNC_KNOWN, "_sync_status"), (verify, VERIFY_KNOWN, "_verify_status")):
        if value not in known:
            raise SystemExit(f"Unknown {col} '{value}' on {v['slug']}@{v['version']}; add it to this script.")
    if status in OUT_OF_MIGRATION:
        return None, (["deselected"] if sync in PLACED else [])
    if status not in BUILD_STEP:
        raise SystemExit(f"Unknown _status '{status}' on {v['slug']}@{v['version']}; add it to BUILD_STEP.")
    step, reason = BUILD_STEP[status]
    reasons = [reason] if reason else []
    if step == "built" and not reasons:
        if sync in PLACED:
            step = ("fixes_pending" if v["_repairs_pending"]
                    else "checked" if verify in VERIFY_UNDERSTOOD else "placed")
            if sync == "out-of-date":
                reasons.append("resync")
            if verify in ("lost", "issues"):
                reasons.append(verify)
        elif sync == "sync-failed":
            reasons.append("sync-failed")
    return step, reasons


def build(jira_snapshot: Path, data: Path = ROOT) -> dict:
    products = {row["slug"]: row for row in read_csv(data / "config/products.csv") if row["bu"] not in NOT_OURS}
    versions = [v for v in read_csv(data / "config/versions.csv") if v["slug"] in products]
    if versions and "_repairs_pending" not in versions[0]:
        raise SystemExit("versions.csv has no _repairs_pending column; run `docushift catalog refresh` first.")

    families: dict[str, dict] = {}
    product_index: dict[str, int] = {}
    product_list = []
    rows = []
    for v in versions:
        product = products[v["slug"]]
        fam_key = f"{product['bu']}/{product['family']}"
        fam = families.setdefault(fam_key, {
            "key": fam_key, "bu": BU_NAMES.get(product["bu"], product["bu"]),
            "name": product["_family_name"] or product["family"], "products": set(), "in_scope": set(),
        })
        fam["products"].add(v["slug"])
        if product["in_scope"] == "true":
            fam["in_scope"].add(v["slug"])
        if v["slug"] not in product_index:
            product_index[v["slug"]] = len(product_list)
            product_list.append([product["display_name"], fam_key, v["slug"]])

        step, reasons = place(v)
        # Packed for size: the page filters 5,192 of these. Status columns are the
        # sheet's own words, verbatim, so the page speaks the sheet's language.
        rows.append([
            product_index[v["slug"]], v["version"], step, reasons,
            v["_status"], v["_status_date"], v["_sync_status"], v["_sync_date"],
            v["_verify_status"], v["_verify_date"], v["_repairs_pending"],
            ENGINE_NAMES.get(v["engine"], "" if v["engine"] in ("", "auto") else v["engine"]),
            v["migrate_decision"], int(v["_md_files"] or 0), int(v["_reframed_md_files"] or 0),
        ])

    family_list = [
        {"key": f["key"], "bu": f["bu"], "name": f["name"], "products": len(f["products"]),
         "inScope": len(f["in_scope"])}
        for f in families.values()
    ]
    return {
        "asOf": dt.date.today().isoformat(),
        "productsTotal": len(products),
        "productsInScope": sum(1 for p in products.values() if p["in_scope"] == "true"),
        "families": family_list,
        "products": product_list,
        "rows": rows,
        "validation": validation_summary(data / "cache/state.db"),
        "jira": jira_work(jira_snapshot),
    }


def jira_work(path: Path) -> dict | None:
    """DOCOPS sub-tasks under this work's epics: points, status and dates, by story.

    Most sub-tasks were logged on 2026-10-07 for work already done, so a resolved date
    is when it was logged, not when it was done. `retro` marks that work (finished
    before the month it was logged in); the page shows it as one column, not a spike.
    """
    if not path.exists():
        return None
    snap = json.loads(path.read_text(encoding="utf-8"))
    issues = {i["key"]: i for i in snap["issues"]}

    def epic_of(key: str | None) -> str | None:
        seen = set()
        while key and key not in seen:
            if key in WORK_EPICS:
                return key
            seen.add(key)
            key = issues.get(key, {}).get("parent")
        return None

    stories = {}
    tasks = []
    for i in issues.values():
        if i["type"] != "Sub-task" or i["status"] == "Canceled":
            continue
        epic = epic_of(i["parent"])
        if epic is None:
            continue
        story = issues.get(i["parent"], {})
        stories.setdefault(i["parent"], {"key": i["parent"], "summary": story.get("summary", ""), "epic": epic,
                                         "epicSummary": issues.get(epic, {}).get("summary", "")})
        tasks.append([i["key"], i["summary"], i["parent"], i["category"], i["status"], i["sp"] or 0,
                      i["resolved"], "retro" in i["labels"], i["created"]])
    return {"fetched": snap["fetched"], "site": "https://csg-engops.atlassian.net/browse/",
            "stories": list(stories.values()), "tasks": tasks}


CHECK_RESULTS = {"clean", "explained", "logged", "issues", "lost"}


def _modified(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if path.exists() else ""


def where_we_stand(data: Path, areas_path: Path, jira_snapshot: Path, now: dt.datetime) -> dict:
    """The first tab and status-latest.md (closeout plan §8b): headline, areas, effort, pending."""
    cfg = status_page.load_areas(areas_path.read_text(encoding="utf-8"))
    products = {row["slug"]: row for row in read_csv(data / "config/products.csv") if row["bu"] not in NOT_OURS}
    versions = [v for v in read_csv(data / "config/versions.csv") if v["slug"] in products]
    index_path = data / "reports/verify/INDEX.csv"
    staging_scope = {(r["slug"], r["version"]) for r in (read_csv(index_path) if index_path.exists() else [])
                     if "staging" in r["scope"].split("+")}

    records, by_version = [], {}
    understood = local_only = 0
    for v in versions:
        step, _ = place(v)
        published = v["_sync_status"] in PLACED
        checked = bool(step) and published and v["_verify_status"] in CHECK_RESULTS
        on_staging = checked and (v["slug"], v["version"]) in staging_scope
        understood += on_staging and v["_verify_status"] in VERIFY_UNDERSTOOD
        local_only += checked and not on_staging
        bu = products[v["slug"]]["bu"]
        records.append({"bu": BU_NAMES.get(bu, bu), "inMig": bool(step),
                        "converted": step not in (None, "not_started", "downloaded"),
                        "published": bool(step) and published, "staging": on_staging,
                        "checked": checked, "understood": checked and v["_verify_status"] in VERIFY_UNDERSTOOD})
        by_version[(v["slug"], v["version"])] = {"migrate_decision": v["migrate_decision"], "published": published}
    head = status_page.headline(records, now.date(), cfg["goLive"], cfg["oldSiteOff"])
    uat_path = data / UAT_XLSX
    uat = status_page.uat_summary(read_xlsx.read(str(uat_path))) if uat_path.exists() else {}
    head["uatAsOf"] = _modified(uat_path)
    head["uatUrl"] = UAT_URL
    for row in head["byBu"]:
        row["health"] = status_page.bu_health(row, uat.get(row["bu"]), cfg["buHealth"].get(row["bu"]))
    t = head["total"]

    issues_path = data / "reports/verify/ISSUES.csv"
    kind_summary = status_page.problem_kinds(read_csv(issues_path) if issues_path.exists() else [], cfg["owners"])
    measures = {
        "conversion": {"done": t["converted"], "total": t["inMig"], "unit": "versions", "detail": "converted"},
        "publishing": {"done": t["published"], "total": t["inMig"], "unit": "versions",
                       "detail": "in the new site's repositories"},
        "staging_checks": {"done": t["staging"], "total": t["published"], "unit": "versions",
                           "detail": f"of those in the repositories, checked on staging; {understood} with every "
                                     f"finding clean, explained or logged; {local_only} more checked against our "
                                     f"own copy only"},
        "problems": {"done": kind_summary["entries"] - kind_summary["unlogged"], "total": kind_summary["entries"],
                     "unit": "finding types", "detail": f"sorted at triage; {kind_summary['unlogged']} still to sort, "
                                                        f"{kind_summary['accepted']} accepted as they are"},
    }
    karan_path = data / "reports/karan-decision-changes-2026-11-12.csv"
    if karan_path.exists():
        measures["karan"] = status_page.karan_measure(read_csv(karan_path), by_version)

    snap = json.loads(jira_snapshot.read_text(encoding="utf-8")) if jira_snapshot.exists() else None
    issues = snap["issues"] if snap else []
    eff = status_page.effort(issues, cfg["areas"]) if snap else None
    rows = status_page.area_rows(cfg["areas"], measures, issues, eff["assigned"] if eff else {}, cfg["owners"])
    plan_path = data / "docs/closeout-plan.md"
    plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
    decisions = status_page.open_decisions(plan_text, cfg["goLive"][:7])
    if eff:
        del eff["assigned"]
        eff["fetched"] = snap["fetched"]
        eff["daysSinceFirst"] = (now.date() - dt.date.fromisoformat(eff["firstIssue"])).days
    return {
        "asOf": now.strftime("%Y-%m-%d %H:%M"),
        "asOfText": f"{now.day} {now.strftime('%b %Y, %H:%M')}"
                    + (f" (Jira as of {status_page.day_text(snap['fetched'])})" if snap else " (no Jira snapshot)"),
        "sources": {"versions": _modified(data / "config/versions.csv"), "checks": _modified(issues_path),
                    "areas": _modified(areas_path), "plan": _modified(plan_path), "uat": _modified(uat_path),
                    "jira": snap["fetched"] if snap else ""},
        "headline": head,
        "areas": rows,
        "effort": eff,
        "decisions": decisions,
        "pending": status_page.pending_by_team(rows, decisions, kind_summary),
        "kinds": kind_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "reports/conversion-status.html")
    parser.add_argument("--md-out", type=Path, default=ROOT / "reports/status-latest.md")
    parser.add_argument("--jira", type=Path, default=ROOT / "reports/jira/docops-snapshot.json")
    parser.add_argument("--areas", type=Path, default=ROOT / "config/status-areas.yaml")
    parser.add_argument("--data-root", type=Path, default=ROOT,
                        help="checkout to read config/, cache/, reports/verify/ and docs/ from")
    args = parser.parse_args()
    data = build(args.jira, args.data_root)
    stand = where_we_stand(args.data_root, args.areas, args.jira, dt.datetime.now())
    data["stand"] = stand
    template = (ROOT / "scratch/conversion_status_template.html").read_text(encoding="utf-8")
    page = template.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    args.out.write_text(page, encoding="utf-8")
    args.md_out.write_text(status_page.render_markdown(stand), encoding="utf-8")
    steps = collections.Counter(r[2] for r in data["rows"] if r[2])
    attention = sum(1 for r in data["rows"] if r[3])
    t = stand["headline"]["total"]
    print(f"wrote {args.out}  {dict(steps)}  needs attention: {attention}"
          f"  jira: {'snapshot ' + data['jira']['fetched'] if data['jira'] else 'no snapshot'}")
    print(f"wrote {args.md_out}  in migration {t['inMig']}, converted {t['converted']}, "
          f"in repositories {t['published']}, checked on staging {t['staging']}")


if __name__ == "__main__":
    main()
