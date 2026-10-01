import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "download-pbf.sh"
URL = "https://download.geofabrik.de/europe/switzerland-latest.osm.pbf"


class DownloadPbfTests(unittest.TestCase):
    def run_download(self, mode, url=URL):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "extract.osm.pbf"
            output.write_bytes(b"existing")
            log = root / "requests"
            curl = root / "curl"
            curl.write_text('''#!/bin/bash
set -eu
while [ "$1" != --output ]; do shift; done
output=$2
url=$3
echo "$url" >> "$REQUEST_LOG"
case "$MODE" in
    success) printf pbf > "$output" ;;
    fallback)
        if [[ "$url" == *-latest.osm.pbf ]]; then
            printf partial > "$output"
            echo 'curl: redirect loop' >&2
            exit 47
        fi
        printf pbf > "$output" ;;
    retry)
        if [ "$(wc -l < "$REQUEST_LOG")" -le 2 ]; then
            printf partial > "$output"
            exit 22
        fi
        printf pbf > "$output" ;;
    empty) : > "$output" ;;
    failure) printf partial > "$output"; exit 22 ;;
esac
''')
            curl.chmod(0o755)
            sleep = root / "sleep"
            sleep.write_text("#!/bin/bash\nexit 0\n")
            sleep.chmod(0o755)
            date = root / "date"
            date.write_text("#!/bin/bash\nprintf '260930\\n'\n")
            date.chmod(0o755)
            result = subprocess.run(
                ["bash", str(SCRIPT), url, str(output)],
                env={**os.environ, "PATH": f"{root}:{os.environ['PATH']}",
                     "MODE": mode, "REQUEST_LOG": str(log)},
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(list(root.glob("*.partial.*")), [])
            return result, output.read_bytes(), log.read_text().splitlines()

    def test_success_is_atomic(self):
        result, data, requests = self.run_download("success")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data, b"pbf")
        self.assertEqual(requests, [URL])

    def test_redirect_loop_uses_dated_extract(self):
        result, data, requests = self.run_download("fallback")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data, b"pbf")
        self.assertEqual(requests, [URL, URL.replace("latest", "260930")])
        self.assertIn("redirect loop", result.stderr)

    def test_transient_failure_retries(self):
        result, data, requests = self.run_download("retry")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data, b"pbf")
        self.assertEqual(len(requests), 3)

    def test_failure_preserves_existing_file(self):
        result, data, requests = self.run_download("failure")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data, b"existing")
        self.assertEqual(len(requests), 6)
        self.assertIn("after 3 attempts", result.stderr)

    def test_empty_response_is_not_published(self):
        result, data, requests = self.run_download("empty")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data, b"existing")
        self.assertEqual(len(requests), 6)
        self.assertIn("Empty response", result.stderr)

    def test_other_hosts_do_not_use_geofabrik_fallback(self):
        url = "https://example.org/region-latest.osm.pbf"
        result, data, requests = self.run_download("failure", url)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(data, b"existing")
        self.assertEqual(requests, [url] * 3)


if __name__ == "__main__":
    unittest.main()
