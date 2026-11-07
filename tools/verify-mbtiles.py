#!/usr/bin/env python3
"""Structural and content checks for a generated regional MBTiles file.

Runs after tilemaker and build_places.py so a broken generator, a truncated
write or a missing geocoding index fails the build instead of shipping. Every
tile is decompressed (cheap CRC check); a deterministic sample is decoded as
MVT so malformed protobuf or unexpected layers also fail.

Exit status is 0 when every check passes.
"""

import argparse
import gzip
import sqlite3
import sys
import zlib
from pathlib import Path

import mapbox_vector_tile

LAYERS = {"streets", "street_labels", "buildings", "addresses",
          "water_polygons", "water_lines", "land"}
REQUIRED_METADATA = {"name", "format", "minzoom", "maxzoom", "bounds", "center", "type", "version"}
GEOCODER_TABLES = {"places", "place_aliases", "place_streets", "place_postcodes",
                   "place_street_tiles"}


def fail(message):
    raise SystemExit(f"{message}")


def check(conn, path, sample):
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        fail(f"{path}: sqlite integrity_check returned {integrity!r}")

    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    missing = ({"tiles", "metadata"} | GEOCODER_TABLES) - tables
    if missing:
        fail(f"{path}: missing tables {sorted(missing)}")

    metadata = dict(conn.execute("SELECT name, value FROM metadata"))
    missing_keys = REQUIRED_METADATA - set(metadata)
    if missing_keys:
        fail(f"{path}: missing metadata keys {sorted(missing_keys)}")
    if metadata["format"] != "pbf":
        fail(f"{path}: format is {metadata['format']!r}, expected 'pbf'")
    minzoom, maxzoom = int(metadata["minzoom"]), int(metadata["maxzoom"])
    if not 0 <= minzoom <= maxzoom <= 22:
        fail(f"{path}: implausible zoom range {minzoom}..{maxzoom}")

    rows = list(conn.execute(
        "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles ORDER BY 1, 2, 3"))
    if not rows:
        fail(f"{path}: no tiles")
    seen = set()
    for zoom, column, row, data in rows:
        if not (minzoom <= zoom <= maxzoom):
            fail(f"{path}: tile zoom {zoom} outside metadata range {minzoom}..{maxzoom}")
        if (zoom, column, row) in seen:
            fail(f"{path}: duplicate tile {zoom}/{column}/{row}")
        seen.add((zoom, column, row))
        if not data:
            fail(f"{path}: empty tile {zoom}/{column}/{row}")
        try:
            gzip.decompress(data)
        except (OSError, EOFError, zlib.error) as error:
            fail(f"{path}: tile {zoom}/{column}/{row} is not valid gzip: {error}")

    stride = max(1, len(rows) // sample)
    decoded = 0
    for zoom, column, row, data in rows[::stride][:sample]:
        try:
            tile = mapbox_vector_tile.decode(gzip.decompress(data))
        except Exception as error:  # decoder raises several unrelated types
            fail(f"{path}: tile {zoom}/{column}/{row} is not valid MVT: {error}")
        unknown = set(tile) - LAYERS
        if unknown:
            fail(f"{path}: tile {zoom}/{column}/{row} has unknown layers {sorted(unknown)}")
        for name, layer in tile.items():
            if layer["extent"] <= 0:
                fail(f"{path}: tile {zoom}/{column}/{row} layer {name} has extent {layer['extent']}")
            for feature in layer["features"]:
                if not feature.get("geometry"):
                    fail(f"{path}: tile {zoom}/{column}/{row} layer {name} has an empty geometry")
        decoded += 1

    counts = {name: conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
              for name in GEOCODER_TABLES}
    for name in ("places", "place_streets", "place_street_tiles"):
        if counts[name] == 0:
            fail(f"{path}: geocoding table {name} is empty")
    orphan = conn.execute(
        "SELECT count(*) FROM place_streets s LEFT JOIN places p ON p.id = s.place_id "
        "WHERE p.id IS NULL").fetchone()[0]
    if orphan:
        fail(f"{path}: {orphan} place_streets rows reference a missing place")
    orphan = conn.execute(
        "SELECT count(*) FROM place_aliases a LEFT JOIN places p ON p.id = a.place_id "
        "WHERE p.id IS NULL").fetchone()[0]
    if orphan:
        fail(f"{path}: {orphan} place_aliases rows reference a missing place")

    return len(rows), decoded, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--sample", type=int, default=200,
                        help="maximum number of tiles to decode as MVT (default 200)")
    args = parser.parse_args()
    if not args.path.is_file():
        fail(f"{args.path}: no such file")
    conn = sqlite3.connect(f"file:{args.path}?mode=ro", uri=True)
    try:
        tiles, decoded, counts = check(conn, args.path, args.sample)
    finally:
        conn.close()
    print(f"{args.path}: {tiles} tiles ok, {decoded} decoded, "
          f"{counts['places']} places, {counts['place_streets']} streets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
