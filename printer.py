"""
Backend de impresión unificado para impresora térmica ESC/POS.

Impresora objetivo: HIOPOS/ICG SoL801V (firmware Sol801v0.54-voice, BFFW V07-1.04)
  • Térmica de recibos 80mm (ancho impresión 72mm, 203 DPI, ~48 caracteres/línea)
  • ESC/POS compatible · auto-cutter · interfaces USB + Ethernet(LAN) + RS232
  • Red: TCP puerto 9100 (estado por UDP 9101)

Soporta cuatro modos de conexión (configurable en config.json → "backend"):

  • "network"  → impresora con RJ45/LAN, por TCP al puerto 9100   (default)
  • "usb"      → impresora por cable USB, escribiendo a /dev/usb/lp0
  • "escpos"   → impresora por USB usando python-escpos (vendor/product id)
  • "serial"   → impresora por RS232/serie (115200 8N1, handshake RTS/CTS)

El ticket ESC/POS se construye una sola vez (build_ticket) y se envía como
bytes crudos por cualquiera de los transportes. Así el formato del ticket
(acentos, doble tamaño, corte) es idéntico independientemente del cable.
"""
import os
import socket
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


# ── Modelo de trabajo de impresión ──────────────────────────────────────────────
@dataclass
class PrintJob:
    producto:    str  = ''
    realizacion: str  = ''
    envasado:    str  = ''
    caducidad:   str  = ''
    congelado:   str  = ''
    copies:      int  = 1
    test_mode:   bool = False


# ── Construcción del ticket ESC/POS ─────────────────────────────────────────────
def _line(text: str) -> bytes:
    """Codifica una línea como Latin-1 (≈WPC1252) + CR+LF.
    Latin-1 cubre todos los caracteres del español. Si una impresora antigua
    da problemas, cambiar errors='replace' por 'ignore'."""
    return text.encode('latin-1', errors='replace') + b'\r\n'


def build_ticket(job: PrintJob) -> bytes:
    """Genera el buffer ESC/POS completo listo para enviar al transporte."""
    INIT      = b'\x1b@'       # ESC @  inicializar
    CP1252    = b'\x1bt\x10'   # ESC t  code page WPC1252 (\x02=CP850 si fallan acentos)
    ALIGN_L   = b'\x1ba\x00'
    ALIGN_C   = b'\x1ba\x01'
    SIZE_NORM = b'\x1b!\x00'
    SIZE_DBL  = b'\x1b!\x30'   # doble alto + ancho
    BOLD_ON   = b'\x1bE\x01'
    BOLD_OFF  = b'\x1bE\x00'
    FEED      = b'\x1bd\x04'   # avanzar 4 líneas
    CUT       = b'\x1dV\x01'   # corte parcial (comentar si no hay cortador)

    buf = bytearray()
    for _ in range(job.copies):
        buf += INIT + CP1252
        if job.test_mode:
            buf += ALIGN_C + BOLD_ON
            buf += _line('-- PRUEBA DE IMPRESION --')
            buf += BOLD_OFF
            buf += _line('RPi Relay Etiquetas v2.0')
            buf += _line('Impresora OK')
            buf += _line('')
        else:
            buf += ALIGN_C + SIZE_DBL
            buf += _line(job.producto)
            buf += SIZE_NORM + ALIGN_L
            buf += _line(f'Realizacion: {job.realizacion}')
            buf += _line(f'Envasado:    {job.envasado}')
            buf += ALIGN_C + SIZE_DBL
            buf += _line(f'CAD: {job.caducidad}')
            if job.congelado:
                buf += SIZE_NORM + ALIGN_L
                buf += _line(f'Congelado:   {job.congelado}')
            buf += SIZE_NORM + _line('')
        buf += FEED + CUT
    return bytes(buf)


# ── Transportes ─────────────────────────────────────────────────────────────────
def _send_network(data: bytes, cfg: dict, timeout: int = 3) -> dict:
    """Envía por TCP a una impresora en red (RJ45/WiFi), puerto 9100 por defecto."""
    ip   = cfg.get('printer_ip', '192.168.34.133')
    port = int(cfg.get('printer_port', 9100))
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.sendall(data)
        return {'ok': True}
    except TimeoutError:
        return {'ok': False, 'msg': f'Timeout al conectar ({ip}:{port})'}
    except ConnectionRefusedError:
        return {'ok': False, 'msg': f'Conexión rechazada ({ip}:{port})'}
    except OSError as e:
        return {'ok': False, 'msg': f'Error de red: {e}'}


def _send_usb_devfile(data: bytes, cfg: dict) -> dict:
    """Envía escribiendo directamente al device USB (kernel usblp).
    No requiere pyusb/libusb; la impresora aparece como /dev/usb/lp0."""
    dev = cfg.get('usb_device', '/dev/usb/lp0')
    if not os.path.exists(dev):
        return {'ok': False, 'msg': f'Dispositivo USB no encontrado ({dev})'}
    try:
        with open(dev, 'wb') as f:
            f.write(data)
        return {'ok': True}
    except PermissionError:
        return {'ok': False, 'msg': f'Sin permisos para {dev} (añadir usuario al grupo lp)'}
    except OSError as e:
        return {'ok': False, 'msg': f'Error USB: {e}'}


def _send_escpos_usb(data: bytes, cfg: dict) -> dict:
    """Envía por USB usando python-escpos (necesita vendor_id/product_id).
    Útil si el kernel no crea /dev/usb/lp0. Requiere: pip install python-escpos pyusb."""
    try:
        from escpos.printer import Usb
    except ImportError:
        return {'ok': False, 'msg': 'python-escpos no instalado (pip install python-escpos pyusb)'}
    try:
        vid = int(str(cfg.get('usb_vendor_id', '0x0000')), 16)
        pid = int(str(cfg.get('usb_product_id', '0x0000')), 16)
        p = Usb(vid, pid)
        p._raw(data)
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'msg': f'Error python-escpos USB: {e}'}


def _send_serial(data: bytes, cfg: dict, timeout: int = 3) -> dict:
    """Envía por RS232/serie. Parámetros de fábrica de la SoL801V:
    115200 baudios, 8 bits de datos, sin paridad, 1 bit de stop, handshake RTS/CTS.
    Requiere: pip install pyserial."""
    try:
        import serial
    except ImportError:
        return {'ok': False, 'msg': 'pyserial no instalado (pip install pyserial)'}
    port = cfg.get('serial_port', '/dev/ttyUSB0')
    baud = int(cfg.get('serial_baud', 115200))
    try:
        with serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,   # 8 bits de datos
            parity=serial.PARITY_NONE,   # sin paridad
            stopbits=serial.STOPBITS_ONE,
            rtscts=True,                 # handshake RTS/CTS (control por hardware)
            timeout=timeout,
            write_timeout=timeout,
        ) as ser:
            ser.write(data)
            ser.flush()
        return {'ok': True}
    except ImportError:
        return {'ok': False, 'msg': 'pyserial no instalado (pip install pyserial)'}
    except Exception as e:
        return {'ok': False, 'msg': f'Error serie ({port}@{baud}): {e}'}


_TRANSPORTS = {
    'network': _send_network,
    'usb':     _send_usb_devfile,
    'escpos':  _send_escpos_usb,
    'serial':  _send_serial,
}


def print_label(job: PrintJob, cfg: dict) -> dict:
    """Construye el ticket y lo envía por el transporte indicado en cfg['backend']."""
    backend = cfg.get('backend', 'network')
    sender  = _TRANSPORTS.get(backend)
    if sender is None:
        return {'ok': False, 'msg': f'Backend desconocido: {backend}'}
    data = build_ticket(job)
    log.info('Enviando %d bytes vía backend=%s', len(data), backend)
    return sender(data, cfg)
