#!/usr/bin/env python3
"""采集农业 AI 模型与技能的实时数据，刷新 ai/stats.json 与 ai/INDEX.md 快照。

用法::

    python3 scripts/fetch_ai_catalog.py            # 联网采集，重写 stats.json 与 INDEX 快照节
    python3 scripts/fetch_ai_catalog.py --check    # 离线校验：INDEX 快照与 stats.json 是否一致（CI 用）
    python3 scripts/fetch_ai_catalog.py --offline  # 不联网，仅用现有 stats.json 重渲染 INDEX

数据源：
  * Hugging Face API（huggingface.co/api，不可达时自动回退 hf-mirror.com/api）
  * GitHub REST API（可用 GITHUB_TOKEN / GH_TOKEN 环境变量提高限额）

目录本身（ai/catalog.yaml）为人工维护的目录源；本脚本不改动它。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "ai" / "catalog.yaml"
STATS_PATH = ROOT / "ai" / "stats.json"
DOC_PATH = ROOT / "ai" / "INDEX.md"

HF_PRIMARY = "https://huggingface.co/api"
HF_MIRROR = "https://hf-mirror.com/api"
GITHUB_API = "https://api.github.com"

MARK_BEGIN = "<!-- BEGIN GENERATED SNAPSHOT -->"
MARK_END = "<!-- END GENERATED SNAPSHOT -->"

USER_AGENT = "agriculture-repo-ai-catalog (+https://github.com/kindsof/agriculture)"

FETCH_TIMEOUT = 12  # 秒（单次请求；huggingface.co 不可达时每个条目最多消耗 2×此值）


class FetchError(RuntimeError):
    pass


# ── 工具函数 ──────────────────────────────────────────────────


def load_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def http_get_json(url: str, *, headers: dict | None = None, retries: int = 2) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    last: Exception | None = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
    raise last if last else RuntimeError(f"request failed: {url}")


def parse_hf_url(url: str) -> tuple[str, str] | None:
    """huggingface.co URL → (api_kind, repo_id)；org 主页返回 (org, name)。

    模型页是 ``<site>/<owner>/<name>``（无 /models/ 前缀），数据集页带
    ``/datasets/`` 前缀，空格间同理。
    """
    parsed = urlparse(url)
    if parsed.netloc not in {"huggingface.co", "www.huggingface.co"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 3 and parts[0] in {"models", "datasets", "spaces"}:
        return parts[0], "/".join(parts[1:])
    if len(parts) == 2:
        return "models", "/".join(parts)
    if len(parts) == 1:
        return "org", parts[0]
    return None


def parse_github_url(url: str) -> str | None:
    """github.com/<owner>/<repo> → 'owner/repo'。"""
    parsed = urlparse(url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None


def parse_modelscope_url(url: str) -> str | None:
    """modelscope.cn/models/<owner>/<name> → 'owner/name'。"""
    parsed = urlparse(url)
    if parsed.netloc not in {"modelscope.cn", "www.modelscope.cn"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 3 and parts[0] == "models":
        return "/".join(parts[1:3])
    return None


def candidate_urls(entry: dict) -> list[str]:
    urls = [entry.get("url"), entry.get("alt_url")]
    return [u for u in urls if isinstance(u, str) and u.startswith("https://")]


# ── 采集 ──────────────────────────────────────────────────────


def _hf_bases():
    """基址顺序：默认主站优先；若本轮主站已失败过，把镜像提到前面。"""
    if _hf_bases.primary_failed:
        return (HF_MIRROR, HF_PRIMARY)
    return (HF_PRIMARY, HF_MIRROR)


_hf_bases.primary_failed = False


def fetch_hf(entry: dict, record: dict) -> None:
    for url in candidate_urls(entry):
        parsed = parse_hf_url(url)
        if parsed is None:
            continue
        api_kind, ident = parsed
        for base in _hf_bases():
            try:
                if api_kind == "org":
                    payload = http_get_json(f"{base}/models?author={ident}&limit=100")
                    assert isinstance(payload, list)
                    record["models"] = len(payload)
                    record["downloads"] = sum(int(m.get("downloads") or 0) for m in payload)
                    record["likes"] = sum(int(m.get("likes") or 0) for m in payload)
                    record["hf_author"] = ident
                else:
                    payload = http_get_json(f"{base}/{api_kind}/{ident}")
                    assert isinstance(payload, dict)
                    record["downloads"] = int(payload.get("downloads") or 0)
                    record["likes"] = int(payload.get("likes") or 0)
                record["hf_base"] = base
                record["hf_id"] = ident
                record["hf_kind"] = api_kind
                return
            except (urllib.error.URLError, TimeoutError, OSError, AssertionError, ValueError):
                if base == HF_PRIMARY:
                    _hf_bases.primary_failed = True
                continue
    record["error"] = "huggingface api unreachable"


def fetch_modelscope(entry: dict, record: dict) -> None:
    for url in candidate_urls(entry):
        ident = parse_modelscope_url(url)
        if ident is None:
            continue
        try:
            payload = http_get_json(f"https://modelscope.cn/api/v1/models/{ident}")
            data = payload.get("Data") or {}
            downloads = data.get("Downloads")
            if isinstance(downloads, (int, float)):
                record["modelscope_downloads"] = int(downloads)
            record["modelscope_id"] = ident
            return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue


def fetch_github(entry: dict, record: dict, token: str | None) -> None:
    for url in candidate_urls(entry):
        repo = parse_github_url(url)
        if repo is None:
            continue
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            payload = http_get_json(f"{GITHUB_API}/repos/{repo}", headers=headers)
            assert isinstance(payload, dict)
            record["stars"] = int(payload.get("stargazers_count") or 0)
            record["pushed_at"] = (payload.get("pushed_at") or "")[:10] or None
            record["github_repo"] = repo
            return
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, AssertionError, ValueError) as exc:
            record["error"] = f"github api: {exc}"
            return
    record["error"] = record.get("error") or "no github url"


def fetch_all(catalog: dict) -> dict:
    from time import sleep

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    data_keys = ("downloads", "likes", "stars", "models", "modelscope_downloads")
    entries: dict[str, dict] = {}
    for entry in catalog["entries"]:
        record: dict = {}
        urls = candidate_urls(entry)
        if any(parse_hf_url(u) for u in urls):
            fetch_hf(entry, record)
        if any(parse_modelscope_url(u) for u in urls):
            fetch_modelscope(entry, record)
        if any(parse_github_url(u) for u in urls):
            fetch_github(entry, record, token)
        if any(k in record for k in data_keys):
            # 某一数据源失败但其他源已取到数据：记为 warning 而非整体失败
            if "error" in record:
                record["warning"] = record.pop("error")
        elif not record:
            record["error"] = "no fetchable https url"
        entries[entry["id"]] = record
        status = "ok"
        if "error" in record:
            status = f"error: {record['error']}"
        elif "warning" in record:
            status = f"partial: {record['warning']}"
        print(f"  {entry['id']:<45} {status}", flush=True)
        sleep(0.5)
    return entries


# ── 渲染 ──────────────────────────────────────────────────────


def _cell(value) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


def _fmt_int(value) -> str:
    return "—" if value is None else f"{value:,}"


def render_snapshot(catalog: dict, stats: dict) -> str:
    """由 catalog.yaml + stats.json 渲染 INDEX.md 的「实时数据快照」一节。"""
    generated = stats.get("generated_at") or "（尚未采集）"
    lines = [
        f"采集时间：**{generated}**（Asia/Shanghai）；下表数值由脚本从 Hugging Face / "
        "GitHub API 自动抓取，未经人工筛选，口径以各平台为准。",
        "",
    ]
    entries = sorted(catalog["entries"], key=lambda e: e["id"])
    records = stats.get("entries", {})

    sections = [
        ("hf-model", "Hugging Face 模型", ("models", "downloads", "likes", "modelscope_downloads")),
        ("dataset", "Hugging Face 数据集", ("downloads", "likes")),
        ("gh-repo", "GitHub 项目", ("stars", "pushed_at")),
        ("paper-list", "论文 / 资源列表", ("stars", "pushed_at")),
        ("skill", "Agent Skill", ("stars", "pushed_at")),
        ("mcp", "MCP 服务器", ("stars", "pushed_at")),
    ]
    for kind, title, cols in sections:
        picked = [e for e in entries if e["kind"] == kind]
        if not picked:
            continue
        lines.append(f"### {title}")
        lines.append("")
        head = ["条目"] + [
            {"models": "模型数", "downloads": "下载量", "likes": "点赞", "stars": "Stars",
             "pushed_at": "最近推送", "modelscope_downloads": "ModelScope 下载"}[c]
            for c in cols
        ] + ["采集状态"]
        lines.append("| " + " | ".join(head) + " |")
        lines.append("|" + "---|" * len(head))
        for e in picked:
            rec = records.get(e["id"], {})
            cells = [f"[{_cell(e['name'])}]({_cell(e['url'])})"]
            for col in cols:
                value = rec.get(col)
                cells.append(_fmt_int(value) if col != "pushed_at" else _cell(value))
            has_native = any(c in rec for c in cols)
            if kind in {"hf-model", "dataset"} and not has_native and "github_repo" in rec:
                status = f"GitHub ★{_fmt_int(rec.get('stars'))}（指标见下方 GitHub 节）"
            elif "error" in rec:
                status = "⚠️ " + _cell(rec.get("error") or "未采集")
            elif "warning" in rec:
                status = "✅（部分源缺失）"
            else:
                status = "✅"
            cells.append(status)
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_into_doc(catalog: dict, stats: dict, doc_text: str) -> str:
    if MARK_BEGIN not in doc_text or MARK_END not in doc_text:
        raise FetchError(f"{DOC_PATH.name} 缺少快照标记 {MARK_BEGIN!r} / {MARK_END!r}")
    start = doc_text.index(MARK_BEGIN) + len(MARK_BEGIN)
    end = doc_text.index(MARK_END)
    body = "\n" + render_snapshot(catalog, stats) + "\n\n"
    return doc_text[:start] + body + doc_text[end:]


def load_stats() -> dict:
    if not STATS_PATH.exists():
        return {"generated_at": None, "entries": {}}
    with STATS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def same_or_write(path: Path, payload: str, *, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if check:
        return current == payload
    path.write_text(payload, encoding="utf-8")
    return True


# ── 入口 ──────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="离线校验 INDEX.md 快照与 stats.json 一致（不写文件，CI 用）")
    mode.add_argument("--offline", action="store_true",
                      help="不联网，仅用现有 stats.json 重渲染 INDEX.md")
    args = parser.parse_args(argv)

    catalog = load_catalog()

    if args.check or args.offline:
        stats = load_stats()
    else:
        from datetime import datetime, timedelta, timezone

        print(f"采集 {len(catalog['entries'])} 个条目 …")
        entries = fetch_all(catalog)
        now_cn = datetime.now(timezone(timedelta(hours=8)))
        stats = {"generated_at": now_cn.strftime("%Y-%m-%d %H:%M"), "entries": entries}
        payload = json.dumps(stats, ensure_ascii=False, indent=2) + "\n"
        same_or_write(STATS_PATH, payload, check=False)

    rendered = render_into_doc(catalog, stats, DOC_PATH.read_text(encoding="utf-8"))
    if args.check:
        current = DOC_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print("error: ai/INDEX.md 的快照节与 ai/stats.json 不一致；"
                  "请运行 python3 scripts/fetch_ai_catalog.py", file=sys.stderr)
            return 1
        print(f"checked: {len(catalog['entries'])} entries, snapshot consistent")
        return 0
    same_or_write(DOC_PATH, rendered, check=False)
    print(f"wrote snapshot for {len(catalog['entries'])} entries "
          f"({STATS_PATH.relative_to(ROOT)}, {DOC_PATH.relative_to(ROOT)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
