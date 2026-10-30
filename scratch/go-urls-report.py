"""Go URL -> target URL report from the saved docs.tibco.com Go URL admin page (DOCOPS-279).

Usage: python -I scratch/go-urls-report.py <saved page.html> <out.csv>
Keeps every row in page order; adds columns that flag the problems.
"""
import collections
import csv
import html
import re
import sys
from urllib.parse import urlsplit

ENTRY = re.compile(
    r'<li class="manage-go-url[^"]*">.*?Target Url:</label><div class="display-inline">(.*?)</div>'
    r'.*?Go Url:</label><div class="display-inline"><a href="(.*?)"[^>]*>(.*?)</a>', re.S)
VERSION = re.compile(r'/(\d+(?:\.\d+)+)(?=/|$)')


def area(url):
    p = urlsplit(url)
    if p.netloc.lower() != 'docs.tibco.com':
        return 'external'
    first = p.path.strip('/').split('/', 1)[0].lower()
    return first or 'root'


def version(url):
    m = VERSION.search(urlsplit(url).path)
    return m.group(1) if m else ''


def norm(url):
    return url.strip().lower().rstrip('/')


def main(src, out):
    text = open(src, encoding='utf-8', errors='replace').read()
    rows = []
    for t, href, g in ENTRY.findall(text):
        go, target = html.unescape(g).strip(), html.unescape(t).strip()
        rows.append({'go_url': go, 'target_url': target, 'link_href_differs': html.unescape(href).strip() != target})

    pair_count = collections.Counter((r['go_url'], r['target_url']) for r in rows)
    targets = collections.defaultdict(list)
    for r in rows:
        if r['target_url'] not in targets[r['go_url']]:
            targets[r['go_url']].append(r['target_url'])
    spellings = collections.defaultdict(set)
    for r in rows:
        spellings[norm(r['go_url'])].add(r['go_url'])

    seen = collections.Counter()
    fields = ['row', 'go_url', 'target_url', 'go_path', 'target_area', 'go_version', 'target_version',
              'pair_occurrences', 'is_repeat', 'go_url_target_count', 'other_targets', 'target_areas_for_go_url',
              'target_is_go_url', 'version_mismatch', 'go_url_spellings', 'malformed_go_url', 'issues']
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            go, target = r['go_url'], r['target_url']
            pair = (go, target)
            seen[pair] += 1
            gp = urlsplit(go).path
            go_path = gp.split('/go/', 1)[1] if '/go/' in gp else gp
            others = [t for t in targets[go] if t != target]
            gv, tv = version(go), version(target)
            malformed = '://' in go_path or ' ' in go or not go.lower().startswith('https://docs.tibco.com/go/')
            issues = []
            if seen[pair] > 1:
                issues.append('repeat')
            if others:
                issues.append('multiple-targets')
            if '/go/' in urlsplit(target).path:
                issues.append('target-is-go-url')
            if gv and tv and gv != tv:
                issues.append('version-mismatch')
            if len(spellings[norm(go)]) > 1:
                issues.append('case-or-slash-variant')
            if malformed:
                issues.append('malformed-go-url')
            if area(target) == 'external':
                issues.append('external-target')
            if r['link_href_differs']:
                issues.append('link-href-differs')
            w.writerow({
                'row': i, 'go_url': go, 'target_url': target, 'go_path': go_path,
                'target_area': area(target), 'go_version': gv, 'target_version': tv,
                'pair_occurrences': pair_count[pair], 'is_repeat': 'yes' if seen[pair] > 1 else 'no',
                'go_url_target_count': len(targets[go]), 'other_targets': ' | '.join(others),
                'target_areas_for_go_url': '+'.join(sorted({area(t) for t in targets[go]})),
                'target_is_go_url': 'yes' if 'target-is-go-url' in issues else 'no',
                'version_mismatch': 'yes' if 'version-mismatch' in issues else 'no',
                'go_url_spellings': len(spellings[norm(go)]),
                'malformed_go_url': 'yes' if malformed else 'no',
                'issues': ';'.join(issues),
            })
    print(f'{len(rows)} rows -> {out}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
