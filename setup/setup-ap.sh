#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Configura wlan0 como Access Point WiFi "Realyetiquetas" (NetworkManager).
#
# CLAVE: el móvil se conecta a este AP y accede tanto al frontend (puerto 80)
# como por SSH (192.168.4.1). Así eth0 queda 100% libre para la impresora y
# el SSH NUNCA se corta aunque reconfigures eth0.
#
# Uso:  sudo bash setup-ap.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

AP_SSID="Realyetiquetas"
AP_IFACE="wlan0"
AP_IP="192.168.4.1/24"
CON_NAME="RealyetiquetasAP"
# Sin contraseña (red abierta). Para protegerla, descomenta el bloque WPA abajo.

echo ">> Configurando AP '$AP_SSID' en $AP_IFACE ..."

# Borra una conexión previa con el mismo nombre (idempotente)
nmcli con delete "$CON_NAME" 2>/dev/null || true

nmcli con add type wifi ifname "$AP_IFACE" con-name "$CON_NAME" \
  autoconnect yes ssid "$AP_SSID"

nmcli con modify "$CON_NAME" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel 6 \
  ipv4.method shared \
  ipv4.addresses "$AP_IP"

# ── Red protegida (opcional): descomenta y pon tu clave ──────────────────────
# nmcli con modify "$CON_NAME" \
#   wifi-sec.key-mgmt wpa-psk \
#   wifi-sec.psk "TuClaveSegura123"

nmcli con up "$CON_NAME"

echo ">> AP levantado:"
echo "   SSID:    $AP_SSID  (red abierta)"
echo "   IP RPi:  ${AP_IP%/*}"
echo "   Frontend: http://${AP_IP%/*}"
echo "   SSH:      ssh n1ce@${AP_IP%/*}"
echo "   DHCP para clientes lo gestiona NetworkManager (ipv4.method=shared, rango 192.168.4.x)"
