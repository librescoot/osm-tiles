# LibreScoot OSM Tiles

Vector tiles for LibreScoot's offline map display, generated from OpenStreetMap data using [Tilemaker](https://github.com/systemed/tilemaker). Includes street names, speed limits, 3D buildings, addresses, and water features — everything scootui needs to render the map and drive navigation.

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

## Generated Files

Monthly CI builds produce one `.mbtiles` file per region. Berlin and Brandenburg are combined into a single file because the Geofabrik extract covers Brandenburg (which contains Berlin).

| Region | Approx. Size |
|--------|-------------|
| `tiles_baden-wuerttemberg.mbtiles` | 302 MB |
| `tiles_bayern.mbtiles` | 367 MB |
| `tiles_berlin_brandenburg.mbtiles` | 134 MB |
| `tiles_bremen.mbtiles` | 11 MB |
| `tiles_hamburg.mbtiles` | 22 MB |
| `tiles_hessen.mbtiles` | 163 MB |
| `tiles_mecklenburg-vorpommern.mbtiles` | 57 MB |
| `tiles_niedersachsen.mbtiles` | 253 MB |
| `tiles_nordrhein-westfalen.mbtiles` | 475 MB |
| `tiles_rheinland-pfalz.mbtiles` | 126 MB |
| `tiles_saarland.mbtiles` | 29 MB |
| `tiles_sachsen.mbtiles` | 113 MB |
| `tiles_sachsen-anhalt.mbtiles` | 84 MB |
| `tiles_schleswig-holstein.mbtiles` | 81 MB |
| `tiles_thueringen.mbtiles` | 75 MB |

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

Test changes on a small region (Bremen at 11 MB) before running the full set.

### Performance

| Region | Time | RAM |
|--------|------|-----|
| Bremen | ~1 min | ~2 GB |
| Berlin/Brandenburg | ~5 min | ~4 GB |
| Nordrhein-Westfalen | ~30 min | ~16 GB |

## Automated Builds

GitHub Actions generates all state tiles monthly on the 3rd ([workflow](.github/workflows/generate-tiles.yml)). Each state runs in parallel. Results are published as a GitHub release tagged `latest`.

Manual trigger: Actions → "Generate Custom Shortbread Tiles - Germany" → Run workflow.

## Technical Details

- **Format**: MBTiles (SQLite + gzip-compressed PBF vector tiles)
- **Zoom**: 0–14
- **Projection**: Web Mercator (EPSG:3857)
- **Source**: [Geofabrik](https://download.geofabrik.de/europe/germany.html) regional extracts of [OpenStreetMap](https://www.openstreetmap.org)
- **Generator**: [Tilemaker](https://github.com/systemed/tilemaker) via the [versatiles](https://versatiles.org) Docker image

## License

CC BY-NC-SA 4.0. Generated tiles contain OpenStreetMap data under the [Open Database License](http://opendatacommons.org/licenses/odbl/1.0/).
