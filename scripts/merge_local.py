#!/usr/bin/env python3
"""把本地语料 61 部并入仓库，且不与 fetch_books.py 争抢生成物。

原则：
  * 不删除任何书籍资源；上游 42 部繁體本与本地 61 部**两套文本并存**
  * fetch_books.py 全量跑会重写 books/catalog.json 与 books/INDEX.md，
    因此本脚本设计为「生成之后追加」，可重复执行且结果一致
  * 本地层用 NX 前缀编号，与 Kanripo 的 KR 编号空间不重叠

编号规则（稳定）：先按归并类别（农业→水利）排序，再按简体书名排序，
依次赋 NX0001…NX0061。新增本地书目时整表重排会改变编号，故编号一经
入库即冻结在 books/nx_index.json 中，后续只增不改。

用法：
    python3 scripts/merge_local.py [--check]
"""
import argparse, json, os, re, shutil, sys
from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY = '/home/zjz/nongye/_legacy'
BOOKS = os.path.join(ROOT, 'books')
LOCAL_DIR = os.path.join(BOOKS, 'local')
NX_FILE = os.path.join(BOOKS, 'nx_index.json')
WATER = {'区域水利', '河工治黄', '水文地理', '运河水道', '漕运', '海塘', '农田水利'}
PROJECT_LABEL = {
    'daizhigev20': '殆知阁 daizhigev20（data 分支）',
    'wikisource': '维基文库（按正文 {{header}} 推断）',
    'gutenberg': 'Project Gutenberg（按正文声明推断）',
    None: '来源待考',
}

t2s = OpenCC('t2s').convert


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def slug(title):
    return re.sub(r'[/\s\\:*?"<>|]+', '', title) or 'untitled'


def resolve_credit(b, p):
    """books_meta 记「待考」时，回落到语料自身的 frontmatter / {{header}} 著录。"""
    author, dynasty, origin = b['author'], b['dynasty'], 'books_meta'
    if author in ('待考', '', None):
        raw = (p.get('author_front') or p.get('header_author') or '').strip().strip("'\"")
        if raw:
            m = re.match(r'^[\[【]?\s*([^】\]【\[\s]{1,8})[\]】]\s*(.+)$', raw.strip())
            if m:
                author = m.group(2).strip()
                if dynasty in ('待考', '', None):
                    dynasty = m.group(1).strip()
            else:
                author = t2s(raw.strip())
            if dynasty in ('待考', '', None) and p.get('header_dynasty'):
                dynasty = t2s(p['header_dynasty'].strip())
            origin = 'corpus_self'
    return author, dynasty, origin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验，不写文件')
    args = ap.parse_args()

    prov = load_json(os.path.join(ROOT, 'corpus', 'provenance.json'), [])
    legacy_books = {}
    with open(os.path.join(LEGACY, 'export', 'books.jsonl'), encoding='utf-8') as f:
        for line in f:
            b = json.loads(line)
            legacy_books[b['filename']] = b
    assert len(prov) == len(legacy_books) == 61, f'本地书目数异常: {len(prov)}/{len(legacy_books)}'

    # 1) 编号：冻结在 nx_index.json，不存在则按规则新建
    nx = load_json(NX_FILE, {})
    if not nx:
        order = sorted(prov, key=lambda r: (
            1 if legacy_books[r['file']]['category'] in WATER else 0,
            t2s(legacy_books[r['file']]['title'])))
        nx = {r['file']: f'NX{i + 1:04d}' for i, r in enumerate(order)}

    by_file = {r['file']: r for r in prov}
    file_of_upstream = {r['upstream_id']: r['file'] for r in prov if r['upstream_id']}
    src_cat = {fn: legacy_books[fn]['category'] for fn in by_file}

    # 2) 复制文本（只读源，不改内容；.txt 统一落为 .md 但正文原样）
    if not args.check:
        os.makedirs(LOCAL_DIR, exist_ok=True)
    copied, missing = 0, []
    for fn, nid in sorted(nx.items(), key=lambda kv: kv[1]):
        src = os.path.join(LEGACY, '农业水利古籍', fn)
        if not os.path.exists(src):
            missing.append(fn)
            continue
        dst = os.path.join(LOCAL_DIR, f"{nid}_{slug(by_file[fn]['title'])}.md")
        if not args.check or not os.path.exists(dst):
            shutil.copyfile(src, dst)
        copied += 1
    assert not missing, f'缺源文件: {missing}'

    # 3) 追加 catalog.json（幂等：先剔除 NX 条目再追加）
    cat_path = os.path.join(BOOKS, 'catalog.json')
    catalog = load_json(cat_path, [])
    kr_entries = [e for e in catalog if not e['id'].startswith('NX')]
    assert len(kr_entries) == 42, f'上游条目数异常: {len(kr_entries)}'

    all_local_entries = []
    for fn, nid in sorted(nx.items(), key=lambda kv: kv[1]):
        p, b = by_file[fn], legacy_books[fn]
        author, dynasty, credit_origin = resolve_credit(b, p)
        all_local_entries.append({
            'id': nid,
            'title': b['title'],
            'author': author,
            'dynasty': dynasty,
            'category': '水利' if b['category'] in WATER else '农业',
            'topic': b['category'],                      # 本地细分类原样保留
            'edition': PROJECT_LABEL[p['source_project']],
            'summary': b.get('note') or '',
            'file': f"local/{nid}_{slug(b['title'])}.md",
            'sections': b['n_chunks'],                    # 本地层的 sections 即切块数
            'chars': b['n_chars'],
            'source_project': p['source_project'],
            'source_status': p['source_status'],
            'needs_review': p['needs_review'],
            'credit_source': credit_origin,
        })

    # catalog.json 的语义是「唯一作品」：重叠书以 KR 条目为主条目，本地简体本
    # 只作 local_variant 指针（文件仍完整保留在 books/local/，一字不删）
    local_only_nx = {nx[r['file']] for r in prov if r['upstream_id'] is None}
    local_entries = [e for e in all_local_entries if e['id'] in local_only_nx]

    # 同一作品的两个版本（如老圃良言、天工开物）不得当两部书算：
    # 主条目取 verified 来源，其余降为 dup_variants 指针，文件全部保留
    groups = {}
    for e in local_entries:
        groups.setdefault(t2s(e['title']), []).append(e)
    duplicates = []
    primary = []
    for key in sorted(groups):
        es = groups[key]
        if len(es) == 1:
            primary.append(es[0])
            continue
        es.sort(key=lambda e: (e['source_status'] != 'verified', e['id']))
        head, rest = es[0], es[1:]
        head['dup_variants'] = [e['id'] for e in rest]
        primary.append(head)
        for e in rest:
            duplicates.append({'nx': e['id'], 'of': head['id'], 'title': e['title'],
                               'edition': e['edition']})
    local_entries = primary
    for e in kr_entries:
        e.pop('local_variant', None)
    variants = []
    for e in kr_entries:
        fn = file_of_upstream.get(e['id'])
        if fn:
            e['local_variant'] = nx[fn]
            variants.append({'kanripo_id': e['id'], 'nx': nx[fn], 'title': e['title'],
                             'match': 'kanripo' if by_file[fn]['kanripo'] else 'title'})

    merged = kr_entries + local_entries
    if not args.check:
        with open(cat_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
            f.write('\n')
        with open(os.path.join(BOOKS, 'variants.json'), 'w', encoding='utf-8') as f:
            json.dump({'kanripo_local': variants, 'local_duplicates': duplicates}, f,
                      ensure_ascii=False, indent=2)
            f.write('\n')
        with open(NX_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(sorted(nx.items(), key=lambda kv: kv[1])), f,
                      ensure_ascii=False, indent=2)
            f.write('\n')

    n_kr_local = len(variants)
    print(f'上游 KR 条目 {len(kr_entries)}（标题与原字段未改动，仅挂 local_variant）')
    print(f'本地 NX 主条目 {len(local_entries)}  →  catalog.json 合计 {len(merged)} 部作品')
    print(f'books/local/ 文本 {copied} 份（全部 61 部本地文本一字不删，'
          f'其中 {n_kr_local} 份为重叠书的简体参校文本）')
    print(f'重叠映射 {n_kr_local} 对（kanripo 佐证 '
          f"{sum(1 for v in variants if v['match'] == 'kanripo')}，"
          f"仅书名 {sum(1 for v in variants if v['match'] == 'title')}）")
    print(f'同名异本 {len(duplicates)} 对降为 dup_variants：'
          + '、'.join(f"{d['of']}←{d['nx']}({d['title']})" for d in duplicates))
    filled = [e['id'] + ' ' + e['title'] + f"[{e['dynasty']}·{e['author']}]"
              for e in all_local_entries if e['credit_source'] == 'corpus_self']
    print(f'待考著录由语料自身补齐 {len(filled)} 部：' + '、'.join(filled))
    dup = len(merged) - len({e['id'] for e in merged})
    assert dup == 0, f'catalog.json 存在重复 id {dup} 条'


if __name__ == '__main__':
    main()
