"""Lay the Japanese Data Virtualization help out like the English (Phase 86, DOCOPS-254).

The Japanese pages are the same source topics as the English ones (`doc/html/ja-JP/X` and
`en-US/X`). English 8.8.x was renamed, not merged: `rename-map.csv` maps each converted page
(old path) to its published path. Each Japanese page goes to its English page's path; pages
with no English twin stay under `unfiled/`. Pictures stay where they are and every link is
rewritten from the page's new place. `toc.yml` is the English menu with each entry's Japanese
title (entries with no Japanese page are dropped, their children lifted). `301.yml` rows are
re-pointed to the new paths.

Reads the synced Japanese tree (C:/tmp/dv-ja-sync), writes C:/tmp/dv-ja-mirror; nothing else.

    python scratch/dv_ja_mirror.py
"""
import csv
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, unquote

import yaml

sys.path.insert(0, "src")
from docushift.utils.anchors import HEADING, anchor_run, titles_of  # noqa: E402
from docushift.validation.references import mask_code  # noqa: E402

SLUG = "tibco-data-virtualization"
SRC = Path("C:/tmp/dv-ja-sync/loc-spotfire-data-virtualization-userdocs/ja-jp") / SLUG
DST = Path("C:/tmp/dv-ja-mirror/loc-spotfire-data-virtualization-userdocs/ja-jp") / SLUG
EN_REPO = Path("C:/github/tibco-docs-aem/en-us-spotfire-data-virtualization-userdocs/en-us") / SLUG
REFRAMED = Path("reframed/en-us-spotfire-data-virtualization") / SLUG
LINK = re.compile(r'(!?\[(?:\\.|[^\]\\])*\])\(([^)\s]+)((?:\s+"[^"]*")?)\)')  # `\[`, `\]` inside the text
SRC_ATTR = re.compile(r'(<(?:img\b[^>]*?\bsrc|a\b[^>]*?\bhref)=")([^"]+)(")')
TITLE = re.compile(r'^title:\s*"?(.*?)"?\s*$', re.M)


def anchors(text: str) -> list[str]:
    """The page's heading anchors in order, as AEM makes them (utils/anchors)."""
    return anchor_run(titles_of(text, HEADING.finditer(mask_code(text))))


#: Section and group titles the Phase 87 restructure created, in Japanese.
JA_TITLES = {
    "What's New": "新着情報", "Getting Started": "はじめに",
    "Installation and Upgrade Guide": "インストールおよびアップグレード ガイド", "Using Studio": "Studio の使用",
    "Web UI": "Web UI", "Adapters": "アダプター", "Business Directory": "Business Directory",
    "Administration and Security": "管理とセキュリティ", "Client Interfaces and APIs": "クライアント インターフェイスと API",
    "Reference Guide": "リファレンス ガイド", "Documentation, Support and Legal": "ドキュメント、サポート、および法的情報",
    "Relational Databases": "リレーショナル データベース", "Cloud Data Warehouses": "クラウド データ ウェアハウス",
    "Big Data, NoSQL and Streaming": "ビッグ データ、NoSQL、ストリーミング", "Files and Cloud Storage": "ファイルとクラウド ストレージ",
    "Enterprise Applications": "エンタープライズ アプリケーション", "SaaS, Marketing and Social": "SaaS、マーケティング、ソーシャル",
    "Web Services and Custom Sources": "Web サービスとカスタム ソース",
}


def english_map(version: str) -> dict[str, str]:
    with open(REFRAMED / version / "rename-map.csv", encoding="utf-8-sig") as fh:
        return {r["old_path"]: r["new_path"] for r in csv.DictReader(fh)}


def mirror(version: str) -> dict:
    seg = version.replace(".", "-")
    src, dst = SRC / "online-help" / seg, DST / "online-help" / seg
    rm = english_map(version)
    pages = sorted(p.relative_to(src).as_posix() for p in src.rglob("*.md"))

    def old_of(p: str) -> str | None:
        # The Japanese package has no adapter guides, so Business Directory is its top-level
        # root: `_templates/Home.md` there is Business Directory's, `BusDirHelp/...` in English.
        own = p.startswith(("StudioHelp/", "DeployManHelp/", "WebUI/", "unfiled/"))
        cand = p if own else "BusDirHelp/" + p
        return cand if cand in rm else None

    # Phase 87: pages the English restructure dropped as duplicates (their rename-map row now
    # names the copy kept). The Japanese copy follows when the kept copy has a Japanese twin;
    # when it has none (an English-only adapter page), the Japanese page stays, at that path.
    before = REFRAMED / (version + ".before-phase87") / "rename-map.csv"
    prev = {}
    if before.exists():
        with open(before, encoding="utf-8-sig") as fh:
            prev = {r["old_path"]: r["new_path"] for r in csv.DictReader(fh)}
    plan_file = Path(f"reports/ai-grouping/{SLUG}-{version}.yaml")
    dropped_prev = ({d["drop"] for d in yaml.safe_load(plan_file.read_text(encoding="utf-8")).get("drop_duplicates") or []}
                    if plan_file.exists() else set())
    is_dup = {p: (old_of(p) is not None and prev.get(old_of(p)) in dropped_prev) for p in pages}

    new_of: dict[str, str] = {}
    owner: dict[str, str] = {}
    merged: set[str] = set()
    unmatched = 0
    for p in sorted(pages, key=lambda q: is_dup[q]):      # pages kept first, duplicates after
        old = old_of(p)
        if old is not None:
            new = rm[old]
        else:
            unmatched += 1
            new = p if p.startswith("unfiled/") else "unfiled/" + p
        if new in owner and is_dup[p]:
            merged.add(p)                                   # links to it go to the copy kept
            new_of[p] = new
            continue
        while new in owner:  # never two pages on one path
            new = new[:-3] + "-ja.md"
        owner[new] = p
        new_of[p] = new

    def rewrite(text: str, page: str, counts: dict) -> str:
        here_old, here_new = posixpath.dirname(page), posixpath.dirname(new_of[page])

        def target(href: str) -> str | None:
            if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith(("#", "/")):
                return None
            path, hash_, frag = href.partition("#")
            if not path:
                return None
            resolved = posixpath.normpath(posixpath.join(here_old, unquote(path)))
            if resolved.endswith(".md"):
                if resolved not in new_of:
                    counts["link to no Japanese page"] += 1
                    return None
                resolved = new_of[resolved]
            rel = posixpath.relpath(resolved, here_new or ".")
            if "%" in path or " " in rel:
                rel = quote(rel)
            counts["rewritten"] += 1
            return rel + (hash_ + frag if hash_ else "")

        def md(m):
            new = target(m.group(2))
            return m.group(0) if new is None else f"{m.group(1)}({new}{m.group(3)})"

        def img(m):
            new = target(m.group(2))
            return m.group(0) if new is None else f"{m.group(1)}{new}{m.group(3)}"

        return SRC_ATTR.sub(img, LINK.sub(md, text))

    if dst.exists():
        shutil.rmtree(dst)
    counts = {"rewritten": 0, "link to no Japanese page": 0, "section rows mapped": 0, "section rows to the page": 0}
    titles: dict[str, str] = {}
    for p in pages:
        text = (src / p).read_text(encoding="utf-8")
        m = TITLE.search(text[:500])
        titles[p] = m.group(1) if m else ""
        if p in merged:
            continue
        out = dst / new_of[p]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rewrite(text, p, counts), encoding="utf-8", newline="")
    assets = 0
    for f in src.rglob("*"):
        rel = f.relative_to(src).as_posix()
        if f.is_file() and not rel.endswith(".md") and rel not in ("toc.yml", "301.yml"):
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            assets += 1

    # Menu: the English one, Japanese titles, English-only entries dropped (children lifted).
    ja_by_new = {new_of[p]: p for p in pages if old_of(p) is not None and p not in merged}
    from_source = set(rm.values())       # English pages with a source topic; any other menu url was generated
    landings: dict[str, tuple[str, list]] = {}
    en_toc = yaml.safe_load((EN_REPO / "online-help" / seg / "toc.yml").read_text(encoding="utf-8"))
    dropped = kept = 0

    def walk(nodes):
        nonlocal dropped, kept
        out = []
        for node in nodes or []:
            url = str(node.get("url") or "")
            children = walk(node.get("subfolderlist"))
            ja = ja_by_new.get(url.partition("#")[0])
            if ja is None and children:
                # A landing with no Japanese page: generated by the restructure, or an English
                # page the Japanese package lacks (a guide's own page). One in Japanese.
                # A section or group landing the restructure generated: one in Japanese too.
                title = JA_TITLES.get(str(node.get("title")), str(node.get("title")))
                landings[url] = (title, children)
                kept += 1
                out.append({"title": title, "url": url, "subfolderlist": children})
                continue
            if ja is None:
                dropped += 1
                out.extend(children)
                continue
            kept += 1
            page, hash_, frag = url.partition("#")
            if hash_:  # a section row: the Japanese heading in the same position (same structure)
                en = anchors((EN_REPO / "online-help" / seg / page).read_text(encoding="utf-8"))
                jp = anchors((dst / page).read_text(encoding="utf-8"))
                if frag in en and en.index(frag) < len(jp) and len(en) == len(jp):
                    url, counts["section rows mapped"] = f"{page}#{jp[en.index(frag)]}", counts["section rows mapped"] + 1
                else:
                    url, counts["section rows to the page"] = page, counts["section rows to the page"] + 1
            en_title = str(node.get("title"))
            title = JA_TITLES.get(en_title) or titles.get(ja) or en_title   # section titles stay sections
            # AEM shows a raw `<` as a tag: written as an entity (angle-brackets fix).
            entry = {"title": title.replace("<", "&lt;").replace(">", "&gt;"), "url": url}
            if children:
                entry["subfolderlist"] = children
            out.append(entry)
        return out

    toc = {"docs_list_title": en_toc.get("docs_list_title"), "docs": walk(en_toc.get("docs"))}
    for page, (title, children) in landings.items():
        lines = ["---", f'title: "{title}"', "---", "", f"# {title}", ""]
        for e in children:
            rel = posixpath.relpath(e["url"].partition("#")[0], posixpath.dirname(page) or ".")
            lines.append(f"- [{e['title']}]({rel})")
        (dst / page).parent.mkdir(parents=True, exist_ok=True)
        (dst / page).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    counts["Japanese landings"] = len(landings)
    counts["duplicates merged"] = len(merged)
    head = ("# AEM table of contents: the English menu with the Japanese titles (Phase 86).\n"
            "# Entries with no Japanese page (the English-only adapter guides) are left out.\n")
    (dst / "toc.yml").write_text(head + yaml.safe_dump(toc, allow_unicode=True, sort_keys=False, width=10_000),
                                 encoding="utf-8", newline="")

    # Redirects: each old ja-JP URL to the page's new path.
    prefix = f"/ja-jp/{SLUG}/online-help/{seg}/"
    lines, moved = [], 0
    for line in (src / "301.yml").read_text(encoding="utf-8").splitlines():
        m = re.match(r'^("[^"]+": ")' + re.escape(prefix) + r'([^"#]+)(#[^"]*)?(")$', line)
        if m and m.group(2) in new_of:
            line, moved = f"{m.group(1)}{prefix}{new_of[m.group(2)]}{m.group(4)}", moved + 1
        lines.append(line)
    (dst / "301.yml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    on_english = sum(1 for p in pages if (EN_REPO / "online-help" / seg / new_of[p]).exists())
    return {"pages": len(pages), "on an English path": on_english, "unfiled (no English twin)": unmatched,
            "assets": assets, "menu entries kept": kept, "menu entries dropped": dropped,
            "redirects re-pointed": moved, **counts}


if __name__ == "__main__":
    for v in sys.argv[1:] or ["8.8.0", "8.8.1"]:
        print(v, mirror(v))
    for f in ("metadata.yml", "online-help/version.yml"):
        if (SRC / f).exists():
            (DST / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC / f, DST / f)
