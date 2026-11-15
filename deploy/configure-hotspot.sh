#!/usr/bin/env bash
set -euo pipefail
# Explicit separate step: this changes the Pi Wi-Fi connection and hostname.
TRACE_IFACE="${TRACE_WIFI_INTERFACE:-wlan0}"
TRACE_SSID="${TRACE_WIFI_NAME:-TRACE-07}"
read -r -s -p 'New hotspot password (8-63 characters): ' TRACE_WIFI_PASSWORD
echo
if [ "${#TRACE_WIFI_PASSWORD}" -lt 8 ] || [ "${#TRACE_WIFI_PASSWORD}" -gt 63 ]; then echo 'Invalid password length'; exit 1; fi
sudo hostnamectl set-hostname trace
sudo nmcli device wifi hotspot ifname "$TRACE_IFACE" con-name trace-hotspot ssid "$TRACE_SSID" password "$TRACE_WIFI_PASSWORD"
unset TRACE_WIFI_PASSWORD
sudo nmcli connection modify trace-hotspot wifi-sec.key-mgmt wpa-psk wifi-sec.proto rsn connection.autoconnect yes
sudo nmcli connection up trace-hotspot
sudo systemctl restart avahi-daemon
echo 'Hotspot configured. Open http://trace.local:8000 from a connected device.'
