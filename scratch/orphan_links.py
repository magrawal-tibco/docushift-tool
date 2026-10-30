import csv, re, posixpath, random
from pathlib import Path
import yaml
eng = {(r['slug'], r['version']): r['engine'] for r in csv.DictReader(open('config/versions.csv', encoding='utf-8-sig'))}
LINK = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)\s#]+\.md)(?:#[^)]*)?\)')
def walk(items, skip=False):
    for it in items or []:
        yield it
        if skip and it.get('title') == 'Unfiled': continue
        yield from walk(it.get('subfolderlist') or [], skip)
out = []; seen_products = {}
tocs = sorted(Path('output').rglob('toc.yml'))
for toc in tocs:
    p = toc.parts
    if len(p) != 5: continue
    fam, slug, ver = p[1], p[2], p[3]
    if seen_products.get(slug, 0) >= 2: continue
    root = toc.parent
    text = toc.read_text(encoding='utf-8')
    if '"Unfiled"' not in text: continue
    data = yaml.safe_load(text) or {}
    items = data.get('docs') or []
    orphans, filed, titles = set(), set(), {}
    for it in walk(items, True):
        if it.get('title') == 'Unfiled':
            for c in walk(it.get('subfolderlist') or []):
                if c.get('url'): orphans.add(c['url']); titles[c['url']] = c.get('title', '')
        elif it.get('url'):
            filed.add(it['url'].split('#')[0]); titles.setdefault(it['url'].split('#')[0], it.get('title', ''))
    orphans -= filed
    r301 = {}
    f301 = root / '301.yml'
    if f301.exists():
        for row in (yaml.safe_load(f301.read_text(encoding='utf-8')) or {}).get('redirects') or []:
            r301.setdefault(row['to'].split('#')[0], row['from'])
    for rel in sorted(filed):
        md = root / rel
        if not md.exists(): continue
        hits = [(t, posixpath.normpath(posixpath.join(posixpath.dirname(rel), m)))
                for t, m in LINK.findall(md.read_text(encoding='utf-8', errors='replace'))]
        hits = [(t, o) for t, o in hits if o in orphans and o != rel]
        if hits:
            t, o = hits[0]
            out.append(dict(family=fam, product=slug, version=ver, engine=eng.get((slug, ver), ''),
                            linking_page_title=titles.get(rel, ''), linking_page_docsite=r301.get(rel, ''),
                            link_text=t.strip()[:80], orphan_title=titles.get(o, '') or '(blank)',
                            orphan_docsite=r301.get(o, ''), linking_page_file=rel, orphan_file=o))
            seen_products[slug] = seen_products.get(slug, 0) + 1
            break
with open('reports/orphan-link-examples.csv', 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out))
