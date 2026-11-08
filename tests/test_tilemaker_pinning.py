"""The tile build pins its generator and never publishes from a branch."""

from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/generate-tiles.yml").read_text())
DOCKERFILE = (ROOT / "tools/tilemaker/Dockerfile").read_text()


class TilemakerPinningTest(unittest.TestCase):
    def test_generator_commit_and_base_image_are_pinned(self):
        commit = re.search(r"ARG TILEMAKER_COMMIT=([0-9a-f]{40})", DOCKERFILE)
        self.assertIsNotNone(commit, "tilemaker commit must be a full SHA")
        self.assertRegex(DOCKERFILE, r"debian:trixie-slim@sha256:[0-9a-f]{64}")
        self.assertNotIn("tilemaker:latest", DOCKERFILE)

    def test_runs_the_built_image_not_a_floating_tag(self):
        job = WORKFLOW["jobs"]["generate_state_tiles"]
        runs = "\n".join(step.get("run", "") for step in job["steps"])
        self.assertIn("tilemaker-deterministic", runs)
        self.assertNotIn("versatiles/versatiles-tilemaker", runs)
        self.assertIn("needs.prepare_tilemaker.result == 'success'", job["if"])

    def test_every_region_is_verified_after_the_geocoding_index(self):
        steps = [step.get("name", "") for step in WORKFLOW["jobs"]["generate_state_tiles"]["steps"]]
        self.assertLess(steps.index("Build geocoding index for ${{ matrix.state.name }}"),
                        steps.index("Verify tiles for ${{ matrix.state.name }}"))
        self.assertLess(steps.index("Verify tiles for ${{ matrix.state.name }}"),
                        next(i for i, n in enumerate(steps) if n.startswith("Build map deltas and upload")))

    def test_deltas_are_built_per_region_right_after_the_tiles(self):
        jobs = WORKFLOW["jobs"]
        steps = [s.get("name", "") for s in jobs["generate_state_tiles"]["steps"]]
        delta = next(i for i, n in enumerate(steps) if n.startswith("Build map deltas"))
        # Each region runs the whole sequence itself: its deltas start as soon as
        # its own tiles are verified, without waiting for the other regions.
        self.assertGreater(delta, steps.index("Verify tiles for ${{ matrix.state.name }}"))
        step = jobs["generate_state_tiles"]["steps"][delta]
        self.assertEqual(step["uses"], "./.github/actions/build-map-deltas")
        self.assertEqual(jobs["generate_state_tiles"]["steps"][0].get("uses"), "actions/checkout@v7")
        self.assertNotIn("generate_state_tiles", jobs["generate_state_tiles"]["needs"])
        action = (ROOT / ".github/actions/build-map-deltas/action.yml").read_text()
        self.assertIn("tools/create-map-deltas.py", action)
        self.assertIn("--cache-dir", action)
        self.assertIn("map-deltas-$REGION", action)  # a directory per region, never a shared one

    def test_files_go_straight_from_each_runner_into_a_draft_release(self):
        jobs = WORKFLOW["jobs"]
        # Runners are separate machines: nothing is carried between them, so no
        # job downloads the tiles that other jobs built. Only the inputs a region
        # needs (the generator image and the clipped extracts) are passed on.
        for name, job in jobs.items():
            for step in job["steps"]:
                if step.get("uses", "").startswith("actions/download-artifact"):
                    self.assertIn(step["with"].get("name"),
                                  ("tilemaker-image", "austrian-city-pbfs", "swiss-canton-pbf"), name)
        self.assertIn("generate_state_tiles", jobs["publish_release"]["needs"])
        self.assertIn("open_release", jobs["generate_state_tiles"]["needs"])
        action = (ROOT / ".github/actions/build-map-deltas/action.yml").read_text()
        self.assertIn("tools/release-assets.py upload", action)
        self.assertIn("tools/tile-cache.sh adopt", action)
        # The shared draft is opened once, before any region starts.
        draft = next(s for s in jobs["open_release"]["steps"] if s.get("id") == "draft")
        self.assertIn("release-assets.py create", draft["run"])
        self.assertEqual(jobs["open_release"]["outputs"]["id"], "${{ steps.draft.outputs.id }}")
        region = next(s for s in jobs["generate_state_tiles"]["steps"] if s.get("name", "").startswith("Build map deltas"))
        self.assertEqual(region["with"]["release-id"], "${{ needs.open_release.outputs.id }}")

    def test_the_release_is_published_only_when_complete_and_only_from_main(self):
        jobs = WORKFLOW["jobs"]
        publish = jobs["publish_release"]
        self.assertIn("github.ref == 'refs/heads/main'", publish["if"])
        self.assertIn("needs.generate_state_tiles.result == 'success'", publish["if"])
        run = next(s for s in publish["steps"] if s.get("name") == "Publish the release")["run"]
        self.assertIn("release-assets.py publish", run)
        self.assertIn("--regions", run)
        self.assertIn("github.ref == 'refs/heads/main'", jobs["open_release"]["if"])
        # Branch runs keep their tiles as artifacts for review instead.
        keep = next(s for s in jobs["generate_state_tiles"]["steps"] if s.get("name", "").startswith("Keep tiles"))
        self.assertEqual(keep["if"], "github.ref != 'refs/heads/main'")
        self.assertEqual(keep["uses"], "actions/upload-artifact@v7")

    def test_no_job_needs_the_gh_cli(self):
        text = (ROOT / ".github/workflows/generate-tiles.yml").read_text()
        action = (ROOT / ".github/actions/build-map-deltas/action.yml").read_text()
        for source in (text, action):
            self.assertNotRegex(source, r"(^|\s)gh (release|api|run)\b")


if __name__ == "__main__":
    unittest.main()
