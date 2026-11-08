#!/usr/bin/env bash
# Local hand-off of built tiles between jobs on the same self-hosted runner.
#
# Downloading 25 workflow artifacts (about 5 GB) from GitHub took close to an
# hour on the runner, while the files were already sitting on its disk a few
# minutes earlier. Jobs keep their tiles here instead and fall back to the
# artifact when the cache has no copy (a different runner, an expired cache).
#
# Layout: $TILE_CACHE_DIR/runs/<run-id>/tiles_<region>.mbtiles
# TILE_CACHE_DIR defaults to $HOME/.cache/librescoot-tiles. Base releases for
# the deltas are cached separately by tools/create-map-deltas.py under bases/.
#
#   tile-cache.sh store <run-id> <region> <file>       keep a verified file
#   tile-cache.sh fetch <run-id> <region> <dest-dir>   link one region; exit 1 if absent
#   tile-cache.sh fetch-all <run-id> <count> <dest-dir>  link every region; exit 1 unless
#                                                        exactly <count> are present
#   tile-cache.sh prune [days]                         drop runs older than N days (7)
set -euo pipefail

root="${TILE_CACHE_DIR:-$HOME/.cache/librescoot-tiles}"
cmd="${1:-}"; shift || true

link_or_copy() {  # hard link when on the same filesystem, copy otherwise
    ln -f "$1" "$2" 2>/dev/null || cp "$1" "$2"
}

case "$cmd" in
    store)
        run=$1; region=$2; file=$3
        [[ "$run" =~ ^[0-9]+$ && "$region" =~ ^[a-z0-9_-]+$ ]] || { echo "bad arguments" >&2; exit 2; }
        dir="$root/runs/$run"
        mkdir -p "$dir"
        # Written under a temporary name and renamed, so a reader never sees a
        # half-copied file.
        cp "$file" "$dir/tiles_$region.mbtiles.part"
        mv -f "$dir/tiles_$region.mbtiles.part" "$dir/tiles_$region.mbtiles"
        ;;
    fetch)
        run=$1; region=$2; dest=$3
        [[ "$run" =~ ^[0-9]+$ && "$region" =~ ^[a-z0-9_-]+$ ]] || { echo "bad arguments" >&2; exit 2; }
        src="$root/runs/$run/tiles_$region.mbtiles"
        [ -f "$src" ] || exit 1
        mkdir -p "$dest"
        link_or_copy "$src" "$dest/tiles_$region.mbtiles"
        ;;
    fetch-all)
        run=$1; count=$2; dest=$3
        [[ "$run" =~ ^[0-9]+$ && "$count" =~ ^[0-9]+$ ]] || { echo "bad arguments" >&2; exit 2; }
        dir="$root/runs/$run"
        [ -d "$dir" ] || exit 1
        shopt -s nullglob
        files=("$dir"/tiles_*.mbtiles)
        [ "${#files[@]}" -eq "$count" ] || exit 1
        mkdir -p "$dest"
        for f in "${files[@]}"; do
            name=$(basename "$f" .mbtiles); region=${name#tiles_}
            mkdir -p "$dest/$region"
            link_or_copy "$f" "$dest/$region/$(basename "$f")"
        done
        ;;
    prune)
        days="${1:-7}"
        [ -d "$root/runs" ] || exit 0
        find "$root/runs" -mindepth 1 -maxdepth 1 -type d -mtime "+$days" -exec rm -rf {} +
        ;;
    *)
        echo "usage: tile-cache.sh store|fetch|fetch-all|prune ..." >&2
        exit 2
        ;;
esac
