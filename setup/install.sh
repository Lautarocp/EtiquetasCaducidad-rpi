#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Instalador completo en la Raspberry Pi.
#
# Pasos:
#   1. Instala dependencias del sistema
#   2. Copia el proyecto a /home/n1ce/relay-etiquetas
#   3. Crea el virtualenv e instala requirements
#   4. Instala y arranca el servicio systemd
#   5. (opcional) levanta el AP WiFi
#
# Uso (desde el directorio del proyecto subido, p.ej. /tmp/relay-src):
#   sudo bash setup/install.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_USER="n1ce"
APP_DIR="/home/${APP_USER}/relay-etiquetas"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "================================================================"
echo " Instalando Relay Etiquetas de Caducidad"
echo " Origen:  $SRC_DIR"
echo " Destino: $APP_DIR"
echo "================================================================"

# ── 1. Dependencias del sistema ────────────────────────────────────────────────
echo ">> [1/5] Instalando dependencias APT ..."
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip network-manager

# ── 2. Copiar proyecto ─────────────────────────────────────────────────────────
echo ">> [2/5] Copiando proyecto a $APP_DIR ..."
mkdir -p "$APP_DIR"
rsync -a --exclude venv --exclude __pycache__ --exclude '*.pyc' \
  --exclude '.git' "$SRC_DIR"/ "$APP_DIR"/
chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"

# config.json inicial si no existe
if [ ! -f "$APP_DIR/config.json" ]; then
  cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"
  echo "   config.json creado desde el ejemplo"
fi

# ── 3. Virtualenv ──────────────────────────────────────────────────────────────
echo ">> [3/5] Creando virtualenv e instalando requirements ..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# ── 4. Servicio systemd ────────────────────────────────────────────────────────
echo ">> [4/5] Instalando servicio systemd ..."
cp "$APP_DIR/setup/relay-etiquetas.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable relay-etiquetas
systemctl restart relay-etiquetas

# ── 5. AP WiFi ─────────────────────────────────────────────────────────────────
echo ">> [5/5] AP WiFi"
read -rp "   ¿Levantar el AP WiFi 'Realyetiquetas' ahora? [s/N] " ans
if [[ "${ans,,}" == "s" ]]; then
  bash "$APP_DIR/setup/setup-ap.sh"
else
  echo "   Omitido. Ejecuta luego: sudo bash $APP_DIR/setup/setup-ap.sh"
fi

echo
echo "================================================================"
echo " ✔ Instalación completa"
echo "   Servicio:  systemctl status relay-etiquetas"
echo "   Logs:      journalctl -u relay-etiquetas -f"
echo "   Impresora RJ45: sudo bash $APP_DIR/setup/setup-printer-net.sh"
echo "   Frontend:  http://192.168.4.1  (conéctate al AP desde el móvil)"
echo "================================================================"
