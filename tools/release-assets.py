#!/usr/bin/env python3
"""Build a GitHub release from several jobs without moving files between them.

Each region job runs on whichever self-hosted runner picked it up and holds its
own tiles and deltas. Collecting 5 GB of workflow artifacts onto one machine
for the release was slow and failed; instead every job uploads its own files
into a shared draft release, and one last job checks it is complete and
publishes it. The runners have no gh CLI, so this talks to the API directly.

    release-assets.py create  --tag T --name N --body B --sha S
    release-assets.py upload  --release-id ID FILE...
    release-assets.py publish --release-id ID --regions a,b,c

`create` prints {"id": ..., "upload_url": ...} and reuses an existing draft for
the same tag, so a re-run continues instead of starting a second release.
`upload` is idempotent: an asset that is already there with the right size and
digest is kept, anything else is replaced. `publish` refuses to publish unless
every selected region has a tiles file with a digest, and every delta has one.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = os.environ.get("RELEASE_REPO", "librescoot/osm-tiles")
API = f"https://api.github.com/repos/{REPO}"
TAG = re.compile(r"^tiles-[A-Za-z0-9]+$")
REGION = re.compile(r"^[a-z0-9_-]+$")
ASSET = re.compile(r"^tiles_[a-z0-9_-]+(\.from-tiles-[A-Za-z0-9]+\.hdelta|\.mbtiles)$")


class ReleaseError(RuntimeError):
    pass


def _headers(extra=None):
    headers = {"User-Agent": "librescoot-release-assets",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ReleaseError("GH_TOKEN is not set")
    headers["Authorization"] = f"Bearer {token}"
    headers.update(extra or {})
    return headers


def call(method, url, body=None, timeout=60):
    """One JSON API call; returns the decoded body ({} for 204)."""
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url, data=data, method=method,
        headers=_headers({"Content-Type": "application/json"} if data else {}))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        raise ReleaseError(f"{method} {url}: HTTP {error.code} {error.read()[:300]!r}") from error
    return json.loads(payload) if payload else {}


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def list_assets(release_id):
    assets, page = [], 1
    while True:
        batch = call("GET", f"{API}/releases/{release_id}/assets?per_page=100&page={page}")
        assets.extend(batch)
        if len(batch) < 100:
            return assets
        page += 1


def create_draft(tag, name, body, sha):
    if not TAG.fullmatch(tag):
        raise ReleaseError(f"bad tag {tag!r}")
    page = 1
    while True:
        batch = call("GET", f"{API}/releases?per_page=100&page={page}")
        for release in batch:
            if release.get("tag_name") == tag:
                if not release.get("draft"):
                    raise ReleaseError(f"{tag} is already published")
                return release
        if len(batch) < 100:
            break
        page += 1
    return call("POST", f"{API}/releases", {
        "tag_name": tag, "target_commitish": sha, "name": name, "body": body,
        "draft": True, "prerelease": False})


def upload_url(release_id):
    # The upload host differs from the API host and is not guessable.
    release = call("GET", f"{API}/releases/{release_id}")
    return release["upload_url"].split("{")[0]


def upload_file(release_id, path, attempts=4, sleep=time.sleep):
    path = Path(path)
    if not ASSET.fullmatch(path.name):
        raise ReleaseError(f"refusing to upload unexpected file name {path.name!r}")
    size, digest = path.stat().st_size, sha256(path)
    base = upload_url(release_id)
    for attempt in range(1, attempts + 1):
        existing = {a["name"]: a for a in list_assets(release_id)}.get(path.name)
        if existing and existing["size"] == size and existing.get("digest") in (None, "sha256:" + digest) \
                and existing.get("state", "uploaded") == "uploaded":
            return "kept"
        if existing:
            call("DELETE", f"{API}/releases/assets/{existing['id']}")
        try:
            with open(path, "rb") as handle:
                request = urllib.request.Request(
                    f"{base}?name={path.name}", data=handle, method="POST",
                    headers=_headers({"Content-Type": "application/octet-stream",
                                      "Content-Length": str(size)}))
                with urllib.request.urlopen(request, timeout=1800) as response:
                    asset = json.load(response)
            if asset["size"] != size or asset.get("digest") not in (None, "sha256:" + digest):
                raise ReleaseError(f"{path.name}: uploaded asset does not match the local file")
            return "uploaded"
        except (urllib.error.URLError, ReleaseError, OSError) as error:
            print(f"{path.name}: upload attempt {attempt} failed: {error}", file=sys.stderr, flush=True)
            if attempt == attempts:
                raise ReleaseError(f"{path.name}: upload failed after {attempts} attempts") from error
            sleep(10 * attempt)
    raise AssertionError("unreachable")


def check_complete(assets, regions):
    """Raise unless every selected region has verified tiles."""
    by_name = {a["name"]: a for a in assets}
    problems = []
    for region in regions:
        asset = by_name.get(f"tiles_{region}.mbtiles")
        if asset is None:
            problems.append(f"missing tiles_{region}.mbtiles")
        elif asset.get("state", "uploaded") != "uploaded" or asset["size"] <= 0:
            problems.append(f"tiles_{region}.mbtiles is not fully uploaded")
        elif not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
            problems.append(f"tiles_{region}.mbtiles has no digest")
    expected = {f"tiles_{r}.mbtiles" for r in regions}
    for asset in assets:
        name = asset["name"]
        if not ASSET.fullmatch(name):
            problems.append(f"unexpected asset {name}")
        elif name.endswith(".hdelta"):
            region = name[len("tiles_"):name.index(".from-")]
            if f"tiles_{region}.mbtiles" not in expected:
                problems.append(f"{name} belongs to a region outside this release")
            elif not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
                problems.append(f"{name} has no digest")
        elif name not in expected:
            problems.append(f"{name} is not a selected region")
    if problems:
        raise ReleaseError("draft release is not publishable: " + "; ".join(problems))


def publish(release_id, regions):
    check_complete(list_assets(release_id), regions)
    return call("PATCH", f"{API}/releases/{release_id}", {"draft": False})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("create")
    c.add_argument("--tag", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--body", default="")
    c.add_argument("--sha", required=True)
    u = sub.add_parser("upload")
    u.add_argument("--release-id", required=True, type=int)
    u.add_argument("files", nargs="+")
    p = sub.add_parser("publish")
    p.add_argument("--release-id", required=True, type=int)
    p.add_argument("--regions", required=True, help="comma-separated region IDs the release must contain")
    args = parser.parse_args(argv)

    if args.command == "create":
        release = create_draft(args.tag, args.name, args.body, args.sha)
        print(json.dumps({"id": release["id"], "tag": release["tag_name"]}))
    elif args.command == "upload":
        for file in args.files:
            print(f"{Path(file).name}: {upload_file(args.release_id, file)}", flush=True)
    else:
        regions = [r for r in args.regions.split(",") if r]
        if not regions or any(not REGION.fullmatch(r) for r in regions):
            raise ReleaseError("bad region list")
        release = publish(args.release_id, regions)
        print(json.dumps({"id": release["id"], "tag": release["tag_name"], "url": release["html_url"]}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ReleaseError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
