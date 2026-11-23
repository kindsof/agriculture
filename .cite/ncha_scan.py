#!/usr/bin/env python3
"""国家文物局国保名录是 art_2587_NN 连续编号的单页，栏目列表页 JS 渲染拉不到列表，
那就直接扫编号——比跟搜索引擎赌运气确定得多。"""
import json, re, html, sys, time, urllib.request
from pathlib import Path
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}
WANT = ['草鞋山', '周原', '兴隆沟', '通天洞', '后土', '徐光启']
out_path = Path('.cite/ncha.json')
found = json.loads(out_path.read_text()) if out_path.exists() else {}
lo, hi = int(sys.argv[1]), int(sys.argv[2])
hit = miss = 0
for n in range(lo, hi + 1):
    if any(n in v for v in [int(k.split('#')[1]) for k in found if '#' in k]):
        continue
    # 同一栏目的文章分散在 3/17、3/18、3/19 三个日期路径下，写死一个就大面积 404
    body, url = '', ''
    for day in (18, 17, 19, 20):
        cand = f'http://www.ncha.gov.cn/art/2022/3/{day}/art_2587_{n}.html'
        try:
            with urllib.request.urlopen(urllib.request.Request(cand, headers=UA), timeout=12) as r:
                body = r.read(200_000).decode('utf-8', 'replace')
            url = cand
            break
        except Exception:
            miss += 1
    if not body:
        continue
    m = re.search(r'<title>(.*?)</title>', body, re.S)
    title = html.unescape(re.sub(r'\s+', ' ', m.group(1))).strip() if m else ''
    hit += 1
    for w in WANT:
        if w in title and w not in found:
            found[w] = {'id': f'ncha#{n}', 'title': title, 'url': url}
            print(f'  命中 {w}: {title}', flush=True)
    if hit % 25 == 0:
        out_path.write_text(json.dumps(found, ensure_ascii=False, indent=1))
        print(f'  扫到 art_2587_{n}（已取 {hit} 页 / 失败 {miss}）', flush=True)
    time.sleep(0.4)
out_path.write_text(json.dumps(found, ensure_ascii=False, indent=1))
print(f'完成：取到 {hit} 页，命中 {len(found)}/{len(WANT)}，未命中 {[w for w in WANT if w not in found]}')
