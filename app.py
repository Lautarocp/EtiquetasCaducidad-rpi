#!/usr/bin/env python3
"""
Relay de etiquetas de caducidad — Raspberry Pi (Flask)

La RPi levanta un AP WiFi ("Realyetiquetas"). El móvil se conecta a ese AP y abre
el frontend en el navegador. Al imprimir, la RPi envía el ticket ESC/POS a la
impresora térmica — por red (RJ45/WiFi) o por USB, según config.json.

Rutas:
  GET  /          → frontend (static/index.html)
  GET  /products  → presets de productos (JSON)
  POST /products  → guardar la lista completa de presets
  GET  /config    → configuración actual de impresora
  POST /config    → guardar configuración (backend, ip, puerto, usb...)
  POST /print     → imprimir etiqueta
  GET  /health    → estado del servicio
"""
import os
import json
import logging

from flask import Flask, request, jsonify, send_from_directory

from printer import print_label, PrintJob
from products import DEFAULT_PRODUCTS
import netcfg

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE   = os.path.join(BASE_DIR, 'config.json')
PRODUCTS_FILE = os.path.join(BASE_DIR, 'products.json')
STATIC_DIR    = os.path.join(BASE_DIR, 'static')

DEFAULT_CONFIG = {
    'backend':        'network',          # network | usb | escpos | serial
    'printer_ip':     '192.168.34.133',   # impresora SoL801V en la red RJ45
    'printer_port':   9100,
    'usb_device':     '/dev/usb/lp0',     # usado si backend == usb
    'usb_vendor_id':  '0x0000',           # usado si backend == escpos
    'usb_product_id': '0x0000',
    'serial_port':    '/dev/ttyUSB0',     # usado si backend == serial
    'serial_baud':    115200,             # SoL801V: 115200 8N1 RTS/CTS
    'eth_ip':         '192.168.34.50/24', # IP de la RPi en la red de la impresora (eth0)
    'eth_gateway':    '192.168.34.96',    # gateway de la red de la impresora
}

# ── App ───────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=STATIC_DIR)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')


def load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def _normalize_preset(p: dict) -> dict | None:
    """Valida y normaliza un preset. Acepta el formato antiguo ({name, days}).
    Devuelve {name, value, unit} o None si es inválido."""
    if not isinstance(p, dict):
        return None
    name = str(p.get('name', '')).strip()
    if not name:
        return None
    # Compatibilidad con el formato antiguo: {name, days}
    if 'value' not in p and 'days' in p:
        value, unit = p.get('days'), 'dias'
    else:
        value, unit = p.get('value'), p.get('unit', 'dias')
    try:
        value = int(value)
    except (ValueError, TypeError):
        return None
    if value < 1:
        return None
    if unit not in ('dias', 'meses'):
        unit = 'dias'
    return {'name': name[:40], 'value': value, 'unit': unit}


def load_products() -> list:
    """Carga products.json; si no existe, devuelve la semilla por defecto."""
    try:
        with open(PRODUCTS_FILE) as f:
            raw = json.load(f)
        presets = [n for p in raw if (n := _normalize_preset(p))]
        return presets if presets else [dict(p) for p in DEFAULT_PRODUCTS]
    except Exception:
        return [dict(p) for p in DEFAULT_PRODUCTS]


def save_products(presets: list) -> None:
    with open(PRODUCTS_FILE, 'w') as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)


# ── Rutas ─────────────────────────────────────────────────────────────────────
@app.get('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


@app.get('/health')
def health():
    return jsonify({'ok': True, 'service': 'relay-etiquetas'})


@app.get('/products')
def get_products():
    return jsonify(load_products())


@app.post('/products')
def set_products():
    """Guarda la lista completa de presets. El frontend gestiona el array y lo
    envía entero (crear/editar/borrar). Cada preset: {name, value, unit}."""
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({'ok': False, 'msg': 'Se esperaba una lista de presets'}), 400

    presets = [n for p in data if (n := _normalize_preset(p))]
    save_products(presets)
    app.logger.info('Presets guardados: %d', len(presets))
    return jsonify({'ok': True, 'products': presets})


@app.get('/config')
def get_config():
    return jsonify(load_config())


@app.post('/config')
def set_config():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'msg': 'Body vacío'}), 400

    cfg = load_config()
    if 'backend' in data and data['backend'] in ('network', 'usb', 'escpos', 'serial'):
        cfg['backend'] = data['backend']
    if 'printer_ip' in data:
        cfg['printer_ip'] = str(data['printer_ip']).strip()
    if 'printer_port' in data:
        try:
            cfg['printer_port'] = int(data['printer_port'])
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'msg': 'Puerto inválido'}), 400
    if 'serial_baud' in data:
        try:
            cfg['serial_baud'] = int(data['serial_baud'])
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'msg': 'Baudios inválidos'}), 400
    for k in ('usb_device', 'usb_vendor_id', 'usb_product_id', 'serial_port',
              'eth_ip', 'eth_gateway'):
        if k in data:
            cfg[k] = str(data[k]).strip()

    save_config(cfg)
    app.logger.info('Config guardada: %s', cfg)
    return jsonify({'ok': True, 'config': cfg})


@app.get('/network/status')
def network_status():
    return jsonify(netcfg.get_eth_status())


@app.post('/network/printer-mode')
def network_printer_mode():
    """Pone eth0 en la red de la impresora. Seguro desde el AP (no corta wlan0)."""
    cfg = load_config()
    result = netcfg.set_printer_mode(cfg['eth_ip'], cfg['eth_gateway'], cfg['printer_ip'])
    app.logger.info('network/printer-mode → %s', result.get('msg'))
    return jsonify(result), (200 if result['ok'] else 503)


@app.post('/network/local-mode')
def network_local_mode():
    """Devuelve eth0 a DHCP/red local."""
    result = netcfg.set_local_mode()
    app.logger.info('network/local-mode → %s', result.get('msg'))
    return jsonify(result), (200 if result['ok'] else 503)


@app.post('/print')
def handle_print():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'msg': 'Body vacío'}), 400

    cfg = load_config()
    job = PrintJob(
        producto    = data.get('producto', '').strip(),
        realizacion = data.get('realizacion', ''),
        envasado    = data.get('envasado', ''),
        caducidad   = data.get('caducidad', ''),
        congelado   = data.get('congelado', ''),
        copies      = min(max(int(data.get('copias', 1)), 1), 10),
        test_mode   = bool(data.get('test', False)),
    )

    if not job.test_mode and not job.producto:
        return jsonify({'ok': False, 'msg': 'Producto vacío'}), 400

    app.logger.info('Imprimiendo: %s (prueba=%s, copias=%d, backend=%s)',
                    job.producto or 'TEST', job.test_mode, job.copies, cfg['backend'])

    result = print_label(job, cfg)
    status = 200 if result['ok'] else 503
    return jsonify(result), status


if __name__ == '__main__':
    # Producción: gunicorn (ver setup/relay-etiquetas.service)
    app.run(host='0.0.0.0', port=80, debug=False)
