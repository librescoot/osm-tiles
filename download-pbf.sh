#!/bin/bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 URL OUTPUT" >&2
    exit 2
fi
url=$1
output=$2
partial=$(mktemp "${output}.partial.XXXXXX")
trap 'rm -f "$partial"' EXIT

for attempt in 1 2 3; do
    urls=("$url")
    # Geofabrik's latest aliases can loop; dated extracts bypass those aliases.
    if [[ "$url" == https://download.geofabrik.de/*-latest.osm.pbf ]]; then
        day=$(date -u -d yesterday +%y%m%d)
        urls+=("${url%-latest.osm.pbf}-${day}.osm.pbf")
    fi
    for candidate in "${urls[@]}"; do
        echo "Downloading $candidate (attempt $attempt/3)" >&2
        if curl --fail --location --silent --show-error \
            --max-redirs 5 --connect-timeout 30 --max-time 1800 \
            --speed-limit 1024 --speed-time 120 \
            --output "$partial" "$candidate"; then
            if [ -s "$partial" ]; then
                mv -f "$partial" "$output"
                exit 0
            fi
            echo "Empty response from $candidate" >&2
        fi
    done
    if [ "$attempt" -lt 3 ]; then
        sleep 30
    fi
done

echo "Failed to download $url after 3 attempts" >&2
exit 1
