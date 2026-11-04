#!/usr/bin/env python3
"""查询农业与水利古籍知识图谱。

用法：
    python3 kg/query.py stats
    python3 kg/query.py search 黃河
    python3 kg/query.py show water:huanghe
    python3 kg/query.py neighbors water:huanghe --depth 2
    python3 kg/query.py books --topic 荒政
    python3 kg/query.py evidence water:huanghe

数据来自 kg/graph.json；先运行 python3 kg/build.py 生成。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "kg" / "graph.json"


def load_graph() -> dict:
    if not GRAPH.exists():
        sys.exit("缺少 kg/graph.json，请先运行 python3 kg/build.py")
    return json.loads(GRAPH.read_text(encoding="utf-8"))


def entity_index(graph: dict) -> dict[str, dict]:
    return {entity["id"]: entity for entity in graph["entities"]}


def relation_label(graph: dict, predicate: str) -> str:
    definition = graph["schema"]["relation_types"].get(predicate, {})
    return definition.get("label", predicate)


def type_label(graph: dict, entity_type: str) -> str:
    definition = graph["schema"]["entity_types"].get(entity_type, {})
    return definition.get("label", entity_type)


def evidence_text(graph: dict, relation: dict) -> str:
    evidence = relation.get("evidence")
    if not evidence:
        return "书目元数据" if relation.get("source") == "catalog" else "分类设定"
    return (
        f"{evidence['book']} · {evidence['juan']} · "
        f"“{evidence['quote']}”"
    )


def print_entity(graph: dict, entity: dict, relations: list[dict]) -> None:
    print(f"{entity['name']}  [{entity['type']} / {type_label(graph, entity['type'])}]")
    print(f"ID: {entity['id']}")
    if entity.get("description"):
        print(f"说明: {entity['description']}")
    if entity.get("aliases"):
        print(f"别名: {'、'.join(entity['aliases'])}")
    properties = entity.get("properties") or {}
    if properties:
        keys = ("author", "dynasty", "category", "topic", "edition", "sections", "chars", "file")
        parts = [f"{key}={properties[key]}" for key in keys if key in properties]
        if parts:
            print("属性: " + "；".join(parts))
    if not relations:
        return
    print("\n关系:")
    for relation in relations:
        subject = graph["_entities"][relation["subject"]]["name"]
        obj = graph["_entities"][relation["object"]]["name"]
        label = relation_label(graph, relation["predicate"])
        count = f" ×{relation['count']}" if "count" in relation else ""
        print(f"  {subject} --{label}{count}--> {obj}")
        print(f"    {evidence_text(graph, relation)}")


def search(graph: dict, term: str) -> None:
    term_lower = term.lower()
    matches = []
    for entity in graph["entities"]:
        haystack = " ".join(
            [entity["id"], entity["name"], entity.get("description", ""), *entity.get("aliases", [])]
        ).lower()
        if term_lower in haystack:
            matches.append(entity)
    if not matches:
        print(f"没有找到与「{term}」匹配的实体")
        return
    for entity in matches:
        print(
            f"{entity['id']:<28} {entity['type']:<14} {entity['name']}  "
            f"{entity.get('description', '')[:50]}"
        )


def show(graph: dict, entity_id: str) -> None:
    entities = graph["_entities"]
    if entity_id not in entities:
        sys.exit(f"没有这个实体：{entity_id}")
    relations = [
        relation
        for relation in graph["relations"]
        if relation["subject"] == entity_id or relation["object"] == entity_id
    ]
    print_entity(graph, entities[entity_id], relations)


def neighbors(graph: dict, entity_id: str, depth: int) -> None:
    entities = graph["_entities"]
    if entity_id not in entities:
        sys.exit(f"没有这个实体：{entity_id}")
    adjacency: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for relation in graph["relations"]:
        adjacency[relation["subject"]].append((relation["object"], relation))
        adjacency[relation["object"]].append((relation["subject"], relation))
    seen = {entity_id}
    queue = deque([(entity_id, 0)])
    while queue:
        current, level = queue.popleft()
        if level >= depth:
            continue
        for neighbor, relation in adjacency[current]:
            if neighbor in seen:
                continue
            seen.add(neighbor)
            direction = "->" if relation["subject"] == current else "<-"
            label = relation_label(graph, relation["predicate"])
            print(
                f"{'  ' * (level + 1)}{direction} {label} "
                f"{entities[neighbor]['name']} ({neighbor})"
            )
            queue.append((neighbor, level + 1))


def books(graph: dict, topic: str | None, dynasty: str | None, category: str | None) -> None:
    entities = graph["_entities"]
    rows = []
    for entity in graph["entities"]:
        if entity["type"] != "Book":
            continue
        properties = entity.get("properties", {})
        if topic and properties.get("topic") != topic:
            continue
        if dynasty and properties.get("dynasty") != dynasty:
            continue
        if category and properties.get("category") != category:
            continue
        rows.append(entity)
    if not rows:
        print("没有符合条件的书目")
        return
    for entity in sorted(rows, key=lambda item: item["properties"].get("topic", "")):
        properties = entity["properties"]
        print(
            f"{entity['name']:<18} {properties.get('dynasty', ''):<4} "
            f"{properties.get('author', ''):<10} {properties.get('topic', ''):<8} "
            f"{properties.get('sections', 0):>3} 卷/篇  {entity['id']}"
        )


def evidence(graph: dict, entity_id: str) -> None:
    entities = graph["_entities"]
    if entity_id not in entities:
        sys.exit(f"没有这个实体：{entity_id}")
    relations = [
        relation
        for relation in graph["relations"]
        if relation.get("evidence")
        and (relation["subject"] == entity_id or relation["object"] == entity_id)
    ]
    for relation in relations:
        subject = entities[relation["subject"]]["name"]
        obj = entities[relation["object"]]["name"]
        print(f"{subject} --{relation_label(graph, relation['predicate'])}--> {obj}")
        print(f"  {evidence_text(graph, relation)}\n")


def stats(graph: dict) -> None:
    meta = graph["meta"]
    print(f"{meta['title']} v{meta['version']}")
    print(f"书目 {meta['book_count']} 部，{meta['section_count']} 卷/篇，约 {meta['char_count'] / 10000:.1f} 万字")
    print(f"实体 {meta['entity_count']} 个，关系 {meta['relation_count']} 条")
    print(f"带原文引文的关系 {meta['evidence_relation_count']} 条")
    print("\n实体类型:")
    for entity_type, count in graph["stats"]["entity_counts"].items():
        print(f"  {type_label(graph, entity_type):<8} {count:>5}")
    print("\n关系类型:")
    for predicate, count in graph["stats"]["relation_counts"].items():
        print(f"  {relation_label(graph, predicate):<8} {count:>5}")
    print("\n高频实体:")
    for item in graph["stats"]["top_entities"][:10]:
        print(f"  {item['name']:<8} {item['count']:>6} 次")


def main() -> int:
    parser = argparse.ArgumentParser(description="查询农业与水利古籍知识图谱")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("stats", help="显示图谱统计")

    search_parser = subparsers.add_parser("search", help="按名称、别名或说明搜索")
    search_parser.add_argument("term")

    show_parser = subparsers.add_parser("show", help="显示实体详情与全部关系")
    show_parser.add_argument("entity_id")

    neighbors_parser = subparsers.add_parser("neighbors", help="按深度遍历相邻实体")
    neighbors_parser.add_argument("entity_id")
    neighbors_parser.add_argument("--depth", type=int, default=1)

    books_parser = subparsers.add_parser("books", help="按主题、朝代或类别筛选书目")
    books_parser.add_argument("--topic")
    books_parser.add_argument("--dynasty")
    books_parser.add_argument("--category")

    evidence_parser = subparsers.add_parser("evidence", help="列出一个实体的全部原文引文")
    evidence_parser.add_argument("entity_id")

    args = parser.parse_args()
    graph = load_graph()
    graph["_entities"] = entity_index(graph)

    if args.command == "stats":
        stats(graph)
    elif args.command == "search":
        search(graph, args.term)
    elif args.command == "show":
        show(graph, args.entity_id)
    elif args.command == "neighbors":
        neighbors(graph, args.entity_id, max(1, args.depth))
    elif args.command == "books":
        books(graph, args.topic, args.dynasty, args.category)
    elif args.command == "evidence":
        evidence(graph, args.entity_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
