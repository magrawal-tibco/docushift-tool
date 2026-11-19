"""Delete `cache/verify/` entries that stored a refusal (Phase 85, DOCOPS-383).

Before Phase 85 the verify fetcher cached a 429 / 5xx answer as the page's answer; about
1,700 were stored overnight 18-19 Nov. The fetcher now ignores them, so this only reclaims
the space and makes the cache honest. Reads every meta file once (one folder level per
hash prefix); no whole-drive scan.

    python scratch/purge_verify_refusals.py           # dry run: counts by status
    python scratch/purge_verify_refusals.py --apply
"""
import json
import sys
from collections import Counter
from pathlib import Path

REFUSED = {0, 429, 500, 502, 503, 504}
APPLY = "--apply" in sys.argv
root = Path("cache/verify")
counts, removed, scanned = Counter(), 0, 0
for meta in root.glob("*/*.json"):
    scanned += 1
    try:
        status = int(json.loads(meta.read_text(encoding="utf-8"))["status"])
    except (OSError, ValueError, KeyError):
        continue
    if status not in REFUSED:
        continue
    counts[status] += 1
    if APPLY:
        meta.unlink(missing_ok=True)  # the meta first: without it the entry is gone
        meta.with_suffix(".bin").unlink(missing_ok=True)
        removed += 1
print(f"{scanned} entries read; refusals by status: {dict(counts)}; "
      + (f"{removed} removed" if APPLY else "dry run"))
