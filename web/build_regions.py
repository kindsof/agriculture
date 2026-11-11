#!/usr/bin/env python3
"""拼装 9 大农区面图层：区域按省份分组 + 省级边界 → regions.geojson

旧 _legacy/map_data.json 的 regions 只有省份列表、没有多边形，而本仓库
web/data/provinces.geojson 已有省级边界，故区域多边形直接由各成员省多边形
合并得到，不引入第三份边界数据。

书名互链不用猜：书名先经 t2s.json 归一到简体，再与 books/catalog.json 的
题名比对。命中唯一才给 work_id；命中多个（如「农书」既可能是陈旉农书也可能
是王祯农书）一律列成 ambiguous 让前端并列显示；一个都不中则标 unmatched。

    python3 web/build_regions.py [--check]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = HERE
DATA = os.path.join(WEB, 'data')
BOOKS = os.path.join(os.path.dirname(WEB), 'books')
CORPUS = os.path.join(os.path.dirname(WEB), 'corpus')
SRC = os.path.join(DATA, 'regions_source.json')
PROV = os.path.join(DATA, 'provinces.geojson')
CAT = os.path.join(BOOKS, 'catalog.json')
T2S = os.path.join(CORPUS, 't2s.json')
OUT = os.path.join(DATA, 'regions.geojson')


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def simp(s, t2s):
    return ''.join(t2s.get(c, c) for c in s)


def index_titles(t2s):
    """简体题名 → [work_id]，保留歧义而不是替读者挑一本"""
    cat = load(CAT)
    works = cat['works'] if isinstance(cat, dict) else cat
    idx = {}
    for w in works:
        key = simp(w['title'], t2s).replace(' ', '')
        idx.setdefault(key, []).append(w['id'])
    return idx


def build():
    src = load(SRC)
    prov = load(PROV)
    t2s = load(T2S)
    titles = index_titles(t2s)
    geom = {}
    for f in prov['features']:
        name = f['properties'].get('name')
        if name:
            geom[name] = f
    feats, report = [], []
    for r in src['regions']:
        polys, adcodes, missing = [], [], []
        for name in r['provinces']:
            f = geom.get(name)
            if not f:
                missing.append(name)
                continue
            g = f['geometry']
            if g['type'] == 'Polygon':
                polys.append(g['coordinates'])
            elif g['type'] == 'MultiPolygon':
                polys.extend(g['coordinates'])
            adcodes.append(f['properties']['adcode'])
        books = []
        for t in r['books']:
            ids = titles.get(simp(t, t2s).replace(' ', ''), [])
            books.append({'title': t,
                          'work_ids': ids,
                          'status': 'linked' if len(ids) == 1
                                    else 'ambiguous' if ids else 'unmatched'})
        feats.append({
            'type': 'Feature',
            'properties': {
                'id': r['id'], 'name': r['name'], 'color': r['color'],
                'summary': r['summary'], 'crops': r['crops'],
                'folkways': r['folkways'], 'heritage_note': r['heritage_note'],
                'provinces': r['provinces'], 'province_adcodes': adcodes,
                'books': books,
            },
            'geometry': {'type': 'MultiPolygon', 'coordinates': polys},
        })
        report.append((r['name'], len(polys), len(missing), missing,
                       sum(1 for b in books if b['status'] == 'linked'),
                       sum(1 for b in books if b['status'] == 'ambiguous'),
                       sum(1 for b in books if b['status'] == 'unmatched')))
    out = {'type': 'FeatureCollection', 'name': '中国农耕文化九大农区',
           'note': src['_source'], 'features': feats}
    return out, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只校验已生成的产物')
    args = ap.parse_args()
    out, report = build()
    ok = True
    for name, npoly, nmiss, missing, nl, na, nu in report:
        flag = '' if npoly and not nmiss else '  !! 有省未取到边界: ' + ','.join(missing)
        print(f'  {name:<14} 省多边形={npoly:<3} 书目 命中{nl} 歧义{na} 未命中{nu}{flag}')
        ok = ok and npoly > 0 and nmiss == 0
    total_books = sum(len(f['properties']['books']) for f in out['features'])
    un = [b['title'] for f in out['features'] for b in f['properties']['books']
          if b['status'] == 'unmatched']
    am = [b['title'] for f in out['features'] for b in f['properties']['books']
          if b['status'] == 'ambiguous']
    print(f'  合计 {len(out["features"])} 区、{total_books} 条书目；'
          f'未命中 {len(un)}：{un}；歧义 {len(am)}：{am}')
    if len(out['features']) != 9:
        print('!! 区域数不是 9'); ok = False
    if args.check:
        cur = load(OUT)
        if json.dumps(cur, ensure_ascii=False, sort_keys=True) != \
                json.dumps(out, ensure_ascii=False, sort_keys=True):
            print('!! regions.geojson 与源数据不一致，请重跑 build_regions.py')
            return 1
        print('  产物与源一致' if ok else '  !! 源数据本身有问题')
        return 0 if ok else 1
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
        f.write('\n')
    print(f'  已写 {os.path.relpath(OUT, os.getcwd())} '
          f'({os.path.getsize(OUT) // 1024} KB)')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
