"""Phase 58 step 8: run `Verifier.version` on one published version, writing nothing.

No report, no `verify_result` row, no versions.csv refresh: findings are buffered
(a `FindingsRun` with no store) and printed. Local only, no network.

    python scratch/verify_toc_probe.py <product-slug> <version> [--all]
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from docushift.catalog import CatalogManager  # noqa: E402
from docushift.config import ConfigManager  # noqa: E402
from docushift.reporting.findings import FindingsRun  # noqa: E402
from docushift.verify import triage  # noqa: E402
from docushift.verify.driver import Verifier  # noqa: E402

slug, version = sys.argv[1], sys.argv[2]
show_all = "--all" in sys.argv
cfg = ConfigManager(root_dir=Path("."))
state = cfg.state_store()
catalog = CatalogManager(cfg.products_path, cfg.versions_path, state, config=cfg).load()
findings = FindingsRun("verify")
findings.start()
target = sys.argv[sys.argv.index("--target") + 1] if "--target" in sys.argv else "C:/github/tibco-docs-aem"
v = Verifier(cfg, catalog, state, Path(target), findings, redirect_sample=10, seed=1,
             triaged=triage.load(cfg.config_dir / "verify-triage.yaml"))
folders = [f for f in v.selection(slug, version) if f.doc_class == "online-help"]
for folder in folders:
    r = v.version(folder)
    print(folder.relative, "skipped:", r.skipped, "| outcome:", r.outcome,
          "errors", r.errors, "warnings", r.warnings, "explained", r.explained)
    print("  codes:", dict(r.codes))
rows = [*findings.recorded, *findings.pending]
by = Counter(f.code for f in rows)
print(by)
for code in sorted(by):
    if code.startswith("VERIFY_TOC") or code == "VERIFY_TOPIC_MISSING" or show_all:
        for f in [x for x in rows if x.code == code][: (999 if show_all else 8)]:
            print(f"  {code} {f.path} :: {f.message[:220]}")
