#!/bin/bash
# =============================================================================
#  install.sh — Instala Relay Etiquetas Caducidad en Raspberry Pi 3B (Debian)
# =============================================================================
set -e

PROJECT_SRC="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="/home/n1ce/relay-etiquetas"
SERVICE="relay-etiquetas"

echo "=============================================="
echo "  Relay Etiquetas Caducidad — Instalador"
echo "=============================================="
echo "Origen:  $PROJECT_SRC"
echo "Destino: $INSTALL_DIR"
echo ""

# ── 1. Dependencias del sistema ───────────────────────────────────────────────
echo "[1/6] Instalando dependencias del sistema..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-venv python3-pip

# ── 2. Copiar archivos del proyecto ───────────────────────────────────────────
echo "[2/6] Copiando archivos a $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR/static"
cp "$PROJECT_SRC/app.py"           "$INSTALL_DIR/"
cp "$PROJECT_SRC/escpos_helper.py" "$INSTALL_DIR/"
cp "$PROJECT_SRC/products.py"      "$INSTALL_DIR/"
cp "$PROJECT_SRC/requirements.txt" "$INSTALL_DIR/"
cp "$PROJECT_SRC/static/index.html" "$INSTALL_DIR/static/"
chown -R n1ce:n1ce "$INSTALL_DIR"

# ── 3. Entorno virtual Python ─────────────────────────────────────────────────
echo "[3/6] Creando entorno virtual e instalando Flask + gunicorn..."
sudo -u n1ce python3 -m venv "$INSTALL_DIR/venv"
sudo -u n1ce "$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── 4. Servicio systemd ───────────────────────────────────────────────────────
echo "[4/6] Configurando servicio systemd..."
sudo cp "$PROJECT_SRC/setup/relay-etiquetas.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"

# ── 5. Red: AP WiFi (wlan0) + IP estática eth0 ───────────────────────────────
echo "[5/6] Configurando red con NetworkManager..."

# Eliminar conexión cliente WiFi actual (si existe) para liberar wlan0
CURRENT_WLAN=$(nmcli -g NAME,DEVICE con show --active 2>/dev/null | grep ":wlan0" | cut -d: -f1 || true)
if [ -n "$CURRENT_WLAN" ]; then
    echo "     Eliminando conexión WiFi cliente: $CURRENT_WLAN"
    sudo nmcli con delete "$CURRENT_WLAN" 2>/dev/null || true
fi

# AP WiFi en wlan0: ipv4.method=shared → NM gestiona DHCP automáticamente
if ! nmcli con show "RelayEtiquetas" &>/dev/null; then
    sudo nmcli con add \
        type wifi \
        ifname wlan0 \
        con-name "RelayEtiquetas" \
        ssid "RelayEtiquetas" \
        mode ap \
        802-11-wireless.band bg \
        802-11-wireless.channel 6 \
        ipv4.method shared \
        ipv4.addresses "192.168.4.1/24" \
        connection.autoconnect yes
    echo "     AP 'RelayEtiquetas' creado — IP: 192.168.4.1"
else
    echo "     AP 'RelayEtiquetas' ya existe, sin cambios."
fi

# IP estática en eth0 para la impresora (conexión directa)
if ! nmcli con show "printer-link" &>/dev/null; then
    sudo nmcli con add \
        type ethernet \
        ifname eth0 \
        con-name "printer-link" \
        ipv4.method manual \
        ipv4.addresses "192.168.168.1/24" \
        connection.autoconnect yes
    echo "     eth0 configurado: 192.168.168.1/24"
else
    echo "     Conexión printer-link ya existe, sin cambios."
fi

# ── 6. Resumen ────────────────────────────────────────────────────────────────
echo ""
echo "[6/6] ¡Instalación completada!"
echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  PRÓXIMOS PASOS                             │"
echo "  │                                             │"
echo "  │  1. Conectar la impresora al puerto eth0    │"
echo "  │     y configurar en ella la IP:             │"
echo "  │       192.168.168.100                       │"
echo "  │                                             │"
echo "  │  2. Reiniciar la Raspberry Pi:              │"
echo "  │       sudo reboot                           │"
echo "  │                                             │"
echo "  │  3. Tras el reinicio, conectarse al WiFi:   │"
echo "  │       Red: RelayEtiquetas (sin contraseña)  │"
echo "  │       URL: http://192.168.4.1               │"
echo "  │                                             │"
echo "  │  ⚠ AVISO: este SSH dejará de funcionar     │"
echo "  │    tras el reboot. Nuevo SSH:               │"
echo "  │       ssh n1ce@192.168.4.1                  │"
echo "  │    (conectado al AP RelayEtiquetas)          │"
echo "  └─────────────────────────────────────────────┘"
echo ""
echo "  Para ver logs del servicio:"
echo "    sudo journalctl -u relay-etiquetas -f"
echo ""
