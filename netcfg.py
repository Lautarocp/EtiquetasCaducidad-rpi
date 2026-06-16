"""
Gestión de la interfaz eth0 vía NetworkManager (nmcli), para activar/desactivar
la red de la impresora desde el frontend.

Seguro de usar desde la web porque el frontend se sirve por el AP WiFi (wlan0):
reconfigurar eth0 NO corta esa conexión. El servicio corre como root, así que
puede ejecutar nmcli directamente (sin sudo).

Las operaciones son fijas (no reciben comandos del usuario) → sin inyección.
"""
import subprocess

ETH_IFACE = 'eth0'
CON_NAME  = 'PrinterLink'


def _run(args: list[str], timeout: int = 25) -> tuple[bool, str]:
    """Ejecuta un comando y devuelve (ok, salida). Nunca lanza excepción."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr).strip()
        return p.returncode == 0, out
    except Exception as e:
        return False, str(e)


def get_eth_status() -> dict:
    """Estado actual de eth0: IP, conexión activa y modo (printer/local)."""
    ok_ip, ip = _run(['nmcli', '-g', 'IP4.ADDRESS', 'device', 'show', ETH_IFACE])
    ok_con, con = _run(['nmcli', '-t', '-g', 'GENERAL.CONNECTION', 'device', 'show', ETH_IFACE])
    ip = ip.split('\n')[0].strip() if ok_ip else ''
    con = con.strip() if ok_con else ''
    mode = 'printer' if con == CON_NAME else 'local'
    return {'iface': ETH_IFACE, 'ip': ip, 'connection': con, 'mode': mode}


def set_printer_mode(eth_ip: str, eth_gateway: str, printer_ip: str) -> dict:
    """Pone eth0 en la red de la impresora (IP estática) y prueba el alcance."""
    _run(['nmcli', 'con', 'delete', CON_NAME])  # idempotente, ignora error
    ok_add, out_add = _run(['nmcli', 'con', 'add', 'type', 'ethernet',
                            'ifname', ETH_IFACE, 'con-name', CON_NAME, 'autoconnect', 'yes'])
    if not ok_add:
        return {'ok': False, 'msg': f'No se pudo crear la conexión: {out_add}'}

    ok_mod, out_mod = _run(['nmcli', 'con', 'modify', CON_NAME,
                            'ipv4.method', 'manual',
                            'ipv4.addresses', eth_ip,
                            'ipv4.gateway', eth_gateway,
                            'ipv4.never-default', 'yes'])
    if not ok_mod:
        return {'ok': False, 'msg': f'No se pudo configurar IP: {out_mod}'}

    ok_up, out_up = _run(['nmcli', 'con', 'up', CON_NAME])
    if not ok_up:
        return {'ok': False, 'msg': f'No se pudo activar eth0: {out_up}'}

    # Prueba de alcance a la impresora
    reachable, _ = _run(['ping', '-c', '2', '-W', '2', printer_ip], timeout=8)
    return {
        'ok': True,
        'msg': f'eth0 en {eth_ip}. Impresora {printer_ip}: '
               + ('alcanzable ✔' if reachable else 'NO responde (revisa cable/encendido)'),
        'reachable': reachable,
        'status': get_eth_status(),
    }


def set_local_mode() -> dict:
    """Devuelve eth0 a DHCP/red local (borra la conexión de impresora)."""
    _run(['nmcli', 'con', 'down', CON_NAME])
    _run(['nmcli', 'con', 'delete', CON_NAME])
    ok, out = _run(['nmcli', 'device', 'connect', ETH_IFACE])
    return {
        'ok': ok,
        'msg': 'eth0 vuelto a DHCP/red local.' if ok else f'Aviso: {out}',
        'status': get_eth_status(),
    }
