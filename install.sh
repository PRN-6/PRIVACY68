#!/usr/bin/env bash
#
# install.sh — Installs PRIVACY68 on Linux.
#
#   ./install.sh            # install for the current user (no root needed)
#   sudo ./install.sh       # install system wide in /opt/PRIVACY68
#
# The installer creates a virtual environment with the dependencies, a
# launcher in ~/.local/bin and a menu entry for the desktop.

set -euo pipefail

cd "$(dirname "$0")"

SYSTEM_WIDE=0
[ "$(id -u)" = "0" ] && SYSTEM_WIDE=1

if [ "$SYSTEM_WIDE" = "1" ]; then
    APP_DIR=/opt/PRIVACY68
    BIN_DIR=/usr/local/bin
    DESKTOP_DIR=/usr/share/applications
else
    APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/PRIVACY68"
    BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
    DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
fi

echo "[*] Installing PRIVACY68 into $APP_DIR"
mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR"

# The application code (the virtual environment is created below).
for item in app.py config.py actions core computer_use extra_plugins plugins server speech ui utils assets; do
    if [ -e "$item" ]; then
        rm -rf "${APP_DIR:?}/$item"
        cp -r "$item" "$APP_DIR/"
    fi
done
if [ -f requirements.txt ]; then
    cp requirements.txt "$APP_DIR/"
fi
if [ -f requirements-linux.txt ]; then
    cp requirements-linux.txt "$APP_DIR/"
fi

echo "[*] Creating the virtual environment..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements-linux.txt"

echo "[*] Creating the launcher..."
cat > "$BIN_DIR/privacy68" <<EOF
#!/usr/bin/env bash
exec "$APP_DIR/venv/bin/python" "$APP_DIR/app.py" "\$@"
EOF
chmod +x "$BIN_DIR/privacy68"

echo "[*] Creating the menu entry..."
cat > "$DESKTOP_DIR/privacy68.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PRIVACY68
Comment=Local voice assistant
Exec=$BIN_DIR/privacy68
Terminal=false
Categories=Utility;
EOF

echo
echo "====================================================="
echo " [OK] PRIVACY68 installed"
echo " Start it with: privacy68"
echo "====================================================="
