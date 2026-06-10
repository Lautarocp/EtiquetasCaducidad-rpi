"""
Generador de comandos ESC/POS y cliente TCP para impresora térmica de red.
"""
import socket
from dataclasses import dataclass


@dataclass
class PrintJob:
    producto:    str  = ''
    realizacion: str  = ''
    envasado:    str  = ''
    caducidad:   str  = ''
    congelado:   str  = ''
    copies:      int  = 1
    test_mode:   bool = False


def _line(text: str) -> bytes:
    """Codifica una línea como Latin-1 (compatible WPC1252) + CR+LF.
    Latin-1 cubre todos los caracteres del español sin conversión extra.
    Si una impresora muy antigua da problemas, cambiar 'replace' por 'ignore'.
    """
    return text.encode('latin-1', errors='replace') + b'\r\n'


def build_ticket(job: PrintJob) -> bytes:
    """Genera el buffer ESC/POS completo listo para enviar por TCP."""

    # ── Comandos ESC/POS ──────────────────────────────────────────────────────
    INIT      = b'\x1b@'       # ESC @  — inicializar impresora
    CP1252    = b'\x1bt\x10'   # ESC t  — code page WPC1252 (cambiar \x10 si hay
                                #          problemas de acentos: \x02=CP850, \x00=CP437)
    ALIGN_L   = b'\x1ba\x00'   # ESC a  — alineación izquierda
    ALIGN_C   = b'\x1ba\x01'   # ESC a  — alineación centro
    SIZE_NORM = b'\x1b!\x00'   # ESC !  — tamaño normal
    SIZE_DBL  = b'\x1b!\x30'   # ESC !  — doble alto + doble ancho
    BOLD_ON   = b'\x1bE\x01'   # ESC E  — negrita on
    BOLD_OFF  = b'\x1bE\x00'   # ESC E  — negrita off
    FEED      = b'\x1bd\x04'   # ESC d  — avanzar 4 líneas
    CUT       = b'\x1dV\x01'   # GS  V  — corte parcial
    #                            ↑ comentar la línea CUT y el uso de 'CUT' abajo
    #                              si la impresora no tiene cortador de papel

    buf = bytearray()

    for _ in range(job.copies):
        buf += INIT + CP1252

        if job.test_mode:
            buf += ALIGN_C + BOLD_ON
            buf += _line('-- PRUEBA DE IMPRESION --')
            buf += BOLD_OFF
            buf += _line('RPi Relay Etiquetas v1.0')
            buf += _line('Impresora OK')
            buf += _line('')
        else:
            # Nombre del producto — centrado, doble tamaño
            buf += ALIGN_C + SIZE_DBL
            buf += _line(job.producto)

            # Fechas — izquierda, tamaño normal
            buf += SIZE_NORM + ALIGN_L
            buf += _line(f'Realizacion: {job.realizacion}')
            buf += _line(f'Envasado:    {job.envasado}')

            # Caducidad — centrado, doble tamaño
            buf += ALIGN_C + SIZE_DBL
            buf += _line(f'CAD: {job.caducidad}')

            # Congelado (opcional)
            if job.congelado:
                buf += SIZE_NORM + ALIGN_L
                buf += _line(f'Congelado:   {job.congelado}')

            buf += SIZE_NORM + _line('')

        buf += FEED + CUT

    return bytes(buf)


def print_label(job: PrintJob, printer_ip: str, printer_port: int = 9100,
                timeout: int = 3) -> dict:
    """Conecta a la impresora por TCP y envía el ticket ESC/POS."""
    ticket = build_ticket(job)
    try:
        with socket.create_connection((printer_ip, printer_port), timeout=timeout) as sock:
            sock.sendall(ticket)
        return {'ok': True}
    except TimeoutError:
        return {'ok': False, 'msg': f'Timeout al conectar ({printer_ip}:{printer_port})'}
    except ConnectionRefusedError:
        return {'ok': False, 'msg': f'Conexión rechazada ({printer_ip}:{printer_port})'}
    except OSError as e:
        return {'ok': False, 'msg': f'Error de red: {e}'}
