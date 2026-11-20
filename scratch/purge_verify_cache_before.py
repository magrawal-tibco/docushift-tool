"""Delete `cache/verify/` entries saved before a date (user, 20 Nov: ~100 GB, option 1).

Every batch line runs `verify --refresh`, so a stored page is only read back within the run
that fetched it; older entries are kept only as evidence for triage. Run this after the
triage that needs them. An entry's age is its meta file's time (the meta is written with the
body). Meta first, so a half-removed entry is never read back. Dry run by default.

    python scratch/purge_verify_cache_before.py 2026-11-20           # dry run: count and size
    python scratch/purge_verify_cache_before.py 2026-11-20 --apply
"""
import sys
from datetime import datetime
from pathlib import Path

cutoff = datetime.strptime(sys.argv[1], "%Y-%m-%d").timestamp()
APPLY = "--apply" in sys.argv
root = Path("cache/verify")
old = kept = size = 0
for meta in root.glob("*/*.json"):
    if meta.stat().st_mtime >= cutoff:
        kept += 1
        continue
    body = meta.with_suffix(".bin")
    old += 1
    size += body.stat().st_size if body.is_file() else 0
    if APPLY:
        meta.unlink(missing_ok=True)
        body.unlink(missing_ok=True)
print(f"before {sys.argv[1]}: {old} entries, {size / 1e9:.1f} GB; kept {kept}; "
      + ("removed" if APPLY else "dry run"))
