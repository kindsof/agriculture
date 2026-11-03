#!/usr/bin/env python3
"""下载并整理农业与水利古籍。

数据来自 Kanripo（漢籍リポジトリ，https://github.com/kanripo）。
脚本按 catalog.yaml 逐部克隆文本仓库，清理四库全书转录中的
页面标记与行末符号，合并为按卷编排的 Markdown 文本，并生成
books/INDEX.md 与 books/catalog.json。

用法：
    python3 scripts/fetch_books.py
    python3 scripts/fetch_books.py --only KR3d0001 KR2k0058
    python3 scripts/fetch_books.py --cache /tmp/kanripo_cache --jobs 8

依赖：Python 3.9+、PyYAML、git。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("缺少 PyYAML，请先运行：python3 -m pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
KANRIPO_URL = "https://github.com/kanripo"

CATEGORY_DIRS = {"农业": "agriculture", "水利": "water"}

DIGITS = "零一二三四五六七八九"


def cn_number(n: int) -> str:
    """把 0-999 的整数转成中文数字，用于卷次标题。"""
    if n < 10:
        return DIGITS[n]
    if n < 20:
        return "十" + (DIGITS[n % 10] if n % 10 else "")
    if n < 100:
        return DIGITS[n // 10] + "十" + (DIGITS[n % 10] if n % 10 else "")
    if n < 1000:
        text = DIGITS[n // 100] + "百"
        rest = n % 100
        if rest == 0:
            return text
        if rest < 10:
            return text + "零" + DIGITS[rest]
        return text + cn_number(rest)
    return str(n)


def juan_label(value: str) -> str:
    """把 Kanripo 的 JUAN 属性转成章节标题。"""
    value = value.strip()
    if not value:
        return "卷首"
    if value in {"提要", "目録", "目录"}:
        return "目錄" if value == "目録" else value
    if re.fullmatch(r"\d+", value):
        number = int(value)
        return "卷首" if number == 0 else f"卷{cn_number(number)}"
    return value


def load_catalog(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    books = data.get("books") if isinstance(data, dict) else None
    if not books:
        raise ValueError(f"{path} 中没有找到 books 列表")
    for book in books:
        for key in ("id", "title", "author", "dynasty", "category"):
            if not book.get(key):
                raise ValueError(f"目录项缺少字段 {key}: {book}")
        if book["category"] not in CATEGORY_DIRS:
            raise ValueError(f"未知类别 {book['category']}: {book['id']}")
    return books


def clone_repo(repo: str, cache: Path) -> Path:
    """浅克隆 Kanripo 仓库；已有完整缓存则直接复用。"""
    dest = cache / repo
    if dest.exists() and any(dest.glob(f"{repo}_*.txt")):
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{KANRIPO_URL}/{repo}.git"
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if result.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise RuntimeError(f"克隆 {repo} 失败：{result.stderr.strip()}")
    return dest


def clean_text(raw: str) -> str:
    """清理 Kanripo 转录：去页面标记、行末 ¶、元数据与替换字符。"""
    lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("#+") or line.startswith("# -*-"):
            continue
        line = re.sub(r"<pb:[^>]*>", "", line)
        line = line.replace("¶", "").replace("\ufffd", "□")
        line = line.rstrip()
        if not line:
            # 原书分页处在转录中表现为空行，不当作段落分隔。
            continue
        lines.append(line)
    return "\n".join(lines).strip("\n")


def parse_meta(raw: str) -> tuple[str, str]:
    title = re.search(r"^#\+TITLE:\s*(.+)$", raw, re.MULTILINE)
    juan = re.search(r"^#\+PROPERTY:\s*JUAN\s+(.+)$", raw, re.MULTILINE)
    return (
        title.group(1).strip() if title else "",
        juan.group(1).strip() if juan else "",
    )


def build_markdown(book: dict, repo_dir: Path) -> tuple[str, int, int]:
    """把一部书的各卷文本合并为 Markdown，返回 (文本, 章节数, 字数)。"""
    files = sorted(repo_dir.glob(f"{book['id']}_*.txt"))
    if not files:
        raise RuntimeError(f"{book['id']} 中没有找到文本文件")

    sections: list[tuple[str, str]] = []
    for path in files:
        raw = path.read_text(encoding="utf-8", errors="replace")
        _, juan = parse_meta(raw)
        cleaned = clean_text(raw)
        if not cleaned:
            continue
        sections.append((juan_label(juan), cleaned))

    if not sections:
        raise RuntimeError(f"{book['id']} 的文本为空")

    header = [
        "---",
        f'title: "{book["title"]}"',
        f'author: "{book["author"]}"',
        f'dynasty: "{book["dynasty"]}"',
        f'category: "{book["category"]}"',
        f'edition: "{book.get("edition", "")}"',
        f'source: "{KANRIPO_URL}/{book["id"]}"',
        'license: "CC BY-SA 4.0"',
        "---",
        "",
        f"# {book['title']}",
        "",
        f"> {book['dynasty']} · {book['author']} · {book.get('edition', '')}",
        "",
        book.get("summary", ""),
        "",
    ]

    body: list[str] = []
    for label, text in sections:
        body.extend([f"## {label}", "", text, ""])

    markdown = "\n".join(header + body).rstrip() + "\n"
    chars = len(re.sub(r"\s", "", "\n".join(text for _, text in sections)))
    return markdown, len(sections), chars


def write_index(books: list[dict], out_dir: Path) -> None:
    total_chars = sum(b["chars"] for b in books)
    total_sections = sum(b["sections"] for b in books)

    lines = [
        "# 古籍目录",
        "",
        "本目录由 `scripts/fetch_books.py` 依据 `catalog.yaml` 自动生成。",
        "",
        f"- 共 **{len(books)} 部**：农业 {sum(1 for b in books if b['category'] == '农业')} 部，"
        f"水利 {sum(1 for b in books if b['category'] == '水利')} 部",
        f"- 合计 **{total_sections} 卷/篇**，约 **{total_chars / 10000:.1f} 万字**",
        "- 底本：Kanripo（漢籍リポジトリ）转录的《四庫全書》等版本",
        "- 许可：CC BY-SA 4.0，详见 [SOURCES.md](../SOURCES.md)",
        "",
    ]

    for category in ("农业", "水利"):
        subset = [b for b in books if b["category"] == category]
        lines.extend(
            [
                f"## {category}（{len(subset)} 部）",
                "",
                "| 书名 | 朝代 | 作者 | 底本 | 卷/篇 | 字数 | 文本 |",
                "|---|---|---|---|---:|---:|---|",
            ]
        )
        for b in subset:
            link = f"{CATEGORY_DIRS[category]}/{b['id']}_{b['title']}.md"
            lines.append(
                f"| {b['title']} | {b['dynasty']} | {b['author']} | "
                f"{b.get('edition', '')} | {b['sections']} | {b['chars'] / 10000:.1f} 万 | "
                f"[阅读]({link}) |"
            )
        lines.append("")

    (out_dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="下载并整理农业与水利古籍")
    parser.add_argument("--catalog", default=str(ROOT / "catalog.yaml"))
    parser.add_argument("--out", default=str(ROOT / "books"))
    parser.add_argument("--cache", default=str(ROOT / ".cache" / "kanripo"))
    parser.add_argument("--jobs", type=int, default=8, help="并行克隆数（默认 8）")
    parser.add_argument("--only", nargs="*", help="只处理指定 id")
    args = parser.parse_args()

    catalog = load_catalog(Path(args.catalog))
    if args.only:
        wanted = set(args.only)
        catalog = [b for b in catalog if b["id"] in wanted]
        missing = wanted - {b["id"] for b in catalog}
        if missing:
            sys.exit(f"目录中没有这些 id：{', '.join(sorted(missing))}")

    out_dir = Path(args.out)
    cache = Path(args.cache)
    out_dir.mkdir(parents=True, exist_ok=True)
    for sub in CATEGORY_DIRS.values():
        (out_dir / sub).mkdir(exist_ok=True)

    print(f"准备下载 {len(catalog)} 部古籍……", flush=True)
    repos: dict[str, Path] = {}
    failures: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(clone_repo, b["id"], cache): b for b in catalog}
        for future in as_completed(futures):
            book = futures[future]
            try:
                repos[book["id"]] = future.result()
                print(f"  已就绪 {book['id']} {book['title']}", flush=True)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{book['id']}: {exc}")
                print(f"  失败 {book['id']}: {exc}", file=sys.stderr, flush=True)

    results: list[dict] = []
    for book in catalog:
        repo_dir = repos.get(book["id"])
        if repo_dir is None:
            continue
        try:
            markdown, sections, chars = build_markdown(book, repo_dir)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{book['id']}: {exc}")
            print(f"  转换失败 {book['id']}: {exc}", file=sys.stderr, flush=True)
            continue

        target = out_dir / CATEGORY_DIRS[book["category"]] / f"{book['id']}_{book['title']}.md"
        target.write_text(markdown, encoding="utf-8")
        try:
            display = target.relative_to(ROOT)
        except ValueError:
            display = target
        record = dict(book)
        record.update(
            {
                "file": str(target.relative_to(out_dir)),
                "sections": sections,
                "chars": chars,
            }
        )
        results.append(record)
        print(f"  已生成 {display}（{sections} 卷，{chars} 字）", flush=True)

    results.sort(key=lambda b: (b["category"], b["id"]))
    catalog_path = out_dir / "catalog.json"
    if args.only and catalog_path.exists():
        # 局部更新时保留其他书目的记录，避免索引只剩本次生成的部分。
        existing = {
            item["id"]: item
            for item in json.loads(catalog_path.read_text(encoding="utf-8"))
        }
        existing.update({item["id"]: item for item in results})
        results = sorted(existing.values(), key=lambda b: (b["category"], b["id"]))

    catalog_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_index(results, out_dir)

    total_chars = sum(b["chars"] for b in results)
    print(
        f"完成：{len(results)} 部，{sum(b['sections'] for b in results)} 卷/篇，"
        f"约 {total_chars / 10000:.1f} 万字。",
        flush=True,
    )
    if failures:
        print("以下条目未完成：", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
