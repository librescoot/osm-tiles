"""The draft-release upload tool, against a fake GitHub API."""

import hashlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_assets", ROOT / "tools/release-assets.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeGitHub:
    """Just enough of the releases API to exercise create, upload and publish."""

    def __init__(self):
        self.releases = {}
        self.assets = {}      # release id -> list of asset dicts
        self.next_id = 100
        self.fail_uploads = 0
        self.drop_digest = False
        self.log = []

    def call(self, method, url, body=None, timeout=60):
        self.log.append((method, url))
        path = url.split("/repos/librescoot/osm-tiles", 1)[1]
        if method == "GET" and path.startswith("/releases?"):
            return list(self.releases.values())
        if method == "POST" and path == "/releases":
            self.next_id += 1
            release = dict(body, id=self.next_id, html_url=f"https://example.invalid/{self.next_id}",
                           upload_url=f"https://uploads.invalid/{self.next_id}/assets{{?name,label}}")
            self.releases[self.next_id] = release
            self.assets[self.next_id] = []
            return release
        if method == "GET" and path.startswith("/releases/") and "/assets" in path:
            rid = int(path.split("/")[2])
            return list(self.assets[rid])
        if method == "GET" and path.startswith("/releases/"):
            return self.releases[int(path.split("/")[2])]
        if method == "DELETE" and path.startswith("/releases/assets/"):
            aid = int(path.rsplit("/", 1)[1])
            for rid, items in self.assets.items():
                self.assets[rid] = [a for a in items if a["id"] != aid]
            return {}
        if method == "PATCH" and path.startswith("/releases/"):
            release = self.releases[int(path.split("/")[2])]
            release.update(body)
            return release
        raise AssertionError((method, url))

    def urlopen(self, request, timeout=0):
        if self.fail_uploads:
            self.fail_uploads -= 1
            raise mod.urllib.error.URLError("connection reset")
        rid = int(request.full_url.split("uploads.invalid/")[1].split("/")[0])
        name = request.full_url.split("name=")[1]
        data = request.data.read()
        self.next_id += 1
        asset = {"id": self.next_id, "name": name, "size": len(data), "state": "uploaded"}
        if not self.drop_digest:
            asset["digest"] = "sha256:" + hashlib.sha256(data).hexdigest()
        self.assets[rid].append(asset)
        return io.BytesIO(json.dumps(asset).encode())


class ReleaseAssetsTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        self.patches = [mock.patch.object(mod, "call", self.gh.call),
                        mock.patch.object(mod.urllib.request, "urlopen", self.gh.urlopen),
                        mock.patch.dict(os.environ, {"GH_TOKEN": "x"})]
        for p in self.patches:
            p.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def file(self, name, data=b"tiles"):
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_create_is_a_draft_and_is_reused_by_a_retry(self):
        first = mod.create_draft("tiles-20261108T120000Z", "name", "body", "a" * 40)
        self.assertTrue(first["draft"])
        self.assertFalse(first["prerelease"])
        again = mod.create_draft("tiles-20261108T120000Z", "name", "body", "a" * 40)
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(sum(1 for m, u in self.gh.log if m == "POST"), 1)

    def test_create_refuses_a_published_tag_and_odd_tags(self):
        release = mod.create_draft("tiles-1", "n", "b", "a" * 40)
        self.gh.releases[release["id"]]["draft"] = False
        with self.assertRaises(mod.ReleaseError):
            mod.create_draft("tiles-1", "n", "b", "a" * 40)
        with self.assertRaises(mod.ReleaseError):
            mod.create_draft("../v1.0", "n", "b", "a" * 40)

    def test_upload_is_idempotent_and_replaces_a_stale_asset(self):
        rid = mod.create_draft("tiles-1", "n", "b", "a" * 40)["id"]
        path = self.file("tiles_bremen.mbtiles", b"first")
        self.assertEqual(mod.upload_file(rid, path), "uploaded")
        self.assertEqual(mod.upload_file(rid, path), "kept")
        path.write_bytes(b"second, longer")
        self.assertEqual(mod.upload_file(rid, path), "uploaded")
        assets = self.gh.assets[rid]
        self.assertEqual([a["size"] for a in assets], [len(b"second, longer")])

    def test_upload_retries_a_dropped_connection(self):
        rid = mod.create_draft("tiles-1", "n", "b", "a" * 40)["id"]
        self.gh.fail_uploads = 2
        slept = []
        self.assertEqual(mod.upload_file(rid, self.file("tiles_bremen.mbtiles"), sleep=slept.append), "uploaded")
        self.assertEqual(len(slept), 2)
        self.gh.fail_uploads = 99
        with self.assertRaises(mod.ReleaseError):
            mod.upload_file(rid, self.file("tiles_hamburg.mbtiles"), attempts=2, sleep=lambda s: None)

    def test_upload_refuses_names_that_are_not_tiles_or_deltas(self):
        rid = mod.create_draft("tiles-1", "n", "b", "a" * 40)["id"]
        for name in ("notes.txt", "tiles_bremen.tar", "tiles_..mbtiles", "valhalla_tiles_bremen.tar"):
            with self.assertRaises(mod.ReleaseError, msg=name):
                mod.upload_file(rid, self.file(name))

    def test_publish_needs_every_selected_region_and_digests(self):
        rid = mod.create_draft("tiles-1", "n", "b", "a" * 40)["id"]
        mod.upload_file(rid, self.file("tiles_bremen.mbtiles"))
        with self.assertRaises(mod.ReleaseError) as ctx:
            mod.publish(rid, ["bremen", "hamburg"])
        self.assertIn("missing tiles_hamburg.mbtiles", str(ctx.exception))
        self.assertTrue(self.gh.releases[rid]["draft"])
        mod.upload_file(rid, self.file("tiles_hamburg.mbtiles"))
        mod.upload_file(rid, self.file("tiles_bremen.from-tiles-0.hdelta"))
        released = mod.publish(rid, ["bremen", "hamburg"])
        self.assertFalse(released["draft"])

    def test_publish_rejects_assets_without_digest_and_strays(self):
        rid = mod.create_draft("tiles-1", "n", "b", "a" * 40)["id"]
        self.gh.drop_digest = True
        mod.upload_file(rid, self.file("tiles_bremen.mbtiles"))
        with self.assertRaises(mod.ReleaseError) as ctx:
            mod.publish(rid, ["bremen"])
        self.assertIn("no digest", str(ctx.exception))
        self.gh.drop_digest = False
        self.gh.assets[rid].clear()
        mod.upload_file(rid, self.file("tiles_bremen.mbtiles"))
        mod.upload_file(rid, self.file("tiles_hamburg.mbtiles"))
        with self.assertRaises(mod.ReleaseError) as ctx:
            mod.publish(rid, ["bremen"])
        self.assertIn("not a selected region", str(ctx.exception))

    def test_publish_rejects_a_half_uploaded_asset(self):
        rid = mod.create_draft("tiles-1", "n", "b", "a" * 40)["id"]
        mod.upload_file(rid, self.file("tiles_bremen.mbtiles"))
        self.gh.assets[rid][0]["state"] = "starter"
        with self.assertRaises(mod.ReleaseError):
            mod.publish(rid, ["bremen"])

    def test_delta_for_a_region_outside_the_release_is_rejected(self):
        rid = mod.create_draft("tiles-1", "n", "b", "a" * 40)["id"]
        mod.upload_file(rid, self.file("tiles_bremen.mbtiles"))
        mod.upload_file(rid, self.file("tiles_hamburg.from-tiles-0.hdelta"))
        with self.assertRaises(mod.ReleaseError) as ctx:
            mod.publish(rid, ["bremen"])
        self.assertIn("outside this release", str(ctx.exception))

    def test_no_token_is_an_error_not_an_anonymous_call(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(mod.ReleaseError):
                mod._headers()

    def test_runs_without_the_gh_cli(self):
        source = (ROOT / "tools/release-assets.py").read_text()
        self.assertNotIn('"gh"', source)


if __name__ == "__main__":
    unittest.main()
