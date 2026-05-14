# Librescoot OSM Tiles

Vector tiles for Librescoot's offline map display, generated from OpenStreetMap data using [Tilemaker](https://github.com/systemed/tilemaker). Includes street names, speed limits, 3D buildings, addresses, and water features — everything scootui needs to render the map and drive navigation.

Part of the [Librescoot](https://librescoot.org/) open-source platform.

## Layers

Every tile file includes all 7 layers. There's a single tile variant per region, not separate "standard" / "address" sets.

| Layer | Zoom | Geometry | Key Attributes |
|-------|------|----------|----------------|
| **streets** | 10–14 | line | `kind`, `name`, `ref`, `maxspeed`, `oneway`, `bridge`, `tunnel`, `surface`, `lanes` |
| **street_labels** | 10–14 | point | `kind`, `name`, `ref` |
| **buildings** | 13–14 | polygon | `kind`, `render_height`, `render_min_height` |
| **addresses** | 14 | point | `housenumber`, `street`, `city`, `postcode`, `suburb`, `name` |
| **water_polygons** | 0–14 | polygon | `kind`, `name` |
| **water_lines** | 8–14 | line | `kind`, `name` |
| **land** | 0–14 | polygon | `kind` |

### Streets

Road types: motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street, service, pedestrian, track, path, footway, cycleway, steps, busway, taxiway.

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
| **`place_aliases`** | All searchable name variants → place_id, including `name`, `name:de`, `name:en`, `name:nl`, `name:fr`, `name:lb`, `alt_name`, `old_name`, and hyphenated-name segments (so "Schwabing" finds both Schwabing-West and Schwabing-Freimann; "Liège" also matches "Lüttich" and "Luik") |
| **`place_streets`** | One row per (place_id, street) with display name, centroid, and address count |
| **`place_postcodes`** | Postcode-specific centroids per (place_id, street, postcode) |

The polygon assignment uses point-in-polygon against admin boundaries — a München address ends up in both the L6 polygon (München) and an L9 polygon (its Stadtbezirk), so the user can search by either. Aliases run through `normalize()` (see `build_places.py` and the matching `AddressDatabaseService::normalize()` in scootui-qt) so French/Lux/Dutch diacritics fold to plain ASCII at index time.

## Generated Files

Monthly CI builds produce one `.mbtiles` file per region. German states use per-state extracts; Benelux uses country-level extracts; France is added at region granularity (just Île-de-France for now). Berlin and Brandenburg are combined into a single file because the Geofabrik Brandenburg extract already covers Berlin.

| Region | Approx. Size |
|--------|-------------|
| `tiles_baden-wuerttemberg.mbtiles` | 274 MB |
| `tiles_bayern.mbtiles` | 340 MB |
| `tiles_belgium.mbtiles` | 351 MB |
| `tiles_berlin_brandenburg.mbtiles` | 125 MB |
| `tiles_bremen.mbtiles` | 9 MB |
| `tiles_hamburg.mbtiles` | 19 MB |
| `tiles_hessen.mbtiles` | 152 MB |
| `tiles_ile-de-france.mbtiles` | 142 MB |
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

Sizes are from the most recent release and will vary slightly between builds as OSM data changes.

## Installation

Download the `.mbtiles` file for your region from the [latest release](../../releases/tag/latest), rename it to `map.mbtiles`, and copy it to the DBC's `/data/maps/` directory — either via USB update mode or directly via the [data-server](https://github.com/librescoot/data-server) HTTP API.

## Local Development

### Generate Tiles

```bash
# Download a regional OSM extract
wget https://download.geofabrik.de/europe/germany/brandenburg-latest.osm.pbf -O /tmp/brandenburg.osm.pbf

# Generate tiles
docker run --rm \
  -v "$(pwd):/var/tm" \
  -v "/tmp:/tmp" \
  -w /var/tm \
  --entrypoint tilemaker \
  versatiles/versatiles-tilemaker \
    --config tilemaker/config.json \
    --process tilemaker/process.lua \
    --input /tmp/brandenburg.osm.pbf \
    --output tiles-output/tiles_berlin_brandenburg.mbtiles
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

GitHub Actions generates tiles for all 19 regions monthly on the 3rd ([workflow](.github/workflows/generate-tiles.yml)). Each region runs in parallel. Results are published as a GitHub release tagged `latest`.

Manual trigger: Actions → "Generate Custom Shortbread Tiles - Germany + Benelux + France" → Run workflow.

## Technical Details

- **Format**: MBTiles (SQLite + gzip-compressed PBF vector tiles)
- **Zoom**: 0–14
- **Projection**: Web Mercator (EPSG:3857)
- **Source**: [Geofabrik](https://download.geofabrik.de/europe/) regional extracts of [OpenStreetMap](https://www.openstreetmap.org)
- **Generator**: [Tilemaker](https://github.com/systemed/tilemaker) via the [versatiles](https://versatiles.org) Docker image

## License

Generated tiles contain OpenStreetMap data under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).

This project is dual-licensed. The source code is available under the
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].
The maintainers reserve the right to grant separate licenses for commercial distribution; please contact the maintainers to discuss commercial licensing.

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
