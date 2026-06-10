#!/usr/bin/env python3
"""
Relay de etiquetas de caducidad — Raspberry Pi 3B (Debian Trixie)

Rutas:
  GET  /           → sirve static/index.html
  GET  /products   → lista de productos JSON
  GET  /config     → configuración actual (IP impresora, puerto)
  POST /config     → guardar nueva configuración
  POST /print      → imprimir etiqueta ESC/POS por TCP
"""
import json
import os
import logging

from flask import Flask, request, jsonify, send_from_directory

from escpos_helper import print_label, PrintJob
from products import PRODUCTS

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
STATIC_DIR  = os.path.join(BASE_DIR, 'static')

DEFAULT_CONFIG = {
    'printer_ip':   '192.168.168.100',  # IP de la impresora en la red eth0
    'printer_port': 9100,
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


# ── Rutas ─────────────────────────────────────────────────────────────────────

@app.get('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


@app.get('/products')
def get_products():
    return jsonify(PRODUCTS)


@app.get('/config')
def get_config():
    return jsonify(load_config())


@app.post('/config')
def set_config():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': False, 'msg': 'Body vacío'}), 400

    cfg = load_config()
    if 'printer_ip' in data:
        cfg['printer_ip'] = str(data['printer_ip']).strip()
    if 'printer_port' in data:
        try:
            cfg['printer_port'] = int(data['printer_port'])
        except (ValueError, TypeError):
            return jsonify({'ok': False, 'msg': 'Puerto inválido'}), 400

    save_config(cfg)
    app.logger.info('Config guardada: %s', cfg)
    return jsonify({'ok': True, 'config': cfg})


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

    app.logger.info('Imprimiendo: %s (prueba=%s, copias=%d)',
                    job.producto or 'TEST', job.test_mode, job.copies)

    result = print_label(job, cfg['printer_ip'], int(cfg['printer_port']))
    status = 200 if result['ok'] else 503
    return jsonify(result), status


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
