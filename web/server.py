#!/usr/bin/env python3
"""Serve the farming-culture GIS web app.

Usage::

    python3 web/server.py                # http://127.0.0.1:8000/
    python3 web/server.py --port 9000
    python3 web/server.py --host 0.0.0.0 --port 8000

The server exposes the static site plus three small read-only JSON
endpoints so the data can also be consumed programmatically:

* ``GET /api/health``  -- service status and site count
* ``GET /api/stats``   -- aggregate counts
* ``GET /api/sites``   -- GeoJSON, optional ``category``/``province``/``q``
* ``GET /api/sites/<id>`` -- a single feature
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

WEB_DIR = Path(__file__).resolve().parent
DATA_DIR = WEB_DIR / "data"
SITES_GEOJSON = DATA_DIR / "sites.geojson"
STATS_JSON = DATA_DIR / "stats.json"

CATEGORIES = {
    "rice",
    "water",
    "tea",
    "mulberry",
    "dryland",
    "custom",
    "specialty",
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _filter_features(
    geojson: dict[str, Any],
    *,
    category: str | None = None,
    province: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    features = geojson.get("features", [])
    needle = (query or "").strip().lower()
    selected = []
    for feature in features:
        props = feature.get("properties", {})
        if category and props.get("category") != category:
            continue
        if province and props.get("province") != province:
            continue
        if needle:
            haystack = " ".join(
                [
                    str(props.get("name", "")),
                    str(props.get("province", "")),
                    str(props.get("city", "")),
                    str(props.get("summary", "")),
                    str(props.get("culture", "")),
                    " ".join(props.get("tags", []) or []),
                    " ".join(props.get("heritage", []) or []),
                ]
            ).lower()
            if needle not in haystack:
                continue
        selected.append(feature)
    return selected


class Handler(SimpleHTTPRequestHandler):
    """Static files plus a tiny read-only JSON API."""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".geojson": "application/geo+json",
        ".json": "application/json; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".svg": "image/svg+xml",
        ".yaml": "text/yaml; charset=utf-8",
    }

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if self.path.startswith("/vendor/"):
            self.send_header("Cache-Control", "public, max-age=86400")
        elif self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json(self._health())
            return
        if parsed.path == "/api/stats":
            try:
                self._send_json(_read_json(STATS_JSON))
            except OSError as exc:
                self._send_json(
                    {"error": f"stats unavailable: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        if parsed.path == "/api/sites":
            self._handle_sites(parse_qs(parsed.query))
            return
        if parsed.path.startswith("/api/sites/"):
            self._handle_site(parsed.path.rsplit("/", 1)[-1])
            return
        if parsed.path.startswith("/api/"):
            self._send_json(
                {"error": "not found"}, HTTPStatus.NOT_FOUND
            )
            return
        super().do_GET()

    def _health(self) -> dict[str, Any]:
        try:
            stats = _read_json(STATS_JSON)
            return {
                "status": "ok",
                "sites": stats.get("total", 0),
                "provinces": stats.get("provinces", 0),
                "updated": stats.get("updated"),
            }
        except OSError as exc:
            return {"status": "degraded", "error": str(exc)}

    def _handle_sites(self, query: dict[str, list[str]]) -> None:
        category = (query.get("category") or [None])[0]
        province = (query.get("province") or [None])[0]
        needle = (query.get("q") or [None])[0]

        if category and category not in CATEGORIES:
            self._send_json(
                {
                    "error": "unknown category",
                    "allowed": sorted(CATEGORIES),
                },
                HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            geojson = _read_json(SITES_GEOJSON)
        except OSError as exc:
            self._send_json(
                {"error": f"site data unavailable: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        features = _filter_features(
            geojson,
            category=category,
            province=province,
            query=needle,
        )
        payload = {
            "type": "FeatureCollection",
            "name": geojson.get("name", "farming-culture-sites"),
            "meta": {
                "total": len(geojson.get("features", [])),
                "returned": len(features),
                "category": category,
                "province": province,
                "q": needle,
            },
            "features": features,
        }
        self._send_json(payload)

    def _handle_site(self, site_id: str) -> None:
        try:
            geojson = _read_json(SITES_GEOJSON)
        except OSError as exc:
            self._send_json(
                {"error": f"site data unavailable: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        for feature in geojson.get("features", []):
            if feature.get("properties", {}).get("id") == site_id:
                self._send_json(feature)
                return
        self._send_json(
            {"error": f"site not found: {site_id}"}, HTTPStatus.NOT_FOUND
        )

    def _send_json(
        self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )


def create_server(
    host: str = "127.0.0.1", port: int = 8000
) -> ThreadingHTTPServer:
    handler = partial(Handler, directory=str(WEB_DIR))
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="bind address")
    parser.add_argument("--port", type=int, default=8000, help="bind port")
    args = parser.parse_args(argv)

    try:
        server = create_server(args.host, args.port)
    except OSError as exc:
        print(f"error: cannot bind {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1

    host, port = server.server_address[:2]
    print(f"中华农耕文化地图: http://{host}:{port}/")
    print(f"数据接口: http://{host}:{port}/api/sites")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
