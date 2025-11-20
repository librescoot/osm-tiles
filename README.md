# Custom Shortbread Tiles for LibreScoot

Automated generation of custom Shortbread-based vector tiles optimized for LibreScoot navigation with embedded speed limit data and optional address data.

## Overview

This repository automatically generates custom MBTiles from OpenStreetMap data using Tilemaker. Unlike downloading pre-built Shortbread tiles from Geofabrik, this approach gives us full control over:

- **Custom OSM tags**: Includes `maxspeed` (speed limits) in the streets layer
- **Layer optimization**: Only includes layers needed for scootui (streets, water_polygons, land)
- **Regional coverage**: Generates tiles for German states individually and combined

## Features

- Custom Shortbread schema based on OSM data
- Speed limit (maxspeed) data embedded in streets layer
- **Two tile variants**: Standard (speed limits only) and Address-enabled (includes address points)
- Minimal layer set for smaller file sizes and faster rendering
- Monthly automated builds via GitHub Actions
- Coverage: All 16 German states + combined Germany file

## Generated Files

Each monthly release includes two variants:

### Standard Tiles
Optimized for navigation with street names, road types, and speed limits.

**Individual State Files:**
- `tiles_baden-wuerttemberg.mbtiles` (~60-120 MB)
- `tiles_bayern.mbtiles` (~80-150 MB)
- `tiles_berlin.mbtiles` (~20-40 MB)
- `tiles_brandenburg.mbtiles` (~60-100 MB)
- `tiles_bremen.mbtiles` (~10-20 MB)
- `tiles_hamburg.mbtiles` (~15-30 MB)
- `tiles_hessen.mbtiles` (~60-100 MB)
- `tiles_mecklenburg-vorpommern.mbtiles` (~50-90 MB)
- `tiles_niedersachsen.mbtiles` (~80-140 MB)
- `tiles_nordrhein-westfalen.mbtiles` (~100-180 MB)
- `tiles_rheinland-pfalz.mbtiles` (~50-90 MB)
- `tiles_saarland.mbtiles` (~10-20 MB)
- `tiles_sachsen.mbtiles` (~50-90 MB)
- `tiles_sachsen-anhalt.mbtiles` (~50-90 MB)
- `tiles_schleswig-holstein.mbtiles` (~50-90 MB)
- `tiles_thueringen.mbtiles` (~40-80 MB)

**Combined File:**
- `tiles_germany.mbtiles` (~800 MB - 1.2 GB)

### Address-Enabled Tiles
Includes all standard features plus detailed address data for geocoding and reverse geocoding.

**Individual State Files:**
- `tiles_addresses_berlin.mbtiles` (~17 MB, 91k addresses)
- `tiles_addresses_brandenburg.mbtiles` (~51 MB, 248k addresses)
- `tiles_addresses_[state].mbtiles` (varies by state)

**Combined File:**
- `tiles_addresses_germany.mbtiles` (estimated ~1.5-2 GB)

## Tile Schema

### Layers

#### 1. streets (zoom 10-14)
Vector linestrings representing roads and paths.

**Attributes:**
- `kind`: Road type (motorway, trunk, primary, secondary, tertiary, residential, etc.)
- `name`: Street name (if available)
- `ref`: Route reference (e.g., "A7", "B27")
- `maxspeed`: Speed limit in km/h (e.g., "50", "100", "DE:urban")
- `oneway`: Boolean, true if one-way street
- `oneway_reverse`: Boolean, true if one-way in reverse direction
- `bridge`: Boolean, true if bridge
- `tunnel`: Boolean, true if tunnel
- `surface`: Surface type (paved, unpaved, asphalt, etc.)
- `lanes`: Number of lanes (if available)

**Road types included:**
- motorway, trunk, primary, secondary, tertiary
- unclassified, residential, living_street
- service, pedestrian, track, path
- footway, cycleway, steps, busway, taxiway

#### 2. water_polygons (zoom 0-14)
Polygon features for water bodies.

**Attributes:**
- `kind`: Water type (water, lake, reservoir, pond, etc.)
- `name`: Name of water body (if available)

**Zoom levels:** Larger water bodies appear at lower zoom levels (6-8), smaller ones at higher zoom levels (10-14).

#### 3. land (zoom 0-14)
Base layer polygons for land features.

**Attributes:**
- `kind`: Land type (wood, grassland, forest, farmland, residential, etc.)

#### 4. addresses (zoom 14 only) - Address-Enabled Tiles Only
Point features for addresses, available only in `tiles_addresses_*.mbtiles` files.

**Attributes:**
- `housenumber`: House number (e.g., "42", "12a")
- `street`: Street name
- `city`: City name
- `postcode`: Postal code
- `suburb`: Suburb or district name (if available)
- `name`: Place name (if available, e.g., for named buildings)

**Note:** Address layer only appears at maximum zoom (14) to avoid clutter at lower zoom levels. Addresses are extracted from both standalone address nodes and building centroids with address tags.

## Usage

### Download Latest Release

Visit the [Releases](../../releases) page and download the latest MBTiles files for your region.

### Integration with scootui

1. Download the appropriate regional or combined Germany MBTiles file
2. Place in scootui's map data directory
3. Configure scootui to use the MBTiles file
4. Access speed limit data from the streets layer's `maxspeed` attribute

Example using flutter_map with vector_map_tiles:

```dart
VectorTileLayer(
  tileProviders: TileProviders({
    'mbtiles': MbTilesVectorTileProvider.fromMbTilesArchive(
      mbTilesArchive: 'path/to/tiles_germany.mbtiles',
    ),
  }),
  // ... style configuration
)
```

### Accessing Speed Limit Data

Speed limits are stored in the `maxspeed` attribute of street features:

```dart
// In your map style or feature handler
final maxspeed = feature.properties['maxspeed'];
if (maxspeed != null) {
  print('Speed limit: $maxspeed km/h');
}
```

### Accessing Address Data (Address-Enabled Tiles)

Address data is available as point features in the `addresses` layer at zoom level 14:

```dart
// Accessing address points
final housenumber = feature.properties['housenumber'];
final street = feature.properties['street'];
final city = feature.properties['city'];
final postcode = feature.properties['postcode'];

if (housenumber != null && street != null) {
  print('Address: $street $housenumber, $postcode $city');
}
```

**Use cases for address data:**
- Reverse geocoding: Find address at a specific location
- Geocoding: Search for addresses and navigate to them
- Address validation: Verify if an address exists in the map data
- Address autocomplete: Suggest addresses as users type

## Local Development

### Prerequisites

- Docker
- wget or curl
- ~100 GB free disk space for Germany-wide generation

### Build Tilemaker Image

```bash
docker build -t tilemaker-custom .
```

### Generate Tiles Locally

#### Standard Tiles (Speed Limits)

**Single Region (e.g., Berlin):**

```bash
# Download OSM data
wget https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf

# Generate standard tiles
docker run --rm \
  -v $(pwd):/var/tm \
  -v /tmp:/tmp \
  -w /var/tm \
  --entrypoint tilemaker \
  versatiles/versatiles-tilemaker \
    --config tilemaker/config.json \
    --process tilemaker/process.lua \
    --input /tmp/berlin-latest.osm.pbf \
    --output tiles-output/tiles_berlin.mbtiles
```

#### Address-Enabled Tiles

**Single Region (e.g., Berlin):**

```bash
# Download OSM data
wget https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf -O /tmp/berlin.osm.pbf

# Generate address tiles
docker run --rm \
  -v $(pwd):/var/tm \
  -v /tmp:/tmp \
  -w /var/tm \
  --entrypoint tilemaker \
  versatiles/versatiles-tilemaker \
    --config tilemaker/config-addresses.json \
    --process tilemaker/process-addresses.lua \
    --input /tmp/berlin.osm.pbf \
    --output tiles-output/tiles_addresses_berlin.mbtiles
```

**Or use the convenience script:**

```bash
./generate-tiles-addresses.sh
```

#### All of Germany

```bash
# Download OSM data
wget https://download.geofabrik.de/europe/germany-latest.osm.pbf

# Generate tiles (requires significant RAM and time)
docker run --rm \
  -v $(pwd)/tilemaker:/config:ro \
  -v $(pwd):/data \
  tilemaker-custom \
  tilemaker \
    --input /data/germany-latest.osm.pbf \
    --output /data/tiles_germany.mbtiles \
    --config /config/config.json \
    --process /config/process.lua
```

**Performance notes:**
- Berlin: ~5-10 minutes, ~4 GB RAM
- Germany: ~2-4 hours, ~32-64 GB RAM

### Customizing the Schema

#### Modify Layers

Edit `tilemaker/config.json` to add/remove layers or adjust zoom levels.

#### Modify Processing Logic

Edit `tilemaker/process.lua` to change how OSM tags are processed or add new attributes.

#### Test Changes Locally

Use a small region like Berlin to quickly test changes before running the full workflow.

## Automated Builds

Tiles are automatically generated monthly on the 3rd via GitHub Actions.

### Manual Trigger

You can manually trigger tile generation:

1. Go to the "Actions" tab
2. Select "Generate Custom Shortbread Tiles - Germany"
3. Click "Run workflow"

### Workflow Overview

1. **Build**: Builds Tilemaker Docker image
2. **Generate State Tiles**: Parallel generation for all 16 German states
3. **Generate Combined Germany**: Single combined file for all of Germany
4. **Release**: Creates a release with all generated MBTiles files

## Technical Details

### Tile Format

- **Format**: MBTiles (SQLite database container)
- **Encoding**: Protocol Buffers (vector tiles)
- **Compression**: GZIP
- **Zoom levels**: 0-14
- **Projection**: Web Mercator (EPSG:3857)

### Data Source

- **OpenStreetMap**: https://www.openstreetmap.org
- **Geofabrik extracts**: https://download.geofabrik.de/europe/germany.html
- **Updated**: Monthly (Geofabrik updates daily, we build monthly)

### Comparison with Geofabrik Shortbread Tiles

| Feature | Geofabrik Shortbread | Our Custom Tiles |
|---------|---------------------|------------------|
| **Layers** | 20+ layers | 3 layers (streets, water_polygons, land) |
| **Speed limits** | Not included | Included in streets layer |
| **File size** | Larger (~150-200 MB per state) | Smaller (~60-120 MB per state) |
| **Customization** | Fixed schema | Fully customizable |
| **Generation** | Pre-built by Geofabrik | Generated by us from OSM data |

## Contributing

Contributions are welcome! Areas for improvement:

- Additional OSM tags (turn restrictions, access restrictions, etc.)
- Style optimization for specific use cases
- Performance improvements in processing
- Additional regions beyond Germany

## License

This project is licensed under CC BY-NC-SA 4.0.

The generated tiles contain OpenStreetMap data and are made available under the Open Database License: http://opendatacommons.org/licenses/odbl/1.0/. Any rights in individual contents of the database are licensed under the Database Contents License: http://opendatacommons.org/licenses/dbcl/1.0/

## Acknowledgments

- [OpenStreetMap](https://www.openstreetmap.org) contributors for the map data
- [Geofabrik](https://www.geofabrik.de) for OSM extracts
- [Tilemaker](https://github.com/systemed/tilemaker) for the tile generation tool
- [Shortbread](https://shortbread-tiles.org) for the schema specification
- LibreScoot community
