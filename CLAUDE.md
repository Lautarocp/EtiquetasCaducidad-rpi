# CLAUDE.md — Relay Etiquetas Caducidad (Raspberry Pi)

App Python/Flask en Raspberry Pi. La RPi levanta un AP WiFi y sirve el frontend en
puerto 80. El móvil se conecta al AP, abre el navegador e imprime etiquetas de
caducidad en una impresora térmica ESC/POS (SoL801) por **red (RJ45)** o **USB**.

## Principio de arquitectura (importante)

**SSH y frontend van por el AP WiFi (wlan0 = 192.168.4.1).** `eth0` queda dedicado
exclusivamente a la impresora. Esto evita el bug original de perder SSH al
reconfigurar `eth0`. Nunca hagas que el SSH dependa de `eth0`.

## Acceso SSH

```
# Red local actual (antes de levantar AP):
ssh n1ce@192.168.2.197    password: Millonario

# Por el AP (después de setup-ap.sh):
ssh n1ce@192.168.4.1      password: Millonario
```

## Red

| Interfaz | Rol | IP |
|---|---|---|
| wlan0 | AP "Realyetiquetas" (frontend + SSH) | 192.168.4.1 |
| eth0  | Enlace impresora (solo backend network) | 192.168.34.50 |

Impresora SoL801: 192.168.34.133, gateway 192.168.34.96, puerto ESC/POS 9100.

## Backends de impresión (config.json → "backend")

- `network` → TCP a `printer_ip:printer_port` (RJ45/WiFi). Default.
- `usb`     → escribe a `/dev/usb/lp0` (kernel usblp). Sin deps extra.
- `escpos`  → python-escpos `Usb(vendor_id, product_id)`. Requiere `python-escpos pyusb`.

Toda la lógica de transporte está en `printer.py`; el ticket ESC/POS se construye una
sola vez en `build_ticket()` y se envía como bytes crudos por cualquier backend.

## Gestión de red desde la web (eth0)

`netcfg.py` permite poner eth0 en la red de la impresora desde el frontend (seguro
porque entras por el AP/wlan0, no se corta). Rutas:
- `GET  /network/status` → IP/conexión/modo de eth0 (printer|local)
- `POST /network/printer-mode` → eth0 a `eth_ip`/`eth_gateway` (config) + ping a la impresora
- `POST /network/local-mode` → eth0 de vuelta a DHCP
El servicio corre como root, así que nmcli se ejecuta sin sudo. Equivale a
setup-printer-net.sh pero por navegador.

## Estructura

```
/home/n1ce/relay-etiquetas/   ← instalado en la RPi
├── app.py            ← Flask, rutas HTTP
├── printer.py        ← backend ESC/POS unificado + build_ticket
├── netcfg.py         ← gestión eth0 (nmcli) desde la web
├── products.py       ← presets
├── config.json       ← runtime (desde config.example.json)
├── static/index.html ← frontend
├── setup/            ← install.sh, setup-ap.sh, setup-printer-net.sh, *.service
└── venv/
```

## Servicio

```bash
sudo systemctl status relay-etiquetas
sudo systemctl restart relay-etiquetas
sudo journalctl -u relay-etiquetas -f
```

## Instalar / actualizar

```bash
# Instalar desde cero
rsync -avz --exclude venv --exclude .git ./ n1ce@192.168.2.197:/tmp/relay-src/
ssh n1ce@192.168.2.197 "sudo bash /tmp/relay-src/setup/install.sh"

# Actualizar código
rsync -avz app.py printer.py products.py static/ n1ce@192.168.4.1:/home/n1ce/relay-etiquetas/
ssh n1ce@192.168.4.1 "sudo systemctl restart relay-etiquetas"
```

## Troubleshooting

- Acentos mal → en `printer.py` cambiar `\x1bt\x10` (CP1252) por `\x1bt\x02` (CP850).
- Sin cortador → comentar `CUT` en `build_ticket()`.
- USB sin permisos → `sudo usermod -aG lp n1ce`.
- Impresora red no responde → `ping 192.168.34.133` desde la RPi.
