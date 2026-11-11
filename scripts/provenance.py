#!/usr/bin/env python3
"""抽取本地语料的逐书来源，生成 corpus/provenance.json。

来源分三档：
  verified   frontmatter 自带 github_repo_url / daizhige_url（殆知阁 daizhigev20）
  inferred   无 frontmatter，按正文特征推断（维基文库 / Project Gutenberg）
  unknown    两者皆无

inferred 一律 needs_review=true，且只填正文里确实存在的证据，不做外部查证。
"""
import json, os, re, collections
from urllib.parse import quote
from opencc import OpenCC

t2s = OpenCC('t2s').convert
SRC = '/home/zjz/nongye/_legacy/农业水利古籍'
BOOKS = '/home/zjz/nongye/_legacy/export/books.jsonl'
ALIAS = {'农书': '陈旉农书', '王祯农书': '王氏农书'}   # 同名异写归一，与 reconcile.py 保持一致


def norm(t):
    t = t2s((t or '').strip()).replace('（陈旉）', '').strip()
    return ALIAS.get(t, t)


def parse_header(block):
    """兼容维基文库两种写法：多行 `| title = X` 与内联 `|title=X|author=Y`。"""
    f = {}
    for k, v in re.findall(r'(?:^|\|)\s*(title|author|times|section|notes)\s*=\s*([^|\n]*)', block):
        f.setdefault(k.lower(), v.strip() or None)
    return f


def detect_no_frontmatter(head):
    """无 frontmatter 时按正文特征推断来源。"""
    if re.search(r'\{\{\s*header\b', head, re.I):
        blk = re.search(r'\{\{\s*header\b(.*?)\}\}', head, re.S | re.I).group(1)
        f = parse_header(blk)
        title = f.get('title')
        return {
            'source_project': 'wikisource',
            'source_status': 'inferred',
            'evidence': '正文含 MediaWiki {{header}} 模板与 [[Category:]] 标记',
            'source_url': ('https://zh.wikisource.org/wiki/' + quote(title)) if title else None,
            'header_title_hant': title,
            'header_author': f.get('author'),
            'header_dynasty': f.get('times'),
            'header_notes': f.get('notes'),
        }
    m = re.search(r'Project Gutenberg.*?eBook', head, re.S)
    if m:
        t = re.search(r'^Title:\s*(.+)$', head, re.M)
        a = re.search(r'^Author:\s*(.+)$', head, re.M)
        return {
            'source_project': 'gutenberg',
            'source_status': 'inferred',
            'evidence': '正文首行即 Project Gutenberg eBook 声明',
            'source_url': None,   # 文件内无电子书号，待人工补
            'header_title_hant': t.group(1).strip() if t else None,
            'header_author': a.group(1).strip() if a else None,
            'header_dynasty': None,
            'header_notes': None,
        }
    return {'source_project': None, 'source_status': 'unknown', 'evidence': None,
            'source_url': None, 'header_title_hant': None, 'header_author': None,
            'header_dynasty': None, 'header_notes': None}


# 注：books/catalog.json 已含本地 NX 条目，取上游时必须过滤 KR 前缀，
# 否则本地书会跟自己的 NX 条目“相匹配”，上游独占/本地独占全部错乱
up = {norm(b['title']): b for b in json.load(open('books/catalog.json', encoding='utf-8'))
      if b['id'].startswith('KR')}
out, stats = [], collections.Counter()

for row in open(BOOKS, encoding='utf-8'):
    b = json.loads(row)
    fn = b['filename']
    path = os.path.join(SRC, fn)
    head = open(path, encoding='utf-8').read(4000) if os.path.exists(path) else ''
    fm = re.match(r'^---\n(.*?)\n---', head, re.S)
    fm = fm.group(1) if fm else ''

    def g(k):
        m = re.search(r'^%s:\s*(.+)$' % k, fm, re.M)
        if not m:
            return None
        v = m.group(1).strip()
        # frontmatter 里作者常写成 author: '[汉]卜式'，剥掉包裹引号
        if len(v) > 1 and v[0] in "'\"" and v[-1] == v[0]:
            v = v[1:-1].strip()
        return v or None

    hant = re.search(r'zh-hant:\s*(.+)', fm)
    kr = re.findall(r'-\s*(KR\w+)/(\w+)', fm)
    rec = {
        'file': fn,
        'title': b['title'],
        'title_hant': (hant.group(1).strip() if hant else None) or b.get('title_hant') or None,
        'author_meta': b['author'],
        'dynasty_meta': b['dynasty'],
        'category_meta': b['category'],
        'author_front': g('author'),
        'ctext_category': g('category'),
        'daizhige_url': g('daizhige_url'),
        'github_repo_url': g('github_repo_url'),
        'lastmod': g('lastmod'),
        'kanripo': [{'id': i, 'edition': e} for i, e in kr],
        'ctext': re.findall(r'-\s*(ctp:\S+)', fm),
        'upstream_id': up.get(norm(b['title']), {}).get('id'),
        'chars': b['n_chars'],
    }

    if rec['github_repo_url'] or rec['daizhige_url']:
        rec['source_project'] = 'daizhigev20'
        rec['source_status'] = 'verified'
        rec['evidence'] = 'frontmatter 自带 github_repo_url / daizhige_url'
        rec['needs_review'] = False
    else:
        rec.update(detect_no_frontmatter(head))
        rec['needs_review'] = True
        # 与 books_meta 的著录做一致性比对（繁体归一到简体后比）
        ha = rec.get('header_author')
        latin = bool(ha) and not re.search(r'[\u4e00-\u9fff]', ha)
        if ha and latin:
            rec['header_author_latin'] = True   # 拼音/西文，不参与著录比对
        elif ha and t2s(ha) not in (b['author'] or '') and b['author'] not in ('待考', ''):
            rec['meta_conflict'] = {'meta_author': b['author'], 'header_author': ha,
                                    'note': '两源著录不一致，待人工判定'}
        elif ha and b['author'] in ('待考', ''):
            rec['meta_fill'] = {'from': t2s(ha), 'dynasty': rec.get('header_dynasty'),
                                'note': 'books_meta 原为待考，可由本来源补'}

    out.append(rec)
    stats[rec['source_status']] += 1
    stats['project:' + str(rec['source_project'])] += 1
    stats['overlap' if rec['upstream_id'] else 'local_only'] += 1
    for flag in ('meta_conflict', 'meta_fill'):
        if rec.get(flag):
            stats[flag] += 1

os.makedirs('corpus', exist_ok=True)
json.dump(out, open('corpus/provenance.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print('记录 %d 条' % len(out))
for k, v in sorted(stats.items()):
    print('  %-16s %d' % (k, v))
print('\ninferred / unknown 明细：')
for r in out:
    if r['source_status'] != 'verified':
        tag = '  ← 著录冲突' if r.get('meta_conflict') else ('  ← 可补著录' if r.get('meta_fill') else '')
        print('  [%s] %s | %s | %s | %s%s' % (
            r['source_status'], r['file'], r.get('header_title_hant'),
            r.get('header_author'), r.get('source_url') or '(无 URL)', tag))
