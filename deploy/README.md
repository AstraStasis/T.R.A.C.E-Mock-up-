# Raspberry Pi deployment

Prepared for Raspberry Pi OS with a desktop and NetworkManager. These scripts
have not been run on a Pi; module selection, touchscreen rotation and Wi-Fi
adapter support remain hardware-dependent. Installation needs internet; runtime does not.

1. Copy the repository to the Pi, log in as its desktop user, run
   `bash deploy/install-pi.sh`.
2. Review then run `bash deploy/configure-hotspot.sh` on the Pi locally. It changes
   the hostname and active Wi-Fi connection, so an SSH session can disconnect.
3. Enable desktop auto-login through Raspberry Pi settings for kiosk on boot.
4. Inspect `systemctl status trace` and `journalctl -u trace`. Stop with
   `sudo systemctl stop trace`. Disable boot startup with `sudo systemctl disable trace`.

The initial service uses port 8000; its QR points to `http://trace.local:8000`.
For the handoff's portless `http://trace.local`, put a local reverse proxy on port
80, forwarding HTTP and WebSocket Upgrade headers to 127.0.0.1:8000. Example
nginx server configuration is supplied. Update TRACE_PUBLIC_URL in /etc/trace.env.
Do not run Python as root to bind port 80.

`/etc/trace.env` is optional, root-owned, permissions 600:

```ini
TRACE_DEVICE=serial
TRACE_SERIAL_PORT=/dev/ttyACM0
TRACE_PUBLIC_URL=http://trace.local
TRACE_WIFI_NAME=TRACE-07
TRACE_RESEARCH_PIN=choose-a-private-pin
```

Restart the service after changes. Without TRACE_DEVICE, simulator mode remains
enabled and visibly labelled. Without a researcher PIN, diagnostics are disabled.
The PIN is a local lab access gate, not Internet-grade authentication. Keep the
server on the board's private network; no accounts or personal data are required.

Serial mode requires firmware following protocol/README.md and a verified channel
map. Disconnects invalidate live values and reconnect automatically. Firmware,
not Python, must enforce output release on power loss or host heartbeat timeout.

Multiple boards on one LAN need unique hostnames; adjust the configured URL and QR.
The SSID shown in the application is configuration, not proof that a hotspot exists.

Remove `~/.config/autostart/trace-kiosk.desktop` to disable kiosk login startup.
