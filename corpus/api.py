#!/usr/bin/env python3
"""corpus.db 之上的只读检索 API —— 只用标准库。

刻意不引入 Flask / jieba / opencc：本机 1 CPU、1.8 GB 内存，旧实现
gunicorn 2 worker × 4 thread 各自要加载 jieba 词典与 OpenCC 字典，是
这台机器上最重的一块。这里单进程 ThreadingHTTPServer + sqlite3 即可。

分词与建库端共用 `build.tokenize`，繁简归一用 `t2s.json`，
所以「查询端与索引端不一致」这个坑不可能出现。

用法：
    python3 corpus/api.py                      # 0.0.0.0:52346
    python3 corpus/api.py --port 52347 --host 127.0.0.1

接口：
    GET /api/health
    GET /api/works?category=&topic=&dynasty=&q=&page=&per_page=
    GET /api/work/<id>
    GET /api/search?q=&category=&work=&page=&per_page=
    GET /api/text/<id>?variant=kanripo|local
    GET /api/solar-terms
    GET /api/nongshi?month=&work=&q=&page=&per_page=
"""
import argparse, http.server, json, os, sqlite3, sys
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from build import tokenize                       # noqa: E402  与建库端同一套分词

DB = os.path.join(HERE, 'corpus.db')
BOOKS = os.path.join(ROOT, 'books')
WEB = os.path.join(ROOT, 'web')
SITES = os.path.join(WEB, 'data', 'sites.geojson')
STATS = os.path.join(WEB, 'data', 'stats.json')
T2S = json.load(open(os.path.join(HERE, 't2s.json'), encoding='utf-8'))

# 静态站与检索 API 共进程共端口：nginx 只需指一处，加端点不用改反代。
MIME = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
    '.geojson': 'application/geo+json; charset=utf-8', '.svg': 'image/svg+xml',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.woff2': 'font/woff2',
    '.yaml': 'text/yaml; charset=utf-8', '.md': 'text/markdown; charset=utf-8',
}
# 路由别名：不搬上游文件就能把旧地图页挂进新导航
ALIASES = {'/': 'home.html', '/map.html': 'index.html'}


def to_simplified(q):
    return ''.join(T2S.get(ch, ch) for ch in q)


def db():
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def clip(text, q, width=52):
    """截取命中处上下文；前端自行加高亮标记。"""
    text = text or ''
    i = text.find(q)
    if i < 0:
        return text[:width * 2]
    a = max(0, i - width)
    b = min(len(text), i + len(q) + width)
    return ('…' if a else '') + text[a:b] + ('…' if b < len(text) else '')


def pages(qs, default=20, cap=100):
    per = min(cap, max(1, int(qs.get('per_page', ['%d' % default])[0])))
    page = max(1, int(qs.get('page', ['1'])[0]))
    return per, page, (page - 1) * per


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *a):
        sys.stderr.write('%s %s\n' % (self.log_date_time_string(), fmt % a))

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        path = u.path.rstrip('/') or '/'
        try:
            if path == '/api':
                return self.send_json({'service': 'agriculture',
                                       'endpoints': ['/api/health', '/api/works', '/api/work/<id>',
                                                     '/api/search', '/api/text/<id>',
                                                     '/api/solar-terms', '/api/nongshi',
                                                     '/api/sites', '/api/sites/<id>', '/api/stats']})
            if path == '/api/health':
                c = db()
                n = {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                     for t in ('works', 'chunks', 'solar_terms', 'nongshi')}
                n['chars_indexed'] = c.execute('SELECT SUM(n_chars) FROM chunks').fetchone()[0]
                n['ok'] = n['chunks'] > 0
                n['sites'] = len(json.load(open(SITES, encoding='utf-8'))['features'])
                return self.send_json(n)
            if path == '/api/works':
                return self.works(qs)
            if path.startswith('/api/work/'):
                return self.work(unquote(path.split('/')[-1]))
            if path == '/api/search':
                return self.search(qs)
            if path.startswith('/api/text/'):
                return self.text(unquote(path.split('/')[-1]), qs)
            if path == '/api/solar-terms':
                return self.send_json([dict(r) for r in db().execute(
                    'SELECT * FROM solar_terms ORDER BY ord')])
            if path == '/api/nongshi':
                return self.nongshi(qs)
            if path == '/api/sites':
                return self.sites(qs)
            if path.startswith('/api/sites/'):
                return self.site(path.rsplit('/', 1)[-1])
            if path == '/api/stats':
                return self.stats()
            if path.startswith('/api/'):
                return self.send_json({'error': 'not found', 'path': path}, 404)
            return self.static(path)
        except Exception as e:                                   # noqa: BLE001
            return self.send_json({'error': type(e).__name__, 'detail': str(e)}, 400)

    # ---- 静态站（web/）----
    def static(self, path):
        rel = ALIASES.get(path, path.lstrip('/'))
        full = os.path.normpath(os.path.join(WEB, rel))
        if not full.startswith(WEB) or not os.path.isfile(full):
            return self.send_json({'error': 'not found', 'path': path}, 404)
        body = open(full, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', MIME.get(os.path.splitext(full)[1],
                                                  'application/octet-stream'))
        self.send_header('Content-Length', str(len(body)))
        # 地图库与字体不变，缓存长一点；页面与自有资源不缓存，免得改了看不到
        cache = ('public, max-age=86400' if '/vendor/' in full
                 else 'no-cache')
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    # ---- GIS 端点：与上游 web/server.py 同语义，app.js 一行不用改 ----
    def sites(self, qs):
        geo = json.load(open(SITES, encoding='utf-8'))
        cat = qs.get('category', [''])[0]
        prov = qs.get('province', [''])[0]
        needle = qs.get('q', [''])[0].strip().lower()
        out = []
        for f in geo['features']:
            p = f.get('properties', {})
            if cat and p.get('category') != cat:
                continue
            if prov and p.get('province') != prov:
                continue
            if needle:
                hay = ' '.join([str(p.get('name', '')), str(p.get('province', '')),
                                str(p.get('city', '')), str(p.get('summary', '')),
                                str(p.get('culture', '')),
                                ' '.join(p.get('tags') or []),
                                ' '.join(p.get('heritage') or [])]).lower()
                if needle not in hay:
                    continue
            out.append(f)
        body = {'type': 'FeatureCollection', 'features': out}
        return self.send_json(body)

    def site(self, sid):
        for f in json.load(open(SITES, encoding='utf-8'))['features']:
            if f.get('properties', {}).get('id') == sid:
                return self.send_json(f)
        return self.send_json({'error': 'no such site', 'id': sid}, 404)

    def stats(self):
        return self.send_json(json.load(open(STATS, encoding='utf-8')))

    # ---- 作品 ----
    def works(self, qs):
        per, page, off = pages(qs)
        where, args = ['1=1'], []
        for k in ('category', 'topic', 'dynasty'):
            v = qs.get(k, [''])[0].strip()
            if v:
                where.append(f'{k} = ?'); args.append(v)
        q = qs.get('q', [''])[0].strip()
        if q:
            where.append('(title LIKE ? OR author LIKE ? OR summary LIKE ?)')
            args += ['%' + q + '%'] * 3
        w = ' AND '.join(where)
        c = db()
        total = c.execute('SELECT COUNT(*) FROM works WHERE ' + w, args).fetchone()[0]
        rows = c.execute('SELECT id,title,author,dynasty,category,topic,edition,'
                         'source_status,needs_review,n_chars,n_chunks,file_main '
                         'FROM works WHERE ' + w + ' ORDER BY id LIMIT ? OFFSET ?',
                         args + [per, off]).fetchall()
        return self.send_json({'total': total, 'page': page, 'per_page': per,
                               'items': [dict(r) for r in rows]})

    def work(self, wid):
        c = db()
        row = c.execute('SELECT * FROM works WHERE id = ?', (wid,)).fetchone()
        if not row:
            return self.send_json({'error': 'no such work', 'id': wid}, 404)
        w = dict(row)
        w['texts'] = [dict(r) for r in c.execute(
            'SELECT variant,file,lang,source_status,n_chars,indexed FROM texts '
            'WHERE work_id = ? ORDER BY variant', (wid,))]
        w['sections'] = [dict(r) for r in c.execute(
            'SELECT seq,section,n_chars FROM chunks WHERE work_id = ? ORDER BY seq', (wid,))]
        return self.send_json(w)

    # ---- 检索 ----
    def search(self, qs):
        raw = qs.get('q', [''])[0].strip()
        if not raw:
            return self.send_json({'error': 'q required'}, 400)
        simp = to_simplified(raw)
        toks = tokenize(simp).split()
        if not toks:
            return self.send_json({'query': raw, 'simplified': simp, 'total': 0, 'hits': []})
        match = ' AND '.join('"%s"' % t for t in toks)
        per, page, off = pages(qs)
        where, args = ['chunks_fts MATCH ?'], [match]
        for k, col in (('category', 'w.category'), ('work', 'w.id')):
            v = qs.get(k, [''])[0].strip()
            if v:
                where.append(f'{col} = ?'); args.append(v)
        w = ' AND '.join(where)
        c = db()
        total = c.execute('SELECT COUNT(*) FROM chunks JOIN works w ON w.id = chunks.work_id '
                          'JOIN chunks_fts ON chunks_fts.cid = chunks.id WHERE ' + w, args).fetchone()[0]
        rows = c.execute('SELECT chunks.id, chunks.work_id, chunks.section, chunks.text, '
                         'w.title, w.dynasty, w.category, w.id AS wid '
                         'FROM chunks JOIN works w ON w.id = chunks.work_id '
                         'JOIN chunks_fts ON chunks_fts.cid = chunks.id WHERE ' + w +
                         ' ORDER BY chunks.id LIMIT ? OFFSET ?', args + [per, off]).fetchall()
        hits = [{'chunk_id': r['id'], 'work_id': r['wid'], 'title': r['title'],
                 'dynasty': r['dynasty'], 'category': r['category'],
                 'section': r['section'], 'snippet': clip(r['text'], simp)} for r in rows]
        return self.send_json({'query': raw, 'simplified': simp, 'tokens': len(toks),
                               'total': total, 'page': page, 'per_page': per, 'hits': hits})

    def text(self, wid, qs):
        variant = qs.get('variant', [''])[0].strip()
        c = db()
        row = c.execute('SELECT * FROM works WHERE id = ?', (wid,)).fetchone()
        if not row:
            return self.send_json({'error': 'no such work', 'id': wid}, 404)
        rel = row['file_kanripo'] if (variant in ('', 'kanripo') and row['file_kanripo']) \
            else row['file_local']
        if not rel:
            return self.send_json({'error': 'no such variant', 'id': wid, 'variant': variant}, 404)
        path = os.path.normpath(os.path.join(BOOKS, rel))
        if not path.startswith(BOOKS) or not os.path.exists(path):
            return self.send_json({'error': 'file missing', 'file': rel}, 500)
        body = open(path, encoding='utf-8').read()
        return self.send_json({'id': wid, 'title': row['title'], 'variant':
                              'kanripo' if rel == row['file_kanripo'] else 'local',
                              'file': rel, 'chars': len(body), 'text': body})

    def nongshi(self, qs):
        per, page, off = pages(qs, default=50)
        where, args = ['1=1'], []
        if qs.get('month', [''])[0].strip().isdigit():
            where.append('month = ?'); args.append(int(qs['month'][0]))
        if qs.get('work', [''])[0].strip():
            where.append('work_id = ?'); args.append(qs['work'][0])
        q = qs.get('q', [''])[0].strip()
        if q:
            where.append('text LIKE ?'); args.append('%' + to_simplified(q) + '%')
        w = ' AND '.join(where)
        c = db()
        total = c.execute('SELECT COUNT(*) FROM nongshi WHERE ' + w, args).fetchone()[0]
        rows = c.execute('SELECT n.*, wo.title FROM nongshi n '
                         'LEFT JOIN works wo ON wo.id = n.work_id WHERE ' + w +
                         ' ORDER BY n.id LIMIT ? OFFSET ?', args + [per, off]).fetchall()
        return self.send_json({'total': total, 'page': page, 'per_page': per,
                               'items': [dict(r) for r in rows]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=52346)
    args = ap.parse_args()
    if not os.path.exists(DB):
        sys.exit('缺少 corpus.db，先跑 python3 corpus/build.py')
    http.server.ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
