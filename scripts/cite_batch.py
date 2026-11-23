#!/usr/bin/env python3
"""Batch-run cite.py-style discovery for many entries, appending results to JSON.

Reads a TSV of ``id<TAB>query`` from stdin, asks Sogou then Bing for each,
keeps every candidate that verifies (HTTP 200 + keyword present), and writes
``{id: [{title, url, host}, ...]}`` to --out.  Resumable: ids already present
in --out are skipped.

Sleeps between queries because both engines throttle this host hard.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cite import (  # noqa: E402
    ENGINE_NOISE,
    SCOPES,
    ihchina_project,
    rank,
    search,
    unusable,
    verify,
)


def candidates(query: str, limit: int) -> list[str]:
    """Collect candidates for an entry name, ``site:``-scoped first.

    Engines on this host mangle multi-token CJK queries (Bing collapses
    "玉蟾岩遗址 道县 栽培稻" to the single character 玉), so only the entry name
    is searched and verify() rejects pages about something else.
    """
    name = query.split()[0]
    links: list[str] = []
    for scope in SCOPES:
        for raw in search(name + scope, limit):
            host = urllib.parse.urlparse(raw).netloc.lower()
            if not host or any(n in host for n in ENGINE_NOISE):
                continue
            if unusable(raw) or raw in links:
                continue
            links.append(raw)
        if len(links) >= limit:
            break
    links.sort(key=rank)
    return links[:limit]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--sleep", type=float, default=8.0)
    parser.add_argument("--tries", type=int, default=3)
    args = parser.parse_args()

    out_path = Path(args.out)
    results: dict[str, list[dict[str, str]]] = (
        json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    )

    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entry_id, _, query = line.partition("\t")
        if not query:
            continue
        if entry_id in results and results[entry_id]:
            continue
        found: list[dict[str, str]] = []
        name = query.split()[0]
        # 民俗类首选非遗网项目页：渠道稳定，且与现有数据的引用习惯一致。
        if entry_id.startswith("custom-"):
            url, title = ihchina_project(name)
            if url:
                found.append({
                    "title": title or name,
                    "url": url,
                    "host": urllib.parse.urlparse(url).netloc.lower(),
                })
        for attempt in range(args.tries if not found else 0):
            for url in candidates(query, args.limit):
                probe = query.split()[0]
                ok, reason, title = verify(url, probe)
                if ok:
                    found.append({
                        "title": title or query,
                        "url": url,
                        "host": urllib.parse.urlparse(url).netloc.lower(),
                    })
                if len(found) >= 2:
                    break
            if found:
                break
            time.sleep(args.sleep * (attempt + 1))
        results[entry_id] = found
        print(f"{entry_id}\t{len(found)}\t{query}", flush=True)
        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        time.sleep(args.sleep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
