#!/usr/bin/env bash
# Create a gzipped tar delta package between two .mbtiles tile files.
#
# The package contains:
#   - metadata.json: versions, sha256 + size of old/new files, patch name
#   - patch.xdelta:  the xdelta3 binary patch
#
# Usage:
#   create-tile-delta.sh <old_file> <new_file> <old_version> <new_version> <output_file>
set -euo pipefail

if [[ $# -ne 5 ]]; then
    echo "Usage: $0 <old_file> <new_file> <old_version> <new_version> <output_file>" >&2
    exit 1
fi

OLD_FILE="$1"
NEW_FILE="$2"
OLD_VERSION="$3"
NEW_VERSION="$4"
OUTPUT_FILE="$5"

command -v xdelta3 >/dev/null 2>&1 || { echo "error: xdelta3 is not installed" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "error: jq is not installed" >&2; exit 1; }

for f in "$OLD_FILE" "$NEW_FILE"; do
    if [[ ! -s "$f" ]]; then
        echo "error: input file '$f' is missing or empty" >&2
        exit 1
    fi
done

OLD_SHA256=$(sha256sum "$OLD_FILE" | awk '{print $1}')
NEW_SHA256=$(sha256sum "$NEW_FILE" | awk '{print $1}')
OLD_SIZE=$(stat -c %s "$OLD_FILE")
NEW_SIZE=$(stat -c %s "$NEW_FILE")

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

echo "Computing delta: $OLD_FILE -> $NEW_FILE"
xdelta3 -e -9 -S none -s "$OLD_FILE" "$NEW_FILE" "$WORKDIR/patch.xdelta"

jq -n \
    --argjson version 1 \
    --arg old_version "$OLD_VERSION" \
    --arg new_version "$NEW_VERSION" \
    --arg old_sha256 "$OLD_SHA256" \
    --arg new_sha256 "$NEW_SHA256" \
    --argjson old_size "$OLD_SIZE" \
    --argjson new_size "$NEW_SIZE" \
    --arg patch "patch.xdelta" \
    --arg created_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{version: $version, old_version: $old_version, new_version: $new_version,
      old_sha256: $old_sha256, new_sha256: $new_sha256,
      old_size: $old_size, new_size: $new_size,
      patch: $patch, created_at: $created_at}' \
    > "$WORKDIR/metadata.json"

mkdir -p "$(dirname "$OUTPUT_FILE")"
tar -czf "$OUTPUT_FILE" -C "$WORKDIR" metadata.json patch.xdelta

DELTA_SIZE=$(stat -c %s "$OUTPUT_FILE")
PERCENT=$(awk -v d="$DELTA_SIZE" -v n="$NEW_SIZE" 'BEGIN { printf "%.2f", d * 100 / n }')

echo "Delta written to $OUTPUT_FILE"
echo "Delta size: $DELTA_SIZE bytes (${PERCENT}% of new file size $NEW_SIZE bytes)"
