#!/usr/bin/env bash
# Build distributable executables for Matteino Launcher (user and admin).
# Builds for the CURRENT OS only (PyInstaller does not cross-compile):
#   - On Linux:  run this script → Linux binaries in dist/
#   - On Windows: run this script (e.g. Git Bash) → .exe in dist/
# Run from project root. Requires: pip install pyinstaller
#   ./scripts/build_releases.sh

set -e
cd "$(dirname "$0")/.."

if ! command -v pyinstaller &>/dev/null; then
    echo "PyInstaller not found. Install with: pip install pyinstaller"
    exit 1
fi

echo "Building for current platform ($(uname -s))..."
echo "Building Matteino Launcher (User)..."
pyinstaller --noconfirm matteino_user.spec

echo "Building Matteino Launcher (Admin)..."
pyinstaller --noconfirm matteino_admin.spec

echo "Done. Executables are in dist/"
