#!/usr/bin/env python3
"""从本地语料 frontmatter 抽取来源，产出 corpus/provenance.json。"""
import json, os, re, collections
from opencc import OpenCC
t2s = OpenCC('t2s').convert
SRC = '/home/zjz/nongye/_legacy/农业水利古籍'
ALIAS = {'农书': '陈旉农书', '王祯农书': '王氏农书'}
def norm(t):
    t = t2s((t or '').strip()).replace('（陈旉）', '').strip()
    return ALIAS.get(t, t)

up = {norm(b['title']): b for b in json.load(open('books/catalog.json', encoding='utf-8'))}
out, stats = [], collections.Counter()
for row in open('/home/zjz/nongye/_legacy/export/books.jsonl', encoding='utf-8'):
    b = json.loads(row); fn = b['filename']
    p = os.path.join(SRC, fn)
    head = open(p, encoding='utf-8').read(4000) if os.path.exists(p) else ''
    m = re.match(r'^---\n(.*?)\n---', head, re.S)
    fm = m.group(1) if m else ''
    def g(k):
        mm = re.search(r'^%s:\s*(.+)$' % k, fm, re.M)
        return mm.group(1).strip() if mm else None
    hant = re.search(r'zh-hant:\s*(.+)', fm)
    kr = re.findall(r'-\s*(KR\w+)/(\w+)', fm)
    ctp = re.findall(r'-\s*(ctp:\S+)', fm)
    rec = {
        'file': fn,
        'title': b['title'],
        'title_hant': (hant.group(1).strip() if hant else None) or b.get('title_hant') or None,
        'author_front': g('author'),
        'ctext_category': g('category'),
        'daizhige_url': g('daizhige_url'),
        'github_repo_url': g('github_repo_url'),
        'lastmod': g('lastmod'),
        'kanripo': [{'id': i, 'edition': e} for i, e in kr],
        'ctext': ctp,
        'upstream_id': up.get(norm(b['title']), {}).get('id'),
        'chars': b['n_chars'],
    }
    out.append(rec)
    stats['有 frontmatter' if fm else '无 frontmatter'] += 1
    stats['有 daizhige 链接' if rec['daizhige_url'] else '无 daizhige 链接'] += 1
    stats['有 kanripo 编号' if kr else '无 kanripo 编号'] += 1
    stats['有 ctext 链接' if ctp else '无 ctext 链接'] += 1
    tag = '重叠' if rec['upstream_id'] else '独占'
    stats[f'{tag}/有frontmatter' if fm else f'{tag}/无frontmatter'] += 1
    stats[f'{tag}/有kanripo' if kr else f'{tag}/无kanripo'] += 1
os.makedirs('corpus', exist_ok=True)
json.dump(out, open('corpus/provenance.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('记录 %d 条' % len(out))
for k, v in sorted(stats.items()): print(' ', k, v)
print('\n无 frontmatter 的文件:', [r['file'] for r in out if not r['daizhige_url'] and not r['kanripo']])
