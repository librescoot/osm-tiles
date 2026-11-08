#!/usr/bin/env bash
# Keep published tiles on the runner as the next run's delta bases.
#
# Downloading a published region file for every delta is the slowest part of a
# run on these runners. Once a region has been uploaded to its release, that
# very file is what the release will publish, so it is filed under the release
# tag in $TILE_CACHE_DIR/bases/<tag>/ (default $HOME/.cache/librescoot-tiles).
# tools/create-map-deltas.py reads that directory, trusts a file only after its
# size and SHA-256 match the release's own digest, and prunes tags that are no
# longer candidates, so a draft that never gets published is cleaned up at the
# next run.
#
#   tile-cache.sh adopt <release-tag> <dir>   file every tiles_*.mbtiles in <dir>
set -euo pipefail

root="${TILE_CACHE_DIR:-$HOME/.cache/librescoot-tiles}"
cmd="${1:-}"; shift || true

link_or_copy() {  # hard link when on the same filesystem, copy otherwise
    ln -f "$1" "$2" 2>/dev/null || cp "$1" "$2"
}

case "$cmd" in
    adopt)
        tag=${1:-}; src=${2:-}
        [[ "$tag" =~ ^tiles-[A-Za-z0-9]+$ ]] || { echo "bad release tag" >&2; exit 2; }
        shopt -s nullglob
        files=("$src"/tiles_*.mbtiles "$src"/*/tiles_*.mbtiles)
        [ "${#files[@]}" -gt 0 ] || { echo "nothing to adopt in $src" >&2; exit 1; }
        dir="$root/bases/$tag"
        mkdir -p "$dir"
        for f in "${files[@]}"; do
            name=$(basename "$f")
            # Written under a temporary name and renamed, so a reader never sees
            # a half-copied file.
            link_or_copy "$f" "$dir/$name.part"
            mv -f "$dir/$name.part" "$dir/$name"
        done
        ;;
    *)
        echo "usage: tile-cache.sh adopt <release-tag> <dir>" >&2
        exit 2
        ;;
esac
