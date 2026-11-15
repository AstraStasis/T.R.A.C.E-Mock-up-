#!/usr/bin/env bash
set -euo pipefail
# Run from a checkout on the Pi. Does not configure Wi-Fi or change hostname.
TRACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TRACE_USER="${SUDO_USER:-$USER}"
if [ "$TRACE_USER" = root ]; then echo 'Run as the Pi desktop user, not root.' >&2; exit 1; fi
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip avahi-daemon chromium
python3 -m venv "$TRACE_ROOT/.venv"
"$TRACE_ROOT/.venv/bin/python" -m pip install -r "$TRACE_ROOT/requirements.txt"
mkdir -p "$TRACE_ROOT/runtime"
sudo tee /etc/systemd/system/trace.service >/dev/null <<EOF
[Unit]
Description=TRACE local circuit laboratory
After=network.target
[Service]
User=$TRACE_USER
WorkingDirectory=$TRACE_ROOT
Environment=TRACE_HOST=0.0.0.0
Environment=TRACE_PORT=8000
Environment=TRACE_PUBLIC_URL=http://trace.local:8000
EnvironmentFile=-/etc/trace.env
ExecStart="$TRACE_ROOT/.venv/bin/python" "$TRACE_ROOT/run.py"
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths="$TRACE_ROOT/runtime"
[Install]
WantedBy=multi-user.target
EOF
sudo usermod -aG dialout "$TRACE_USER"
sudo systemctl daemon-reload
sudo systemctl enable --now avahi-daemon trace.service
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/trace-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TRACE kiosk
Exec=chromium --kiosk --no-first-run --disable-session-crashed-bubble http://localhost:8000
X-GNOME-Autostart-enabled=true
EOF
echo 'TRACE installed. Backend: http://localhost:8000. Desktop login starts kiosk.'
echo 'Configure desktop auto-login in Raspberry Pi settings if desired.'
echo 'Hotspot and mDNS hostname: see deploy/README.md. Hardware mode: /etc/trace.env.'
