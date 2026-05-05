#!/usr/bin/env python3
"""
Build the geocoding index sidecar inside an mbtiles file.

Reads the OSM PBF for the same region as the mbtiles, extracts administrative
boundary polygons (kreisfreie Stadt L6 with de:place=city, Gemeinde L8,
Stadtbezirk L9), runs PIP for every address point in the addresses MVT layer,
aggregates centroids per (place, street) and (place, street, postcode), and
writes four tables alongside the existing tiles + metadata:

    places           — all admin polygons with stats (one row per place)
    place_aliases    — searchable name variants → place_id (lookup index)
    place_streets    — pre-aggregated streets per place + centroid
    place_postcodes  — pre-aggregated postcode-specific centroids per street

The device-side AddressDatabaseService just reads these tables; no tile
iteration, no PIP, no on-device alias generation.
"""

import argparse
import gzip
import math
import re
import sqlite3
import sys
import time
from collections import defaultdict

import mapbox_vector_tile
import osmium
import shapely.wkb
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.strtree import STRtree


SIMPLIFY_TOLERANCE_DEG = 0.0005   # ~50 m at mid-latitudes
ADMIN_LEVELS = {"6", "8", "9"}
DIRECTION_STOP = {"West", "Ost", "Nord", "Süd"}
STREET_NAME_SUFFIX_RE = re.compile(
    r"(straße|strasse|weg|allee|gasse|platz|ring)$", re.IGNORECASE
)


def normalize(name: str) -> str:
    """Mirrors AddressDatabaseService::normalize() in scootui-qt.

    Critical: this must produce identical output to the C++ implementation,
    otherwise the device-side trie lookup won't match the server-side index.
    """
    out = []
    for c in name:
        u = ord(c)
        if u in (0x00C4, 0x00E4):
            out.append("ae")
        elif u in (0x00D6, 0x00F6):
            out.append("oe")
        elif u in (0x00DC, 0x00FC):
            out.append("ue")
        elif u == 0x00DF:
            out.append("ss")
        elif c.isalnum():
            out.append(c.lower())
        elif c in (" ", "-"):
            out.append(c)
    r = "".join(out)
    r = r.replace("str ", "strasse ")
    if r.endswith("str"):
        r = r[:-3] + "strasse"
    r = r.replace("pl ", "platz ")
    if r.endswith("pl"):
        r = r[:-2] + "platz"
    return r


def gen_aliases(tags: dict, name: str):
    """Yield (display, normalized, source) per alias.

    Sources:
        name        canonical OSM name tag
        name:de     German variant
        name:en     English variant (catches Munich/Köln/etc.)
        alt_name    semicolon-separated alternates
        old_name    historical names
        segment     hyphenated-name parts (Schwabing-West → "Schwabing")
    """
    seen = {}

    def add(disp: str, source: str):
        nrm = normalize(disp)
        if not nrm or nrm in seen:
            return
        seen[nrm] = (disp, source)

    if name:
        add(name, "name")
    for src_key, label in (("name:de", "name:de"),
                            ("name:en", "name:en"),
                            ("alt_name", "alt_name"),
                            ("old_name", "old_name")):
        v = tags.get(src_key)
        if not v:
            continue
        for part in re.split(r"[;,]", v):
            p = part.strip()
            if p:
                add(p, label)
    if name and "-" in name:
        for seg in name.split("-"):
            seg = seg.strip()
            if len(seg) >= 4 and seg not in DIRECTION_STOP:
                add(seg, "segment")
    return [(d, n, s) for n, (d, s) in seen.items()]


class PlaceCollector(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.wkbfab = osmium.geom.WKBFactory()
        self.places = []
        self.skipped_invalid = 0
        self.skipped_l6_non_city = 0
        self.skipped_named_like_street = 0

    def area(self, a):
        tags = a.tags
        if tags.get("boundary") != "administrative":
            return
        level = tags.get("admin_level")
        if level not in ADMIN_LEVELS:
            return
        if level == "6" and tags.get("de:place") != "city":
            self.skipped_l6_non_city += 1
            return

        name = tags.get("name", "")
        if not name:
            self.skipped_invalid += 1
            return
        # Some OSM contributors mistag streets as admin boundaries; filter
        # those by name shape so they don't pollute the place list.
        if STREET_NAME_SUFFIX_RE.search(name):
            self.skipped_named_like_street += 1
            return
        if re.match(r"^[\d.]+$", name):
            self.skipped_invalid += 1
            return

        try:
            wkb_hex = self.wkbfab.create_multipolygon(a)
            geom = shapely.wkb.loads(bytes.fromhex(wkb_hex))
        except Exception:
            self.skipped_invalid += 1
            return
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            self.skipped_invalid += 1
            return

        simple = geom.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        if simple.is_empty or not simple.is_valid:
            simple = geom
        if isinstance(simple, Polygon):
            simple = MultiPolygon([simple])

        pop = tags.get("population", "") or ""
        try:
            pop_int = int(pop) if pop.isdigit() else 0
        except ValueError:
            pop_int = 0

        centroid = simple.representative_point()
        minx, miny, maxx, maxy = simple.bounds

        # Capture tags as a plain dict — pyosmium TagList becomes invalid
        # after the callback returns.
        tag_dict = {k: v for k, v in tags}

        self.places.append({
            "id": a.orig_id(),
            "admin_level": int(level),
            "name": name,
            "name_de": tag_dict.get("name:de"),
            "name_en": tag_dict.get("name:en"),
            "alt_names": tag_dict.get("alt_name"),
            "de_place": tag_dict.get("de:place"),
            "population": pop_int,
            "centroid_lat": centroid.y,
            "centroid_lng": centroid.x,
            "bbox_min_lat": miny, "bbox_min_lng": minx,
            "bbox_max_lat": maxy, "bbox_max_lng": maxx,
            "polygon_wkb": shapely.wkb.dumps(simple),
            "_tags": tag_dict,
            "_geom": simple,
        })


SCHEMA_SQL = """
CREATE TABLE places (
    id INTEGER PRIMARY KEY,
    admin_level INTEGER NOT NULL,
    name TEXT NOT NULL,
    name_de TEXT,
    name_en TEXT,
    alt_names TEXT,
    de_place TEXT,
    population INTEGER NOT NULL DEFAULT 0,
    address_count INTEGER NOT NULL DEFAULT 0,
    street_count INTEGER NOT NULL DEFAULT 0,
    centroid_lat REAL NOT NULL,
    centroid_lng REAL NOT NULL,
    bbox_min_lat REAL NOT NULL,
    bbox_min_lng REAL NOT NULL,
    bbox_max_lat REAL NOT NULL,
    bbox_max_lng REAL NOT NULL,
    polygon_wkb BLOB NOT NULL
);
CREATE INDEX idx_places_bbox
    ON places(bbox_min_lat, bbox_max_lat, bbox_min_lng, bbox_max_lng);

CREATE TABLE place_aliases (
    alias_norm TEXT NOT NULL,
    place_id INTEGER NOT NULL,
    alias_display TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (alias_norm, place_id)
);
CREATE INDEX idx_place_aliases_norm ON place_aliases(alias_norm);
CREATE INDEX idx_place_aliases_place ON place_aliases(place_id);

CREATE TABLE place_streets (
    place_id INTEGER NOT NULL,
    street_norm TEXT NOT NULL,
    street_display TEXT NOT NULL,
    centroid_lat REAL NOT NULL,
    centroid_lng REAL NOT NULL,
    address_count INTEGER NOT NULL,
    PRIMARY KEY (place_id, street_norm)
);
CREATE INDEX idx_place_streets_place ON place_streets(place_id);

CREATE TABLE place_postcodes (
    place_id INTEGER NOT NULL,
    street_norm TEXT NOT NULL,
    postcode TEXT NOT NULL,
    centroid_lat REAL NOT NULL,
    centroid_lng REAL NOT NULL,
    PRIMARY KEY (place_id, street_norm, postcode)
);
"""


def reset_schema(db):
    cur = db.cursor()
    for tbl in ("place_postcodes", "place_streets", "place_aliases", "places"):
        cur.execute(f"DROP TABLE IF EXISTS {tbl}")
    cur.executescript(SCHEMA_SQL)


def index_addresses(db, places, place_geoms, tree):
    """Iterate address tiles, PIP, aggregate per place/street/postcode."""
    place_addr_count = defaultdict(int)
    place_streets_seen = defaultdict(set)
    # (place_id, street_norm) -> [count, sum_lat, sum_lng, display]
    street_runs = {}
    # (place_id, street_norm, postcode) -> [count, sum_lat, sum_lng]
    pc_runs = {}

    addr_total = 0
    unassigned = 0
    n = 1 << 14

    cur = db.execute("""
        SELECT tile_column, tile_row, tile_data
        FROM tiles WHERE zoom_level=14
    """)
    for x, tms_y, blob in cur:
        try:
            data = gzip.decompress(blob)
            tile = mapbox_vector_tile.decode(data)
        except Exception:
            continue
        layer = tile.get("addresses")
        if not layer:
            continue
        extent = layer.get("extent", 4096)

        for feat in layer["features"]:
            if feat["geometry"]["type"] != "Point":
                continue
            addr_total += 1
            px, py = feat["geometry"]["coordinates"]
            lon = (x + px / extent) / n * 360.0 - 180.0
            slippy_y = n - 1 - tms_y
            ymerc = (slippy_y + 1 - py / extent) / n
            zz = math.pi * (1 - 2 * ymerc)
            lat = math.degrees(math.atan(math.sinh(zz)))

            props = feat["properties"]
            street = (props.get("street") or props.get("name") or "").strip()
            if not street:
                continue
            street_norm = normalize(street)
            if not street_norm:
                continue
            postcode = (props.get("postcode") or "").strip()

            pt = Point(lon, lat)
            matched = False
            for idx in tree.query(pt):
                if not place_geoms[idx].contains(pt):
                    continue
                pid = places[idx]["id"]
                matched = True
                place_addr_count[pid] += 1
                place_streets_seen[pid].add(street_norm)

                sk = (pid, street_norm)
                sr = street_runs.get(sk)
                if sr is None:
                    sr = [0, 0.0, 0.0, street]
                    street_runs[sk] = sr
                sr[0] += 1
                sr[1] += lat
                sr[2] += lon

                if postcode:
                    pk = (pid, street_norm, postcode)
                    pr = pc_runs.get(pk)
                    if pr is None:
                        pr = [0, 0.0, 0.0]
                        pc_runs[pk] = pr
                    pr[0] += 1
                    pr[1] += lat
                    pr[2] += lon
            if not matched:
                unassigned += 1

    return {
        "addr_total": addr_total,
        "unassigned": unassigned,
        "place_addr_count": place_addr_count,
        "place_streets_seen": place_streets_seen,
        "street_runs": street_runs,
        "pc_runs": pc_runs,
    }


def write_tables(db, places, idx):
    cur = db.cursor()

    place_rows = []
    for p in places:
        addrs = idx["place_addr_count"].get(p["id"], 0)
        streets = len(idx["place_streets_seen"].get(p["id"], ()))
        place_rows.append((
            p["id"], p["admin_level"], p["name"], p["name_de"], p["name_en"],
            p["alt_names"], p["de_place"], p["population"], addrs, streets,
            p["centroid_lat"], p["centroid_lng"],
            p["bbox_min_lat"], p["bbox_min_lng"],
            p["bbox_max_lat"], p["bbox_max_lng"],
            p["polygon_wkb"],
        ))
    cur.executemany(
        "INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        place_rows,
    )

    alias_rows = []
    for p in places:
        for disp, nrm, src in gen_aliases(p["_tags"], p["name"]):
            alias_rows.append((nrm, p["id"], disp, src))
    cur.executemany(
        "INSERT OR IGNORE INTO place_aliases VALUES (?,?,?,?)",
        alias_rows,
    )

    street_rows = [
        (pid, snorm, disp, sum_lat / count, sum_lng / count, count)
        for (pid, snorm), (count, sum_lat, sum_lng, disp) in idx["street_runs"].items()
        if count > 0
    ]
    cur.executemany(
        "INSERT INTO place_streets VALUES (?,?,?,?,?,?)",
        street_rows,
    )

    pc_rows = [
        (pid, snorm, pc, sum_lat / count, sum_lng / count)
        for (pid, snorm, pc), (count, sum_lat, sum_lng) in idx["pc_runs"].items()
        if count > 0
    ]
    cur.executemany(
        "INSERT INTO place_postcodes VALUES (?,?,?,?,?)",
        pc_rows,
    )

    return len(place_rows), len(alias_rows), len(street_rows), len(pc_rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pbf", help="Input OSM PBF file")
    ap.add_argument("mbtiles", help="Output .mbtiles (modified in place)")
    ap.add_argument("--idx", default="sparse_mem_array",
                    help="pyosmium node index backend")
    args = ap.parse_args()

    t0 = time.time()
    print(f"[1/4] Extracting place polygons from {args.pbf}", flush=True)
    h = PlaceCollector()
    h.apply_file(args.pbf, locations=True, idx=args.idx)
    print(f"      {len(h.places)} places, "
          f"{h.skipped_l6_non_city} L6 non-city skipped, "
          f"{h.skipped_named_like_street} named-like-street skipped, "
          f"{h.skipped_invalid} invalid skipped — {time.time()-t0:.1f}s",
          flush=True)
    by_lvl = defaultdict(int)
    for p in h.places:
        by_lvl[p["admin_level"]] += 1
    for lvl in sorted(by_lvl):
        print(f"        L{lvl}: {by_lvl[lvl]}", flush=True)

    place_geoms = [p["_geom"] for p in h.places]
    tree = STRtree(place_geoms)

    print(f"[2/4] Indexing addresses against places", flush=True)
    t1 = time.time()
    db = sqlite3.connect(args.mbtiles)
    idx = index_addresses(db, h.places, place_geoms, tree)
    pct = 100 * idx["unassigned"] / max(1, idx["addr_total"])
    print(f"      {idx['addr_total']} addresses, "
          f"{idx['unassigned']} unassigned ({pct:.2f}%) — "
          f"{time.time()-t1:.0f}s", flush=True)

    print(f"[3/4] Writing tables", flush=True)
    t2 = time.time()
    reset_schema(db)
    np, na, ns, npc = write_tables(db, h.places, idx)
    db.commit()
    print(f"      places={np} aliases={na} streets={ns} postcodes={npc} — "
          f"{time.time()-t2:.1f}s", flush=True)

    sz_poly = db.execute("SELECT SUM(LENGTH(polygon_wkb)) FROM places").fetchone()[0] or 0
    print(f"[4/4] Done in {time.time()-t0:.0f}s "
          f"(polygon_wkb total: {sz_poly/1024:.0f} KiB)", flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
