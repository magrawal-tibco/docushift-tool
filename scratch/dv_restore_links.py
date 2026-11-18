"""Restore the Data Virtualization links the source broke (DOCOPS-254, DOCOPS-382).

The DV team answered our error report for 8.9.0 ("Corrected Link" column in
cache/data-virtualization-broken-references - data-virtualization-broken-references.csv).
8.8.1 and 8.8.0 are predicted from 8.9.0 by page name (file numbers shift between versions;
user, 18 Nov). The converter kept each broken link's text and dropped the link, so the text
sits alone in a table cell: `| OAuthJWTCertType | ... |`. This turns that cell back into a link
to the page's Markdown, in the repo and in the reframed/ workspace (so a later sync keeps it).

Skipped and reported: links on pages that are not published (83Views, a duplicate of 82Views),
the missing pictures ("Image not found"), and any cell not found exactly once.

    python scratch/dv_restore_links.py            # dry run
    python scratch/dv_restore_links.py --apply
"""
import csv
import os
import re
import sys
from urllib.parse import unquote

APPLY = "--apply" in sys.argv
CSV = "cache/data-virtualization-broken-references - data-virtualization-broken-references.csv"
REPO = "C:/github/tibco-docs-aem/en-us-spotfire-data-virtualization-userdocs"
WS = "reframed/en-us-spotfire-data-virtualization/tibco-data-virtualization"
SEG = {"8.9.0": "8-9-0", "8.8.1": "8-8-1", "8.8.0": "8-8-0"}
FIXES = {"Page name and section glued together", "Link target is just a number"}
# The team's answer for "ApplicantApplications" names the singular page; the plural page exists,
# so the plural is used. Raised with the team in the hand-over note.
OVERRIDE = {("AdapterHelp/DynamicsGP/83Views.html", "ApplicantApplications"): "84ApplicantApplications.html"}


def load_map(version):
    """old page path under doc/html (no extension) -> (repo-relative md path, anchor)."""
    text = open(f"{REPO}/en-us/tibco-data-virtualization/online-help/{SEG[version]}/301.yml", encoding="utf-8").read()
    out = {}
    for old, new in re.findall(r'^"(https://docs\.tibco\.com/[^"]+)": "(/en-us/[^"]+\.md(?:#[^"]*)?)"$', text, re.M):
        rel = unquote(old.split("/doc/html/", 1)[1])
        rel = rel.removeprefix("en-US/")
        md, _, anchor = new.lstrip("/").partition("#")
        out[re.sub(r"\.html?$", "", rel)] = (md, anchor)
    return out


def by_name(pages, folder, name):
    """The page in `folder` whose file name, without its number prefix, is `name`."""
    hits = [k for k in pages if k.rsplit("/", 1)[0] == folder and re.sub(r"^\d+", "", k.rsplit("/", 1)[1]) == name]
    return hits[0] if len(hits) == 1 else None


rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
answers = {}
for x in rows:
    if x["Version"] == "8.9.0" and x["Corrected Link"].strip():
        key = (x["Page (source)"], x["Link text"])
        answers[key] = OVERRIDE.get(key, x["Corrected Link"].strip())

maps = {v: load_map(v) for v in SEG}
edits = {}  # md path -> list of (text, link)
report = {"restored": 0, "unpublished page": 0, "no answer": 0, "target not found": 0}
for x in rows:
    if x["Problem"] not in FIXES:
        continue
    v, src, text = x["Version"], x["Page (source)"], x["Link text"]
    pages = maps[v]
    src_key = re.sub(r"\.html?$", "", src)
    if src_key not in pages:
        report["unpublished page"] += 1
        continue
    src89 = re.sub(r"\.htm$", ".html", src)
    answer = answers.get((src89, text))
    if not answer:
        report["no answer"] += 1
        continue
    folder = src_key.rsplit("/", 1)[0]
    target = by_name(pages, folder, re.sub(r"^\d+", "", re.sub(r"\.html?$", "", answer)))
    if not target:
        report["target not found"] += 1
        print("  target not found:", v, src, text, answer)
        continue
    src_md = pages[src_key][0]
    tgt_md, anchor = pages[target]
    link = os.path.relpath(tgt_md, os.path.dirname(src_md)).replace(os.sep, "/") + (f"#{anchor}" if anchor else "")
    edits.setdefault((v, src_md), []).append((text, link))

def link_first(body, text, link, k):
    """Link the first k plain occurrences of `text` (whole word, not already a link, not in the
    front matter, a heading or code). Returns (body, how many were linked)."""
    lines = body.split("\n")
    word = re.compile(r"(?<![\w\[/#.-])" + re.escape(text) + r"(?![\w\]-])(?!\]\()")
    done, in_front, in_code = 0, lines[0] == "---", False
    for i, line in enumerate(lines):
        if in_front:
            in_front = not (i > 0 and line == "---")
            continue
        if line.startswith("```"):
            in_code = not in_code
        if in_code or line.startswith("#") or done == k:
            continue
        def sub(m):
            nonlocal done
            if done == k or line[: m.start()].count("`") % 2:
                return m.group(0)
            done += 1
            return f"[{text}]({link})"
        lines[i] = word.sub(sub, line)
    return "\n".join(lines), done


problems = 0
for (v, md), pairs in sorted(edits.items()):
    rel = md.split(f"/online-help/{SEG[v]}/", 1)[1]
    wanted = {}
    for text, link in pairs:
        wanted.setdefault((text, link), 0)
        wanted[(text, link)] += 1
    for path in (f"{REPO}/{md}", f"{WS}/{v}/{rel}"):
        body = open(path, encoding="utf-8").read()
        for (text, link), k in wanted.items():
            body, n = link_first(body, text, link, k)
            if n != k:
                problems += 1
                print(f"  {n} of {k} linked for {text!r} in {path}")
            if path.startswith(REPO):
                report["restored"] += n
        if APPLY:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(body)

print(report, "cells not found exactly once:", problems, "(applied)" if APPLY else "(dry run)")
