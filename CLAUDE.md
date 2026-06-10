# CLAUDE.md — Relay Etiquetas Caducidad (Raspberry Pi 3B)

Proyecto Python/Flask que corre en una Raspberry Pi 3B con Raspbian 13 (Debian Trixie).
La RPi genera un AP WiFi y sirve el frontend en el puerto 80. La impresora térmica
se conecta directamente al puerto eth0.

## Acceso SSH

```
# Mientras la RPi está en la red local original (antes de activar AP):
ssh n1ce@192.168.2.179   password: Millonario

# Después de activar el AP (conectado a la red RelayEtiquetas):
ssh n1ce@192.168.4.1     password: Millonario
```

## Estructura del proyecto

```
/home/n1ce/relay-etiquetas/   ← instalado en la RPi
├── app.py                    ← servidor Flask, rutas HTTP
├── escpos_helper.py          ← ESC/POS TCP + PrintJob dataclass
├── products.py               ← lista de presets de productos
├── config.json               ← IP/puerto impresora (generado en runtime)
├── requirements.txt          ← flask, gunicorn
├── static/
│   └── index.html            ← frontend completo (vanilla JS)
└── venv/                     ← entorno virtual Python
```

## Red (NetworkManager)

| Interfaz | Rol | IP |
|---|---|---|
| wlan0 | AP WiFi "RelayEtiquetas" | 192.168.4.1 |
| eth0 | Enlace directo impresora | 192.168.168.1 |

La impresora debe tener IP estática **192.168.168.100** configurada en sus propios ajustes.
El AP usa `ipv4.method=shared` — NetworkManager gestiona el DHCP para clientes
automáticamente (rango 192.168.4.x).

## Servicio

```bash
sudo systemctl status relay-etiquetas
sudo systemctl restart relay-etiquetas
sudo journalctl -u relay-etiquetas -f
```

## Instalar desde cero

```bash
# 1. Subir archivos (desde Mac/Linux con acceso a 192.168.2.179)
rsync -avz --exclude venv --exclude __pycache__ --exclude '*.pyc' \
  /ruta/local/EtiquetasCaducidad-rpi/ n1ce@192.168.2.179:/tmp/relay-src/

# 2. En la RPi, ejecutar el instalador
ssh n1ce@192.168.2.179
sudo bash /tmp/relay-src/setup/install.sh

# 3. Reiniciar
sudo reboot
```

## Actualizar código sin reinstalar

```bash
# Subir solo archivos Python/HTML
rsync -avz app.py escpos_helper.py products.py static/ \
  n1ce@192.168.4.1:/home/n1ce/relay-etiquetas/

# Reiniciar servicio
ssh n1ce@192.168.4.1 "sudo systemctl restart relay-etiquetas"
```

## Cambiar IP de la impresora

Desde el frontend en http://192.168.4.1 → panel "Impresora ⚙ Config".
O por API:

```bash
curl -X POST http://192.168.4.1/config \
  -H 'Content-Type: application/json' \
  -d '{"printer_ip":"192.168.168.100","printer_port":9100}'
```

## Dependencias en Debian Trixie

```bash
sudo apt install python3 python3-venv python3-pip
# (NetworkManager ya está instalado por defecto)
```

## Troubleshooting

- **Frontend no carga**: `sudo systemctl status relay-etiquetas`
- **Impresora no responde**: `ping 192.168.168.100` desde la RPi
- **AP no aparece**: `nmcli con show RelayEtiquetas` y `sudo nmcli con up RelayEtiquetas`
- **Acentos en tickets**: cambiar `\x10` por `\x02` en `escpos_helper.py` (línea CP1252)
- **Sin corte de papel**: comentar la línea `CUT` en `build_ticket()` de `escpos_helper.py`
