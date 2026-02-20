#!/usr/bin/env bash
# Build a shippable package: executables (from dist/) + your custom files (from distribution/).
# Run this on your machine after you have the exes in dist/ (from CI artifact or local build).
#
# Usage:
#   ./scripts/distribute.sh [platform]
#
# 1. Put executables in dist/ (download CI artifact and unzip into dist/, or build locally).
# 2. Put configs, images, run scripts, etc. in distribution/.
# 3. Run: ./scripts/distribute.sh
#    Optional: ./scripts/distribute.sh linux   or  windows  or  macos  to name the output.
#
# Output: a folder and a .zip (e.g. release/ and release.zip, or release-linux/ and release-linux.zip)
#         containing the exes plus everything from distribution/, ready to ship.

set -e
cd "$(dirname "$0")/.."

PLATFORM="$1"
if [ -n "$PLATFORM" ]; then
  OUT_DIR="release-$PLATFORM"
else
  OUT_DIR="release"
fi
OUT_ZIP="${OUT_DIR}.zip"

if [ ! -d dist ] || [ -z "$(ls -A dist 2>/dev/null)" ]; then
  echo "dist/ is missing or empty. Put the executables there first:"
  echo "  - Download the dist-<platform> artifact from GitHub Actions and unzip into dist/"
  echo "  - Or run ./scripts/build_releases.sh to build locally"
  exit 1
fi

echo "Creating package: $OUT_DIR and $OUT_ZIP"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

echo "  - Adding executables from dist/"
cp -r dist/* "$OUT_DIR/"

if [ -d distribution ] && [ -n "$(ls -A distribution 2>/dev/null)" ]; then
  echo "  - Adding your files from distribution/"
  cp -r distribution/* "$OUT_DIR/"
else
  echo "  - (no distribution/ contents; add configs, images, scripts there if you need them)"
fi

echo "  - Zipping to $OUT_ZIP"
rm -f "$OUT_ZIP"
(cd "$OUT_DIR" && zip -r "../$OUT_ZIP" .)

echo "Done. Ship: $OUT_DIR/ or $OUT_ZIP"
