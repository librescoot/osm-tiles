"""The local tile hand-off between jobs on one runner."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools/tile-cache.sh"


class TileCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "cache"
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_cache(self, *args, check=False):
        env = dict(os.environ, TILE_CACHE_DIR=str(self.root))
        return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True, text=True, check=check)

    def tile(self, name, data=b"tiles"):
        path = self.work / name
        path.write_bytes(data)
        return path

    def test_store_then_fetch_returns_the_same_bytes(self):
        self.run_cache("store", "123", "bremen", str(self.tile("a.mbtiles", b"bremen!")), check=True)
        self.assertFalse(list(self.root.rglob("*.part")))
        out = self.work / "out"
        self.assertEqual(self.run_cache("fetch", "123", "bremen", str(out)).returncode, 0)
        self.assertEqual((out / "tiles_bremen.mbtiles").read_bytes(), b"bremen!")

    def test_missing_entries_are_a_clean_miss(self):
        self.assertEqual(self.run_cache("fetch", "123", "bremen", str(self.work / "o")).returncode, 1)
        self.run_cache("store", "123", "bremen", str(self.tile("a.mbtiles")), check=True)
        self.assertEqual(self.run_cache("fetch", "124", "bremen", str(self.work / "o")).returncode, 1)
        self.assertEqual(self.run_cache("fetch", "123", "hamburg", str(self.work / "o")).returncode, 1)

    def test_fetch_all_needs_exactly_the_expected_regions(self):
        for region in ("bremen", "hamburg"):
            self.run_cache("store", "7", region, str(self.tile(region + ".mbtiles", region.encode())), check=True)
        dest = self.work / "all"
        self.assertEqual(self.run_cache("fetch-all", "7", "3", str(dest)).returncode, 1)
        self.assertEqual(self.run_cache("fetch-all", "7", "1", str(dest)).returncode, 1)
        self.assertEqual(self.run_cache("fetch-all", "7", "2", str(dest)).returncode, 0)
        self.assertEqual((dest / "hamburg/tiles_hamburg.mbtiles").read_bytes(), b"hamburg")

    def test_fetch_never_hands_out_a_partial_file(self):
        run = self.root / "runs/9"
        run.mkdir(parents=True)
        (run / "tiles_bremen.mbtiles.part").write_bytes(b"half")
        self.assertEqual(self.run_cache("fetch", "9", "bremen", str(self.work / "o")).returncode, 1)
        self.assertEqual(self.run_cache("fetch-all", "9", "1", str(self.work / "a")).returncode, 1)

    def test_rejects_path_tricks(self):
        f = str(self.tile("a.mbtiles"))
        self.assertEqual(self.run_cache("store", "1/../2", "bremen", f).returncode, 2)
        self.assertEqual(self.run_cache("store", "1", "../x", f).returncode, 2)
        self.assertEqual(self.run_cache("fetch", "1", "a b", str(self.work)).returncode, 2)

    def test_prune_keeps_recent_runs(self):
        for run in ("1", "2"):
            self.run_cache("store", run, "bremen", str(self.tile("a.mbtiles")), check=True)
        old = self.root / "runs/1"
        past = old.stat().st_mtime - 30 * 86400
        os.utime(old, (past, past))
        self.run_cache("prune", "7", check=True)
        self.assertFalse((self.root / "runs/1").exists())
        self.assertTrue((self.root / "runs/2/tiles_bremen.mbtiles").exists())

    def test_fetch_survives_the_cache_being_deleted_afterwards(self):
        self.run_cache("store", "5", "bremen", str(self.tile("a.mbtiles", b"keep")), check=True)
        out = self.work / "o"
        self.run_cache("fetch", "5", "bremen", str(out), check=True)
        (self.root / "runs/5/tiles_bremen.mbtiles").unlink()
        self.assertEqual((out / "tiles_bremen.mbtiles").read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
