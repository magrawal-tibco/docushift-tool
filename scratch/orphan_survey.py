import csv, re, collections, posixpath
from pathlib import Path
import yaml
eng = {(r['slug'], r['version']): r['engine'] for r in csv.DictReader(open('config/versions.csv', encoding='utf-8-sig'))}
LINK = re.compile(r'\]\(([^)\s#]+\.md)(?:#[^)]*)?\)')
def walk(items, skip=False):
    for it in items or []:
        yield it
        if skip and it.get('title') == 'Unfiled': continue
        yield from walk(it.get('subfolderlist') or [], skip)
stats = collections.defaultdict(collections.Counter)
for toc in Path('output').rglob('toc.yml'):
    p = toc.parts
    if len(p) != 5: continue
    root = toc.parent; e = eng.get((p[2], p[3]), '?')
    data = yaml.safe_load(toc.read_text(encoding='utf-8')) or {}
    items = data.get('guides') or data.get('items') or data.get('docs') or (data if isinstance(data, list) else [])
    orphans = set(); filed = set()
    for it in walk(items, True):
        if it.get('title') == 'Unfiled':
            for c in walk(it.get('subfolderlist') or []):
                if c.get('url'): orphans.add(c['url'])
        elif it.get('url'): filed.add(it['url'])
    orphans -= filed
    st = stats[e]; st['versions'] += 1; st['topics'] += len(orphans) + len(filed)
    if not orphans: continue
    st['versions_with'] += 1; st['orphans'] += len(orphans)
    linked = set(); from_filed = set()
    for md in root.rglob('*.md'):
        rel = md.relative_to(root).as_posix()
        if rel == 'unfiled.md': continue
        for m in LINK.findall(md.read_text(encoding='utf-8', errors='replace')):
            t = posixpath.normpath(posixpath.join(posixpath.dirname(rel), m))
            if t in orphans and t != rel:
                linked.add(t)
                if rel in filed: from_filed.add(t)
    st['linked_from_any'] += len(linked); st['linked_from_filed'] += len(from_filed)
    csh = root / 'csh.yml'
    if csh.exists():
        txt = csh.read_text(encoding='utf-8')
        st['csh_targets'] += sum(1 for o in orphans if o in txt)
    r301 = root / '301.yml'
    if r301.exists():
        txt = r301.read_text(encoding='utf-8')
        st['in_301'] += sum(1 for o in orphans if f'to: {o}' in txt)
    st['empty_or_tiny'] += sum(1 for o in orphans if (root / o).exists() and len((root / o).read_text(encoding='utf-8', errors='replace').split('---', 2)[-1].split()) < 20)
for e, st in stats.items(): print(e, dict(st))
