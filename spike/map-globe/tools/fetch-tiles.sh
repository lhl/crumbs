#!/bin/sh
# Fetch everything the fully-local (PMTiles) basemap needs into git-ignored dirs:
#   public/tiles/protomaps-demo.pmtiles  regional extracts (Kyoto / Taipei / Lisbon demo regions)
#   public/fonts/<stack>/<range>.pbf     glyphs for @protomaps/basemaps styles (Noto Sans stacks)
#   public/sprites/v4/*                  sprite sheets for POI/road icons
# Nothing here is committed; re-run with FORCE=1 to refresh. Data: © OpenStreetMap contributors (ODbL),
# tiles by Protomaps; fonts/sprites from github.com/protomaps/basemaps-assets.
set -eu
cd "$(dirname "$0")/.."
BUILD="${PROTOMAPS_BUILD:-20261026}"   # build.protomaps.com daily build, YYYYMMDD
PMTILES_VERSION="1.28.2"

# 1) pmtiles CLI (PATH, or a pinned local download into tools/bin/)
if command -v pmtiles >/dev/null 2>&1; then PM="pmtiles";
elif [ -x tools/bin/pmtiles ]; then PM="tools/bin/pmtiles";
else
  mkdir -p tools/bin
  curl -fsSL "https://github.com/protomaps/go-pmtiles/releases/download/v${PMTILES_VERSION}/go-pmtiles_${PMTILES_VERSION}_Linux_x86_64.tar.gz" \
    | tar xz -C tools/bin pmtiles
  PM="tools/bin/pmtiles"
fi
echo "using $PM ($($PM version 2>/dev/null | head -1 || true))"

# 2) Regional PMTiles extract (HTTP range requests against the planet build — downloads ~tens of MB, not 120 GB)
mkdir -p public/tiles
if [ ! -f public/tiles/protomaps-demo.pmtiles ] || [ -n "${FORCE:-}" ]; then
  "$PM" extract "https://build.protomaps.com/${BUILD}.pmtiles" public/tiles/protomaps-demo.pmtiles \
    --region=tools/demo-regions.geojson --maxzoom=15
else
  echo "tiles already present (FORCE=1 to refresh)"
fi

# 2b) Lightweight globe backdrop: the whole planet at low zoom only (z0-5, ~15 MB),
# so the local globe shows continents/labels everywhere; detail comes from the regional archive.
if [ ! -f public/tiles/protomaps-globe.pmtiles ] || [ -n "${FORCE:-}" ]; then
  "$PM" extract "https://build.protomaps.com/${BUILD}.pmtiles" public/tiles/protomaps-globe.pmtiles --maxzoom=5
else
  echo "globe tiles already present (FORCE=1 to refresh)"
fi

# 3) Fonts + sprites (small repo tarball; extracted locally so no font/sprite traffic at runtime)
if [ ! -d public/fonts ] || [ ! -d public/sprites ] || [ -n "${FORCE:-}" ]; then
  tmp="$(mktemp -d)"
  curl -fsSL https://codeload.github.com/protomaps/basemaps-assets/tar.gz/refs/heads/main -o "$tmp/assets.tar.gz"
  tar xzf "$tmp/assets.tar.gz" -C "$tmp"
  rm -rf public/fonts public/sprites
  cp -r "$tmp"/basemaps-assets-main/fonts public/fonts
  mkdir -p public/sprites
  cp -r "$tmp"/basemaps-assets-main/sprites/v4 public/sprites/v4
  rm -rf "$tmp"
else
  echo "fonts/sprites already present (FORCE=1 to refresh)"
fi

du -sh public/tiles/protomaps-demo.pmtiles public/tiles/protomaps-globe.pmtiles public/fonts public/sprites
echo "done — start the app (npm run dev / preview) and pick 'Protomaps PMTiles (fully local)'."
