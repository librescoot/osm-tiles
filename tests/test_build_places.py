#!/usr/bin/env python3
"""Tests for the address sidecar schema and tile coverage index."""

import gzip
import math
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import mapbox_vector_tile
from shapely.geometry import Polygon
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_places import (  # noqa: E402
    decode_address_tile,
    index_addresses,
    reset_schema,
    write_tables,
)


class BuildPlacesDecoderTest(unittest.TestCase):
    def test_decode_address_tile_matches_full_decoder_and_skips_other_layers(self):
        encoded = mapbox_vector_tile.encode([
            {
                "name": "addresses",
                "features": [
                    {
                        "geometry": {"type": "Point", "coordinates": [700, 1200]},
                        "properties": {
                            "street": "Hauptstraße", "postcode": "12345", "ref": "unused",
                        },
                    },
                    {
                        "geometry": {"type": "Point", "coordinates": [3000, 3200]},
                        "properties": {"name": "Nebenweg", "postcode": "54321"},
                    },
                    {
                        "geometry": {"type": "MultiPoint", "coordinates": [
                            [100, 100], [200, 200],
                        ]},
                        "properties": {"name": "ignored"},
                    },
                ],
            },
            {
                "name": "buildings",
                "features": [{
                    "geometry": {"type": "Polygon", "coordinates": [[
                        [100, 100], [300, 100], [300, 300], [100, 300], [100, 100],
                    ]]},
                    "properties": {"height": 12},
                }],
            },
        ])

        decoded = decode_address_tile(encoded)
        expected = mapbox_vector_tile.decode(encoded)["addresses"]
        expected_features = []
        for feature in expected["features"]:
            if feature["geometry"]["type"] != "Point":
                continue
            props = feature["properties"]
            expected_features.append((
                *feature["geometry"]["coordinates"],
                props.get("street"),
                props.get("name"),
                props.get("postcode"),
            ))
        self.assertEqual(decoded, {
            "addresses": {
                "extent": expected["extent"],
                "features": expected_features,
            },
        })
        self.assertEqual(
            decode_address_tile(mapbox_vector_tile.encode([{
                "name": "buildings",
                "features": [],
            }])),
            {},
        )

    def test_batched_index_matches_strict_contains_and_address_accounting(self):
        extent = 4096
        zoom_tiles = 1 << 14
        px = py = 2048
        lon = (8192 + px / extent) / zoom_tiles * 360.0 - 180.0
        slippy_y = zoom_tiles - 1 - 8192
        ymerc = (slippy_y + 1 - py / extent) / zoom_tiles
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ymerc))))
        places = [{"id": 1}, {"id": 2}]
        geometries = [
            Polygon([
                (lon - 0.001, lat - 0.01), (lon + 0.002, lat - 0.01),
                (lon + 0.002, lat + 0.01), (lon - 0.001, lat + 0.01),
            ]),
            Polygon([
                (lon, lat - 0.01), (lon + 0.001, lat - 0.01),
                (lon + 0.001, lat + 0.01), (lon, lat + 0.01),
            ]),
        ]
        layer = {"addresses": {
            "extent": extent,
            "features": [
                (px, py, "Hauptstraße", None, "12345"),
                (px, py, None, "Hauptstr", None),
                (4095, py, "Aussenweg", None, None),
                (px, py, None, None, None),
            ],
        }}
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE tiles (tile_column, tile_row, zoom_level, tile_data)")
            db.execute(
                "INSERT INTO tiles VALUES (?, ?, ?, ?)",
                (8192, 8192, 14, gzip.compress(b"test tile")),
            )
            with patch("build_places.decode_address_tile", return_value=layer):
                result = index_addresses(db, places, STRtree(geometries))
        finally:
            db.close()

        self.assertEqual(result["addr_total"], 4)
        self.assertEqual(result["unassigned"], 1)
        self.assertEqual(dict(result["place_addr_count"]), {1: 2})
        self.assertEqual(result["street_runs"][(1, "hauptstrasse")][0], 2)
        self.assertEqual(result["pc_runs"][(1, "hauptstrasse", "12345")][0], 1)
        self.assertEqual(
            result["street_tiles"][(1, "hauptstrasse", "12345")],
            {(8192, 8192)},
        )


class BuildPlacesSchemaTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        reset_schema(self.db)

    def tearDown(self):
        self.db.close()

    def test_street_tile_rows_cover_postcoded_and_postcodeless_addresses(self):
        places = [{
            "id": 42,
            "admin_level": 8,
            "name": "Teststadt",
            "name_de": None,
            "name_en": None,
            "alt_names": None,
            "de_place": None,
            "population": 0,
            "centroid_lat": 52.0,
            "centroid_lng": 13.0,
            "bbox_min_lat": 51.9,
            "bbox_min_lng": 12.9,
            "bbox_max_lat": 52.1,
            "bbox_max_lng": 13.1,
            "polygon_wkb": b"polygon",
            "_tags": {"name": "Teststadt"},
        }]
        index = {
            "place_addr_count": {42: 3},
            "place_streets_seen": {42: {"hauptstrasse"}},
            "street_runs": {(42, "hauptstrasse"): [3, 156.0, 39.0, "Hauptstraße"]},
            "pc_runs": {(42, "hauptstrasse", "12345"): [2, 104.0, 26.0]},
            "street_tiles": {
                (42, "hauptstrasse", "12345"): {(8800, 5400), (8801, 5400)},
                (42, "hauptstrasse", ""): {(8801, 5400)},
            },
        }

        counts = write_tables(self.db, places, index)
        self.assertEqual(counts[-1], 3)
        rows = self.db.execute(
            "SELECT postcode, tile_column, tile_row FROM place_street_tiles "
            "ORDER BY postcode, tile_column"
        ).fetchall()
        self.assertEqual(rows, [
            ("", 8801, 5400),
            ("12345", 8800, 5400),
            ("12345", 8801, 5400),
        ])

    def test_reset_schema_removes_stale_tile_rows(self):
        self.db.execute(
            "INSERT INTO place_street_tiles VALUES (42, 'road', '', 1, 2)"
        )
        reset_schema(self.db)
        count = self.db.execute("SELECT COUNT(*) FROM place_street_tiles").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
