#!/usr/bin/env bash
#
# build.sh — Builds PRIVACY68 for Linux.
#
#   ./build.sh                 # build the application folder
#   ./build.sh --clean         # remove the build output first
#
# The result is dist/PRIVACY68/ (a folder the user can copy anywhere) and
# dist/PRIVACY68-v<version>-linux.tar.gz for distribution.

set -euo pipefail

cd "$(dirname "$0")"

VERSION="$(grep -oP 'APP_VERSION\s*=\s*"\K[^"]+' build_exe.py || echo 1.4.1)"
VENV=".venv"

if [ "${1:-}" = "--clean" ]; then
    echo "[*] Removing the previous build..."
    rm -rf build dist
fi

if [ ! -d "$VENV" ]; then
    echo "[*] Creating the virtual environment..."
    python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "[*] Installing the dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements-linux.txt

echo "[*] Building the application..."
python build_exe.py

echo "[*] Packaging the tarball..."
tar -czf "dist/PRIVACY68-v${VERSION}-linux.tar.gz" -C dist PRIVACY68

echo
echo "====================================================="
echo " [DONE] PRIVACY68 v${VERSION} Linux build complete"
echo " Application : dist/PRIVACY68/"
echo " Tarball     : dist/PRIVACY68-v${VERSION}-linux.tar.gz"
echo "====================================================="
