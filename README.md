# Librescoot OSM Tiles

Vector tiles for Librescoot's offline map display, generated from OpenStreetMap data using [Tilemaker](https://github.com/systemed/tilemaker). Includes street names, speed limits, 3D buildings, addresses, and water features — everything scootui needs to render the map and drive navigation.

Part of the [Librescoot](https://librescoot.org/) open-source platform.

## Layers

Every tile file includes all 7 layers. There's a single tile variant per region, not separate "standard" / "address" sets.

| Layer | Zoom | Geometry | Key Attributes |
|-------|------|----------|----------------|
| **streets** | 10–14 | line | `kind`, `name`, `ref`, `route_networks`, `maxspeed`, `oneway`, `bridge`, `tunnel`, `surface`, `lanes` |
| **street_labels** | 10–14 | point | `kind`, `name`, `ref` |
| **buildings** | 13–14 | polygon | `kind`, `render_height`, `render_min_height` |
| **addresses** | 14 | point | `housenumber`, `street`, `city`, `postcode`, `suburb`, `name` |
| **water_polygons** | 0–14 | polygon | `kind`, `name` |
| **water_lines** | 8–14 | line | `kind`, `name` |
| **land** | 0–14 | polygon | `kind` |

### Streets

Road types: motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street, service, pedestrian, track, path, footway, cycleway, steps, busway, taxiway.

`route_networks` is a semicolon-separated list of the way's `route=road` relation networks (for example, `DE:national;e-road`).

`maxspeed` values come directly from OSM — numeric ("50", "100") or symbolic ("DE:urban", "DE:motorway"). scootui's speed limit display handles both.

### Buildings

3D extrusion attributes (`render_height`, `render_min_height`) are derived from `building:height`, `height`, `building:levels`, or a 10 m default. scootui's map style uses these via `fill-extrusion` for the 3D building layer.

### Addresses

Extracted from both standalone `addr:*` nodes and building centroids that carry address tags. Available at zoom 14 only.

## Geocoding Index Tables

In addition to the MVT layers above, each `.mbtiles` ships a small SQLite-only geocoding index, built from administrative boundary polygons (kreisfreie Stadt L6 with `de:place=city`, Gemeinde L8, Stadtbezirk L9). scootui-qt reads these directly instead of iterating tiles to build its own address database.

| Table | Purpose |
|-------|---------|
| **`places`** | One row per place polygon (admin_level, name, name:de/en/alt, population, address_count, street_count, centroid, bbox, polygon_wkb) |
| **`place_aliases`** | All searchable name variants → place_id, including `name`, `name:de`, `name:en`, `name:nl`, `name:fr`, `name:lb`, `name:it`, `alt_name`, `old_name`, and hyphenated-name segments (so "Schwabing" finds both Schwabing-West and Schwabing-Freimann; "Liège" also matches "Lüttich" and "Luik") |
| **`place_streets`** | One row per (place_id, street) with display name, centroid, and address count |
| **`place_postcodes`** | Postcode-specific centroids per (place_id, street, postcode) |
| **`place_street_tiles`** | Exact zoom-14 tile coverage per (place_id, street, postcode), allowing house-number lookup to decode only relevant tiles instead of a fixed 7×7 window |

The polygon assignment uses point-in-polygon against admin boundaries — a München address ends up in both the L6 polygon (München) and an L9 polygon (its Stadtbezirk), so the user can search by either. Aliases run through `normalize()` (see `build_places.py` and the matching `AddressDatabaseService::normalize()` in scootui-qt) so French/Lux/Dutch/Italian diacritics fold to plain ASCII at index time.

## Generated Files

Monthly CI builds produce one `.mbtiles` file per region. German states use per-state extracts; Benelux uses country-level extracts; France uses regional extracts (Île-de-France and Alsace); Mallorca is covered by the Islas Baleares extract; Graz and Vienna are clipped from Geofabrik's Austria extract; Kanton Zürich is clipped from Geofabrik's Switzerland extract with an approximately 20 km buffer (within Switzerland); Italy uses Geofabrik's macro-area extracts (Nord-Ovest covers Lombardy plus Piedmont, Liguria and Aosta Valley — Geofabrik offers no per-regione extracts). Berlin and Brandenburg are combined into a single file because the Geofabrik Brandenburg extract already covers Berlin.

| Region | Approx. Size |
|--------|-------------|
| `tiles_alsace.mbtiles` | 83 MB |
| `tiles_baden-wuerttemberg.mbtiles` | 274 MB |
| `tiles_bayern.mbtiles` | 340 MB |
| `tiles_belgium.mbtiles` | 351 MB |
| `tiles_berlin_brandenburg.mbtiles` | 125 MB |
| `tiles_bremen.mbtiles` | 9 MB |
| `tiles_hamburg.mbtiles` | 19 MB |
| `tiles_graz.mbtiles` | 25 MB |
| `tiles_hessen.mbtiles` | 152 MB |
| `tiles_ile-de-france.mbtiles` | 142 MB |
| `tiles_islas-baleares.mbtiles` | 31 MB |
| `tiles_italy-nord-ovest.mbtiles` | first build pending |
| `tiles_luxembourg.mbtiles` | 16 MB |
| `tiles_mecklenburg-vorpommern.mbtiles` | 54 MB |
| `tiles_netherlands.mbtiles` | 541 MB |
| `tiles_niedersachsen.mbtiles` | 236 MB |
| `tiles_nordrhein-westfalen.mbtiles` | 422 MB |
| `tiles_rheinland-pfalz.mbtiles` | 116 MB |
| `tiles_saarland.mbtiles` | 26 MB |
| `tiles_sachsen.mbtiles` | 103 MB |
| `tiles_sachsen-anhalt.mbtiles` | 79 MB |
| `tiles_schleswig-holstein.mbtiles` | 74 MB |
| `tiles_thueringen.mbtiles` | 70 MB |
| `tiles_vienna.mbtiles` | 39 MB |
| `tiles_zurich.mbtiles` | first build pending |

Sizes are from the most recent release and will vary slightly between builds as OSM data changes.

## Installation

Download the `.mbtiles` file for your region from [downloads.librescoot.org](https://downloads.librescoot.org/), rename it to `map.mbtiles`, and copy it to the DBC's `/data/maps/` directory — either via USB update mode or directly via the [data-server](https://github.com/librescoot/data-server) HTTP API.

## Local Development

### Generate Tiles

```bash
# Download a regional OSM extract
bash download-pbf.sh https://download.geofabrik.de/europe/germany/brandenburg-latest.osm.pbf /tmp/brandenburg.osm.pbf

# Build the pinned generator (see "Generator" below)
docker build -t tilemaker-deterministic tools/tilemaker

# Generate tiles
docker run --rm \
  -v "$(pwd):/var/tm" \
  -v "/tmp:/tmp" \
  -w /var/tm \
  tilemaker-deterministic \
    --config tilemaker/config.json \
    --process tilemaker/process.lua \
    --input /tmp/brandenburg.osm.pbf \
    --output tiles-output/tiles_berlin_brandenburg.mbtiles

# Add the geocoding index tables the dashboard searches
python3 build_places.py /tmp/brandenburg.osm.pbf tiles-output/tiles_berlin_brandenburg.mbtiles

# Check the result the same way CI does
python3 tools/verify-mbtiles.py tiles-output/tiles_berlin_brandenburg.mbtiles
```

Or use the batch script to generate all states:

```bash
./generate-tiles.sh
```

### Customizing

- **tilemaker/config.json** — layer definitions, zoom ranges, simplification
- **tilemaker/process.lua** — OSM tag extraction, attribute mapping, zoom-level assignment

Test changes on a small region (Bremen at 9 MB, Luxembourg at 16 MB) before running the full set.

### Performance

| Region | Time | RAM |
|--------|------|-----|
| Bremen | ~1 min | ~2 GB |
| Berlin/Brandenburg | ~5 min | ~4 GB |
| Nordrhein-Westfalen | ~30 min | ~16 GB |
| Netherlands | ~25 min | ~14 GB |

## Automated Builds

GitHub Actions generates tiles for all 24 regions monthly on the 1st ([workflow](.github/workflows/generate-tiles.yml)). Each region runs in parallel. Results are published as timestamped GitHub releases. The Austrian city extracts are prepared once per run from the ~810 MB country PBF (about 1 GB peak disk), with a 3 GB free-space check; the source and extracts are deleted from the runner after upload. Each regional job removes its input PBF and output tile after uploading the artifact.

PBF downloads require `curl` and GNU `date`. They log errors and retry up to three times. If a Geofabrik `latest` URL fails, the downloader tries the previous UTC day's dated extract without falling back to older data. Downloads are staged in temporary files and renamed only after a successful, nonempty response.

Manual trigger: Actions → "Generate Custom Shortbread Tiles - Germany + Benelux + France + Italy + Spain + Austria" → Run workflow. Enter `all` or comma-separated region IDs such as `alsace,islas-baleares,graz,vienna`. A successful build on `main` publishes a timestamped release with only the selected regions; builds on other branches leave workflow artifacts. Monthly runs build the full list in `.github/regions.json`.

Each release also carries map deltas for the region's recent published versions. Each region runs the whole sequence in its own job (build, geocoding index, verification, deltas), so a finished region starts its deltas while the others are still building; only the release waits for all of them. `MAP_DELTA_BASES` sets how many earlier releases each region is patched against (default 2). The recovery path (`reuse_run_id`) builds deltas as one job per region too, bounded by `MAP_DELTA_CONCURRENCY` (default 4).
The patch is an HDiffPatch stream over `tools/canonical-mbtiles.py`'s canonical
form (schema, rows in a fixed order, decompressed tile payloads), wrapped in a
small header with the base and target canonical hashes. Deltas refer to
immutable earlier releases, so they keep working and are never rewritten; a
vehicle can update from any version that still has one, and falls back to the
full file otherwise. The canonical format is also implemented on the dashboard;
`tools/canonical-mbtiles.py` is the reference for it.

Jobs hand tiles to each other through the runner's own disk
(`$HOME/.cache/librescoot-tiles`, or the repository variable `TILE_CACHE_DIR`)
instead of downloading them again: the build job stores each verified region
with `tools/tile-cache.sh`, and the delta and release jobs take it from there,
falling back to the workflow artifact only when the runner has no copy. Base
releases for the deltas are cached the same way by `tools/create-map-deltas.py`,
verified against the release's own digest before use. After a release is
published its files simply become the next run's delta bases (moved from the
run's folder to the base cache), so a monthly run downloads no base at all for
the newest version and only the older one if it was never cached. A run's own
tiles are removed once published; a failsafe drops runs older than 14 days that
never published, such as branch runs.

To publish from tiles that an earlier run already built and verified, start the
workflow with `reuse_run_id` set to that run's ID (and the same regions). The
tile build is skipped; deltas are built and the release is published from that
run's artifacts. This recovers from a failure in the delta or release step
without rebuilding every region.

A branch run stops at workflow artifacts: it builds and verifies the tiles but does not create a release, so a generator change can be tried on a scooter without moving the public per-region index. `tools/verify-mbtiles.py` opens every file read-only, checks SQLite integrity, metadata, every tile's gzip stream, a sample of decoded vector tiles and the geocoding tables, and fails the region job on any problem.

## Technical Details

- **Format**: MBTiles (SQLite + gzip-compressed PBF vector tiles)
- **Zoom**: 0–14
- **Projection**: Web Mercator (EPSG:3857)
- **Source**: [Geofabrik](https://download.geofabrik.de/europe/) regional extracts of [OpenStreetMap](https://www.openstreetmap.org)
- **Generator**: [Tilemaker](https://github.com/systemed/tilemaker), built from the commit pinned in `tools/tilemaker/Dockerfile` ([upstream PR 981](https://github.com/systemed/tilemaker/pull/981)), which makes tile content independent of thread scheduling
- **Verification**: `tools/verify-mbtiles.py` runs on every built region before upload
- **Deltas**: `tools/create-map-deltas.py` publishes `tiles_<region>.from-<base-version>.hdelta` next to each release, patching the canonical tile stream of up to two recent published bases

## License

Generated tiles contain OpenStreetMap data under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).

This project is dual-licensed. The source code is available under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].
The maintainers reserve the right to grant separate licenses for commercial distribution; please contact the maintainers to discuss commercial licensing.

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
