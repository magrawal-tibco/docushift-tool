"""Unfiled DV page paths without spaces: lower case, hyphenated (user, 19 Nov; DOCOPS-382).

95 English page files under `unfiled/` had spaces in their path (`unfiled/DB2/Version Support.md`,
`unfiled/Google Cloud Storage/Basic_Tab1.md`). A folder or file name with a space becomes lower
case with hyphens (`version-support.md`, `google-cloud-storage/`); everything inside a renamed
folder moves with it. Every relative link, `toc.yml` url and `301.yml` row into a moved file is
re-pointed, and so are the moved pages' own links. Done in the repo (git mv) and in reframed/
(including `rename-map.csv`), so a later sync or reframe keeps the names.

    python scratch/dv_unfiled_spaces.py            # dry run
    python scratch/dv_unfiled_spaces.py --apply
"""
import csv
import io
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, unquote

APPLY = "--apply" in sys.argv
SLUG = "tibco-data-virtualization"
REPO = Path("C:/github/tibco-docs-aem/en-us-spotfire-data-virtualization-userdocs")
WS = Path("reframed/en-us-spotfire-data-virtualization") / SLUG
LINK = re.compile(r'(!?\[(?:\\.|[^\]\\])*\])\(([^)\s]+)((?:\s+"[^"]*")?)\)')
ATTR = re.compile(r'(<(?:img\b[^>]*?\bsrc|a\b[^>]*?\bhref)=")([^"]+)(")')


def tidy(name: str) -> str:
    stem, dot, ext = name.rpartition(".") if "." in name else (name, "", "")
    stem = re.sub(r"-{2,}", "-", re.sub(r"\s+", "-", stem.strip())).lower()
    return f"{stem}.{ext.lower()}" if dot else stem


def plan(root: Path) -> dict[str, str]:
    """old relative path -> new, for every file under a renamed unfiled/ folder or name."""
    moves = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if not rel.startswith("unfiled/") or " " not in rel:
            continue
        moves[rel] = "/".join(tidy(s) if " " in s else s for s in rel.split("/"))
    return moves


def relink(text: str, page_old: str, page_new: str, moves: dict[str, str]) -> tuple[str, int]:
    n = 0

    def target(href: str) -> str | None:
        nonlocal n
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith(("#", "/")):
            return None
        path, hash_, frag = href.partition("#")
        if not path:
            return None
        old_abs = posixpath.normpath(posixpath.join(posixpath.dirname(page_old), unquote(path)))
        new_abs = moves.get(old_abs, old_abs)
        if new_abs == old_abs and page_old == page_new:
            return None
        rel = posixpath.relpath(new_abs, posixpath.dirname(page_new) or ".")
        rel = quote(rel) if ("%" in path or " " in rel) else rel
        if rel == path:
            return None
        n += 1
        return rel + (hash_ + frag if hash_ else "")

    text = LINK.sub(lambda m: m.group(0) if (t := target(m.group(2))) is None
                    else f"{m.group(1)}({t}{m.group(3)})", text)
    text = ATTR.sub(lambda m: m.group(0) if (t := target(m.group(2))) is None
                    else f"{m.group(1)}{t}{m.group(3)}", text)
    return text, n


def run(root: Path, in_git: bool, url_prefix: str) -> dict:
    moves = plan(root)
    if not moves:
        return {"moved": 0}
    pages_moved = sum(1 for k in moves if k.endswith(".md"))
    links = rows = 0
    # Every page's links, read before anything moves.
    new_text = {}
    for p in root.rglob("*.md"):
        old = p.relative_to(root).as_posix()
        text, n = relink(p.read_text(encoding="utf-8"), old, moves.get(old, old), moves)
        if n or old in moves:
            new_text[old] = text
            links += n
    for name in ("toc.yml", "301.yml"):
        f = root / name
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for old, new in moves.items():
            for a, b in ((url_prefix + old, url_prefix + new), (f"url: {old}", f"url: {new}"),
                         (f'url: "{old}', f'url: "{new}')):
                if a in text:
                    rows += text.count(a)
                    text = text.replace(a, b)
        new_text[name] = text
    if APPLY:
        for old, new in sorted(moves.items()):
            dst = root / new
            dst.parent.mkdir(parents=True, exist_ok=True)
            if in_git:
                subprocess.run(["git", "-C", str(REPO), "mv", str(root / old), str(dst)], check=True)
            else:
                os.replace(root / old, dst)
        for old, text in new_text.items():
            (root / moves.get(old, old)).write_text(text, encoding="utf-8", newline="")
        for d in sorted({(root / o).parent for o in moves}, key=lambda d: -len(d.parts)):
            while d != root and d.exists() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
        rm = root / "rename-map.csv"
        if rm.exists():
            text = rm.read_text(encoding="utf-8-sig")
            rows_in = list(csv.reader(io.StringIO(text)))
            for r in rows_in[1:]:
                if len(r) > 1 and r[1] in moves:
                    r[1] = moves[r[1]]
            out = io.StringIO()
            csv.writer(out, lineterminator="\n").writerows(rows_in)
            rm.write_text(out.getvalue(), encoding="utf-8-sig", newline="")
    return {"files moved": len(moves), "pages moved": pages_moved, "links re-pointed": links,
            "toc/301 rows re-pointed": rows, "example": next(iter(moves.items()))}


for version in ("8.8.0", "8.8.1", "8.9.0"):
    seg = version.replace(".", "-")
    repo_root = REPO / "en-us" / SLUG / "online-help" / seg
    print(version, "repo", run(repo_root, True, f"/en-us/{SLUG}/online-help/{seg}/"))
    print(version, "workspace", run(WS / version, False, ""))
print("(applied)" if APPLY else "(dry run)")
