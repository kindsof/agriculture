#!/usr/bin/env python3
"""构建并校验农业与水利古籍知识图谱。

数据来源：
  - books/catalog.json：书目、作者、朝代、主题、卷数、字数与全文路径
  - books/*.md：古籍全文，用于抽取提及证据
  - kg/data/entities.yaml：人工整理的主题实体
  - kg/data/relations.yaml：人工整理的语义关系
  - kg/data/about.yaml：书目与核心主题实体的对应
  - kg/data/topics.yaml：主题、朝代的稳定 ID

输出：
  - kg/graph.json / entities.jsonl / relations.jsonl / graph.jsonld
  - kg/INDEX.md
  - kg/schema.dot / schema.svg

用法：
    python3 kg/build.py                 # 构建并校验
    python3 kg/build.py --scan          # 打印每部书的实体提及统计，便于整理
    python3 kg/build.py --no-svg        # 跳过 Graphviz 渲染
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KG_DIR = ROOT / "kg"
DATA_DIR = KG_DIR / "data"
BOOKS_DIR = ROOT / "books"

TYPE_ORDER = [
    "Book",
    "Topic",
    "Dynasty",
    "Person",
    "Place",
    "Waterway",
    "WaterFacility",
    "Crop",
    "Tool",
    "Technique",
    "Institution",
    "Concept",
]
INDEX_TYPE_ORDER = [
    "Waterway",
    "WaterFacility",
    "Crop",
    "Tool",
    "Technique",
    "Institution",
    "Place",
    "Person",
    "Concept",
]
TYPE_COLORS = {
    "Book": "#e8f0fe",
    "Topic": "#f3e8fd",
    "Dynasty": "#f3e8fd",
    "Person": "#fde8e8",
    "Place": "#e8f5e9",
    "Waterway": "#e0f2fe",
    "WaterFacility": "#e0f2fe",
    "Crop": "#fef3c7",
    "Tool": "#fce7f3",
    "Technique": "#fce7f3",
    "Institution": "#f3f4f6",
    "Concept": "#f3f4f6",
}
RELATION_ORDER = [
    "has_topic",
    "written_in",
    "authored_by",
    "about",
    "mentions",
    "annotates",
    "related_to",
    "is_a",
    "part_of",
    "located_in",
    "managed_by",
    "applied_to",
]


class KGError(Exception):
    """知识图谱数据或校验错误。"""


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KGError(f"缺少文件：{path}") from exc
    except yaml.YAMLError as exc:
        raise KGError(f"YAML 解析失败 {path}：{exc}") from exc
    if not isinstance(data, dict):
        raise KGError(f"{path} 顶层应为映射")
    return data


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def relation_id(subject: str, predicate: str, obj: str) -> str:
    return f"{subject}--{predicate}--{obj}"


def load_schema() -> tuple[dict, dict]:
    data = load_yaml(KG_DIR / "schema.yaml")
    entity_types = data.get("entity_types")
    relation_types = data.get("relation_types")
    if not isinstance(entity_types, dict) or not isinstance(relation_types, dict):
        raise KGError("schema.yaml 需要 entity_types 与 relation_types 两个映射")
    for name in TYPE_ORDER:
        if name not in entity_types:
            raise KGError(f"schema.yaml 缺少实体类型 {name}")
    for name in RELATION_ORDER:
        if name not in relation_types:
            raise KGError(f"schema.yaml 缺少关系类型 {name}")
    return entity_types, relation_types


def load_catalog() -> tuple[list[dict], dict[str, str], dict[str, list[tuple[int, str]]]]:
    path = BOOKS_DIR / "catalog.json"
    try:
        books = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KGError(f"缺少 {path}，请先运行 scripts/fetch_books.py") from exc
    texts: dict[str, str] = {}
    headings: dict[str, list[tuple[int, str]]] = {}
    for book in books:
        file_path = BOOKS_DIR / book["file"]
        if not file_path.exists():
            raise KGError(f"{book['id']} 的全文不存在：{file_path}")
        text = file_path.read_text(encoding="utf-8")
        texts[book["id"]] = text
        headings[book["id"]] = [
            (match.start(), match.group(1).strip())
            for match in re.finditer(r"^## (.+)$", text, re.MULTILINE)
        ]
    return books, texts, headings


def load_taxonomy() -> tuple[dict[str, dict], dict[str, dict]]:
    data = load_yaml(DATA_DIR / "topics.yaml")
    topics = data.get("topics") or {}
    dynasties = data.get("dynasties") or {}
    for name, item in {**topics, **dynasties}.items():
        if not item.get("id"):
            raise KGError(f"topics.yaml 中 {name} 缺少 id")
    return topics, dynasties


def base_entity(
    entity_id: str,
    entity_type: str,
    name: str,
    *,
    description: str = "",
    aliases: list[str] | None = None,
    index: bool = True,
    disambiguation: bool = False,
    properties: dict | None = None,
) -> dict:
    return {
        "id": entity_id,
        "type": entity_type,
        "name": name,
        "aliases": sorted({alias.strip() for alias in (aliases or []) if alias.strip()}),
        "description": description.strip(),
        "index": bool(index),
        "disambiguation": bool(disambiguation),
        "properties": properties or {},
    }


def make_book_entities(books: list[dict]) -> dict[str, dict]:
    entities: dict[str, dict] = {}
    for book in books:
        eid = f"book:{book['id']}"
        entities[eid] = base_entity(
            eid,
            "Book",
            book["title"],
            description=book.get("summary", ""),
            aliases=[book["id"]],
            properties={
                "kr_id": book["id"],
                "author": book["author"],
                "dynasty": book["dynasty"],
                "category": book["category"],
                "topic": book["topic"],
                "edition": book.get("edition", ""),
                "sections": book["sections"],
                "chars": book["chars"],
                "file": f"books/{book['file']}",
                "source": f"https://github.com/kanripo/{book['id']}",
            },
        )
    return entities


def make_taxonomy_entities(
    books: list[dict], topics: dict[str, dict], dynasties: dict[str, dict]
) -> dict[str, dict]:
    entities: dict[str, dict] = {}
    for topic_name in sorted({book["topic"] for book in books}):
        if topic_name not in topics:
            raise KGError(f"catalog.yaml 的主题「{topic_name}」未在 kg/data/topics.yaml 中登记")
        item = topics[topic_name]
        entities[item["id"]] = base_entity(
            item["id"],
            "Topic",
            topic_name,
            description=item.get("description", ""),
            aliases=[topic_name],
            index=False,
        )
    for dynasty_name in sorted({book["dynasty"] for book in books}):
        if dynasty_name not in dynasties:
            raise KGError(f"catalog.yaml 的朝代「{dynasty_name}」未在 kg/data/topics.yaml 中登记")
        item = dynasties[dynasty_name]
        entities[item["id"]] = base_entity(
            item["id"],
            "Dynasty",
            dynasty_name,
            description=item.get("description", ""),
            aliases=[dynasty_name],
            index=False,
        )
    return entities


def load_curated_entities(entity_types: dict) -> dict[str, dict]:
    path = DATA_DIR / "entities.yaml"
    data = load_yaml(path)
    items = data.get("entities")
    if not isinstance(items, list) or not items:
        raise KGError(f"{path} 需要非空的 entities 列表")
    entities: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            raise KGError(f"{path} 中存在非映射条目：{item!r}")
        for key in ("id", "type", "name"):
            if not item.get(key):
                raise KGError(f"{path} 条目缺少 {key}：{item!r}")
        eid = item["id"]
        etype = item["type"]
        if etype not in entity_types:
            raise KGError(f"{eid} 的类型 {etype} 未在 schema.yaml 中定义")
        if eid in entities:
            raise KGError(f"实体 ID 重复：{eid}")
        entities[eid] = base_entity(
            eid,
            etype,
            item["name"],
            description=item.get("description", ""),
            aliases=item.get("aliases", []),
            index=item.get("index", True),
            disambiguation=item.get("disambiguation", False),
            properties=item.get("properties", {}),
        )
    return entities


def build_alias_index(entities: dict[str, dict]) -> dict[str, str]:
    """返回 别名 -> 实体 ID；别名冲突直接报错，避免错误归属。"""
    alias_to_entity: dict[str, str] = {}
    for entity in entities.values():
        if entity["type"] in {"Book", "Topic", "Dynasty"}:
            continue
        for alias in {entity["name"], *entity["aliases"]}:
            if not alias:
                continue
            previous = alias_to_entity.get(alias)
            if previous and previous != entity["id"]:
                raise KGError(
                    f"别名「{alias}」同时属于 {previous} 与 {entity['id']}，请改用更明确的别名"
                )
            alias_to_entity[alias] = entity["id"]
    return alias_to_entity


def find_juan(headings: list[tuple[int, str]], offset: int) -> str:
    label = "卷首"
    for position, heading in headings:
        if position <= offset:
            label = heading
        else:
            break
    return label


def quote_around(text: str, offset: int, max_length: int = 100) -> str:
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", offset)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end].strip()
    if not line or line.startswith("#"):
        start = max(0, offset - max_length // 2)
        end = min(len(text), offset + max_length // 2)
        line = text[start:end].strip()
    elif len(line) > max_length:
        start = max(line_start, offset - max_length // 2)
        end = min(line_end, offset + max_length // 2)
        line = text[start:end].strip()
    return line


def body_start_offset(text: str) -> int:
    """跳过 YAML front matter、书名、题记与摘要，返回正文起点。"""
    start = 0
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            start = end + 4
    heading = text.find("\n## ", start)
    return heading + 1 if heading != -1 else start


METADATA_MARKERS = (
    "欽定四庫全書",
    "四庫全書",
    "地理類",
    "地理𩔖",
    "農家類",
    "書類",
    "書𩔖",
    "政書類",
    "時令類",
    "時令𩔖",
    "史部",
    "經部",
    "子部",
)


def is_evidence_line(line: str, book_title: str = "") -> bool:
    """判断一行是否适合作为正文引文，跳过题名与四庫分類標目。"""
    if not line or line.startswith("#"):
        return False
    if any(marker in line for marker in METADATA_MARKERS):
        return False
    if book_title and book_title in line:
        return False
    return len(line) >= 8


def make_evidence(
    book_id: str,
    offset: int,
    texts: dict[str, str],
    headings: dict[str, list[tuple[int, str]]],
) -> dict:
    quote = quote_around(texts[book_id], offset)
    if not quote:
        raise KGError(f"无法为 {book_id} 的位置 {offset} 提取引文")
    if normalize(quote) not in normalize(texts[book_id]):
        raise KGError(f"{book_id} 的引文未通过原文校验：{quote[:40]}")
    return {
        "book": book_id,
        "juan": find_juan(headings[book_id], offset),
        "quote": quote,
        "offset": offset,
    }


def scan_mentions(
    entities: dict[str, dict],
    books: list[dict],
    texts: dict[str, str],
) -> tuple[dict[str, dict[str, dict]], Counter]:
    """扫描全部书目，返回 {book_id: {entity_id: {count, offset}}}。"""
    alias_to_entity = build_alias_index(entities)
    if not alias_to_entity:
        raise KGError("没有可扫描的实体别名")
    pattern = re.compile(
        "|".join(re.escape(alias) for alias in sorted(alias_to_entity, key=len, reverse=True))
    )
    mentions: dict[str, dict[str, dict]] = {}
    totals: Counter = Counter()
    for book in books:
        book_id = book["id"]
        text = texts[book_id]
        body_start = body_start_offset(text)
        found: dict[str, dict] = {}
        for match in pattern.finditer(text):
            if match.start() < body_start:
                continue
            entity_id = alias_to_entity[match.group(0)]
            record = found.setdefault(
                entity_id,
                {"count": 0, "offset": match.start(), "body_offset": None},
            )
            record["count"] += 1
            if record["body_offset"] is None:
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.start())
                if line_end == -1:
                    line_end = len(text)
                if is_evidence_line(text[line_start:line_end].strip(), book["title"]):
                    record["body_offset"] = match.start()
        mentions[book_id] = found
        totals.update({entity_id: record["count"] for entity_id, record in found.items()})
    return mentions, totals


def validate_relation(
    relation: dict,
    entities: dict[str, dict],
    relation_types: dict,
    texts: dict[str, str],
    headings: dict[str, list[tuple[int, str]]],
) -> dict:
    subject = relation.get("subject")
    predicate = relation.get("predicate")
    obj = relation.get("object")
    if subject not in entities:
        raise KGError(f"关系主语不存在：{subject}")
    if obj not in entities:
        raise KGError(f"关系宾语不存在：{obj}")
    if predicate not in relation_types:
        raise KGError(f"关系类型未定义：{predicate}")
    definition = relation_types[predicate]
    if entities[subject]["type"] not in definition.get("domain", []):
        raise KGError(
            f"{subject}（{entities[subject]['type']}）不能作为 {predicate} 的主语"
        )
    if entities[obj]["type"] not in definition.get("range", []):
        raise KGError(f"{obj}（{entities[obj]['type']}）不能作为 {predicate} 的宾语")

    provenance = definition.get("provenance", "evidence")
    evidence = relation.get("evidence")
    if provenance == "evidence":
        if not isinstance(evidence, dict):
            raise KGError(f"{relation_id(subject, predicate, obj)} 缺少 evidence")
        book_id = evidence.get("book")
        quote = (evidence.get("quote") or "").strip()
        if book_id not in texts:
            raise KGError(f"{relation_id(subject, predicate, obj)} 的 evidence.book 无效：{book_id}")
        if not quote:
            raise KGError(f"{relation_id(subject, predicate, obj)} 的 evidence.quote 为空")
        offset = texts[book_id].find(quote)
        if offset < 0:
            raise KGError(
                f"{relation_id(subject, predicate, obj)} 的引文未在 {book_id} 中找到：{quote[:60]}"
            )
        relation["evidence"] = {
            "book": book_id,
            "juan": evidence.get("juan") or find_juan(headings[book_id], offset),
            "quote": quote,
            "offset": offset,
        }
        relation["source"] = "text"
    else:
        if evidence:
            raise KGError(f"{relation_id(subject, predicate, obj)} 的 {provenance} 关系不应带引文")
        relation["source"] = provenance
    relation["id"] = relation_id(subject, predicate, obj)
    return relation


def add_relation(
    relations: dict[tuple[str, str, str], dict],
    relation: dict,
    *,
    replace: bool = False,
) -> None:
    key = (relation["subject"], relation["predicate"], relation["object"])
    if key in relations and not replace:
        raise KGError(f"关系重复：{relation_id(*key)}")
    relations[key] = relation


def load_curated_relations(
    entities: dict[str, dict],
    relation_types: dict,
    texts: dict[str, str],
    headings: dict[str, list[tuple[int, str]]],
) -> dict[tuple[str, str, str], dict]:
    data = load_yaml(DATA_DIR / "relations.yaml")
    items = data.get("relations") or []
    if not isinstance(items, list):
        raise KGError("relations.yaml 的 relations 应为列表")
    relations: dict[tuple[str, str, str], dict] = {}
    for item in items:
        if not isinstance(item, dict):
            raise KGError(f"relations.yaml 中存在非映射条目：{item!r}")
        relation = {
            "subject": item.get("subject"),
            "predicate": item.get("predicate"),
            "object": item.get("object"),
            "evidence": item.get("evidence"),
            "note": item.get("note", ""),
        }
        relation = validate_relation(relation, entities, relation_types, texts, headings)
        add_relation(relations, relation)
    return relations


def load_about(
    entities: dict[str, dict],
    books: list[dict],
    mentions: dict[str, dict[str, dict]],
    texts: dict[str, str],
    headings: dict[str, list[tuple[int, str]]],
) -> tuple[dict[str, list[str]], dict[tuple[str, str, str], dict]]:
    data = load_yaml(DATA_DIR / "about.yaml")
    about = data.get("about") or {}
    if not isinstance(about, dict):
        raise KGError("about.yaml 的 about 应为 书目 ID -> 实体 ID 列表 的映射")
    book_by_id = {book["id"]: book for book in books}
    book_ids = set(book_by_id)
    about_by_book: dict[str, list[str]] = {}
    relations: dict[tuple[str, str, str], dict] = {}
    for book_id, entity_ids in about.items():
        if book_id not in book_ids:
            raise KGError(f"about.yaml 中的书目不存在：{book_id}")
        if not isinstance(entity_ids, list) or not entity_ids:
            raise KGError(f"about.yaml 中 {book_id} 的实体列表为空")
        seen: set[str] = set()
        about_by_book[book_id] = []
        for entity_id in entity_ids:
            if entity_id in seen:
                raise KGError(f"about.yaml 中 {book_id} 重复列出 {entity_id}")
            seen.add(entity_id)
            if entity_id not in entities:
                raise KGError(f"about.yaml 中的实体不存在：{entity_id}")
            record = mentions.get(book_id, {}).get(entity_id)
            if not record:
                raise KGError(
                    f"about.yaml 指定 {book_id} 论述 {entity_id}，但正文中未匹配到该实体的别名"
                )
            subject = f"book:{book_id}"
            offset = record.get("body_offset") or record["offset"]
            relation = {
                "subject": subject,
                "predicate": "about",
                "object": entity_id,
                "evidence": make_evidence(book_id, offset, texts, headings),
                "count": record["count"],
                "source": "text",
                "note": "",
            }
            relation["id"] = relation_id(subject, "about", entity_id)
            add_relation(relations, relation)
            about_by_book[book_id].append(entity_id)
    return about_by_book, relations


def make_catalog_relations(
    books: list[dict],
    entities: dict[str, dict],
    topics: dict[str, dict],
    dynasties: dict[str, dict],
) -> dict[tuple[str, str, str], dict]:
    relations: dict[tuple[str, str, str], dict] = {}
    person_alias: dict[str, str] = {}
    for entity in entities.values():
        if entity["type"] == "Person":
            for alias in {entity["name"], *entity["aliases"]}:
                person_alias[alias] = entity["id"]

    for book in books:
        subject = f"book:{book['id']}"
        topic_id = topics[book["topic"]]["id"]
        relation = {
            "subject": subject,
            "predicate": "has_topic",
            "object": topic_id,
            "source": "catalog",
            "note": "",
        }
        relation["id"] = relation_id(subject, "has_topic", topic_id)
        add_relation(relations, relation)

        dynasty_id = dynasties[book["dynasty"]]["id"]
        relation = {
            "subject": subject,
            "predicate": "written_in",
            "object": dynasty_id,
            "source": "catalog",
            "note": "",
        }
        relation["id"] = relation_id(subject, "written_in", dynasty_id)
        add_relation(relations, relation)

        tokens = [
            token.strip()
            for token in re.split(r"[、，,；;／/]|等", book["author"])
            if token.strip()
        ]
        for token in tokens:
            person_id = person_alias.get(token)
            if not person_id:
                continue
            relation = {
                "subject": subject,
                "predicate": "authored_by",
                "object": person_id,
                "source": "catalog",
                "note": "",
            }
            relation["id"] = relation_id(subject, "authored_by", person_id)
            add_relation(relations, relation)
    return relations


def make_auto_mentions(
    books: list[dict],
    entities: dict[str, dict],
    mentions: dict[str, dict[str, dict]],
    about_by_book: dict[str, list[str]],
    texts: dict[str, str],
    headings: dict[str, list[tuple[int, str]]],
    *,
    min_count: int,
    max_per_book: int,
) -> dict[tuple[str, str, str], dict]:
    relations: dict[tuple[str, str, str], dict] = {}
    for book in books:
        book_id = book["id"]
        skip = set(about_by_book.get(book_id, []))
        candidates = []
        for entity_id, record in mentions.get(book_id, {}).items():
            entity = entities[entity_id]
            if entity_id in skip or not entity["index"] or record["count"] < min_count:
                continue
            candidates.append(
                (entity_id, record["count"], record.get("body_offset") or record["offset"])
            )
        candidates.sort(
            key=lambda item: (
                -item[1],
                TYPE_ORDER.index(entities[item[0]]["type"]),
                entities[item[0]]["name"],
            )
        )
        for entity_id, count, offset in candidates[:max_per_book]:
            subject = f"book:{book_id}"
            relation = {
                "subject": subject,
                "predicate": "mentions",
                "object": entity_id,
                "evidence": make_evidence(book_id, offset, texts, headings),
                "count": count,
                "source": "text",
                "note": "",
            }
            relation["id"] = relation_id(subject, "mentions", entity_id)
            add_relation(relations, relation)
    return relations


def relation_sort_key(relation: dict) -> tuple:
    predicate = relation["predicate"]
    predicate_index = RELATION_ORDER.index(predicate) if predicate in RELATION_ORDER else 99
    return (
        predicate_index,
        relation["subject"],
        -relation.get("count", 0),
        relation["object"],
    )


def compute_stats(
    entities: dict[str, dict],
    relations: dict[tuple[str, str, str], dict],
    mentions: dict[str, dict[str, dict]],
    books: list[dict],
) -> dict:
    entity_counts = Counter(entity["type"] for entity in entities.values())
    relation_counts = Counter(relation["predicate"] for relation in relations.values())
    evidence_counts = Counter(
        relation["predicate"] for relation in relations.values() if relation.get("evidence")
    )
    total_mentions = Counter()
    for per_book in mentions.values():
        for entity_id, record in per_book.items():
            total_mentions[entity_id] += record["count"]
    top_entities = [
        {
            "id": entity_id,
            "name": entities[entity_id]["name"],
            "type": entities[entity_id]["type"],
            "count": count,
        }
        for entity_id, count in total_mentions.most_common(15)
    ]
    books_by_topic: dict[str, list[str]] = defaultdict(list)
    for book in books:
        books_by_topic[book["topic"]].append(book["id"])
    return {
        "entity_counts": dict(entity_counts),
        "relation_counts": dict(relation_counts),
        "evidence_counts": dict(evidence_counts),
        "top_entities": top_entities,
        "books_by_topic": dict(books_by_topic),
        "book_count": len(books),
        "section_count": sum(book["sections"] for book in books),
        "char_count": sum(book["chars"] for book in books),
        "entity_count": len(entities),
        "disambiguation_entity_count": sum(
            1 for entity in entities.values() if entity["disambiguation"]
        ),
        "relation_count": len(relations),
        "evidence_relation_count": sum(
            1 for relation in relations.values() if relation.get("evidence")
        ),
        "mention_relation_count": relation_counts.get("mentions", 0),
        "about_relation_count": relation_counts.get("about", 0),
    }


def graph_entity(entity: dict) -> dict:
    return {
        "id": entity["id"],
        "type": entity["type"],
        "name": entity["name"],
        "aliases": entity["aliases"],
        "description": entity["description"],
        "disambiguation": entity["disambiguation"],
        "properties": entity["properties"],
    }


def graph_relation(relation: dict) -> dict:
    output = {
        "id": relation["id"],
        "subject": relation["subject"],
        "predicate": relation["predicate"],
        "object": relation["object"],
        "source": relation.get("source", ""),
    }
    if "count" in relation:
        output["count"] = relation["count"]
    if relation.get("evidence"):
        output["evidence"] = relation["evidence"]
    if relation.get("note"):
        output["note"] = relation["note"]
    return output


def write_jsonld(
    path: Path,
    entities: list[dict],
    relations: list[dict],
    meta: dict,
) -> None:
    base = "https://github.com/kindsof/agriculture/tree/main/kg"
    context = {
        "@vocab": f"{base}/vocab#",
        "id": "@id",
        "type": "@type",
        "name": "https://schema.org/name",
        "description": "https://schema.org/description",
        "aliases": "https://schema.org/alternateName",
        "subject": {"@id": f"{base}/vocab#subject", "@type": "@id"},
        "object": {"@id": f"{base}/vocab#object", "@type": "@id"},
        "predicate": f"{base}/vocab#predicate",
        "evidence": f"{base}/vocab#evidence",
        "count": "https://schema.org/value",
    }
    graph = []
    for entity in entities:
        graph.append(
            {
                "@id": f"{base}#{entity['id']}",
                "@type": entity["type"],
                "name": entity["name"],
                "description": entity["description"],
                "aliases": entity["aliases"],
                "properties": entity["properties"],
            }
        )
    for relation in relations:
        item = {
            "@id": f"{base}#{relation['id']}",
            "@type": relation["predicate"],
            "subject": {"@id": f"{base}#{relation['subject']}"},
            "object": {"@id": f"{base}#{relation['object']}"},
            "predicate": relation["predicate"],
            "source": relation.get("source", ""),
        }
        if "count" in relation:
            item["count"] = relation["count"]
        if relation.get("evidence"):
            item["evidence"] = relation["evidence"]
        graph.append(item)
    path.write_text(
        json.dumps(
            {"@context": context, "meta": meta, "@graph": graph},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def book_link(book: dict) -> str:
    return f"../books/{book['file']}"


def book_cell(book: dict) -> str:
    return f"[{book['title']}]({book_link(book)})"


def quote_short(quote: str, length: int = 42) -> str:
    quote = quote.replace("\n", " ").strip()
    return quote if len(quote) <= length else quote[:length] + "…"


def render_index(
    books: list[dict],
    entities: dict[str, dict],
    relations: dict[tuple[str, str, str], dict],
    mentions: dict[str, dict[str, dict]],
    about_by_book: dict[str, list[str]],
    stats: dict,
    entity_types: dict,
    relation_types: dict,
) -> str:
    book_by_id = {book["id"]: book for book in books}
    total_mentions = Counter()
    for per_book in mentions.values():
        for entity_id, record in per_book.items():
            total_mentions[entity_id] += record["count"]

    lines: list[str] = [
        "# 古籍知识图谱索引",
        "",
        "> 本文件由 `kg/build.py` 自动生成，请勿手工编辑。",
        "",
        "## 概览",
        "",
        f"- 书目 **{stats['book_count']} 部**，{stats['section_count']} 卷/篇，约 "
        f"**{stats['char_count'] / 10000:.1f} 万字**",
        f"- 实体 **{stats['entity_count']} 个**（含 {stats['disambiguation_entity_count']} 个消歧辅助实体），"
        f"关系 **{stats['relation_count']} 条**",
        f"- 带原文引文的关系 **{stats['evidence_relation_count']} 条**，全部通过原文子串校验",
        f"- 人工标註的主题论述 {stats['about_relation_count']} 条，自动抽取的提及 "
        f"{stats['mention_relation_count']} 条",
        "",
        "机器可读文件：[graph.json](graph.json)、[entities.jsonl](entities.jsonl)、"
        "[relations.jsonl](relations.jsonl)、[graph.jsonld](graph.jsonld)；"
        "结构与用法见 [README.md](README.md)。",
        "",
        "## 实体类型",
        "",
        "| 类型 | 数量 | 说明 |",
        "|---|---:|---|",
    ]
    for entity_type in TYPE_ORDER:
        if entity_type not in entity_types:
            continue
        count = stats["entity_counts"].get(entity_type, 0)
        lines.append(
            f"| {entity_types[entity_type]['label']}（{entity_type}） | {count} | "
            f"{entity_types[entity_type].get('description', '')} |"
        )

    lines.extend(
        [
            "",
            "## 关系类型",
            "",
            "| 关系 | 数量 | 说明 |",
            "|---|---:|---|",
        ]
    )
    for predicate in RELATION_ORDER:
        if predicate not in relation_types:
            continue
        count = stats["relation_counts"].get(predicate, 0)
        lines.append(
            f"| {relation_types[predicate]['label']}（{predicate}） | {count} | "
            f"{relation_types[predicate].get('description', '')} |"
        )

    lines.extend(
        [
            "",
            "## 书目",
            "",
            "| 书名 | 朝代 | 作者 | 主题 | 卷/篇 | 字数 | 主题实体 | 全文 |",
            "|---|---|---|---|---:|---:|---|---|",
        ]
    )
    for book in books:
        subject = f"book:{book['id']}"
        about_names = [
            entities[entity_id]["name"]
            for entity_id in about_by_book.get(book["id"], [])
        ]
        about_text = "、".join(about_names) if about_names else "—"
        lines.append(
            f"| {book['title']} | {book['dynasty']} | {book['author']} | {book['topic']} | "
            f"{book['sections']} | {book['chars'] / 10000:.1f} 万 | {about_text} | "
            f"[阅读]({book_link(book)}) |"
        )

    lines.extend(
        [
            "",
            "## 主题分布",
            "",
            "| 主题 | 书目数 | 书目 |",
            "|---|---:|---|",
        ]
    )
    for topic_name in sorted(stats["books_by_topic"]):
        book_ids = stats["books_by_topic"][topic_name]
        links = "、".join(book_cell(book_by_id[book_id]) for book_id in book_ids)
        lines.append(f"| {topic_name} | {len(book_ids)} | {links} |")

    lines.extend(
        [
            "",
            "## 实体索引",
            "",
            "表中「提及」为正文别名匹配次数；`index: false` 的实体（如「犁」「麻」）"
            "不生成自动 `mentions` 关系，仅用于人工标註与分类。",
            "",
        ]
    )
    for entity_type in INDEX_TYPE_ORDER:
        subset = sorted(
            (
                entity
                for entity in entities.values()
                if entity["type"] == entity_type and not entity["disambiguation"]
            ),
            key=lambda entity: entity["name"],
        )
        if not subset:
            continue
        lines.extend(
            [
                f"### {entity_types[entity_type]['label']}",
                "",
                "| 名称 | 说明 | 提及 | 主要书目 |",
                "|---|---|---:|---|",
            ]
        )
        for entity in subset:
            top_books = sorted(
                (
                    (book_id, record["count"])
                    for book_id, per_book in mentions.items()
                    if (record := per_book.get(entity["id"]))
                ),
                key=lambda item: (-item[1], item[0]),
            )[:3]
            if top_books:
                books_text = "、".join(
                    f"{book_cell(book_by_id[book_id])}（{count}）"
                    for book_id, count in top_books
                )
            else:
                books_text = "—"
            description = entity["description"] or "—"
            lines.append(
                f"| {entity['name']} | {description} | {total_mentions.get(entity['id'], 0)} | "
                f"{books_text} |"
            )
        lines.append("")

    semantic_predicates = [
        "annotates",
        "related_to",
        "is_a",
        "part_of",
        "located_in",
        "managed_by",
        "applied_to",
    ]
    semantic_relations = sorted(
        (
            relation
            for relation in relations.values()
            if relation["predicate"] in semantic_predicates
        ),
        key=relation_sort_key,
    )
    lines.extend(
        [
            "## 语义关系",
            "",
            "| 主语 | 关系 | 宾语 | 出处 / 引文 |",
            "|---|---|---|---|",
        ]
    )
    for relation in semantic_relations:
        subject = entities[relation["subject"]]["name"]
        obj = entities[relation["object"]]["name"]
        predicate = relation_types[relation["predicate"]]["label"]
        evidence = relation.get("evidence")
        if evidence:
            book = book_by_id.get(evidence["book"])
            if book:
                source_text = (
                    f"{book_cell(book)} · {evidence['juan']} · "
                    f"“{quote_short(evidence['quote'])}”"
                )
            else:
                source_text = f"{evidence['book']} · “{quote_short(evidence['quote'])}”"
        elif relation.get("source") == "editorial":
            source_text = "分类设定"
        else:
            source_text = "书目元数据"
        lines.append(f"| {subject} | {predicate} | {obj} | {source_text} |")

    lines.extend(
        [
            "",
            "## 生成与校验",
            "",
            "```bash",
            "python3 kg/build.py",
            "python3 kg/build.py --scan   # 查看每部书的实体提及统计",
            "```",
            "",
            "构建脚本会校验实体 ID、关系端点、类型约束与全部引文；"
            "任何一条引文无法在对应古籍全文中找到，构建即失败。"
            "自动提及使用别名最长匹配，只表示正文出现，不等同于语义论断；"
            "人工标註的「主题论述」才表示该书以此实体为核心论题。",
            "",
        ]
    )
    return "\n".join(lines)


def render_schema_dot(entity_types: dict, relation_types: dict) -> str:
    """生成类型层示意图；完整的 domain/range 约束见 schema.yaml。"""
    lines = [
        "digraph kg_schema {",
        '  graph [rankdir=LR, bgcolor="white", pad=0.4, nodesep=0.55, ranksep=1.0, fontname="Noto Sans CJK SC", labelloc="t", label="古籍知识图谱类型示意（完整约束见 schema.yaml）", fontsize=12];',
        '  node [shape=box, style="rounded,filled", fontname="Noto Sans CJK SC", fontsize=10, color="#9ca3af", penwidth=0.8];',
        '  edge [fontname="Noto Sans CJK SC", fontsize=8, color="#6b7280", arrowsize=0.6];',
    ]
    for entity_type in TYPE_ORDER:
        definition = entity_types[entity_type]
        label = definition["label"]
        lines.append(
            f'  "{entity_type}" [label="{label}\\n{entity_type}", '
            f'fillcolor="{TYPE_COLORS.get(entity_type, "#ffffff")}"];'
        )
    lines.extend(
        [
            '  "Theme" [label="主題實體\\n人物・地域・水道・作物・農具・技術…", shape=box, style="rounded,filled", fillcolor="#f9fafb", color="#9ca3af"];',
            '  "Book" -> "Topic" [label="has_topic"];',
            '  "Book" -> "Dynasty" [label="written_in"];',
            '  "Book" -> "Person" [label="authored_by"];',
            '  "Book" -> "Book" [label="annotates / related_to"];',
            '  "Book" -> "Theme" [label="about / mentions"];',
            '  "Theme" -> "Concept" [label="is_a"];',
            '  "Waterway" -> "Waterway" [label="part_of"];',
            '  "Waterway" -> "Place" [label="located_in"];',
            '  "WaterFacility" -> "Place" [label="located_in"];',
            '  "Waterway" -> "Person" [label="managed_by"];',
            '  "WaterFacility" -> "Person" [label="managed_by"];',
            '  "Technique" -> "Waterway" [label="applied_to"];',
            '  "Technique" -> "WaterFacility" [label="applied_to"];',
            '  "Tool" -> "Concept" [label="is_a"];',
            '  "Crop" -> "Concept" [label="is_a"];',
            '  "WaterFacility" -> "Concept" [label="is_a"];',
            '  "Technique" -> "Concept" [label="is_a"];',
            '  "Institution" -> "Concept" [label="is_a"];',
            '  "Waterway" -> "Concept" [label="is_a"];',
        ]
    )
    lines.append("}")
    return "\n".join(lines) + "\n"


def dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_overview_svg(books: list[dict], topics: dict[str, dict]) -> bool:
    dot_path = KG_DIR / "overview.dot"
    svg_path = KG_DIR / "overview.svg"
    counts = Counter(book["topic"] for book in books)
    lines = [
        "digraph kg_overview {",
        '  graph [rankdir=LR, bgcolor="white", pad=0.35, nodesep=0.25, ranksep=0.7, fontname="Noto Sans CJK SC", labelloc="t", label="书目主题总览", fontsize=13];',
        '  node [fontname="Noto Sans CJK SC", fontsize=9, color="#9ca3af", penwidth=0.7];',
        '  edge [color="#d1d5db", arrowsize=0.4];',
    ]
    for topic_name in sorted(counts):
        topic_id = topics[topic_name]["id"]
        lines.append(
            f'  "{topic_id}" [label="{dot_escape(topic_name)}\\n{counts[topic_name]} 部", '
            'shape=box, style="rounded,filled", fillcolor="#f3e8fd"];'
        )
    for book in books:
        topic_id = topics[book["topic"]]["id"]
        fill = "#fef3c7" if book["category"] == "农业" else "#e0f2fe"
        lines.append(
            f'  "book:{book["id"]}" [label="{dot_escape(book["title"])}", '
            f'shape=note, style="filled", fillcolor="{fill}"];'
        )
        lines.append(f'  "{topic_id}" -> "book:{book["id"]}";')
    lines.append("}")
    dot_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dot = shutil.which("dot")
    if not dot:
        return False
    result = subprocess.run(
        [dot, "-Tsvg", str(dot_path), "-o", str(svg_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"警告：overview.svg 渲染失败：{result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def render_schema_svg(entity_types: dict, relation_types: dict) -> bool:
    dot_path = KG_DIR / "schema.dot"
    svg_path = KG_DIR / "schema.svg"
    dot_path.write_text(render_schema_dot(entity_types, relation_types), encoding="utf-8")
    dot = shutil.which("dot")
    if not dot:
        print("警告：未找到 Graphviz dot，跳过 schema.svg 渲染", file=sys.stderr)
        return False
    result = subprocess.run(
        [dot, "-Tsvg", str(dot_path), "-o", str(svg_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"警告：Graphviz 渲染失败：{result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def print_scan(
    books: list[dict],
    entities: dict[str, dict],
    mentions: dict[str, dict[str, dict]],
    totals: Counter,
) -> None:
    print("每部书的实体提及（按次数排序，最多 12 个）：")
    for book in books:
        found = mentions.get(book["id"], {})
        ranked = sorted(
            found.items(),
            key=lambda item: (-item[1]["count"], entities[item[0]]["name"]),
        )[:12]
        print(f"\n{book['id']} {book['title']}（{book['chars'] / 10000:.1f} 万字）")
        if not ranked:
            print("  （无匹配）")
            continue
        for entity_id, record in ranked:
            entity = entities[entity_id]
            print(f"  {record['count']:>4}  {entity['type']:<14} {entity['name']}  ({entity_id})")

    zero = sorted(
        (
            entity
            for entity in entities.values()
            if entity["type"] not in {"Book", "Topic", "Dynasty"}
            and totals.get(entity["id"], 0) == 0
        ),
        key=lambda entity: (entity["type"], entity["name"]),
    )
    print(f"\n未被任何书目提及的实体：{len(zero)} 个")
    for entity in zero:
        print(f"  {entity['type']:<14} {entity['name']}  ({entity['id']})")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建农业与水利古籍知识图谱")
    parser.add_argument("--scan", action="store_true", help="打印实体提及统计")
    parser.add_argument("--no-svg", action="store_true", help="跳过 Graphviz 渲染")
    parser.add_argument("--min-count", type=int, default=2, help="自动提及的最小出现次数")
    parser.add_argument("--max-mentions", type=int, default=10, help="每部书最多保留的自动提及数")
    args = parser.parse_args()

    try:
        entity_types, relation_types = load_schema()
        books, texts, headings = load_catalog()
        topics, dynasties = load_taxonomy()

        entities: dict[str, dict] = {}
        entities.update(make_book_entities(books))
        entities.update(make_taxonomy_entities(books, topics, dynasties))
        entities.update(load_curated_entities(entity_types))

        mentions, totals = scan_mentions(entities, books, texts)
        if args.scan:
            print_scan(books, entities, mentions, totals)
            return 0

        relations: dict[tuple[str, str, str], dict] = {}
        relations.update(
            make_catalog_relations(books, entities, topics, dynasties)
        )
        relations.update(
            load_curated_relations(entities, relation_types, texts, headings)
        )
        about_by_book, about_relations = load_about(
            entities, books, mentions, texts, headings
        )
        relations.update(about_relations)
        relations.update(
            make_auto_mentions(
                books,
                entities,
                mentions,
                about_by_book,
                texts,
                headings,
                min_count=args.min_count,
                max_per_book=args.max_mentions,
            )
        )

        stats = compute_stats(entities, relations, mentions, books)
        meta = {
            "title": "农业与水利古籍知识图谱",
            "description": f"以本仓库 {stats['book_count']} 部农业、水利、荒政、时令与禹贡古籍全文为基础整理的知识图谱。",
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "https://github.com/kindsof/agriculture",
            "license": "CC BY-SA 4.0",
            "book_count": stats["book_count"],
            "section_count": stats["section_count"],
            "char_count": stats["char_count"],
            "entity_count": stats["entity_count"],
            "disambiguation_entity_count": stats["disambiguation_entity_count"],
            "relation_count": stats["relation_count"],
            "evidence_relation_count": stats["evidence_relation_count"],
            "schema_version": "1.0",
        }
        entity_list = [
            graph_entity(entities[entity_id])
            for entity_id in sorted(
                entities,
                key=lambda item: (
                    TYPE_ORDER.index(entities[item]["type"]),
                    entities[item]["name"],
                ),
            )
        ]
        relation_list = [
            graph_relation(relation)
            for relation in sorted(relations.values(), key=relation_sort_key)
        ]

        graph = {
            "meta": meta,
            "schema": {
                "entity_types": entity_types,
                "relation_types": relation_types,
            },
            "stats": stats,
            "entities": entity_list,
            "relations": relation_list,
        }
        (KG_DIR / "graph.json").write_text(
            json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with (KG_DIR / "entities.jsonl").open("w", encoding="utf-8") as handle:
            for entity in entity_list:
                handle.write(json.dumps(entity, ensure_ascii=False) + "\n")
        with (KG_DIR / "relations.jsonl").open("w", encoding="utf-8") as handle:
            for relation in relation_list:
                handle.write(json.dumps(relation, ensure_ascii=False) + "\n")
        write_jsonld(KG_DIR / "graph.jsonld", entity_list, relation_list, meta)

        index_text = render_index(
            books,
            entities,
            relations,
            mentions,
            about_by_book,
            stats,
            entity_types,
            relation_types,
        )
        (KG_DIR / "INDEX.md").write_text(index_text, encoding="utf-8")

        if not args.no_svg:
            render_schema_svg(entity_types, relation_types)
            render_overview_svg(books, topics)

        print(
            f"完成：{stats['book_count']} 部书，{stats['section_count']} 卷/篇，"
            f"{stats['entity_count']} 个实体，{stats['relation_count']} 条关系，"
            f"其中 {stats['evidence_relation_count']} 条带原文引文。"
        )
        zero = [
            entity
            for entity in entities.values()
            if entity["type"] not in {"Book", "Topic", "Dynasty", "Concept"}
            and not entity["disambiguation"]
            and totals.get(entity["id"], 0) == 0
        ]
        if zero:
            print(
                f"提示：{len(zero)} 个实体未被正文提及，可考虑补充别名或删除：",
                file=sys.stderr,
            )
            for entity in zero[:12]:
                print(f"  - {entity['id']} {entity['name']}", file=sys.stderr)
            if len(zero) > 12:
                print(f"  - 其余 {len(zero) - 12} 个见 --scan 输出", file=sys.stderr)
        return 0
    except KGError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
