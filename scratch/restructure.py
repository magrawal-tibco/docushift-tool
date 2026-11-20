"""Apply a reviewed structure plan to one reframed DV version (Phase 87, DOCOPS-385).

    python scratch/restructure.py reports/ai-grouping/tibco-data-virtualization-8.9.0.yaml          # dry run
    python scratch/restructure.py reports/ai-grouping/tibco-data-virtualization-8.9.0.yaml --apply

The plan (schema in the AI draft brief) names the new top level: sections, their items (an
existing menu entry and its whole subtree, optionally retitled, renamed or collapsed), new
groups with generated landing pages, and identical duplicates to drop. This script:
- maps every file of the version folder to its new path (an entry's page and its folder move
  together, so pictures inside move too; `unfiled/` and `resources/` stay);
- refuses a plan that leaves a menu entry unplaced or places one twice;
- rewrites every relative link from each page's old place to its new one;
- writes `toc.yml`, generated landing pages, `rename-map.csv` (new names kept by later
  reframes), `redirects.yml` (+ a row from each page's current path to its new one) and the
  `301.yml` targets.
Works on `reframed/en-us-spotfire-data-virtualization/tibco-data-virtualization/<version>/`;
`sync` then publishes it. Dry run writes nothing and prints the counts and the new top level.
"""
from __future__ import annotations

import csv
import io
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import yaml

APPLY = "--apply" in sys.argv
PLAN = Path(sys.argv[1])
plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
VERSION = str(plan["version"])
ROOT = Path("reframed/en-us-spotfire-data-virtualization/tibco-data-virtualization") / VERSION
KEEP_IN_PLACE = ("unfiled/", "resources/")
META = {"toc.yml", "301.yml", "redirects.yml", "rename-map.csv", "reframe.yml", "review-queue.csv",
        "metadata.yml", "csh.yml"}
LINK = re.compile(r'(!?\[(?:\\.|[^\]\\])*\])\(([^)\s]+)((?:\s+"[^"]*")?)\)')
ATTR = re.compile(r'(<(?:img\b[^>]*?\bsrc|a\b[^>]*?\bhref)=")([^"]+)(")')


def fail(msg: str) -> None:
    sys.exit(f"STOP: {msg}")


# ---- the current menu ----
toc_text = (ROOT / "toc.yml").read_text(encoding="utf-8")
toc = yaml.safe_load(toc_text)
first_node: dict[str, dict] = {}


def index(nodes):
    for n in nodes or []:
        url = str(n.get("url") or "").partition("#")[0]
        if url:
            first_node.setdefault(url, n)
        index(n.get("subfolderlist"))


index(toc["docs"])
top_urls = [str(n.get("url") or "").partition("#")[0] for n in toc["docs"]]

# ---- the plan: placement rules ----
exact: dict[str, str] = {}             # page -> new page (landings)
prefix: list[tuple[str, str]] = []     # old stem -> new stem ("a/b" covers a/b.md and a/b/...)
lifted: list[tuple[str, str]] = []     # collapsed entry's folder -> new parent folder
generated: dict[str, tuple[str, list]] = {}   # new landing page -> (title, child entries)
retitle: dict[str, str] = {}
placed: list[str] = []
drops = {d["drop"]: d["keep"] for d in plan.get("drop_duplicates") or []}


def stem(url: str) -> str:
    return url[:-3] if url.endswith(".md") else url


collapsed: set[str] = set()


def place(items, parent: str) -> list:
    """Rules for `items` under the folder `parent`; returns their new menu entries, in order.

    Items apply in order. A collapsed entry is replaced by its children (its page is a
    section landing or a dropped duplicate); a later item naming one of those children
    takes that child's place in the menu (and may rename its folder).
    """
    out: list = []
    slot: dict[str, int] = {}   # lifted child url -> its position in `out`

    def put(url: str | None, entry) -> None:
        if url is not None and url in slot:
            out[slot.pop(url)] = entry
        else:
            out.append(entry)

    for item in items or []:
        if "group" in item:
            g = item["group"]
            folder = f"{parent}/{g['folder']}".strip("/")
            children = place(g.get("items"), folder)
            generated[folder + ".md"] = (g["title"], children)
            put(None, {"title": g["title"], "url": folder + ".md", "subfolderlist": children})
            continue
        url = item["from"]
        node = first_node.get(url)
        if node is None:
            fail(f"{url}: not a menu entry of {VERSION}")
        old = stem(url)
        if item.get("collapse"):
            if url not in drops and url not in [x.get("landing") for x in plan["sections"]]:
                fail(f"{url}: collapsed, but its page is neither a landing nor a dropped duplicate")
            collapsed.add(url)
            lifted.append((old, parent))
            kids = [c for c in node.get("subfolderlist") or [] if str(c.get("url") or "").partition("#")[0]]
            at = slot.pop(url, None)
            entries = [("child", c) for c in kids]
            if at is None:
                base = len(out)
                out.extend(entries)
            else:                          # a collapsed entry that was itself a lifted child
                out[at:at + 1] = entries
                base = at
                for k, v in list(slot.items()):
                    if v > at:
                        slot[k] = v + len(entries) - 1
            for i, c in enumerate(kids):
                slot[str(c.get("url")).partition("#")[0]] = base + i
            continue
        placed.append(url)
        new = f"{parent}/{item.get('folder') or posixpath.basename(old)}".strip("/")
        prefix.append((old, new))
        if item.get("title"):
            retitle[url] = item["title"]
        put(url, ("node", node))
    return out


new_docs = []
for sec in plan["sections"]:
    folder = sec["folder"]
    landing = sec.get("landing") or "new"
    items = place(sec.get("items"), folder)
    if landing == "new":
        generated[folder + ".md"] = (sec["title"], items)
    else:
        placed.append(landing)
        exact[landing] = folder + ".md"
    new_docs.append({"title": sec["title"], "url": folder + ".md", "subfolderlist": items, "_landing": landing})

missing = [u for u in top_urls if u and u not in placed and u not in collapsed and u not in drops
           and not u.startswith("unfiled/")]
twice = sorted({u for u in placed if placed.count(u) > 1})
if missing:
    fail(f"top-level entries not placed: {missing}")
if twice:
    fail(f"placed twice: {twice}")

offmenu: list[str] = []
rules = sorted([(o, n, "move") for o, n in prefix] + [(o, n, "lift") for o, n in lifted],
               key=lambda r: -len(r[0]))
prefix.sort(key=lambda p: -len(p[0]))
lifted.sort(key=lambda p: -len(p[0]))


def new_path(rel: str) -> str | None:
    """Where a file goes; None if it is dropped."""
    if rel in drops:
        return None
    if rel in exact:
        return exact[rel]
    if rel.startswith(KEEP_IN_PLACE) or "/" not in rel and rel in META:
        return rel
    # The most specific rule wins, whether it renames a folder or lifts a collapsed one's
    # children: `web-ui/sdv-web-ui` (collapsed into the Web UI section) beats `web-ui`
    # (moved to What's New as Key New Features).
    for old, new, kind in rules:
        if kind == "move" and (rel == old + ".md" or rel.startswith(old + "/")):
            return new + rel[len(old):]
        if kind == "lift" and rel.startswith(old + "/"):
            return f"{new}/{rel[len(old) + 1:]}".strip("/")
    if rel.endswith(".md"):          # an off-menu page no rule covers: kept, under unfiled/
        offmenu.append(rel)
        return "unfiled/" + rel
    return rel                       # a picture or file outside every moved folder stays


files = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()]
moves = {f: new_path(f) for f in files}
unplaced = [f for f, n in moves.items() if n == "__unplaced__"]
if unplaced:
    fail(f"{len(unplaced)} file(s) placed by no rule, e.g. {unplaced[:5]}")
targets = [n for n in moves.values() if n]
clash = sorted({n for n in targets if targets.count(n) > 1}) if len(set(targets)) != len(targets) else []
if clash:
    fail(f"two files on one path: {clash[:5]}")
for page in generated:
    if page in set(targets):
        fail(f"generated landing {page} collides with a moved page")


def resolve(rel: str) -> str | None:
    """A page's new path, following a dropped duplicate to the copy kept (through chains:
    a copy kept for one drop can itself be dropped for another)."""
    seen = set()
    while rel in drops and rel not in seen:
        seen.add(rel)
        rel = drops[rel]
    return moves.get(rel)


# ---- the new menu ----
collapsed_or_placed = collapsed | set(placed)
def remap_entry(entry) -> list:
    if isinstance(entry, tuple):
        _, node = entry
        url = str(node.get("url") or "")
        page, h, frag = url.partition("#")
        # Children collapsed or placed elsewhere by the plan are not copied here (they would
        # show twice in the menu).
        kids = [e for c in node.get("subfolderlist") or []
                if str(c.get("url") or "").partition("#")[0] not in collapsed_or_placed
                for e in remap_entry(("node", c))]
        if page in drops:            # a dropped duplicate's entry goes; its children stay
            return kids
        out = {"title": retitle.get(page) or node.get("title"), "url": (resolve(page) or page) + (h + frag)}
        if kids:
            out["subfolderlist"] = kids
        return [out]
    kids = [e for c in entry.get("subfolderlist") or [] for e in remap_entry(c)]
    out = {"title": entry["title"], "url": entry["url"]}
    if kids:
        out["subfolderlist"] = kids
    return [out]


menu = [e for sec in new_docs for e in remap_entry({k: v for k, v in sec.items() if k != "_landing"})]
for d in toc["docs"]:  # the support and legal pages stay at the end when no section took them
    u = str(d.get("url") or "")
    if u in exact.values():
        continue


# ---- links ----
def relink(text: str, old_page: str, new_page: str) -> tuple[str, int]:
    n = 0

    def target(href: str):
        nonlocal n
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith(("#", "/")):
            return None
        path, h, frag = href.partition("#")
        if not path:
            return None
        old_abs = posixpath.normpath(posixpath.join(posixpath.dirname(old_page), unquote(path)))
        new_abs = resolve(old_abs) or old_abs
        rel = posixpath.relpath(new_abs, posixpath.dirname(new_page) or ".")
        if "%" in path or " " in rel:
            rel = quote(rel)
        if rel == path:
            return None
        n += 1
        return rel + (h + frag if h else "")

    text = LINK.sub(lambda m: m.group(0) if (t := target(m.group(2))) is None
                    else f"{m.group(1)}({t}{m.group(3)})", text)
    text = ATTR.sub(lambda m: m.group(0) if (t := target(m.group(2))) is None
                    else f"{m.group(1)}{t}{m.group(3)}", text)
    return text, n


def landing_page(page: str, title: str, children: list) -> str:
    lines = ["---", f'title: "{title}"', "---", "", f"# {title}", ""]
    for e in children:
        if isinstance(e, tuple):
            e = remap_entry(e)
            e = e[0] if e else None
        if not e:
            continue
        rel = posixpath.relpath(e["url"].partition("#")[0], posixpath.dirname(page) or ".")
        lines.append(f"- [{e['title']}]({rel})")
    return "\n".join(lines) + "\n"


stats = {"files": len(files), "moved": sum(1 for f, n in moves.items() if n and n != f),
         "dropped duplicates": sum(1 for n in moves.values() if n is None),
         "generated landings": len(generated), "off-menu pages to unfiled/": len(offmenu),
         "links rewritten": 0}
print(f"{VERSION}: {stats}")
for e in menu:
    print(f"  {e['title']}  [{e['url']}]  ({len(e.get('subfolderlist') or [])} under it)")

if not APPLY:
    print("(dry run)")
    sys.exit(0)

# ---- write: build the new tree beside the old one, then swap ----
staging = ROOT.with_name(VERSION + ".restructure")
if staging.exists():
    shutil.rmtree(staging)
for f, n in moves.items():
    if n is None:
        continue
    src, dst = ROOT / f, staging / n
    dst.parent.mkdir(parents=True, exist_ok=True)
    if f.endswith(".md"):
        text, k = relink(src.read_text(encoding="utf-8"), f, n)
        stats["links rewritten"] += k
        dst.write_text(text, encoding="utf-8", newline="")
    elif "/" not in f and f in META:
        continue
    else:
        shutil.copy2(src, dst)
for page, (title, children) in generated.items():
    (staging / page).parent.mkdir(parents=True, exist_ok=True)
    (staging / page).write_text(landing_page(page, title, children), encoding="utf-8", newline="")

head = "".join(line + "\n" for line in toc_text.splitlines() if line.startswith("#"))
(staging / "toc.yml").write_text(
    head + yaml.safe_dump({"docs_list_title": toc.get("docs_list_title"), "docs": menu},
                          allow_unicode=True, sort_keys=False, width=10_000), encoding="utf-8", newline="")

text = (ROOT / "rename-map.csv").read_text(encoding="utf-8-sig")
rows = list(csv.reader(io.StringIO(text)))
for r in rows[1:]:
    if len(r) > 1 and r[1]:
        r[1] = resolve(r[1]) or r[1]
buf = io.StringIO()
csv.writer(buf, lineterminator="\n").writerows(rows)
(staging / "rename-map.csv").write_text(buf.getvalue(), encoding="utf-8-sig", newline="")

red = yaml.safe_load((ROOT / "redirects.yml").read_text(encoding="utf-8")) or {}
items = red.get("redirects") or []
for r in items:
    page, h, frag = str(r["to"]).partition("#")
    r["to"] = (resolve(page) or page) + (h + frag)
seen = {r["from"] for r in items}
for f, n in moves.items():  # the current published path of each moved page
    if f.endswith(".md") and f not in seen and (n is None or n != f):
        items.append({"from": f, "to": resolve(f)})
red["redirects"] = items
(staging / "redirects.yml").write_text(
    "# Written by `docushift reframe` (Stage 6b); restructured by scratch/restructure.py (Phase 87).\n"
    + yaml.safe_dump(red, allow_unicode=True, sort_keys=False, width=10_000), encoding="utf-8", newline="")

lines = []
for line in (ROOT / "301.yml").read_text(encoding="utf-8").splitlines():
    # Both shapes: `"old": "/en-us/.../<page>#a"` (repo) and `  to: <page>#a` (reframed).
    m = re.match(r'^("[^"]+": ")(/en-us/[^"#]*?/online-help/[^/]+/)([^"#]+)(#[^"]*)?(")$', line)
    if m:
        line = f"{m.group(1)}{m.group(2)}{resolve(m.group(3)) or m.group(3)}{m.group(4) or ''}{m.group(5)}"
    m = re.match(r'^(\s*to:\s*)([^#\s]+\.md)(#\S*)?\s*$', line)
    if m:
        line = f"{m.group(1)}{resolve(m.group(2)) or m.group(2)}{m.group(3) or ''}"
    lines.append(line)
(staging / "301.yml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
for f in ("reframe.yml", "review-queue.csv", "metadata.yml", "csh.yml"):
    if (ROOT / f).exists():
        shutil.copy2(ROOT / f, staging / f)

backup = ROOT.with_name(VERSION + ".before-phase87")
if backup.exists():
    shutil.rmtree(backup)
ROOT.rename(backup)
staging.rename(ROOT)
print(f"applied: {stats}; previous tree kept at {backup}")
