"""Phase 33 step 1: per converted version, the best (drop k, URL prefix) mapping and its coverage.

Mappings that yield the same URL for every source are one mapping (EMS: drop 1 + '.../doc' ==
drop 2 + '.../doc/html'), so votes are grouped by the URL set they produce.
"""
import sqlite3
from collections import Counter, defaultdict
from urllib.parse import unquote, urlsplit
from pathlib import Path
from docushift.discovery.sitemap import SitemapCache, SitemapError

cache = SitemapCache(Path("cache/coveo"))
db = sqlite3.connect("cache/state.db")
pairs = db.execute("SELECT DISTINCT slug, version FROM output_map ORDER BY slug, version").fetchall()
out = []
for slug, version in pairs:
    sources = [r[0] for r in db.execute("SELECT source FROM output_map WHERE slug=? AND version=?", (slug, version))]
    try:
        pages = cache.pages(slug, version)
    except SitemapError:
        pages = None
    if pages is None:
        out.append((slug, version, len(sources), None, 0, 0, "", 0)); continue
    paths = [unquote(urlsplit(p.loc).path).lstrip("/") for p in pages]
    by_tail = defaultdict(set)
    for p in paths:
        segs = p.split("/")
        for i in range(len(segs)):
            by_tail["/".join(segs[i:])].add("/".join(segs[:i]))
    # mapping -> set of URLs it produced
    produced = defaultdict(set)
    for s in sources:
        parts = s.split("/")
        for k in range(0, min(4, len(parts))):
            tail = "/".join(parts[k:])
            for prefix in by_tail.get(tail, ()):
                produced[(k, prefix)].add(prefix + "/" + tail if prefix else tail)
    groups = {}
    for m, urls in produced.items():
        groups.setdefault(frozenset(urls), m)
    ranked = sorted(((len(u), m) for u, m in groups.items()), reverse=True)
    best = ranked[0] if ranked else (0, None)
    rival = ranked[1][0] if len(ranked) > 1 else 0
    out.append((slug, version, len(sources), len(pages), best[0], rival, str(best[1]), sum(1 for x in ranked if x[0] > 0)))

import csv
with open("scratch/coveo-overlap.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["slug","version","sources","leaf_pages","best_hits","rival_hits","best_mapping","mappings"]); w.writerows(out)
conv = len(out); leaf = [r for r in out if r[3] is not None]
print("converted versions", conv, "with leaf", len(leaf))
buckets = Counter()
for r in leaf:
    pct = r[4] / r[2] if r[2] else 0
    buckets["100%" if pct == 1 else ">=90%" if pct >= .9 else ">=50%" if pct >= .5 else ">0%" if pct > 0 else "0%"] += 1
print("coverage of output_map by best mapping:", dict(buckets))
close = [r for r in leaf if r[4] and r[5] >= r[4] * 0.9]
print("versions with a rival within 10%:", len(close))
