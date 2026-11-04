"""DOCOPS-322: one origin template per product from the confirmed URLs, plus addresses to test it.

Read-only for everything but its two outputs:

  reports/origin-url-patterns.draft.yaml  -- `products:` entries in `config/origin-urls.yaml`'s
      shape (template, drop_segments, verified), plus `home_page_only` and `no_redirect` lists.
      A DRAFT: not read by any command. Copied into `config/origin-urls.yaml` when the
      301.yml rebuild resumes (on hold for the AEM team's changes, 2026-11-03).
  reports/origin-url-pattern-tests.csv    -- per product, 3 other topics of the sampled
      version and the address the template gives each, for a person to open (`works` column).

A confirmed URL is `live_url`, else `suggested_url` where `suggestion_ok` is yes. A WebWorks
`wwhelp.htm#href=<topic>` is read as the topic's own address (confirmed 2026-11-03).

    python scratch/origin_url_patterns.py
"""
import csv
import sqlite3
from collections import defaultdict
from pathlib import PurePosixPath
from urllib.parse import quote, unquote, urlsplit

import yaml

SHEET = "reports/origin-url-requests.csv"
DRAFT = "reports/origin-url-patterns.draft.yaml"
TESTS = "reports/origin-url-pattern-tests.csv"
WWHELP = "wwhelp/wwhimpl/js/html/wwhelp.htm"

rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
db = sqlite3.connect("file:cache/state.db?mode=ro", uri=True)


def confirmed(row) -> str:
    url = row["live_url"].strip()
    if not url and row.get("suggestion_ok", "").strip().lower() in ("yes", "y"):
        url = row["suggested_url"].strip()
    if WWHELP in url:
        head, _, topic = url.partition(WWHELP)
        topic = topic.partition("#href=")[2]
        return head + quote(unquote(topic)) if topic else ""  # wwhelp.htm alone names no topic
    return url


def derive(row, url: str):
    """(template, drop_segments) such that template.format(folder_path, path) == url, or None."""
    source = PurePosixPath(row["sample_topic_in_package"]).parts
    served = [unquote(p) for p in urlsplit(url).path.strip("/").split("/")]
    common = 0
    while common < min(len(source), len(served)) and source[-1 - common].lower() == served[-1 - common].lower():
        common += 1
    if common == 0:
        return None
    drop = len(source) - common
    prefix = "/".join(served[:-common])
    folder = row["docsite_folder"].strip("/")
    if folder and f"/{folder}/" in f"/{prefix}/":
        prefix = f"/{prefix}/".replace(f"/{folder}/", "/{folder_path}/", 1).strip("/")
    return f"https://docs.tibco.com/{prefix}/{{path}}", drop


by_product: dict[str, list[tuple[str, int, str, dict]]] = defaultdict(list)
home_only, no_redirect, failed = [], [], []
for row in rows:
    note = row["notes"].strip().lower()
    url = confirmed(row)
    if "not eligible" in note:
        continue  # handled as a catalog change (2026-11-04)
    if "no online help" in note:
        no_redirect.append({"slug": row["slug"], "version": row["version"], "reason": row["notes"].strip()})
        continue
    if not url and ("home page" in note or "no specific topic" in note or "no redirection required" in note):
        home_only.append({"slug": row["slug"], "version": row["version"], "reason": row["notes"].strip()})
        continue
    if not url:
        continue
    found = derive(row, url)
    if found is None:
        # The URL names another topic than the sample (BPM 4.3.0): use that topic's own
        # package path, found by its file name in the version's output map.
        name = unquote(urlsplit(url).path.rsplit("/", 1)[-1]).lower()
        hits = [s for (s,) in db.execute("select source from output_map where slug=? and version=?",
                                         (row["slug"], row["version"])) if s.lower().endswith("/" + name)]
        if len(hits) == 1:
            found = derive({**row, "sample_topic_in_package": hits[0]}, url)
    if found is None:
        failed.append((row["slug"], row["version"], url))
        continue
    by_product[row["slug"]].append((found[0], found[1], url, row))

products, conflicts = {}, []
for slug, found in sorted(by_product.items()):
    shapes = {(t, d) for t, d, _, _ in found}
    template, drop, url, row = found[0]
    entry = {"template": template, "drop_segments": drop,
             "verified": f"{url} (sheet {row['version']}, 2026-11-04)"}
    if len(shapes) > 1:
        conflicts.append((slug, sorted(shapes)))
        # One product, two package shapes: `drop_segments` is per product today, so this
        # needs a per-version value (or "drop the wrapper when present") before it is applied.
        entry["per_version"] = {r["version"]: {"template": t, "drop_segments": d} for t, d, _, r in found}
    products[slug] = entry

with open(DRAFT, "w", encoding="utf-8") as handle:
    handle.write("# DRAFT for config/origin-urls.yaml (DOCOPS-322). Not read by any command.\n"
                 "# Built by scratch/origin_url_patterns.py from reports/origin-url-requests.csv.\n")
    yaml.safe_dump({"products": products, "home_page_only": home_only, "no_redirect": no_redirect},
                   handle, sort_keys=False, allow_unicode=True, width=200)

with open(TESTS, "w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.writer(handle)
    writer.writerow(["slug", "version", "topic_in_package", "test_url", "works", "notes"])
    for slug, found in sorted(by_product.items()):
        template, drop, _url, row = found[0]
        number = row["version"]
        folder = row["docsite_folder"].strip("/")
        sources = [s for (s,) in db.execute("select source from output_map where slug=? and version=? order by source",
                                            (slug, number))
                   if s.lower().endswith((".htm", ".html")) and s != row["sample_topic_in_package"]]
        picks = [sources[int(i * len(sources) / 3)] for i in range(3)] if len(sources) >= 3 else sources
        for source in picks:
            parts = PurePosixPath(source).parts
            if len(parts) <= drop:
                continue
            tail = quote("/".join(parts[drop:]))
            writer.writerow([slug, number, source, template.format(folder_path=folder, path=tail), "", ""])

print(f"{DRAFT}: {len(products)} product templates, {len(home_only)} home-page-only, {len(no_redirect)} no redirect")
print(f"{TESTS}: written")
for slug, shapes in conflicts:
    print("  versions disagree:", slug, shapes)
for item in failed:
    print("  no template derivable:", *item)
