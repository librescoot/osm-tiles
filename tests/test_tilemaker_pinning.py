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
                        steps.index("Upload tiles for ${{ matrix.state.name }}"))

    def test_deltas_are_built_per_region_right_after_the_tiles(self):
        jobs = WORKFLOW["jobs"]
        steps = [s.get("name", "") for s in jobs["generate_state_tiles"]["steps"]]
        delta = next(i for i, n in enumerate(steps) if n.startswith("Build map deltas for"))
        # Each region runs the whole sequence itself: its deltas start as soon as
        # its own tiles are verified, without waiting for the other regions.
        self.assertGreater(delta, steps.index("Verify tiles for ${{ matrix.state.name }}"))
        self.assertGreater(delta, next(i for i, n in enumerate(steps) if n.startswith("Keep tiles for")))
        self.assertNotIn("generate_state_tiles", jobs["generate_state_tiles"].get("needs", []))
        step = jobs["generate_state_tiles"]["steps"][delta]
        self.assertEqual(step["uses"], "./.github/actions/build-map-deltas")
        self.assertEqual(jobs["generate_state_tiles"]["steps"][0].get("uses"), "actions/checkout@v7")
        action = (ROOT / ".github/actions/build-map-deltas/action.yml").read_text()
        self.assertIn("tools/create-map-deltas.py", action)
        self.assertIn("--cache-dir", action)
        self.assertIn("map-deltas-$REGION", action)  # a directory per region, never a shared one

    def test_the_release_waits_for_every_region_and_its_deltas(self):
        jobs = WORKFLOW["jobs"]
        self.assertEqual(jobs["release"]["needs"],
                         ["select_regions", "generate_state_tiles", "create_deltas"])
        publish = next(s for s in jobs["release"]["steps"] if s.get("name") == "Publish release")
        self.assertIn("deltas/**/*.hdelta", publish["with"]["files"])

    def test_the_recovery_path_builds_deltas_from_reused_tiles(self):
        jobs = WORKFLOW["jobs"]
        self.assertIn("inputs.reuse_run_id != ''", jobs["create_deltas"]["if"])
        self.assertIn("'skipped'", jobs["create_deltas"]["if"])
        # One region per job, so no runner holds every artifact at once, and the
        # parallelism is a repository variable rather than a constant.
        strategy = jobs["create_deltas"]["strategy"]
        self.assertIn("select_regions.outputs.regions", strategy["matrix"]["state"])
        self.assertIn("MAP_DELTA_CONCURRENCY", strategy["max-parallel"])
        downloads = [step["with"] for step in jobs["create_deltas"]["steps"]
                     if step.get("uses", "").startswith("actions/download-artifact")]
        self.assertEqual([d["name"] for d in downloads], ["tiles_${{ matrix.state.name }}"])
        publish = next(step for step in jobs["release"]["steps"]
                       if step.get("name") == "Publish release")
        self.assertIn("deltas/**/*.hdelta", publish["with"]["files"])

    def test_a_run_can_reuse_the_tiles_of_an_earlier_run(self):
        jobs = WORKFLOW["jobs"]
        on = WORKFLOW.get("on") or WORKFLOW.get(True)
        self.assertIn("reuse_run_id", on["workflow_dispatch"]["inputs"])
        for name in ("prepare_tilemaker", "prepare_austria", "prepare_switzerland",
                     "generate_state_tiles"):
            self.assertIn("inputs.reuse_run_id == ''", jobs[name]["if"], name)
        # Deltas and the release still run when the build was skipped on purpose,
        # and take their artifacts from the reused run.
        for name in ("create_deltas", "release"):
            self.assertIn("inputs.reuse_run_id != ''", jobs[name]["if"], name)
            self.assertIn("skipped", jobs[name]["if"], name)
            for step in jobs[name]["steps"]:
                if step.get("uses", "").startswith("actions/download-artifact") and \
                        str(step["with"].get("name", step["with"].get("pattern", ""))).startswith("tiles_"):
                    # The delta job only exists for a reuse; the release serves both.
                    expected = ("${{ inputs.reuse_run_id }}" if name == "create_deltas"
                                else "${{ inputs.reuse_run_id || github.run_id }}")
                    self.assertEqual(step["with"]["run-id"], expected)
                    self.assertIn("github-token", step["with"])

    def test_tiles_are_handed_over_on_the_runner_before_downloading(self):
        jobs = WORKFLOW["jobs"]
        names = lambda job: [s.get("name", "") for s in jobs[job]["steps"]]
        build = names("generate_state_tiles")
        self.assertLess(build.index("Verify tiles for ${{ matrix.state.name }}"),
                        next(i for i, n in enumerate(build) if n.startswith("Keep tiles for")))
        self.assertLess(next(i for i, n in enumerate(build) if n.startswith("Keep tiles for")),
                        build.index("Upload tiles for ${{ matrix.state.name }}"))
        for job in ("create_deltas", "release"):
            steps = jobs[job]["steps"]
            local = next(s for s in steps if s.get("id") == "local")
            fallback = next(s for s in steps if s.get("uses", "").startswith("actions/download-artifact")
                            and str(s["with"].get("name", s["with"].get("pattern", ""))).startswith("tiles_"))
            self.assertLess(steps.index(local), steps.index(fallback), job)
            self.assertIn("steps.local.outputs.found != 'true'", fallback["if"], job)
        recovery = next(s for s in jobs["create_deltas"]["steps"] if s.get("name", "").startswith("Build map deltas"))
        self.assertEqual(recovery["uses"], "./.github/actions/build-map-deltas")
        steps = [s.get("name", "") for s in jobs["release"]["steps"]]
        # Published files become the next run's delta bases, only after publishing.
        self.assertLess(steps.index("Publish release"), steps.index("Keep the published files as delta bases"))
        adopt = next(s for s in jobs["release"]["steps"] if s.get("name") == "Keep the published files as delta bases")
        self.assertNotIn("always()", str(adopt.get("if", "")))
        self.assertIn("adopt", adopt["run"])
        self.assertIn("forget", adopt["run"])
        self.assertTrue(any(n.startswith("Drop stale tile runs") for n in steps))
        self.assertEqual(jobs["release"]["steps"][0].get("uses"), "actions/checkout@v7")

    def test_only_main_publishes(self):
        release = WORKFLOW["jobs"]["release"]
        self.assertIn("github.ref == 'refs/heads/main'", release["if"])
        self.assertEqual(WORKFLOW["jobs"]["generate_state_tiles"]["needs"],
                         ["select_regions", "prepare_tilemaker", "prepare_austria",
                          "prepare_switzerland"])


if __name__ == "__main__":
    unittest.main()
