"""DOCOPS-322: suggest a docs.tibco.com address for every unfilled row of the URL request sheet.

Rules learned from the URLs the user filled (2026-11-04), checked against every one of them
before anything is written:

  <wrapper>/html/<topic>          -> /pub/<docsite_folder>/doc/html/<topic>
  <wrapper>/<folder>/<topic>      -> /pub/<docsite_folder>/doc/html/<folder>/<topic>   (BPM bpmhelp/)
  doc/html/<topic>  (no wrapper)  -> /pub/<docsite_folder>/doc/html/<topic>
  html/<topic>      (no wrapper)  -> /pub/<docsite_folder>/doc/html/<topic>
  WebWorks <wrapper>/html/<topic> -> /pub/<docsite_folder>/doc/<code>/html/<topic>, <code> = the
                                     folder's first segment (the topic's own address, not wwhelp.htm#href=)

Adds `suggested_url` and an empty `suggestion_ok` (yes / no) beside `live_url`; keeps every
filled value. Writes `reports/origin-url-requests.csv` in place.

    python scratch/origin_url_suggest.py
"""
import csv
from pathlib import PurePosixPath
from urllib.parse import quote, unquote

SHEET = "reports/origin-url-requests.csv"
BASE = "https://docs.tibco.com/pub"

catalog = {(r["slug"], r["version"]): r for r in csv.DictReader(open("config/versions.csv", encoding="utf-8-sig"))}
rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
fields = list(rows[0].keys())
for extra in ("suggested_url", "suggestion_ok"):
    if extra not in fields:
        fields.insert(fields.index("live_url"), extra)


def suggest(row) -> str:
    folder = row["docsite_folder"].strip("/")
    parts = PurePosixPath(row["sample_topic_in_package"]).parts
    if not folder or not parts:
        return ""
    segment = row["version"].replace(".", "-").lower()
    wrapped = len(parts) > 2 and parts[0].lower().endswith(segment)
    rest = list(parts[1:] if wrapped else parts)
    if rest[:2] == ["doc", "html"]:
        rest = rest[2:]
    elif rest[:1] == ["html"]:
        rest = rest[1:]
    engine = (catalog.get((row["slug"], row["version"])) or {}).get("engine", "")
    prefix = f"doc/{folder.split('/')[0]}/html" if engine == "webworks" else "doc/html"
    return f"{BASE}/{folder}/{prefix}/{quote('/'.join(rest))}"


def given(row) -> str:
    """The filled URL as the topic's own address: a WebWorks `wwhelp.htm#href=` is read through."""
    url = row["live_url"].strip()
    if "wwhelp.htm#href=" in url:
        head, _, topic = url.partition("wwhelp/wwhimpl/js/html/wwhelp.htm#href=")
        return head + quote(unquote(topic))
    return url


checked = matched = 0
for row in rows:
    if row["live_url"].strip() and "#href=" in row["live_url"] or (row["live_url"].strip() and "wwhelp.htm" not in row["live_url"]):
        checked += 1
        if suggest(row) == given(row):
            matched += 1
        else:
            print("  rule misses:", row["slug"], row["version"], "|", suggest(row), "|", given(row))
print(f"rules reproduce {matched} of {checked} filled URLs")

suggested = 0
for row in rows:
    row.setdefault("suggestion_ok", "")
    if not row["live_url"].strip() and not row["notes"].strip():
        row["suggested_url"] = suggest(row)
        suggested += bool(row["suggested_url"])
    else:
        row.setdefault("suggested_url", "")
with open(SHEET, "w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f"{SHEET}: {suggested} suggestions written "
      f"({sum(1 for r in rows if r['suggested_url'] and r['needed'] == 'yes')} on needed rows)")
