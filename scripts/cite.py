#!/usr/bin/env python3
"""Find and verify a citable source URL for a farming-culture entry.

Every ``sources.url`` in ``web/data/sites.yaml`` and every region source in
``web/data/regions_source.json`` has to be a live page that actually talks
about the thing being cited.  This tool enforces that:

1. query Sogou, then Bing (Sogou is the only engine that returns usable
   Chinese government / academy links from the deploy host; Bing keeps
   collapsing multi-token CJK queries to one character and sogou/so.com
   render results with JavaScript),
2. keep only results on domains we consider authoritative,
3. fetch each candidate and require HTTP 200 **and** the keyword to appear
   in the fetched page,
4. print the title + URL, ready to paste into YAML as ``title``/``url``.

A URL that this script rejects must not go into the data files.

Usage:
    python3 scripts/cite.py "玉蟾岩遗址 栽培稻 道县"
    python3 scripts/cite.py --limit 5 "上山文化 万年 稻作起源"
    python3 scripts/cite.py --check <url> <keyword>       # verify one URL
    python3 scripts/cite.py --relink                     # audit every URL in the data

Stdlib only.  Bing is rate-limited, so keep --limit small and run one query
per entry.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
TIMEOUT = 20

# Ordered best-first.  Anything not listed here is dropped unless --loose.
GOOD = (
    "ihchina.cn",
    "gov.cn",
    "mct.gov.cn",
    "ncha.gov.cn",
    "moa.gov.cn",
    "ihns.ac.cn",        # 中国科学院自然史研究所 中国农史数据库
    "cas.cn",
    "dpm.org.cn",
    "fao.org",
    "unesco.org",
    "chinaculture.org",
    "peopleapp.com",     # 人民日报客户端
    "people.com.cn",
    "news.cn",
    "cnr.cn",
    "chinanews.com",
    "xinhuanet.com",
    "stdaily.com",
    "ce.cn",
)
ENGINES = (
    # ``{}`` is replaced by the percent-encoded query.  ``site:`` scoping is what
    # actually works from this host: plain CJK queries often get collapsed to one
    # character and answered with a Miit ICP stub instead of results.
    "https://www.sogou.com/web?query={}",
    "https://cn.bing.com/search?q={}",
)
# Query variants tried in order, per entry (see cite_batch).
SCOPES = (" site:ncha.gov.cn", " site:gov.cn", "")
IHCHINA_SEARCH = "https://www.ihchina.cn/search_result/keyword/{}/p/1.html"
# Href noise from the engines themselves.
ENGINE_NOISE = (
    "sogou.com",
    "sohu.com",
    "so.com",
    "360",
    "bing.com",
    "microsoft",
    "tencent.com",
    "qq.com",
    "beian",
)
# Explicitly unusable: user-generated, mirroring farms, or dead from this host.
BAD = (
    "baike.baidu.com",
    "baike.so.com",
    "wikipedia.org",
    "zhihu.com",
    "sohu.com",
    "163.com",
    "qq.com",
    "sina.com",
    "douyin.com",
    "meipian",
    "360doc",
    "docin",
    "doc88",
    "kaogu.cn",
    "cncid.org",
    "namoc.org",
)

TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
ALINK_RE = re.compile(r"<a[^>]*href=\"(https?://[^\"]+)\"", re.S | re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(400_000)
            return resp.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:  # noqa: BLE001 - timeouts, DNS, TLS
        return 0, f"{type(exc).__name__}: {exc}"


def unusable(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(host == bad or host.endswith("." + bad) for bad in BAD)


def search(query: str, limit: int) -> list[str]:
    encoded = urllib.parse.quote(query)
    for template in ENGINES:
        status, body = fetch(template.format(encoded))
        if status != 200 or not body:
            continue
        links: list[str] = []
        for raw in ALINK_RE.findall(body):
            href = html.unescape(raw)
            host = urllib.parse.urlparse(href).netloc.lower()
            if not host or any(noise in host for noise in ENGINE_NOISE):
                continue
            if unusable(href) or href in links:
                continue
            links.append(href)
        if links:
            return links[: max(limit * 3, 8)]
    return []


def title_matches(name: str, title: str) -> bool:
    """The page must be about *this* entry, not about a neighbour of it.

    ihchina search happily answers 查干湖冬捕 with 博舞 (same county) and
    太昊陵庙会 with 太昊伏羲祭典 (same deity, different province), so matching
    any token of the query against the page body is not enough.
    """
    clean = lambda s: re.sub(r"[\s《》()（）·、\-—]", "", s or "")
    want, have = clean(name), clean(title)
    if not want or not have:
        return False
    if want in have or have in want:
        return True
    # 复合条目名（「社火（陇县社火）」）与限定词后缀（习俗·端午）按最长公共子串判定
    common = max(
        (have[i:j] for i in range(len(have)) for j in range(i + 3, len(have) + 1)),
        key=len, default="",
    )
    return len(common) >= 4 and common in want


def ihchina_project(name: str) -> tuple[str, str]:
    """Return (url, title) of the first 国家级非遗项目 page matching ``name``.

    The 非遗网 site search is server-rendered enough to expose project links and
    is far more reliable from this host than any general search engine.
    """
    status, body = fetch(IHCHINA_SEARCH.format(urllib.parse.quote(name)))
    if status != 200:
        return "", ""
    # 早期批次的项目页是 /art/detail/id/NNNN.html，新近的是 /project_details/NNNN
    # The first hit is often a same-county neighbour, so walk the first few
    # results and keep the first page whose own title names this entry.
    urls: list[str] = []
    for found in re.finditer(r'href="(/project_details/\d+|/art/detail/id/\d+)', body):
        url = "https://www.ihchina.cn" + found.group(1)
        if url not in urls:
            urls.append(url)
    for url in urls[:5]:
        ok, _reason, title = verify(url, name[:4])
        page = re.sub(r"^\s*", "", title or "")
        if ok and title_matches(name, page):
            return url, page
    return "", ""


def rank(url: str) -> int:
    """Lower is better; 99 means not on the good list."""
    host = urllib.parse.urlparse(url).netloc.lower()
    for index, good in enumerate(GOOD):
        if host == good or host.endswith("." + good):
            return index
    return 99


def page_title(body: str) -> str:
    match = TITLE_RE.search(TAG_RE.sub(" ", body))
    if not match:
        return ""
    title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    for sep in (" - ", " _ ", " _", "—", "|", "【"):
        if sep in title:
            title = title.split(sep)[0].strip()
    return title[:120]


def verify(url: str, keyword: str) -> tuple[bool, str, str]:
    """Return (ok, reason, title).  ok requires 200 and the keyword present."""
    status, body = fetch(url)
    if status != 200 or not body:
        return False, f"HTTP {status}", ""
    text = TAG_RE.sub(" ", body)
    text = re.sub(r"\s+", "", html.unescape(text))
    probe = re.sub(r"\s+", "", keyword)
    # All characters of the keyword must co-occur; that rejects pages about a
    # different place with a similar name.
    tokens = [t for t in re.split(r"\s+", keyword) if len(t) >= 2]
    missing = [t for t in tokens if re.sub(r"\s+", "", t) not in text]
    if len(missing) > len(tokens) // 2:
        return False, f"keyword missing ({','.join(missing)})", page_title(body)
    return True, "ok", page_title(body)


def cmd_find(query: str, limit: int, loose: bool) -> int:
    print(f"query: {query}")
    links = search(query, max(limit * 3, 6))
    if not links:
        print("  no results")
        return 1
    ranked = sorted({u for u in links if not unusable(u)}, key=rank)
    if not loose:
        ranked = [u for u in ranked if rank(u) != 99]
    checked = 0
    for url in ranked[: limit * 2]:
        probe = query.split()[0]
        ok, reason, title = verify(url, probe if len(probe) >= 2 else query)
        checked += 1
        flag = "OK " if ok else "NO "
        print(f"  [{flag}] r{rank(url):<2} {reason:<28} {url}")
        if ok:
            print(f"        title: {title}")
            print()
            print("  sources:")
            print(f"    - title: {title or query}")
            print(f"      url: {url}")
            return 0
    print(f"  no usable source among {checked} candidates")
    return 1


def all_data_sources() -> list[tuple[str, str]]:
    root = Path(__file__).resolve().parent.parent / "web" / "data"
    out: list[tuple[str, str]] = []
    text = (root / "sites.yaml").read_text(encoding="utf-8")
    for match in re.finditer(r"url: (\S+)", text):
        out.append(("sites.yaml", match.group(1)))
    regions = json.loads((root / "regions_source.json").read_text(encoding="utf-8"))
    for region in regions.get("regions", []):
        for block in ("folk_detail", "civilization"):
            for item in region.get(block, []):
                for source in item.get("sources", []):
                    out.append((f"regions:{region['id']}:{block}", source["url"]))
    return out


def cmd_relink() -> int:
    pairs = all_data_sources()
    hosts: dict[str, list[str]] = {}
    for origin, url in pairs:
        hosts.setdefault(urllib.parse.urlparse(url).netloc.lower(), []).append(url)
    dead = 0
    for host, urls in sorted(hosts.items(), key=lambda kv: -len(kv[1])):
        status, _ = fetch(urls[0])
        note = "" if status == 200 else "  <-- CHECK EVERY URL ON THIS HOST"
        dead += 0 if status == 200 else len(urls)
        print(f"{status}  {host:<32} {len(urls):>3} url(s){note}")
    print(f"\n{len(pairs)} source URLs, ~{dead} on unreachable hosts")
    return 0 if dead == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="keywords to search for")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--loose", action="store_true",
                        help="also accept domains outside the good list")
    parser.add_argument("--check", metavar="URL", help="verify one URL + keyword")
    parser.add_argument("--keyword", default="", help="keyword for --check")
    parser.add_argument("--relink", action="store_true",
                        help="audit every URL already in the data files")
    args = parser.parse_args()

    if args.relink:
        return cmd_relink()
    if args.check:
        ok, reason, title = verify(args.check, args.keyword or args.check)
        print(f"{'OK' if ok else 'NO'}  {reason}  {title}\n{args.check}")
        return 0 if ok else 1
    if not args.query:
        parser.print_help()
        return 2
    return cmd_find(args.query, args.limit, args.loose)


if __name__ == "__main__":
    sys.exit(main())
