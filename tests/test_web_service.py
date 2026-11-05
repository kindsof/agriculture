"""Tests for the farming-culture GIS web service.

Run with::

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
sys.path.insert(0, str(WEB_DIR))

import build_data  # noqa: E402
import server  # noqa: E402


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = build_data.load_yaml()
        cls.sites = cls.data["sites"]
        cls.provinces = build_data.load_provinces()
        cls.geojson = build_data.build_geojson(cls.sites)
        cls.stats = build_data.build_stats(cls.sites)

    def test_generated_data_is_current(self) -> None:
        build_data.build(check=True)

    def test_site_schema_and_coordinates(self) -> None:
        build_data.validate_sites(self.sites, self.provinces)

    def test_counts_and_coverage(self) -> None:
        self.assertEqual(len(self.sites), 69)
        self.assertEqual(self.stats["total"], 69)
        self.assertEqual(self.stats["provinces"], 31)
        self.assertEqual(len(self.geojson["features"]), 69)
        self.assertEqual(
            sum(item["count"] for item in self.stats["categories"].values()),
            69,
        )

    def test_ids_are_unique_and_slugged(self) -> None:
        ids = [site["id"] for site in self.sites]
        self.assertEqual(len(ids), len(set(ids)))
        for site_id in ids:
            self.assertRegex(site_id, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def test_every_site_has_source_and_heritage(self) -> None:
        for site in self.sites:
            self.assertGreaterEqual(len(site["sources"]), 1, site["id"])
            self.assertGreaterEqual(len(site["heritage"]), 1, site["id"])
            for source in site["sources"]:
                self.assertTrue(
                    source["url"].startswith(("http://", "https://")),
                    site["id"],
                )

    def test_point_in_province(self) -> None:
        zhejiang = next(
            feature
            for feature in self.provinces["features"]
            if feature["properties"].get("name") == "浙江省"
        )
        self.assertTrue(
            build_data.point_in_province(120.29, 28.14, zhejiang)
        )
        self.assertFalse(
            build_data.point_in_province(116.40, 39.90, zhejiang)
        )

    def test_geojson_properties(self) -> None:
        feature = next(
            item
            for item in self.geojson["features"]
            if item["properties"]["id"] == "qingtian-rice-fish"
        )
        self.assertEqual(feature["geometry"]["type"], "Point")
        self.assertEqual(
            feature["geometry"]["coordinates"], [120.29, 28.14]
        )
        self.assertEqual(feature["properties"]["province"], "浙江省")
        self.assertIn(
            "全球重要农业文化遗产（2005，首批）",
            feature["properties"]["heritage"],
        )


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = server.create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path: str):
        return urlopen(self.url(path), timeout=5)

    def get_json(self, path: str):
        with self.get(path) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health(self) -> None:
        payload = self.get_json("/api/health")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["sites"], 69)
        self.assertEqual(payload["provinces"], 31)

    def test_sites_endpoint(self) -> None:
        payload = self.get_json("/api/sites")
        self.assertEqual(payload["type"], "FeatureCollection")
        self.assertEqual(payload["meta"]["total"], 69)
        self.assertEqual(payload["meta"]["returned"], 69)
        self.assertEqual(len(payload["features"]), 69)

    def test_sites_filters(self) -> None:
        tea = self.get_json("/api/sites?category=tea")
        self.assertEqual(tea["meta"]["returned"], 10)
        self.assertTrue(
            all(
                feature["properties"]["category"] == "tea"
                for feature in tea["features"]
            )
        )

        zhejiang = self.get_json(
            "/api/sites?province=%E6%B5%99%E6%B1%9F%E7%9C%81"
        )
        self.assertEqual(zhejiang["meta"]["returned"], 10)

        search = self.get_json("/api/sites?q=%E9%BE%99%E4%BA%95")
        self.assertEqual(search["meta"]["returned"], 2)

    def test_single_site(self) -> None:
        feature = self.get_json("/api/sites/west-lake-longjing")
        self.assertEqual(
            feature["properties"]["name"], "西湖龙井茶文化系统"
        )

    def test_unknown_site(self) -> None:
        with self.assertRaises(HTTPError) as context:
            self.get("/api/sites/not-a-site")
        self.assertEqual(context.exception.code, 404)
        body = json.loads(context.exception.read().decode("utf-8"))
        context.exception.close()
        self.assertIn("not found", body["error"])

    def test_unknown_category(self) -> None:
        with self.assertRaises(HTTPError) as context:
            self.get("/api/sites?category=bogus")
        self.assertEqual(context.exception.code, 400)
        body = json.loads(context.exception.read().decode("utf-8"))
        context.exception.close()
        self.assertIn("allowed", body)

    def test_static_site(self) -> None:
        with self.get("/") as response:
            self.assertEqual(response.status, 200)
            html = response.read().decode("utf-8")
        self.assertIn("中华农耕文化地图", html)
        self.assertIn("assets/app.js", html)

    def test_static_data_and_vendor(self) -> None:
        with self.get("/data/sites.geojson") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                response.headers.get_content_type(), "application/geo+json"
            )
        with self.get("/vendor/leaflet/leaflet.js") as response:
            self.assertEqual(response.status, 200)
            self.assertIn(
                "text/javascript", response.headers.get("Content-Type", "")
            )

    def test_missing_static(self) -> None:
        with self.assertRaises(HTTPError) as context:
            self.get("/does-not-exist.html")
        self.assertEqual(context.exception.code, 404)
        context.exception.close()


if __name__ == "__main__":
    unittest.main()
