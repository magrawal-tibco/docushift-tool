import csv
from pathlib import Path
from docushift.config import ConfigManager
from docushift.catalog import CatalogManager
from docushift.state import StateStore
from docushift.sync import WorkspaceDistributor
from docushift.utils.slug import version_segment

TARGETS = {"tibco": Path(r"C:\github\tibco-docs-aem"), "ibi": Path(r"C:\github\ibi-docs-aem")}
cfg = ConfigManager(root_dir=Path("."))
manager = CatalogManager(cfg.products_path, cfg.versions_path, StateStore(cfg.state_db_path), config=cfg)
dist = WorkspaceDistributor(cfg, manager)
src = Path("reports/sitemap-missing.csv")
rows = list(csv.DictReader(src.open(encoding="utf-8")))
out = []
for r in rows:
    p = manager.get_product(r["slug"])
    path = dist.doc_class_dir(p, TARGETS[r["bu"]]) / version_segment(r["version"])
    out.append({**{k: r[k] for k in ("bu", "family", "slug", "version", "engine")},
                "publishing_path": str(path), "published": "yes" if path.is_dir() else "no",
                "reason": r["reason"], "detail": r["detail"]})
with src.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader(); w.writerows(out)
print(len(out))
