"""Filing published tiles as the next run's delta bases."""

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

    def run_cache(self, *args):
        env = dict(os.environ, TILE_CACHE_DIR=str(self.root))
        return subprocess.run([str(SCRIPT), *args], env=env, capture_output=True, text=True)

    def test_adopt_files_the_published_tiles_under_the_release_tag(self):
        for region in ("bremen", "hamburg"):
            (self.work / f"tiles_{region}.mbtiles").write_bytes(region.encode())
        (self.work / "tiles_bremen.from-tiles-1.hdelta").write_bytes(b"delta")
        self.assertEqual(self.run_cache("adopt", "tiles-20261108T120000Z", str(self.work)).returncode, 0)
        base = self.root / "bases/tiles-20261108T120000Z"
        self.assertEqual((base / "tiles_bremen.mbtiles").read_bytes(), b"bremen")
        self.assertEqual((base / "tiles_hamburg.mbtiles").read_bytes(), b"hamburg")
        # Deltas are not bases, and nothing half-written is left behind.
        self.assertEqual(sorted(p.name for p in base.iterdir()),
                         ["tiles_bremen.mbtiles", "tiles_hamburg.mbtiles"])

    def test_adopt_works_from_per_region_subdirectories(self):
        (self.work / "bremen").mkdir()
        (self.work / "bremen/tiles_bremen.mbtiles").write_bytes(b"b")
        self.assertEqual(self.run_cache("adopt", "tiles-1", str(self.work)).returncode, 0)
        self.assertTrue((self.root / "bases/tiles-1/tiles_bremen.mbtiles").exists())

    def test_adopted_files_survive_the_working_copy_being_removed(self):
        (self.work / "tiles_bremen.mbtiles").write_bytes(b"keep")
        self.run_cache("adopt", "tiles-1", str(self.work))
        (self.work / "tiles_bremen.mbtiles").unlink()
        self.assertEqual((self.root / "bases/tiles-1/tiles_bremen.mbtiles").read_bytes(), b"keep")

    def test_adopt_refuses_odd_tags_and_empty_input(self):
        self.assertEqual(self.run_cache("adopt", "../x", str(self.work)).returncode, 2)
        self.assertEqual(self.run_cache("adopt", "tiles-1", str(self.work)).returncode, 1)
        self.assertFalse((self.root / "bases").exists())

    def test_unknown_commands_are_rejected(self):
        self.assertEqual(self.run_cache("prune").returncode, 2)
        self.assertEqual(self.run_cache().returncode, 2)


if __name__ == "__main__":
    unittest.main()
