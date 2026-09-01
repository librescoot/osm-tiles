#!/usr/bin/env python3
"""Tests for the address sidecar schema and tile coverage index."""

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_places import reset_schema, write_tables  # noqa: E402


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
