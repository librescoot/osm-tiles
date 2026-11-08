"""Tests for the map delta generator and its container format."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("create_map_deltas", ROOT / "tools/create-map-deltas.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def asset(name, digest, size=12):
    return {"name": name, "size": size, "digest": "sha256:" + digest}


def release(tag, date, *assets, **flags):
    return {"tag_name": tag, "published_at": date, "assets": list(assets), **flags}


class MapDeltaTest(unittest.TestCase):
    def test_bases_are_newest_distinct_per_region(self):
        a, b, c = "a" * 64, "b" * 64, "c" * 64
        releases = [release("tiles-20261001T000000Z", "2026-10-01",
                            asset("tiles_bremen.mbtiles", a)),
                    release("tiles-20261101T000000Z", "2026-11-01",
                            asset("tiles_bremen.mbtiles", b)),
                    release("tiles-20261102T000000Z", "2026-11-02",
                            asset("tiles_bremen.mbtiles", b)),
                    release("tiles-20261103T000000Z", "2026-11-03",
                            asset("tiles_bremen.mbtiles", c), draft=True)]
        picked = mod.bases(releases, 2)["bremen"]
        # Newest release wins for a digest that several releases repeat.
        self.assertEqual([entry["version"] for entry in picked],
                         ["tiles-20261102T000000Z", "tiles-20261001T000000Z"])
        self.assertEqual([entry["digest"] for entry in picked],
                         ["sha256:" + b, "sha256:" + a])

    def test_container_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.hdelta"
            header = {"algorithm": "hdiffpatch", "format": "mbtiles-canonical-1"}
            mod.write_container(path, header, _Bytes(b"payload"))
            back, payload = mod.read_container(path)
            self.assertEqual(back, header)
            self.assertEqual(payload, b"payload")

    def test_truncated_container_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.hdelta"
            mod.write_container(path, {"a": 1}, _Bytes(b"payload"))
            path.write_bytes(path.read_bytes()[:-2])
            with self.assertRaises(ValueError):
                mod.read_container(path)

    def test_generator_builds_a_verifiable_delta(self):
        encoder = os.environ.get("HDIFFZ")
        if not encoder or not Path(encoder).is_file():
            self.skipTest("Set HDIFFZ for real patch generation")
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.mbtiles"
            _build(base, b"a" * 4096)
            artwork = root / "artifacts" / "bremen"
            artwork.mkdir(parents=True)
            target = artwork / "tiles_bremen.mbtiles"
            _build(target, b"a" * 4096 + b"b" * 16)
            digest = hashlib.sha256(base.read_bytes()).hexdigest()
            releases = [[release("tiles-20261001T000000Z", "2026-10-01",
                                 asset("tiles_bremen.mbtiles", digest,
                                       base.stat().st_size))]]
            real_run = mod.subprocess.run

            def run(args, **kwargs):
                if args[:3] == ["gh", "release", "download"]:
                    shutil.copyfile(base, Path(args[-1]) / "tiles_bremen.mbtiles")
                    return None
                return real_run(args, **kwargs)

            with mock.patch.object(mod, "release_pages", return_value=releases[0]), \
                 mock.patch.object(mod.subprocess, "run", side_effect=run), \
                 mock.patch.object(mod.sys, "argv",
                                   ["generator", str(root / "artifacts"), "--bases", "1"]), \
                 mock.patch.dict(os.environ, {"PATH": str(Path(encoder).parent) + ":" + os.environ["PATH"]}):
                mod.main()
            patch = artwork / "tiles_bremen.from-tiles-20261001T000000Z.hdelta"
            self.assertTrue(patch.is_file())
            header, payload = mod.read_container(patch)
            self.assertEqual(header["base_sha256"], digest)
            self.assertEqual(header["format"], "mbtiles-canonical-1")
            self.assertEqual(header["algorithm"], "hdiffpatch")
            self.assertTrue(payload)


class _Bytes:
    def __init__(self, data):
        self._data = data

    def read_bytes(self):
        return self._data


def _build(path, tile):
    import gzip
    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE metadata (name text, value text, UNIQUE (name))")
    conn.execute("CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, tile_data blob)")
    conn.execute("INSERT INTO metadata VALUES ('name', 'test')")
    conn.execute("INSERT INTO tiles VALUES (10, 1, 1, ?)", (gzip.compress(tile, mtime=0),))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    unittest.main()
