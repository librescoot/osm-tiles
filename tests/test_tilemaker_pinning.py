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

    def test_deltas_are_built_and_kept_with_their_release(self):
        jobs = WORKFLOW["jobs"]
        self.assertIn("create_deltas", jobs)
        self.assertEqual(jobs["release"]["needs"],
                         ["select_regions", "generate_state_tiles", "create_deltas"])
        runs = "\n".join(step.get("run", "") for step in jobs["create_deltas"]["steps"])
        self.assertIn("tools/create-map-deltas.py", runs)
        self.assertIn("--bases 2", runs)
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
                    self.assertEqual(step["with"]["run-id"], "${{ inputs.reuse_run_id || github.run_id }}")
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
        deltas = next(s for s in jobs["create_deltas"]["steps"] if s.get("name", "").startswith("Build deltas"))
        self.assertIn("--cache-dir", deltas["run"])
        self.assertTrue(any(s.get("name", "").startswith("Drop old tile runs") for s in jobs["release"]["steps"]))
        self.assertEqual(jobs["release"]["steps"][0].get("uses"), "actions/checkout@v7")

    def test_only_main_publishes(self):
        release = WORKFLOW["jobs"]["release"]
        self.assertIn("github.ref == 'refs/heads/main'", release["if"])
        self.assertEqual(WORKFLOW["jobs"]["generate_state_tiles"]["needs"],
                         ["select_regions", "prepare_tilemaker", "prepare_austria",
                          "prepare_switzerland"])


if __name__ == "__main__":
    unittest.main()
