#!/bin/bash
set -e

# Create output directory
OUTPUT_DIR="./tiles-output"
mkdir -p "$OUTPUT_DIR"

# Regions to build (format: "name|url"). German states use per-state extracts;
# Benelux countries use country-level extracts as a single tile each.
REGIONS=(
    "baden-wuerttemberg|https://download.geofabrik.de/europe/germany/baden-wuerttemberg-latest.osm.pbf"
    "bayern|https://download.geofabrik.de/europe/germany/bayern-latest.osm.pbf"
    "berlin|https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf"
    "brandenburg|https://download.geofabrik.de/europe/germany/brandenburg-latest.osm.pbf"
    "bremen|https://download.geofabrik.de/europe/germany/bremen-latest.osm.pbf"
    "hamburg|https://download.geofabrik.de/europe/germany/hamburg-latest.osm.pbf"
    "hessen|https://download.geofabrik.de/europe/germany/hessen-latest.osm.pbf"
    "mecklenburg-vorpommern|https://download.geofabrik.de/europe/germany/mecklenburg-vorpommern-latest.osm.pbf"
    "niedersachsen|https://download.geofabrik.de/europe/germany/niedersachsen-latest.osm.pbf"
    "nordrhein-westfalen|https://download.geofabrik.de/europe/germany/nordrhein-westfalen-latest.osm.pbf"
    "rheinland-pfalz|https://download.geofabrik.de/europe/germany/rheinland-pfalz-latest.osm.pbf"
    "saarland|https://download.geofabrik.de/europe/germany/saarland-latest.osm.pbf"
    "sachsen|https://download.geofabrik.de/europe/germany/sachsen-latest.osm.pbf"
    "sachsen-anhalt|https://download.geofabrik.de/europe/germany/sachsen-anhalt-latest.osm.pbf"
    "schleswig-holstein|https://download.geofabrik.de/europe/germany/schleswig-holstein-latest.osm.pbf"
    "thueringen|https://download.geofabrik.de/europe/germany/thueringen-latest.osm.pbf"
    "netherlands|https://download.geofabrik.de/europe/netherlands-latest.osm.pbf"
    "belgium|https://download.geofabrik.de/europe/belgium-latest.osm.pbf"
    "luxembourg|https://download.geofabrik.de/europe/luxembourg-latest.osm.pbf"
)

# Function to generate tiles for a region
generate_tiles() {
    local name=$1
    local pbf_file=$2
    local output_file=$3

    echo "Generating tiles for $name..."
    docker run --rm \
        -v "$(pwd):/var/tm" \
        -v "/tmp:/tmp" \
        -w /var/tm \
        --entrypoint tilemaker \
        versatiles/versatiles-tilemaker \
            --config tilemaker/config.json \
            --process tilemaker/process.lua \
            --input "$pbf_file" \
            --output "$output_file"

    echo "Building geocoding index sidecar for $name..."
    python3 "$(dirname "$0")/build_places.py" "$pbf_file" "$output_file"

    echo "✓ Completed: $output_file"
    ls -lh "$output_file"
}

echo "=== Generating tiles ==="
for entry in "${REGIONS[@]}"; do
    region="${entry%%|*}"
    url="${entry##*|}"
    pbf_file="/tmp/${region}.osm.pbf"
    output_file="$OUTPUT_DIR/tiles_${region}.mbtiles"

    if [ -f "$output_file" ]; then
        echo "⊘ Skipping $region (output already exists)"
        continue
    fi

    if [ ! -f "$pbf_file" ]; then
        echo "Downloading $region..."
        wget -q --show-progress -O "$pbf_file" "$url"
    else
        echo "⊘ Using existing PBF for $region"
    fi

    generate_tiles "$region" "$pbf_file" "$output_file"
done

echo ""
echo "=== All tiles generated successfully ==="
echo "Output directory: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"
