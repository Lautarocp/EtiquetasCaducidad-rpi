#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Configura eth0 con IP estática en la red de la impresora térmica (RJ45).
#
# La impresora SoL801 está en 192.168.34.133 (gateway 192.168.34.96). Para que
# la RPi pueda enviarle tickets por TCP 9100, eth0 debe estar en esa misma /24.
#
# Esto NO afecta al SSH: tú entras por el AP WiFi (192.168.4.1), no por eth0.
#
# SOLO necesario si conectas la impresora por RED (RJ45). Si la conectas por
# USB, NO ejecutes este script — deja eth0 en DHCP o desconectado.
#
# Uso:  sudo bash setup-printer-net.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ETH_IFACE="eth0"
ETH_IP="192.168.34.50/24"      # IP libre de la RPi en la red de la impresora
ETH_GW="192.168.34.96"         # gateway de la impresora (opcional)
CON_NAME="PrinterLink"

echo ">> Configurando $ETH_IFACE para la red de la impresora ..."

nmcli con delete "$CON_NAME" 2>/dev/null || true

nmcli con add type ethernet ifname "$ETH_IFACE" con-name "$CON_NAME" \
  autoconnect yes

nmcli con modify "$CON_NAME" \
  ipv4.method manual \
  ipv4.addresses "$ETH_IP" \
  ipv4.gateway "$ETH_GW" \
  ipv4.never-default yes        # eth0 NO es la ruta por defecto (deja libre el AP)

nmcli con up "$CON_NAME"

echo ">> eth0 configurado:"
echo "   IP RPi:    ${ETH_IP%/*}"
echo "   Impresora: 192.168.34.133:9100"
echo
echo ">> Prueba de alcance a la impresora:"
ping -c 2 -W 2 192.168.34.133 && echo "   ✔ Impresora alcanzable" || echo "   ✘ No responde (revisa cable/IP de la impresora)"
