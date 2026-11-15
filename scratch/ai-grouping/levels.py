"""Level-based merging, measured per guide (read-only).

Rule at depth L (a guide is depth 1): every TOC entry at depth L becomes ONE page holding its
whole subtree; every entry above L is a page of its own body; a leaf above L is its own page.
No word cap. Usage: python levels.py <product-slug> <version>
"""
import statistics
import sys
from pathlib import Path

import yaml

ROOT = Path("C:/github/docushift-tool")
sys.path.insert(0, str(ROOT / "src"))
from docushift.reframe.driver import _Source  # noqa: E402
from docushift.reframe.toc import schema_for  # noqa: E402


def own_words(node, src, seen):
    p = getattr(node, "path", None)
    if not p or getattr(node, "fragment", None) or p in seen:
        return 0
    seen.add(p)
    try:
        return src.words(p) or 0
    except Exception:  # noqa: BLE001
        return 0


def subtree(node, src, seen):
    return own_words(node, src, seen) + sum(subtree(c, src, seen) for c in node.children)


def pages_at(guide, level, src):
    pages, seen = [], set()

    def walk(node, depth):
        if depth == level or not node.children:
            pages.append((node.title, subtree(node, src, seen), depth))
            return
        w = own_words(node, src, seen)
        if w:
            pages.append((node.title, w, depth))
        for c in node.children:
            walk(c, depth + 1)

    walk(guide, 1)
    return pages


def depth_of(node, d=1):
    return max([d] + [depth_of(c, d + 1) for c in node.children])


def main(slug, version):
    conv = next((ROOT / "output").glob(f"*/{slug}/{version}"))
    doc = yaml.safe_load((conv / "toc.yml").read_text(encoding="utf-8"))
    roots = schema_for(doc, None).parse(doc)
    src = _Source(conv)
    print(f"{slug} {version}\n")
    for g in roots:
        if not g.children:
            continue
        total = subtree(g, src, set())
        print(f"## {g.title}: {total:,} words, menu depth {depth_of(g)}, {sum(1 for _ in g.walk()) if hasattr(g, 'walk') else '?'} entries")
        print("| level | pages | median | p90 | max | <300 | >5,000 | >10,000 |")
        print("|---|---|---|---|---|---|---|---|")
        for level in range(1, depth_of(g) + 1):
            ws = sorted(w for _, w, _ in pages_at(g, level, src))
            p90 = ws[int(0.9 * (len(ws) - 1))]
            print(f"| {level} | {len(ws)} | {int(statistics.median(ws)):,} | {p90:,} | {ws[-1]:,} | "
                  f"{sum(w < 300 for w in ws)} | {sum(w > 5000 for w in ws)} | {sum(w > 10000 for w in ws)} |")
        print()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])


def chapters(slug, version, guide_title):
    """Per chapter (depth-2 entry) of one guide: words and pages at chapter-relative depths."""
    conv = next((ROOT / "output").glob(f"*/{slug}/{version}"))
    doc = yaml.safe_load((conv / "toc.yml").read_text(encoding="utf-8"))
    roots = schema_for(doc, None).parse(doc)
    src = _Source(conv)
    g = next(r for r in roots if r.title == guide_title)
    print(f"| chapter | words | depth | pages if whole | pages one level down (max words) | two levels down (max) |")
    print("|---|---|---|---|---|---|")
    for ch in g.children:
        total = subtree(ch, src, set())
        d = depth_of(ch)
        l2 = pages_at(ch, 2, src) if ch.children else [(ch.title, total, 1)]
        l3 = pages_at(ch, 3, src) if d >= 3 else l2
        print(f"| {ch.title[:48]} | {total:,} | {d} | 1 | {len(l2)} ({max(w for _, w, _ in l2):,}) | {len(l3)} ({max(w for _, w, _ in l3):,}) |")


def plan(slug, version, limit):
    """Each chapter (depth-2 entry) gets the shallowest relative depth whose largest page <= limit."""
    conv = next((ROOT / "output").glob(f"*/{slug}/{version}"))
    doc = yaml.safe_load((conv / "toc.yml").read_text(encoding="utf-8"))
    roots = schema_for(doc, None).parse(doc)
    src = _Source(conv)
    pages, choice = [], {}
    for g in roots:
        gw = own_words(g, src, set())
        if gw or not g.children:
            pages.append(subtree(g, src, set()) if not g.children else gw)
        for ch in g.children:
            d = depth_of(ch)
            for lv in range(1, d + 1):
                ps = [w for _, w, _ in pages_at(ch, lv, src)] if ch.children else [subtree(ch, src, set())]
                if max(ps) <= limit or lv == d:
                    break
            choice[f"{g.title[:20]} / {ch.title[:40]}"] = (lv, len(ps), max(ps))
            pages += ps
    pages.sort()
    return pages, choice


def draft(slug, version, guide_depth, overrides, limit=5000):
    """guide_depth: {guide: 1 for a one-page guide}; overrides: {(guide, chapter): depth}; else auto."""
    conv = next((ROOT / "output").glob(f"*/{slug}/{version}"))
    doc = yaml.safe_load((conv / "toc.yml").read_text(encoding="utf-8"))
    roots = schema_for(doc, None).parse(doc)
    src = _Source(conv)
    rows, pages = [], []
    for g in roots:
        if not g.children:
            continue
        if guide_depth.get(g.title) == 1:
            w = subtree(g, src, set()); pages.append(w)
            rows.append((g.title, "(whole guide)", 1, 1, w, w, "guide")); continue
        gw = own_words(g, src, set())
        if gw: pages.append(gw)
        for ch in g.children:
            d = depth_of(ch)
            key = (g.title, ch.title)
            if key in overrides:
                lv, how = overrides[key], "set"
            else:
                for lv in range(1, d + 1):
                    ps = [w for _, w, _ in pages_at(ch, lv, src)] if ch.children else [subtree(ch, src, set())]
                    if max(ps) <= limit or lv == d:
                        break
                how = "auto"
            ps = [w for _, w, _ in pages_at(ch, lv, src)] if ch.children else [subtree(ch, src, set())]
            pages += ps
            rows.append((g.title, ch.title, lv, len(ps), sum(ps), max(ps), how))
    return rows, sorted(pages)
