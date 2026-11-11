#!/usr/bin/env python3
"""从 books/ 重建 corpus.db —— 检索层的唯一数据源。

设计依据见 ../PLAN.md（D3 / D4 / D8）：

  * **索引只建简体层**。简体文本沿用旧切块 `_legacy/export/chunks_text.jsonl.gz`：
    旧切块规则不可复现（构建脚本已失传），且 `nongshi` 560 条农事靠 `chunk_id`
    指向这些切块，重新切块会打断全部引用。因此本脚本不发明新的切块规则。
  * **繁体层只登记不索引**。`books/agriculture|water` 的 Kanripo 繁體本作为可阅
    文本登记在 `texts`，待与简体参校本逐段对齐后再进索引。
  * **运行时零第三方依赖**。中文检索用自建二元切分（本机 SQLite 3.26 的 FTS5
    没有 trigram，需 >= 3.34），繁简归一用导出的 `t2s.json`；查询期不需要 jieba
    也不需要 opencc。

用法：
    python3 corpus/build.py            # 构建 corpus.db 与 manifest.json
    python3 corpus/build.py --export   # 另外导出 solar-terms.yaml / nongshi.yaml / t2s.json
    python3 corpus/build.py --check    # 重建并与 manifest.json 比对（CI 用）
"""
import argparse, gzip, hashlib, json, os, re, shutil, sqlite3, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEGACY = '/home/zjz/nongye/_legacy'
DB = os.path.join(HERE, 'corpus.db')
MANIFEST = os.path.join(HERE, 'manifest.json')
CHUNKS_ASSET = os.path.join(HERE, 'legacy_chunks.jsonl.gz')
EXPECTED_CHARS = 6730563          # 与 _legacy/build_report.md 逐位吻合

CJK_RUN = re.compile(r'[㐀-䶿一-鿿豈-﫿]+')

CN_MONTH = {'正': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
            '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}
# 文中自带的月份声明，兼容 \[X月\] 、 [X月] 与 ○X月[X月] 三种写法
MONTH_DECL = re.compile(
    r'^(?:○|◎|●)?\s*(?:\\?\[([正一二三四五六七八九十]{1,2})月\\?\]'
    r'|([正一二三四五六七八九十]{1,2})月\\?\[)')


def derive_months(rows):
    """按文档顺序解析文中月份声明，向下继承（限同一 chunk 内）。

    为何要修：旧构建脚本已失传，从数据倒推它是拿 **chunk 号尾数当月份**：
    chunk 333 整块被标 3 月（开头明写 `○二月\\[二月\\]仲春建卯`）、
    chunk 334 整块被标 4 月（里面「五月」块跟着错）。所以真错全部是
    **相差 1 个月** 的错标。

    只修 ±1：跳多个月的不改，标为 `conflict` 保留原值。实例是「四杀没时」
    两条通用占辞（id 384/399，原标 11/12 月），它们的 chunk_id 挂在 334 会
    被继承成 6 月 —— 跳 5、6 个月，说明是条目自身 chunk 归属错，不是月份错。

    不拿节气名推断：曾试过把「○冬至杂占」按节气表归到十一月，但那是拿
    我们的推断覆盖原文自带的章节结构，不贴原文。

    返回 {id: (生效月份, 原值, 依据)}；依据 ∈ declared|inherited|legacy|conflict。
    """
    out, cur, cur_chunk = {}, None, None
    for r in sorted(rows, key=lambda r: (r['book_id'], r['chunk_id'], r['id'])):
        m = MONTH_DECL.match((r['text'] or '').strip())
        declared = CN_MONTH.get(m.group(1) or m.group(2)) if m else None
        if declared is not None:
            cur, cur_chunk = declared, r['chunk_id']
            out[r['id']] = (cur, r['month'], 'declared')
        elif cur is not None and r['chunk_id'] == cur_chunk:
            if abs(cur - r['month']) <= 1:
                out[r['id']] = (cur, r['month'], 'inherited')
            else:
                out[r['id']] = (r['month'], r['month'], 'conflict')
        else:
            out[r['id']] = (r['month'], r['month'], 'legacy')
    return out


def tokenize(text):
    """中文串同时产单字与二元 token；非中文（空白/标点/数字/字母）丢弃。

    只建二元的坑：单字查询（如「耕」「桑」）在二元索引里根本不存在，
    召回会跌到个位数（实测「耕」4 条 vs 子串真値 468 条）。所以单字与
    二元双写：>=2 字的相邻语义仍由二元 token 保证，单字查询走单字 token。

    查询端必须用同一个函数，search 侧直接 `from build import tokenize`。
    """
    toks = []
    for run in CJK_RUN.findall(text or ''):
        toks.extend(list(run))
        if len(run) > 1:
            toks.extend(run[i:i + 2] for i in range(len(run) - 1))
    return ' '.join(toks)


bigrams = tokenize          # 旧名兼容


def sha1(s):
    return hashlib.sha1((s or '').encode('utf-8')).hexdigest()[:16]


def clean_text(s):
    """旧库文本里混着 `\\[正月\\]` 这类转义，统一还原为 [正月]。"""
    return (s or '').replace('\\[', '[').replace('\\]', ']')


def jl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def jl_pairs(path):
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        for line in f:
            yield json.loads(line)


def schema(conn):
    conn.executescript('''
    CREATE TABLE works(
      id TEXT PRIMARY KEY, title TEXT, author TEXT, dynasty TEXT,
      category TEXT, topic TEXT, edition TEXT, source_project TEXT,
      source_status TEXT, needs_review INTEGER, summary TEXT,
      file_main TEXT, file_kanripo TEXT, file_local TEXT,
      n_chars INTEGER, n_chunks INTEGER);
    CREATE TABLE texts(
      work_id TEXT, variant TEXT, file TEXT, lang TEXT,
      source_status TEXT, n_chars INTEGER, indexed INTEGER,
      PRIMARY KEY(work_id, variant));
    CREATE TABLE chunks(
      id INTEGER PRIMARY KEY, work_id TEXT, seq INTEGER, section TEXT,
      text TEXT, n_chars INTEGER, sha1 TEXT);
    CREATE INDEX chunks_work ON chunks(work_id);
    CREATE VIRTUAL TABLE chunks_fts USING fts5(cid UNINDEXED, tok);
    CREATE TABLE solar_terms(
      id INTEGER PRIMARY KEY, name TEXT, season TEXT, lunar_month INTEGER,
      solar_date TEXT, farming TEXT, ord INTEGER);
    CREATE TABLE nongshi(
      id INTEGER PRIMARY KEY, work_id TEXT, month INTEGER, month_legacy INTEGER,
      month_source TEXT, label TEXT, text TEXT, chunk_id INTEGER);
    ''')


def build(conn):
    catalog = json.load(open(os.path.join(ROOT, 'books', 'catalog.json'), encoding='utf-8'))
    variants = json.load(open(os.path.join(ROOT, 'books', 'variants.json'), encoding='utf-8'))
    nx_index = json.load(open(os.path.join(ROOT, 'books', 'nx_index.json'), encoding='utf-8'))
    legacy_books = {b['id']: b for b in jl(os.path.join(LEGACY, 'export', 'books.jsonl'))}

    # books/local/ 实际文件名（NX 前缀 → 路径），以磁盘为准不靠拼规则
    nx_file = {}
    for fn in os.listdir(os.path.join(ROOT, 'books', 'local')):
        nx_file[fn.split('_')[0]] = 'local/' + fn

    # 旧 book_id → 本地文件名 → NX；NX 若对应上游书则归到上游 work
    nx_of_filename = nx_index
    work_of_localfile = {}
    for fn, nid in nx_of_filename.items():
        work_of_localfile[fn] = nid
    # KR 条目的 local_variant 指针：NX → 应归入的 KR work
    kr_of_nx = {}
    for e in catalog:
        if e.get('local_variant'):
            kr_of_nx[e['local_variant']] = e['id']
    work_of_localfile = {fn: kr_of_nx.get(nid, nid) for fn, nid in work_of_localfile.items()}
    # 同作品异本（NX0009 天工开物古腾堡版、NX0025 老圃良言维基版）已降级不占作品位，
    # 但它们的旧切块还指着这些 id，不重定向到主条目就会被 JOIN 掉，55 个 chunk 检索不到
    alias = {d['nx']: d['of'] for d in variants.get('local_duplicates', [])}
    work_of_localfile = {fn: alias.get(w, w) for fn, w in work_of_localfile.items()}

    # works：一部作品一行
    for e in catalog:
        if e['id'].startswith('KR'):
            nid = e.get('local_variant')
            conn.execute('INSERT INTO works VALUES(' + ','.join('?' * 16) + ')', (
                e['id'], e['title'], e['author'], e['dynasty'], e['category'], e['topic'],
                e['edition'], 'kanripo', 'verified', 0, e['summary'],
                e['file'], e['file'], nx_file.get(nid) if nid else None, e['chars'], None))
            conn.execute('INSERT INTO texts VALUES(?,?,?,?,?,?,?)', (
                e['id'], 'kanripo', e['file'], 'hant', 'verified', e['chars'], 0))
        else:
            conn.execute('INSERT INTO works VALUES(' + ','.join('?' * 16) + ')', (
                e['id'], e['title'], e['author'], e['dynasty'], e['category'], e['topic'],
                e['edition'], e['source_project'], e['source_status'],
                1 if e['needs_review'] else 0, e['summary'],
                e['file'], None, e['file'], e['chars'], None))
            conn.execute('INSERT INTO texts VALUES(?,?,?,?,?,?,?)', (
                e['id'], 'local', e['file'], 'hans', e['source_status'], e['chars'], 1))

    # 同作品异本（天工开物、老圃良言）也登记为可阅文本
    dup_nx = {d['nx']: d['of'] for d in variants.get('local_duplicates', [])}
    for nid, wid in dup_nx.items():
        conn.execute('INSERT OR REPLACE INTO texts VALUES(?,?,?,?,?,?,?)', (
            wid, 'dup-' + nid, nx_file[nid], 'hans',
            'verified' if nid not in ('NX0009',) else 'inferred', None, 1))
    # 重叠书的简体参校本
    prov = json.load(open(os.path.join(ROOT, 'corpus', 'provenance.json'), encoding='utf-8'))
    status_of_nx = {}
    for r in prov:
        status_of_nx[nx_of_filename.get(r['file'], '?')] = r['source_status']
    for nid, kr in kr_of_nx.items():
        conn.execute('INSERT OR REPLACE INTO texts VALUES(?,?,?,?,?,?,?)', (
            kr, 'local-' + nid, nx_file[nid], 'hans', status_of_nx.get(nid, 'unknown'), None, 1))

    # 旧切块资产必须随仓走，否则仓库自己复现不出检索层
    asset = CHUNKS_ASSET if os.path.exists(CHUNKS_ASSET) else os.path.join(
        LEGACY, 'export', 'chunks_text.jsonl.gz')
    n = 0
    for c in jl_pairs(asset):
        fb = legacy_books.get(c['book_id'])
        if not fb:
            sys.exit(f'旧 chunk {c["id"]} 的 book_id {c["book_id"]} 在 books.jsonl 中不存在')
        wid = work_of_localfile[fb['filename']]
        text = clean_text(c['text_sim'])
        conn.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?)',
                     (c['id'], wid, c['seq'], clean_text(c['section']), text,
                      c['n_chars'], sha1(text)))
        conn.execute('INSERT INTO chunks_fts(rowid, cid, tok) VALUES(?,?,?)',
                     (c['id'], c['id'], tokenize(text)))
        n += 1

    for r in jl(os.path.join(LEGACY, 'export', 'solar_terms.jsonl')):
        conn.execute('INSERT INTO solar_terms VALUES(?,?,?,?,?,?,?)', (
            r['id'], r['name'], r['season'], r['lunar_month'], r['solar_date'],
            clean_text(r['farming']), r['ord']))

    n_fixed = 0
    months = derive_months(jl(os.path.join(LEGACY, 'export', 'nongshi.jsonl')))
    for r in jl(os.path.join(LEGACY, 'export', 'nongshi.jsonl')):
        fb = legacy_books.get(r['book_id'])
        wid = work_of_localfile[fb['filename']] if fb else None
        eff, legacy_month, source = months[r['id']]
        if eff != legacy_month:
            n_fixed += 1
        conn.execute('INSERT INTO nongshi VALUES(?,?,?,?,?,?,?,?)', (
            r['id'], wid, eff, legacy_month, source, r['label'], clean_text(r['text']), r['chunk_id']))
    print(f'农事月份按文中声明修正 {n_fixed} 行')

    conn.execute('UPDATE works SET n_chunks = '
                 '(SELECT COUNT(*) FROM chunks WHERE chunks.work_id = works.id)')
    conn.commit()          # 不 commit 的话 close 会回滚，落盘变空库
    return n, n_fixed


def manifest(conn):
    m = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
         for t in ('works', 'texts', 'chunks', 'chunks_fts', 'solar_terms', 'nongshi')}
    m['n_chars_indexed'] = conn.execute('SELECT COALESCE(SUM(n_chars),0) FROM chunks').fetchone()[0]
    rows = conn.execute('SELECT work_id, n_chars, sha1 FROM chunks ORDER BY id').fetchall()
    m['chunks_digest'] = hashlib.sha256(
        '|'.join(f'{a}:{b}:{c}' for a, b, c in rows).encode()).hexdigest()
    nulls = conn.execute('SELECT COUNT(*) FROM chunks WHERE work_id IS NULL').fetchone()[0]
    m['chunks_without_work'] = nulls
    # work_id 悬空（指向已降级/不存在的作品）会在 API 的 JOIN 里静默消失
    m['chunks_dangling'] = conn.execute(
        'SELECT COUNT(*) FROM chunks WHERE work_id NOT IN (SELECT id FROM works)').fetchone()[0]
    orphan = conn.execute('SELECT COUNT(*) FROM nongshi WHERE work_id NOT IN (SELECT id FROM works)').fetchone()[0]
    m['nongshi_without_work'] = orphan
    m['nongshi_month_fixed'] = conn.execute(
        'SELECT COUNT(*) FROM nongshi WHERE month != month_legacy').fetchone()[0]
    m['nongshi_month_conflict'] = conn.execute(
        "SELECT COUNT(*) FROM nongshi WHERE month_source = 'conflict'").fetchone()[0]
    return m


def export():
    """导出可手工修订的数据源：节气、农事、繁简单字表。"""
    import yaml
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    for table, out, key in (('solar_terms', 'solar-terms.yaml', '节气农时'),
                            ('nongshi', 'nongshi.yaml', '农事月令')):
        rows = [dict(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY id')]
        with open(os.path.join(HERE, out), 'w', encoding='utf-8') as f:
            f.write(f'# {key}，由 corpus/build.py --export 从 corpus.db 导出\n')
            yaml.safe_dump(rows, f, allow_unicode=True, sort_keys=False, width=100)
        print(f'  {out}: {len(rows)} 条')
    # 繁简单字表：运行时归一查询词用，避免依赖 opencc
    from opencc import OpenCC
    cc = OpenCC('t2s')
    m = {}
    for cp in list(range(0x3400, 0x4DC0)) + list(range(0x4E00, 0xA000)):
        ch = chr(cp)
        s = cc.convert(ch)
        if s and s != ch and len(s) == 1:
            m[ch] = s
    with open(os.path.join(HERE, 't2s.json'), 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, sort_keys=True)
    print(f'  t2s.json: {len(m)} 个单字映射')
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--export', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    tmpdir = tempfile.mkdtemp(prefix='corpus-check-', dir=HERE)
    tmp = os.path.join(tmpdir, 'corpus.db')
    try:
        conn = sqlite3.connect(tmp)
        schema(conn)
        n, n_fixed = build(conn)
        m = manifest(conn)
        conn.close()

        ok = True
        print(f'chunks {n} 条（索引 {m["chunks_fts"]} 行，字数 {m["n_chars_indexed"]:,}）')
        print(f'works {m["works"]} / texts {m["texts"]} / solar_terms {m["solar_terms"]} / nongshi {m["nongshi"]}')
        print(f'chunks_digest {m["chunks_digest"][:16]}  work_id 缺失 {m["chunks_without_work"]} / {m["nongshi_without_work"]}')
        print(f'农事月份修正 {m["nongshi_month_fixed"]} 行（原值在 month_legacy），'
              f'存疑保留 {m["nongshi_month_conflict"]} 行')

        if n != 1791:
            print('!! 切块数不是 1791'); ok = False
        if m['n_chars_indexed'] != EXPECTED_CHARS:
            print(f'!! 字数 {m["n_chars_indexed"]} != 预期 {EXPECTED_CHARS}'); ok = False
        if m['works'] != 73 or m['texts'] != 103:
            print(f'!! works/texts 数量异常：{m["works"]}/{m["texts"]}（预期 73/103 = KR42 + NX31 + 异本2 + 参校28）'); ok = False
        if m['chunks_without_work'] or m['nongshi_without_work'] or m['chunks_dangling']:
            print(f'!! 有行未能归属作品（悬空 chunk {m["chunks_dangling"]}）'); ok = False

        if args.check:
            old = json.load(open(MANIFEST, encoding='utf-8')) if os.path.exists(MANIFEST) else None
            if old is None:
                print('!! 没有 manifest.json，无法 --check'); ok = False
            else:
                diff = {k: (old.get(k), v) for k, v in m.items() if old.get(k) != v}
                print('manifest 一致' if not diff else f'manifest 差异 {diff}')
                ok = ok and not diff
        elif ok:
            shutil.copyfile(tmp, DB)
            with open(MANIFEST, 'w', encoding='utf-8') as f:
                json.dump(m, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.write('\n')
            print('已写入', DB, f'({os.path.getsize(DB) / 1048576:.1f} MB)')
            if args.export:
                export()
        else:
            print('!! 校验未过，不覆盖 corpus.db')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
