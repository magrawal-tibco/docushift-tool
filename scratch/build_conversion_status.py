"""Build reports/conversion-status.html: the conversion status page for a business audience.

A reader, never a writer: it reads config/products.csv, config/versions.csv,
cache/state.db and the published tree, and embeds what it found into the page.
Counts follow the rules of `docushift status` (reporting/status.py), so the two
agree; it uses only the standard library so it runs without the tool installed.

    python scratch/build_conversion_status.py [--target-dir C:/github/tibco-docs-aem]
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


def progress(db_path: Path) -> dict[tuple[str, str], dict]:
    """The same evidence StateStore.progress() reads: what each stage recorded."""
    db = sqlite3.connect(db_path)
    rows: dict[tuple[str, str], dict] = {}
    for slug, version, download, extract, error in db.execute(
        "SELECT slug, version, download_path, extract_path, error FROM version_state"
    ):
        rows[(slug, version)] = {"d": bool(download), "x": bool(extract), "c": False, "e": error}
    for slug, version in db.execute("SELECT DISTINCT slug, version FROM output_map"):
        rows.setdefault((slug, version), {"d": False, "x": False, "c": False, "e": None})["c"] = True
    return rows


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


def published_versions(target: Path | None) -> set[tuple[str, str]]:
    """(slug, dashed-version) for every version folder under <repo>/<loc>/<slug>/online-help/."""
    found: set[tuple[str, str]] = set()
    if target is None or not target.is_dir():
        return found
    for folder in target.glob("*/*/*/online-help/*"):
        if folder.is_dir():
            found.add((folder.parent.parent.name, folder.name))
    return found


def build(target: Path | None) -> dict:
    products = {row["slug"]: row for row in read_csv(ROOT / "config/products.csv")}
    versions = read_csv(ROOT / "config/versions.csv")
    state = progress(ROOT / "cache/state.db")
    published = published_versions(target)

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

        in_scope = product["in_scope"] == "true"
        retired = v["release_status"] == "retired"
        eligible = in_scope and not retired and v["convert_eligible"] == "true"
        # Where the version stops: a gate, or a pipeline state for the eligible ones.
        if not in_scope:
            stage = "out_of_scope"
        elif retired:
            stage = "retired"
        elif not eligible:
            stage = "not_selected"
        else:
            rec = state.get((v["slug"], v["version"]), {})
            is_pub = (v["slug"], v["version"].replace(".", "-")) in published
            if is_pub:
                stage = "published"
            elif rec.get("c"):
                stage = "converted"
            elif rec.get("x"):
                stage = "blocked_format"
            elif rec.get("e") and not rec.get("d"):
                stage = "blocked_download"
            elif rec.get("d"):
                stage = "in_progress"
            else:
                stage = "not_started"
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
            })
        if stage in ("blocked_format", "blocked_download"):
            entry = blocked[(product["display_name"], stage)]
            entry["versions"].append(v["version"])
            entry["family"] = fam_key

        rows.append([
            fam_key,
            stage,
            v["migrate_decision"],
        ])

    family_list = [
        {"key": k, "bu": f["bu"], "name": f["name"], "products": len(f["products"]),
         "inScope": len(f["in_scope"])}
        for k, f in families.items()
    ]
    blocked_list = [
        {"product": name, "kind": kind, "family": e["family"], "versions": e["versions"]}
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
    parser.add_argument("--target-dir", type=Path, default=Path("C:/github/tibco-docs-aem"))
    parser.add_argument("--out", type=Path, default=ROOT / "reports/conversion-status.html")
    args = parser.parse_args()
    data = build(args.target_dir)
    template = (ROOT / "scratch/conversion_status_template.html").read_text(encoding="utf-8")
    page = template.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out}  {data['gates']}")


if __name__ == "__main__":
    main()
