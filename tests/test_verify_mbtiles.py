"""Fixture tests for the generated-MBTiles verifier."""

import gzip
import importlib.util
import sqlite3
import unittest
from pathlib import Path

import mapbox_vector_tile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_mbtiles", ROOT / "tools/verify-mbtiles.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

GEOCODER_SCHEMA = (ROOT / "build_places.py").read_text().split('SCHEMA_SQL = """', 1)[1].split('"""', 1)[0]


def tile(layers=("streets",), features=None):
    payload = [{
        "name": name,
        "extent": 4096,
        "version": 2,
        "features": features if features is not None else [{
            "geometry": {"type": "LineString", "coordinates": [[0, 0], [10, 10]]},
            "properties": {"kind": "residential", "name": "Testweg"},
        }],
    } for name in layers]
    return gzip.compress(mapbox_vector_tile.encode(payload, default_options={"y_coord_down": True}), mtime=0)


def build(path, tiles=None, metadata=None, skip_tables=(), empty_places=False):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE metadata (name text, value text, UNIQUE (name))")
    conn.execute("CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob)")
    conn.executescript(GEOCODER_SCHEMA)
    meta = {"name": "test", "format": "pbf", "minzoom": "0", "maxzoom": "14",
            "bounds": "-1,-1,1,1", "center": "0,0,0", "type": "baselayer",
            "version": "1"}
    meta.update(metadata or {})
    conn.executemany("INSERT INTO metadata VALUES (?, ?)", meta.items())
    rows = tiles if tiles is not None else [(10, 1, 1, tile())]
    conn.executemany("INSERT INTO tiles VALUES (?, ?, ?, ?)", rows)
    if not empty_places:
        conn.execute("INSERT INTO places (id, admin_level, name, centroid_lat, centroid_lng, "
                     "bbox_min_lat, bbox_min_lng, bbox_max_lat, bbox_max_lng, polygon_wkb) "
                     "VALUES (1, 6, 'Teststadt', 0, 0, -1, -1, 1, 1, x'00')")
        conn.execute("INSERT INTO place_aliases VALUES ('teststadt', 1, 'Teststadt', 'name')")
        conn.execute("INSERT INTO place_streets VALUES (1, 'testweg', 'Testweg', 0, 0, 1)")
        conn.execute("INSERT INTO place_postcodes VALUES (1, 'testweg', '12345', 0, 0)")
        conn.execute("INSERT INTO place_street_tiles VALUES (1, 'testweg', '12345', 1, 1)")
    for table in skip_tables:
        conn.execute(f"DROP TABLE {table}")
    conn.commit()
    conn.close()


class VerifyMBTilesTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "tiles.mbtiles"

    def tearDown(self):
        self.dir.cleanup()

    def run_check(self):
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        try:
            return module.check(conn, self.path, 200)
        finally:
            conn.close()

    def test_accepts_complete_file(self):
        build(self.path)
        tiles, decoded, counts = self.run_check()
        self.assertEqual((tiles, decoded, counts["places"]), (1, 1, 1))

    def test_rejects_missing_geocoder_table(self):
        build(self.path, skip_tables=("place_streets",))
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_rejects_invalid_gzip(self):
        build(self.path, tiles=[(10, 1, 1, b"not gzip")])
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_rejects_invalid_mvt(self):
        build(self.path, tiles=[(10, 1, 1, gzip.compress(b"\xff\xff\xff\xff", mtime=0))])
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_rejects_unknown_layer(self):
        build(self.path, tiles=[(10, 1, 1, tile(layers=("not_a_layer",)))])
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_rejects_zoom_outside_metadata(self):
        build(self.path, tiles=[(15, 1, 1, tile())])
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_rejects_duplicate_tile(self):
        build(self.path, tiles=[(10, 1, 1, tile()), (10, 1, 1, tile())])
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_rejects_empty_geocoder(self):
        build(self.path, empty_places=True)
        with self.assertRaises(SystemExit):
            self.run_check()

    def test_rejects_missing_metadata(self):
        build(self.path, metadata={"format": "png"})
        with self.assertRaises(SystemExit):
            self.run_check()


if __name__ == "__main__":
    unittest.main()
