#!/usr/bin/env python3
"""Build and validate the farming-culture map data.

The canonical site list lives in ``web/data/sites.yaml``.  This script
validates it (including checking that every coordinate falls inside the
province it claims) and generates:

* ``web/data/sites.geojson`` -- the GeoJSON consumed by the web map
* ``web/data/stats.json``    -- counts used by the page header and tests

Run ``python3 web/build_data.py`` after editing the YAML.  Use
``--check`` in CI to verify that the generated files are up to date
without writing anything.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml

WEB_DIR = Path(__file__).resolve().parent
DATA_DIR = WEB_DIR / "data"
SITES_YAML = DATA_DIR / "sites.yaml"
SITES_GEOJSON = DATA_DIR / "sites.geojson"
STATS_JSON = DATA_DIR / "stats.json"
PROVINCES_GEOJSON = DATA_DIR / "provinces.geojson"

CATEGORIES = {
    "rice": "稻作文化",
    "water": "梯田水利",
    "tea": "茶文化",
    "mulberry": "蚕桑渔农",
    "dryland": "旱作游牧",
    "custom": "农事民俗",
    "specialty": "特色物产",
}

REQUIRED_FIELDS = (
    "id",
    "name",
    "category",
    "province",
    "city",
    "lng",
    "lat",
    "summary",
    "culture",
    "heritage",
    "tags",
    "sources",
)

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class DataError(ValueError):
    """Raised when the site data does not satisfy the schema."""


def load_yaml(path: Path = SITES_YAML) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("sites"), list):
        raise DataError(f"{path} must contain a top-level 'sites' list")
    return data


def load_provinces(path: Path = PROVINCES_GEOJSON) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _iter_polygons(geometry: dict[str, Any]) -> Iterable[list[list[list[float]]]]:
    """Yield polygons (outer ring + holes) from a Polygon/MultiPolygon."""
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        yield from geometry["coordinates"]


def _point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting; returns True when the point is inside the ring."""
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_province(
    lng: float, lat: float, province: dict[str, Any]
) -> bool:
    for polygon in _iter_polygons(province["geometry"]):
        if not polygon:
            continue
        if _point_in_ring(lng, lat, polygon[0]) and not any(
            _point_in_ring(lng, lat, hole) for hole in polygon[1:]
        ):
            return True
    return False


def _require_text(value: Any, field: str, site_id: str, min_len: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < min_len:
        raise DataError(f"{site_id}: '{field}' must be text of length >= {min_len}")
    return value.strip()


def _validate_source(source: Any, site_id: str) -> None:
    if not isinstance(source, dict):
        raise DataError(f"{site_id}: each source must be a mapping")
    title = _require_text(source.get("title"), "source.title", site_id)
    url = _require_text(source.get("url"), "source.url", site_id)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DataError(f"{site_id}: invalid source URL {url!r} ({title})")


def validate_sites(
    sites: list[dict[str, Any]],
    provinces: dict[str, Any],
    *,
    check_coordinates: bool = True,
) -> None:
    """Validate every site, raising DataError on the first problem."""
    if not sites:
        raise DataError("no sites found")

    province_by_name = {
        feature["properties"].get("name"): feature
        for feature in provinces["features"]
        if feature["properties"].get("name")
    }

    seen: set[str] = set()
    for index, site in enumerate(sites, start=1):
        if not isinstance(site, dict):
            raise DataError(f"site #{index} must be a mapping")
        site_id = site.get("id") or f"site #{index}"
        if not isinstance(site_id, str) or not ID_RE.match(site_id):
            raise DataError(f"{site_id}: id must match {ID_RE.pattern}")
        if site_id in seen:
            raise DataError(f"duplicate id: {site_id}")
        seen.add(site_id)

        for field in REQUIRED_FIELDS:
            if field not in site:
                raise DataError(f"{site_id}: missing field '{field}'")

        _require_text(site["name"], "name", site_id)
        _require_text(site["city"], "city", site_id)
        _require_text(site["summary"], "summary", site_id, 20)
        _require_text(site["culture"], "culture", site_id, 10)

        category = site["category"]
        if category not in CATEGORIES:
            raise DataError(
                f"{site_id}: category {category!r} not in {sorted(CATEGORIES)}"
            )

        province_name = site["province"]
        if province_name not in province_by_name:
            raise DataError(
                f"{site_id}: unknown province {province_name!r}"
            )

        lng, lat = site["lng"], site["lat"]
        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            raise DataError(f"{site_id}: lng/lat must be numbers")
        if not 73 <= lng <= 136 or not 3 <= lat <= 54:
            raise DataError(
                f"{site_id}: coordinate ({lng}, {lat}) outside China bounds"
            )

        heritage = site["heritage"]
        if (
            not isinstance(heritage, list)
            or not 1 <= len(heritage) <= 5
            or not all(isinstance(item, str) and item.strip() for item in heritage)
        ):
            raise DataError(f"{site_id}: heritage must be a list of 1-5 strings")

        tags = site["tags"]
        if (
            not isinstance(tags, list)
            or not 2 <= len(tags) <= 6
            or not all(isinstance(item, str) and item.strip() for item in tags)
        ):
            raise DataError(f"{site_id}: tags must be a list of 2-6 strings")

        sources = site["sources"]
        if not isinstance(sources, list) or not 1 <= len(sources) <= 3:
            raise DataError(f"{site_id}: sources must be a list of 1-3 items")
        for source in sources:
            _validate_source(source, site_id)

        if check_coordinates and not point_in_province(
            float(lng), float(lat), province_by_name[province_name]
        ):
            raise DataError(
                f"{site_id}: coordinate ({lng}, {lat}) is outside {province_name}"
            )


def build_geojson(sites: list[dict[str, Any]]) -> dict[str, Any]:
    features = []
    for site in sites:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(site["lng"]), float(site["lat"])],
                },
                "properties": {
                    "id": site["id"],
                    "name": site["name"],
                    "category": site["category"],
                    "province": site["province"],
                    "city": site["city"],
                    "summary": site["summary"],
                    "culture": site["culture"],
                    "heritage": site["heritage"],
                    "tags": site["tags"],
                    "sources": site["sources"],
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "farming-culture-sites",
        "features": features,
    }


def build_stats(sites: list[dict[str, Any]]) -> dict[str, Any]:
    categories = Counter(site["category"] for site in sites)
    provinces = Counter(site["province"] for site in sites)
    return {
        "total": len(sites),
        "provinces": len(provinces),
        "categories": {
            key: {
                "label": label,
                "count": categories.get(key, 0),
            }
            for key, label in CATEGORIES.items()
        },
        "provinceCounts": dict(sorted(provinces.items())),
        "updated": None,
    }


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def _same_file(path: Path, payload: dict[str, Any]) -> bool:
    if not path.exists():
        return False
    expected = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return path.read_text(encoding="utf-8") == expected


def build(check: bool = False) -> dict[str, Any]:
    data = load_yaml()
    sites = data["sites"]
    provinces = load_provinces()
    validate_sites(sites, provinces)

    geojson = build_geojson(sites)
    stats = build_stats(sites)
    stats["updated"] = str(data.get("updated") or "")

    if check:
        stale = [
            str(path)
            for path, payload in ((SITES_GEOJSON, geojson), (STATS_JSON, stats))
            if not _same_file(path, payload)
        ]
        if stale:
            raise DataError(
                "generated data is out of date; run python3 web/build_data.py "
                f"(stale: {', '.join(stale)})"
            )
    else:
        _dump_json(SITES_GEOJSON, geojson)
        _dump_json(STATS_JSON, stats)

    return {"sites": sites, "geojson": geojson, "stats": stats}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate and check generated files are current; do not write",
    )
    args = parser.parse_args(argv)

    try:
        result = build(check=args.check)
    except (DataError, OSError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    stats = result["stats"]
    action = "checked" if args.check else "wrote"
    print(
        f"{action} {stats['total']} sites across {stats['provinces']} provinces; "
        f"categories: "
        + ", ".join(
            f"{key}={value['count']}"
            for key, value in stats["categories"].items()
            if value["count"]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
