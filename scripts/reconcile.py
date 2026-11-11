#!/usr/bin/env python3
"""对账：本地 61 部（_legacy/export/books.jsonl）与上游 books/catalog.json。"""
import json, sys
from collections import defaultdict
from opencc import OpenCC

LOCAL = '/home/zjz/nongye/_legacy/export/books.jsonl'
t2s = OpenCC('t2s').convert
# 同名异写归一：本地用通行名，四库用另一题名
ALIAS = {'农书': '陈旉农书', '王祯农书': '王氏农书'}

def norm(t):
    t = t2s((t or '').strip()).replace('（陈旉）', '').strip()
    return ALIAS.get(t, t)

up = [b for b in json.load(open('books/catalog.json', encoding='utf-8')) if b['id'].startswith('KR')]
loc = [json.loads(l) for l in open(LOCAL, encoding='utf-8')]
by_up = defaultdict(list)
for b in up: by_up[norm(b['title'])].append(b)

rows, used = [], set()
for b in loc:
    key = norm(b['title'])
    m = by_up.get(key)
    if m:
        u = m[0]; used.add(u['id'])
        rows.append(('重叠', b, u))
    else:
        rows.append(('本地独占', b, None))
up_only = [u for u in up if u['id'] not in used]

def fmt(n): return f"{n:,}" if n else '-'
out = ['# 书目对账：本地语料 × 上游仓库', '',
       '由 `python3 scripts/reconcile.py` 生成，勿手工编辑。', '',
       f"- 上游 catalog.json：**{len(up)}** 部 / {fmt(sum(b['chars'] for b in up))} 字",
       f"- 本地 books.jsonl：**{len(loc)}** 部 / {fmt(sum(b['n_chars'] for b in loc))} 字",
       f"- 重叠 **{len(rows) - sum(1 for r in rows if r[0]=='本地独占')}** 部　"
       f"本地独占 **{sum(1 for r in rows if r[0]=='本地独占')}** 部　上游独占 **{len(up_only)}** 部", '']

out += ['## 重叠书目（以上游繁體本为正文，本地简体本降为 variant）', '',
        '| 书名 | 朝代 | 上游 id | 上游字数 | 本地字数 | 字数比 |', '|---|---|---|---|---|---|']
for _, b, u in sorted(rows, key=lambda r: norm(r[1]['title'])):
    if u is None: continue
    ratio = round(b['n_chars'] / u['chars'], 2) if u['chars'] else None
    out.append(f"| {t2s(b['title'])} | {b['dynasty']} | {u['id']} | {fmt(u['chars'])} | {fmt(b['n_chars'])} | {ratio} |")

out += ['', '## 本地独占（迁入仓库，id 前缀 NX）', '',
        '| 拟用 id | 书名 | 朝代 | 作者 | 类别 | 地域 | 字数 | 块数 |', '|---|---|---|---|---|---|---|---|']
nx = 0
for st, b, u in sorted(rows, key=lambda r: (r[1]['category'], norm(r[1]['title']))):
    if st == '重叠': continue
    nx += 1
    out.append(f"| NX{nx:04d} | {t2s(b['title'])} | {b['dynasty']} | {b['author']} | {b['category']} | "
               f"{b['region']} | {fmt(b['n_chars'])} | {b['n_chunks']} |")

out += ['', '## 上游独占（本地缺失，直接用上游）', '',
        '| id | 书名 | 朝代 | 主题 | 字数 |', '|---|---|---|---|---|']
for u in sorted(up_only, key=lambda u: norm(u['title'])):
    out.append(f"| {u['id']} | {u['title']} | {u['dynasty']} | {u['topic']} | {fmt(u['chars'])} |")

open('RECONCILE.md', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print(f"OK 重叠={len(rows)-nx} 本地独占={nx} 上游独占={len(up_only)}")
print("上游独占:", " ".join(u["title"] for u in sorted(up_only, key=lambda u: norm(u["title"]))))
