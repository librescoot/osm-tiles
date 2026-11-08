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

    def test_cache_reuses_a_verified_base_and_drops_bad_ones(self):
        data = b"published map bytes"
        digest = hashlib.sha256(data).hexdigest()
        base = {"version": "tiles-20261001T000000Z", "name": "tiles_bremen.mbtiles",
                "digest": "sha256:" + digest, "size": len(data), "release": {}}
        calls = []

        def fetch(release, name, destination):
            calls.append(destination)
            Path(destination).write_bytes(data)

        with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as scratch, \
                mock.patch.object(mod, "download_asset", side_effect=fetch):
            path, fresh = mod.fetch_base(base, scratch, cache)
            self.assertTrue(fresh)
            self.assertEqual(path, Path(cache) / base["version"] / base["name"])
            self.assertEqual(path.read_bytes(), data)
            self.assertFalse(list(Path(cache).rglob("*.part")))
            # Second run: served from the cache, nothing downloaded.
            path, fresh = mod.fetch_base(base, scratch, cache)
            self.assertFalse(fresh)
            self.assertEqual(len(calls), 1)
            # A cached file that no longer matches the digest is fetched again.
            path.write_bytes(b"corrupted")
            path, fresh = mod.fetch_base(base, scratch, cache)
            self.assertTrue(fresh)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(len(calls), 2)

    def test_cache_rejects_a_bad_download_without_keeping_it(self):
        base = {"version": "tiles-20261001T000000Z", "name": "tiles_bremen.mbtiles",
                "digest": "sha256:" + "0" * 64, "size": 3, "release": {}}
        with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as scratch, \
                mock.patch.object(mod, "download_asset",
                                  side_effect=lambda r, n, d: Path(d).write_bytes(b"abc")):
            with self.assertRaises(RuntimeError):
                mod.fetch_base(base, scratch, cache)
            self.assertEqual(list(Path(cache).rglob("*.mbtiles*")), [])
            with self.assertRaises(RuntimeError):
                mod.fetch_base(base, scratch, None)
            self.assertEqual(list(Path(scratch).iterdir()), [])

    def test_prune_removes_only_this_regions_stale_bases(self):
        with tempfile.TemporaryDirectory() as cache:
            for tag in ("tiles-1", "tiles-2", "tiles-3"):
                (Path(cache) / tag).mkdir()
                (Path(cache) / tag / "tiles_bremen.mbtiles").write_bytes(b"x")
                (Path(cache) / tag / "tiles_hamburg.mbtiles").write_bytes(b"y")
            mod.prune_cache(cache, "bremen", {"tiles-3"})
            left = sorted(str(p.relative_to(cache)) for p in Path(cache).rglob("*.mbtiles"))
            self.assertEqual(left, ["tiles-1/tiles_hamburg.mbtiles", "tiles-2/tiles_hamburg.mbtiles",
                                    "tiles-3/tiles_bremen.mbtiles", "tiles-3/tiles_hamburg.mbtiles"])

    def test_runs_without_the_gh_cli(self):
        # The self-hosted runners do not have gh; nothing may shell out to it.
        source = (ROOT / "tools/create-map-deltas.py").read_text()
        self.assertNotIn('"gh"', source)
        self.assertNotIn("'gh'", source)

    def test_download_picks_the_named_asset_by_api_url(self):
        release = {"tag_name": "tiles-1", "assets": [
            {"name": "other.mbtiles", "url": "https://api.invalid/assets/1"},
            {"name": "tiles_bremen.mbtiles", "url": "https://api.invalid/assets/2"}]}
        seen = []

        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n=-1):
                return b"" if seen.append("read") or len(seen) > 1 else b"bytes"

        def opener(request, timeout=0):
            seen.append(request.full_url)
            self.assertEqual(request.get_header("Accept"), "application/octet-stream")
            return Response()

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod.urllib.request, "urlopen", opener):
            mod.download_asset(release, "tiles_bremen.mbtiles", Path(tmp) / "x")
        self.assertEqual(seen[0], "https://api.invalid/assets/2")
        with self.assertRaises(RuntimeError):
            mod.download_asset(release, "missing.mbtiles", "/dev/null")

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

            def fetch(release, name, destination):
                self.assertEqual(release["tag_name"], "tiles-20261001T000000Z")
                shutil.copyfile(base, destination)

            with mock.patch.object(mod, "release_pages", return_value=releases[0]), \
                 mock.patch.object(mod, "download_asset", side_effect=fetch), \
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
            # The dashboard checks free space from these before it rebuilds.
            self.assertGreater(header["base_canonical_size"], 0)
            self.assertGreater(header["target_canonical_size"], 0)
            self.assertEqual(header["target_size"], target.stat().st_size)
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
