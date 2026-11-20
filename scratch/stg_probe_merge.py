"""Has staging rebuilt the versions a `wip` merge touched? Read-only; writes nothing in the repos.

Per version folder the merge changed, three signs, each read fresh from staging:
- **date**: the page's "Last published" value, new when it is on or after the merge day;
- **headings**: up to N pages whose doubled title the merge removed -- still doubled, or not;
- **breadcrumb**: the version's `docs_list_title`, shown only. It does not count: on
  stg-docs.ibi.com (20 Nov) the breadcrumb still read "Online Help" after the rebuild.

UPDATED = every counted sign reads new; OLD = every one reads old; MIXED otherwise.

    python scratch/stg_probe_merge.py <repo> <merge-sha> [--base https://stg-docs.ibi.com] [--pages 3]
"""
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from datetime import date as _date, datetime

import yaml

sys.path.insert(0, "src")
from docushift.config import ConfigManager  # noqa: E402
from docushift.verify import published  # noqa: E402
from docushift.verify import text as texts  # noqa: E402
from docushift.verify.driver import _toc_tree  # noqa: E402
from docushift.verify.fetch import Fetcher  # noqa: E402
from docushift.verify.toc import by_title, pages_only  # noqa: E402

repo, merge = Path(sys.argv[1]), sys.argv[2]
args = sys.argv[3:]
base = args[args.index("--base") + 1] if "--base" in args else "https://stg-docs.ibi.com"
per_version = int(args[args.index("--pages") + 1]) if "--pages" in args else 3


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def show(rev: str, path: str) -> str:
    try:
        return git("show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return ""


def norm(s: str) -> str:
    return " ".join(texts.words(s))


HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def doubled(md: str) -> bool:
    """The Markdown's first two headings carry the same words (the doubled title)."""
    heads, fenced = [], False
    for line in re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "", md, flags=re.DOTALL).splitlines():
        if line.strip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and (m := HEAD.match(line)):
            heads.append(norm(m.group(2)))
        if len(heads) == 2:
            break
    return len(heads) == 2 and heads[0] == heads[1] and bool(heads[0])


def list_title(rev: str, path: str) -> str:
    try:
        return str((yaml.safe_load(show(rev, path)) or {}).get("docs_list_title") or "")
    except yaml.YAMLError:
        return ""


merged_on = _date.fromisoformat(git("log", "-1", "--format=%cs", merge).strip())
changed: dict[str, list[tuple[str, str]]] = defaultdict(list)
for line in git("diff", "--name-status", "-M", f"{merge}^1", merge).splitlines():
    parts = line.split("\t")
    bits = PurePosixPath(parts[-1]).parts
    if len(bits) >= 5:
        changed["/".join(bits[:4])].append((parts[1], parts[-1]))

cfg = ConfigManager(root_dir=Path("."))
docsite = cfg.load_docsite()
crawl = dict(docsite.get("crawl") or {})
own = dict(docsite.get("verify") or {})
if own.get("rate_limit_per_second") is not None:
    crawl["rate_limit_per_second"] = own["rate_limit_per_second"]
fetcher = Fetcher(Path(tempfile.mkdtemp(prefix="stg-probe-")), crawl, refresh=True, workers=1)
DATE = re.compile(r"Last published\s*:?\s*</span>\s*<span[^>]*>\s*([^<]+?)\s*<", re.I)
CRUMB = re.compile(r'class="cmp-breadcrumb".*?</nav>', re.S)


def crumb(html: str) -> str:
    m = CRUMB.search(html)
    return norm(re.sub(r"<[^>]+>", " ", m.group(0))) if m else ""


rows = []
for vf in sorted(changed):
    locale, slug, doc_class, segment = vf.split("/")
    folder = repo / vf
    toc = _toc_tree(folder / "toc.yml")
    signs, notes, date = [], [], ""
    landing = None
    for url in published.entry_urls(base, locale, slug, doc_class, segment, toc) if toc else []:
        got = fetcher.get(url)
        if got.ok and published.is_page(got.text, url):
            landing = got.text
            break
    if landing is None:
        rows.append((vf, "NOT SERVED", "", ["no page served for this version"]))
        continue
    date = (DATE.search(landing) or [None, ""])[1]
    old_t, new_t = list_title(f"{merge}^1", f"{vf}/toc.yml"), list_title(merge, f"{vf}/toc.yml")
    if old_t != new_t and new_t:
        line = crumb(landing)
        sign = "new" if norm(new_t) in line else "old" if norm(old_t) in line else "?"
        notes.append(f"breadcrumb {sign} (not counted): expects '{new_t}'")
    menu = published.read_menu(landing, url)
    href_of = {}
    if menu is not None and menu.children:
        match = by_title(pages_only(toc), menu).matched
        for row, _ in pages_only(toc).walk():
            twin = match.get(id(row))
            if row.key and twin is not None and twin.ref:
                href_of.setdefault(row.key.partition("#")[0], twin.ref.partition("#")[0])
    tried = 0
    rel = len(vf) + 1
    for old, new in changed[vf]:
        if tried >= per_version or not new.endswith(".md"):
            continue
        page = new[rel:]
        if page not in href_of or not doubled(show(f"{merge}^1", old)) or doubled(show(merge, new)):
            continue
        tried += 1
        check = published._page(fetcher, page, href_of[page], folder, check_title=False)
        if check.status != "ok":
            notes.append(f"{page}: {check.status}")
            continue
        heads = [norm(h) for h, _ in check.headings]
        twice = len(heads) > 1 and heads[0] == heads[1]
        sign = "old" if twice else "new"
        signs.append(sign)
        notes.append(f"heading {sign}: {page}")
        date = date or (DATE.search(fetcher.get(href_of[page]).text) or [None, ""])[1]
    if date:
        try:
            signs.append("new" if datetime.strptime(date, "%b %d, %Y").date() >= merged_on else "old")
        except ValueError:
            notes.append(f"date not read: {date}")
    state = ("UPDATED" if signs and all(s == "new" for s in signs) else
             "OLD" if signs and all(s == "old" for s in signs) else "MIXED" if signs else "UNSURE")
    rows.append((vf, state, date, notes))

for vf, state, date, notes in rows:
    print(f"{state:10} {vf}   last published: {date or '-'}")
    for n in notes:
        print(f"             {n}")
done = sum(s == "UPDATED" for _, s, _, _ in rows)
print(f"\n{done} of {len(rows)} versions updated; {fetcher.requests} requests")
