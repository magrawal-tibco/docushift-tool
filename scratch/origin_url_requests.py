"""Phase 60 follow-up: a sheet asking for one live URL per product whose 301 map cannot be built.

Read-only. For every published TIBCO online-help version with no `301.yml`, one row: the
product, the version, why there is no map (not in the docsite's Coveo sitemap, or in it
but no template derived), and a **sample topic** -- its title as published and its path in
the downloaded package -- with an empty `live_url` column for a person to fill from
docs.tibco.com. One live URL is enough to declare the product's template in
`config/origin-urls.yaml` (template + drop_segments); a row marked `needed=no` shares its
layout with a row above it and may be left blank.

    python scratch/origin_url_requests.py   -> reports/origin-url-requests.csv
"""
import csv
import html
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, "src")
from docushift.config import ConfigManager  # noqa: E402
from docushift.origins import folder_path  # noqa: E402
from docushift.utils.csvio import natural_version_key  # noqa: E402
from docushift.utils.slug import version_segment  # noqa: E402

cfg = ConfigManager(root_dir=Path("."))

TREE = Path("C:/github/tibco-docs-aem")
OUT = Path("reports/origin-url-requests.csv")

catalog = {(r["slug"], version_segment(r["version"])): r
           for r in csv.DictReader(open("config/versions.csv", encoding="utf-8-sig"))}
products = {r["slug"]: r for r in csv.DictReader(open("config/products.csv", encoding="utf-8-sig"))}
sitemap = set(json.load(open("cache/coveo/manifest.json", encoding="utf-8"))["products"])
db = sqlite3.connect("file:cache/state.db?mode=ro", uri=True)

missing: list[tuple[str, str, str]] = []  # (repo, slug, segment)
for repo in sorted(p for p in TREE.iterdir() if (p / ".git").exists()):
    files = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True,
                           encoding="utf-8").stdout.splitlines()
    tocs = {f.rsplit("/", 1)[0] for f in files if "/online-help/" in f and f.endswith("/toc.yml")}
    maps = {f.rsplit("/", 1)[0] for f in files if "/online-help/" in f and f.endswith("/301.yml")}
    for folder in sorted(tocs - maps):
        parts = folder.split("/")  # en-us/<slug>/online-help/<segment>
        if len(parts) == 4:
            missing.append((repo.name, parts[1], parts[3]))


TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)


def sample(slug: str, number: str, extracted: Path) -> tuple[str, str]:
    """A topic in the version's TOC, from the middle of its list: (title, package path).

    The title is read from the downloaded page itself (`<h1>`, else `<title>`): it is
    what the reader sees on docs.tibco.com, and a merged page's published name differs.
    """
    rows = db.execute("select source, output from output_map where slug=? and version=? order by source",
                      (slug, number)).fetchall()
    rows = [(s, o) for s, o in rows if s.lower().endswith((".htm", ".html")) and not o.startswith("unfiled/")
            and "index" not in PurePosixPath(s).stem.lower()]
    if not rows:
        return "", ""
    source, _output = rows[len(rows) // 2]
    title = ""
    try:
        raw = (extracted / PurePosixPath(source)).read_bytes()
        text = raw.decode("utf-8") if raw.startswith(b"\xef\xbb\xbf") or _utf8(raw) else raw.decode("cp1252", "replace")
        found = H1.search(text) or TITLE.search(text)
        if found:
            title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", found.group(1))).split())
    except OSError:
        pass
    return title, source


def _utf8(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def layout(source: str, segment: str) -> str:
    """What a product's template depends on: the package's top folder, wrapper dropped.

    A wrapper is the first folder when it names the version (`tibco-x-1-2-0/html/...`);
    the next folder (`html`, `doc`, `designerhelp`) is then the served root.
    """
    parts = PurePosixPath(source).parts
    if len(parts) > 2 and parts[0].lower().endswith(segment.lower()):
        return f"wrapper/{parts[1]}"
    return parts[0] if len(parts) > 1 else ""


seen: set[tuple[str, str]] = set()
OUT.parent.mkdir(exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.writer(handle)
    writer.writerow(["slug", "product", "version", "reason", "needed", "start_here", "docsite_folder",
                     "sample_topic_title", "sample_topic_in_package", "live_url", "notes"])
    # Newest version first within a product, so the row marked `needed` is the one
    # readers use most and the one most likely still served.
    ordered = sorted(missing, key=lambda m: (m[1], natural_version_key(m[2])), reverse=True)
    ordered.sort(key=lambda m: m[1])
    for repo, slug, segment in ordered:
        row = catalog.get((slug, segment))
        number = row["version"] if row else segment
        product = products.get(slug) or {}
        extracted = cfg.extract_path(row["_bu"], row["_family"], slug, number) if row else Path()
        title, source = sample(slug, number, extracted)
        shape = (slug, layout(source, segment))
        needed = "yes" if shape not in seen else "no"
        seen.add(shape)
        reason = "not in docsite sitemap" if slug not in sitemap else "in sitemap, no map derived"
        writer.writerow([slug, product.get("display_name", ""), number, reason, needed,
                         f"https://docs.tibco.com/products/{slug}",
                         folder_path(row["zip_url"]) if row else "", title, source, "", ""])
print(f"{OUT}: {len(missing)} versions, {len({m[1] for m in missing})} products, "
      f"{sum(1 for s in seen)} layouts to fill")
