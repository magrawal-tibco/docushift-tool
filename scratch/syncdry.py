import collections,re
rows=[l.split('|') for l in open('scratch/tibco-sync-dry.log',encoding='utf-8',errors='replace') if l.startswith('| ') and 'Product' not in l]
rows=[[c.strip() for c in r[1:-1]] for r in rows if len(r)>6]
print(len(rows))
print('online help', collections.Counter(r[2] for r in rows).most_common())
print('documents', collections.Counter(re.sub(r'\d+','N',r[3]) for r in rows).most_common(8))
