#!/usr/bin/env python3
"""Generate MBTiles deltas against previously published regional releases.

Each `.hdelta` is a small container: a JSON header followed by an HDiffPatch
stream over the canonical tile stream (tools/canonical-mbtiles.py). The header
carries the base and target canonical hashes, so a client can verify both ends
without trusting the release index for them.

Only bases that still exist as published releases are used, and each release
keeps its own deltas, so a client on an older version can still find one.
"""

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "canonical_mbtiles", Path(__file__).resolve().parent / "canonical-mbtiles.py")
canonical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(canonical)

TILES = re.compile(r"^tiles_([a-z0-9_-]+)\.mbtiles$")
TAG = re.compile(r"^tiles-[A-Za-z0-9]+$")
MAGIC = b"MDP1"


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def bases(releases, limit):
    """Newest distinct published asset per region, newest first."""
    result = {}
    ordered = sorted(releases, key=lambda r: r.get("published_at") or "", reverse=True)
    for release in ordered:
        tag = release.get("tag_name", "")
        if release.get("draft") or release.get("prerelease") or not TAG.fullmatch(tag):
            continue
        for asset in release.get("assets", []):
            match = TILES.fullmatch(asset["name"])
            digest = asset.get("digest") or ""
            if not match or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                continue
            region = match.group(1)
            candidates = result.setdefault(region, [])
            if len(candidates) >= limit:
                continue
            if all(entry["digest"] != digest for entry in candidates):
                candidates.append({"version": tag, "digest": digest,
                                   "size": asset["size"], "name": asset["name"]})
    return result


def write_container(path, header, patch):
    payload = patch.read_bytes()
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    with open(path, "wb") as out:
        out.write(MAGIC)
        out.write(struct.pack(">I", len(encoded)))
        out.write(encoded)
        out.write(struct.pack(">Q", len(payload)))
        out.write(payload)


def read_container(path):
    with open(path, "rb") as handle:
        if handle.read(4) != MAGIC:
            raise ValueError("not an MDP1 container")
        (header_len,) = struct.unpack(">I", handle.read(4))
        header = json.loads(handle.read(header_len))
        (payload_len,) = struct.unpack(">Q", handle.read(8))
        payload = handle.read()
        if len(payload) != payload_len:
            raise ValueError("truncated patch payload")
    return header, payload


def release_pages():
    out = subprocess.check_output(
        ["gh", "api", "--paginate", "--slurp",
         "repos/librescoot/osm-tiles/releases?per_page=100"])
    return [release for page in json.loads(out) for release in page]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("--bases", type=int, default=2,
                        help="how many recent bases per region (default 2)")
    parser.add_argument("--max-ratio", type=float, default=0.9,
                        help="drop a delta larger than this fraction of the full file")
    args = parser.parse_args()

    previous = bases(release_pages(), args.bases)
    encoder = os.environ.get("HDIFFZ", "hdiffz")
    with tempfile.TemporaryDirectory(prefix="map-delta-") as tmp:
        tmp = Path(tmp)
        for target in sorted(args.artifacts.glob("**/tiles_*.mbtiles")):
            match = TILES.fullmatch(target.name)
            if not match:
                continue
            region = match.group(1)
            candidates = previous.get(region, [])
            if not candidates:
                print(f"{region}: no published base", flush=True)
                continue
            conn = __import__("sqlite3").connect(f"file:{target}?mode=ro", uri=True)
            try:
                target_canonical = tmp / f"{region}-target.canonical"
                target_hash = canonical.write(conn, target_canonical)
            finally:
                conn.close()
            full_size = target.stat().st_size
            for base in candidates:
                base_file = tmp / base["name"]
                subprocess.run(["gh", "release", "download", base["version"],
                                "--repo", "librescoot/osm-tiles", "--pattern", base["name"],
                                "--dir", tmp], check=True)
                if base_file.stat().st_size != base["size"] or sha256(base_file) != base["digest"][7:]:
                    raise RuntimeError(f"base verification failed: {base['version']}/{base['name']}")
                conn = __import__("sqlite3").connect(f"file:{base_file}?mode=ro", uri=True)
                try:
                    base_canonical = tmp / f"{region}-{base['version']}.canonical"
                    base_hash = canonical.write(conn, base_canonical)
                finally:
                    conn.close()
                patch = tmp / f"{region}-{base['version']}.hdiff"
                subprocess.run([encoder, "-m-4", "-p-2", "-c-zstd-20",
                                str(base_canonical), str(target_canonical), str(patch)], check=True)
                subprocess.run([encoder, "-t", str(base_canonical), str(target_canonical),
                                str(patch)], check=True)
                container = target.with_name(
                    f"tiles_{region}.from-{base['version']}.hdelta")
                write_container(container, {
                    "algorithm": "hdiffpatch",
                    "format": "mbtiles-canonical-1",
                    "region": region,
                    "base_version": base["version"],
                    "base_sha256": base["digest"][7:],
                    "base_canonical_sha256": base_hash,
                    "target_canonical_sha256": target_hash,
                    "base_canonical_size": base_canonical.stat().st_size,
                    "target_canonical_size": target_canonical.stat().st_size,
                    "target_size": full_size,
                }, patch)
                read_container(container)
                if container.stat().st_size >= full_size * args.max_ratio:
                    container.unlink()
                    print(f"{region}: delta from {base['version']} is not worthwhile", flush=True)
                else:
                    print(f"{region}: {base['version']} -> {container.name}, "
                          f"{container.stat().st_size} bytes", flush=True)
                base_file.unlink()
                base_canonical.unlink()
                patch.unlink()
            target_canonical.unlink()


if __name__ == "__main__":
    main()
