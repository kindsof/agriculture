"""Tests for the agriculture AI catalog (ai/ directory).

Run with::

    python3 -m unittest discover -s tests -v

All tests are offline: they validate the curated catalog schema, URL sanity,
and that ai/INDEX.md's generated snapshot section is consistent with
ai/stats.json via ``scripts/fetch_ai_catalog.py --check``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / "ai"
CATALOG_PATH = AI_DIR / "catalog.yaml"
DOC_PATH = AI_DIR / "INDEX.md"
STATS_PATH = AI_DIR / "stats.json"
SCRIPT = ROOT / "scripts" / "fetch_ai_catalog.py"

sys.path.insert(0, str(ROOT / "scripts"))

import fetch_ai_catalog  # noqa: E402

VALID_KINDS = {"hf-model", "gh-repo", "skill", "dataset", "mcp", "paper-list"}
REQUIRED_FIELDS = {
    "id", "name", "kind", "url", "langs", "domain", "org", "since", "note",
}


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with CATALOG_PATH.open(encoding="utf-8") as fh:
            cls.catalog = yaml.safe_load(fh)
        cls.entries = cls.catalog["entries"]

    def test_meta_present(self) -> None:
        self.assertIn("meta", self.catalog)
        self.assertTrue(self.catalog["meta"].get("snapshot_date"))

    def test_entry_schema(self) -> None:
        for entry in self.entries:
            missing = REQUIRED_FIELDS - set(entry)
            self.assertFalse(missing, f"{entry.get('id')}: missing {missing}")
            self.assertIn(entry["kind"], VALID_KINDS, entry["id"])
            self.assertIsInstance(entry["langs"], list)
            self.assertTrue(str(entry["since"]).isdigit() and len(str(entry["since"])) == 4)

    def test_entry_ids_unique_and_prefixed(self) -> None:
        ids = [e["id"] for e in self.entries]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
        for entry in self.entries:
            prefix = entry["id"].split(":", 1)[0]
            self.assertIn(prefix, VALID_KINDS, entry["id"])

    def test_urls_https(self) -> None:
        for entry in self.entries:
            for field in ("url", "alt_url"):
                url = entry.get(field)
                if url:
                    parsed = urlparse(url)
                    self.assertEqual(parsed.scheme, "https", f"{entry['id']}.{field}")
                    self.assertTrue(parsed.netloc, f"{entry['id']}.{field}")

    def test_catalog_cases_diverse(self) -> None:
        kinds = {e["kind"] for e in self.entries}
        for kind in ("hf-model", "gh-repo", "skill", "dataset"):
            self.assertIn(kind, kinds, f"catalog should cover {kind} entries")


class DocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC_PATH.read_text(encoding="utf-8")
        with CATALOG_PATH.open(encoding="utf-8") as fh:
            cls.catalog = yaml.safe_load(fh)

    def test_snapshot_markers(self) -> None:
        self.assertIn(fetch_ai_catalog.MARK_BEGIN, self.doc)
        self.assertIn(fetch_ai_catalog.MARK_END, self.doc)
        self.assertLess(
            self.doc.index(fetch_ai_catalog.MARK_BEGIN),
            self.doc.index(fetch_ai_catalog.MARK_END),
        )

    def test_every_catalog_url_appears_in_doc(self) -> None:
        """目录条目必须在文档正文有对应链接，保证目录与文档同步。"""
        for entry in self.catalog["entries"]:
            self.assertIn(entry["url"], self.doc, f"missing {entry['id']} url in INDEX.md")

    def test_doc_mentions_key_sections(self) -> None:
        for heading in ("实时数据快照", "趋势观察", "方法与维护", "更新记录"):
            self.assertIn(heading, self.doc)


class SnapshotTests(unittest.TestCase):
    def test_stats_json_shape(self) -> None:
        if not STATS_PATH.exists():
            self.skipTest("stats.json not generated yet")
        stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
        self.assertIn("generated_at", stats)
        self.assertIn("entries", stats)
        with CATALOG_PATH.open(encoding="utf-8") as fh:
            catalog = yaml.safe_load(fh)
        ids = {e["id"] for e in catalog["entries"]}
        for entry_id in stats["entries"]:
            self.assertIn(entry_id, ids, "stats.json references unknown catalog id")

    def test_check_script_passes_offline(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class ParserTests(unittest.TestCase):
    def test_parse_hf_model_url(self) -> None:
        got = fetch_ai_catalog.parse_hf_url("https://huggingface.co/AgriGPT/AgriGPT-7B")
        self.assertEqual(got, ("models", "AgriGPT/AgriGPT-7B"))

    def test_parse_hf_dataset_url(self) -> None:
        got = fetch_ai_catalog.parse_hf_url(
            "https://huggingface.co/datasets/KisanVaani/agriculture-qa-english-only"
        )
        self.assertEqual(got, ("datasets", "KisanVaani/agriculture-qa-english-only"))

    def test_parse_hf_org_url(self) -> None:
        got = fetch_ai_catalog.parse_hf_url("https://huggingface.co/CopyleftCultivars")
        self.assertEqual(got, ("org", "CopyleftCultivars"))

    def test_parse_non_hf_url(self) -> None:
        self.assertIsNone(
            fetch_ai_catalog.parse_hf_url("https://github.com/foo/bar")
        )

    def test_parse_github_url(self) -> None:
        got = fetch_ai_catalog.parse_github_url(
            "https://github.com/human-avatar/skills-for-agriculture"
        )
        self.assertEqual(got, "human-avatar/skills-for-agriculture")

    def test_parse_modelscope_url(self) -> None:
        got = fetch_ai_catalog.parse_modelscope_url(
            "https://modelscope.cn/models/NAULLM/Sinong1.0-32B"
        )
        self.assertEqual(got, "NAULLM/Sinong1.0-32B")


if __name__ == "__main__":
    unittest.main()
