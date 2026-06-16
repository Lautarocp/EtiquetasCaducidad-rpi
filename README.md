# 🏷️ Relay Etiquetas de Caducidad — Raspberry Pi

Sistema para **imprimir etiquetas de caducidad desde el móvil**. La Raspberry Pi levanta
un punto de acceso WiFi propio; te conectas con el móvil, abres el navegador, rellenas
producto y fechas, y la RPi envía el ticket a la **impresora térmica SoL801V** (por red
RJ45, USB o RS232).

```
   📱 Móvil ──WiFi "Realyetiquetas"──> 🥧 Raspberry Pi ──RJ45 / USB / RS232──> 🖨️ SoL801V
        navegador (frontend web)         Flask, puerto 80                   ESC/POS, 80mm
```

No necesita internet: todo funciona en local sobre el AP de la propia Raspberry.

---

## 📑 Índice

1. [¿Cómo funciona?](#-cómo-funciona)
2. [El problema que resuelve (SSH no se corta)](#-el-problema-que-resuelve-ssh-no-se-corta)
3. [Hardware: impresora SoL801V](#-hardware-impresora-sol801v)
4. [Formas de conectar la impresora](#-formas-de-conectar-la-impresora)
5. [Instalación paso a paso](#-instalación-paso-a-paso)
6. [Modo de uso diario](#-modo-de-uso-diario)
7. [Configurar la impresora (frontend y API)](#-configurar-la-impresora)
8. [Administración del servicio](#-administración-del-servicio)
9. [Actualizar el código](#-actualizar-el-código)
10. [Resolución de problemas](#-resolución-de-problemas)
11. [Estructura del proyecto](#-estructura-del-proyecto)
12. [Referencia de la API](#-referencia-de-la-api)

---

## 🔧 ¿Cómo funciona?

- La RPi corre un servidor **Flask** (vía gunicorn) en el **puerto 80**.
- `wlan0` se configura como **Access Point WiFi** abierto llamado **`Realyetiquetas`**.
- Cualquier móvil que se conecte a ese WiFi puede abrir **http://192.168.4.1** y usar la app.
- Al pulsar **Imprimir**, el navegador envía los datos a la RPi, que construye el ticket
  en formato **ESC/POS** y lo manda a la impresora por el transporte configurado.

---

## 🛡️ El problema que resuelve (SSH no se corta)

**Síntoma original:** al arrancar el proyecto, se reconfiguraba `eth0` para la impresora
y **se perdía la conexión SSH** (porque entrabas por ese mismo cable de red).

**Solución de esta arquitectura:**

> El **SSH y el frontend van por el AP WiFi** (`wlan0` → `192.168.4.1`).
> Así `eth0` queda dedicado **exclusivamente** a la impresora. Pase lo que pase con
> `eth0`, tu acceso SSH por WiFi **nunca se cae**.

| Interfaz | Rol | IP |
|---|---|---|
| `wlan0` | AP WiFi "Realyetiquetas" → frontend **+ SSH** | `192.168.4.1` |
| `eth0`  | Enlace directo a la impresora (solo modo red) | `192.168.34.50` |

Para administrar la RPi, conéctate al WiFi `Realyetiquetas` y haz `ssh n1ce@192.168.4.1`.

---

## 🖨️ Hardware: impresora SoL801V

Datos confirmados de la unidad (HIOPOS / ICG SoL801V, firmware `Sol801v0.54-voice`):

| Parámetro | Valor |
|---|---|
| Comandos | **ESC/POS** |
| Papel | Continuo, **80mm** (ancho impresión 72mm), 203 DPI |
| Fuente | 12×24 → **48 caracteres por línea** |
| Cortador | **ON** (corte automático por ticket) |
| Velocidad | 250 mm/s · Densidad media |
| Interfaces | **RS232 + USB + Ethernet (LAN)** |
| Red | IP fija `192.168.34.133/24`, gateway `192.168.34.96`, **DHCP OFF** |
| Puerto red | TCP **9100** (estado por UDP 9101) |
| Serie | **115200 baudios, 8 bits, sin paridad, handshake RTS/CTS** |

> Es una impresora de **tickets/recibos de 80mm**, no una etiquetadora adhesiva. Cada
> "etiqueta" es un trozo de papel continuo separado por el corte automático.

---

## 🔌 Formas de conectar la impresora

El transporte se elige en `config.json` (campo `backend`) o desde el frontend → ⚙ Config:

| `backend` | Conexión física | Qué necesitas | Recomendación |
|---|---|---|---|
| `network` | **RJ45** (red, TCP 9100) | `setup-printer-net.sh` para poner `eth0` en `192.168.34.x` | ⭐ La más robusta (IP fija) |
| `usb`     | **USB** → `/dev/usb/lp0` | Nada extra; `eth0` queda libre | La más simple para empezar |
| `serial`  | **RS232** (115200 8N1 RTS/CTS) → `/dev/ttyUSB0` | Adaptador USB-serie + `pip install pyserial` | Solo si no hay red/USB |
| `escpos`  | **USB** vía python-escpos (vendor/product id) | `pip install python-escpos pyusb` | Alternativa si falla `/dev/usb/lp0` |

---

## 🚀 Instalación paso a paso

### Requisitos previos

- Raspberry Pi con Raspbian (probado en Trixie) y NetworkManager.
- Acceso SSH inicial a la RPi (en la red local actual: `n1ce@192.168.2.197`).
- La impresora SoL801V.

### Paso 1 — Subir el proyecto a la RPi

Desde tu ordenador, en la carpeta del proyecto:

```bash
rsync -avz --exclude venv --exclude __pycache__ --exclude .git \
  ./ n1ce@192.168.2.197:/tmp/relay-src/
```

> Si prefieres, también puedes clonar el repo directamente en la RPi:
> `git clone https://github.com/Lautarocp/EtiquetasCaducidad-rpi.git /tmp/relay-src`

### Paso 2 — Ejecutar el instalador

```bash
ssh n1ce@192.168.2.197
sudo bash /tmp/relay-src/setup/install.sh
```

El instalador hace todo automáticamente:

1. Instala dependencias del sistema (`python3`, `venv`, `network-manager`).
2. Copia el proyecto a `/home/n1ce/relay-etiquetas`.
3. Crea el entorno virtual e instala las dependencias Python.
4. Instala y arranca el **servicio systemd** (arranque automático al encender).
5. Pregunta si quieres **levantar el AP WiFi** ahora.

### Paso 3 — Configurar la conexión de la impresora

**Opción A · Impresora por RED (RJ45):**

```bash
sudo bash /home/n1ce/relay-etiquetas/setup/setup-printer-net.sh
```

Esto pone `eth0` en `192.168.34.50/24` y hace un `ping` de prueba a `192.168.34.133`.

**Opción B · Impresora por USB:** no hace falta nada de red. Solo elige el backend
`usb` en el frontend (paso siguiente).

### Paso 4 — Reiniciar y comprobar

```bash
sudo reboot
```

Tras reiniciar, el AP `Realyetiquetas` y el servicio arrancan solos.

---

## 📱 Modo de uso diario

1. En el **móvil**, abre los ajustes WiFi y conéctate a la red **`Realyetiquetas`**
   (es abierta, sin contraseña).
2. Abre el navegador en **http://192.168.4.1**
3. En la app:
   - **Producto**: elige un *preset* (rellena nombre y calcula la caducidad según los
     días configurados) o escribe el nombre a mano.
   - **Fechas**: Realización y Envasado vienen con la fecha de hoy; Caducidad se calcula
     sola al elegir un preset (puedes ajustarla). Congelado es opcional.
   - **Copias**: número de etiquetas a imprimir (1–10).
   - **Vista previa**: muestra cómo quedará el ticket.
4. Pulsa **🖨️ Imprimir**. Verás un mensaje verde "Impresión enviada correctamente".
5. Para verificar la impresora sin gastar datos reales, usa **⚙ Imprimir prueba**.

---

## ⚙️ Configurar la impresora

### Desde el frontend

Panel **Impresora → ⚙ Config**. Elige el tipo de conexión y rellena los campos:

- **Red**: IP (`192.168.34.133`) y puerto (`9100`).
- **USB**: ruta del dispositivo (`/dev/usb/lp0`).
- **Serie RS232**: puerto (`/dev/ttyUSB0`) y baudios (`115200`).
- **USB (escpos)**: Vendor ID y Product ID (obtenidos con `lsusb`).

Pulsa **Guardar**. El resumen bajo el panel muestra la conexión activa.

### Desde la API (curl)

```bash
# Red (RJ45)
curl -X POST http://192.168.4.1/config -H 'Content-Type: application/json' \
  -d '{"backend":"network","printer_ip":"192.168.34.133","printer_port":9100}'

# USB
curl -X POST http://192.168.4.1/config -H 'Content-Type: application/json' \
  -d '{"backend":"usb","usb_device":"/dev/usb/lp0"}'

# Serie RS232
curl -X POST http://192.168.4.1/config -H 'Content-Type: application/json' \
  -d '{"backend":"serial","serial_port":"/dev/ttyUSB0","serial_baud":115200}'
```

---

## 🔧 Administración del servicio

```bash
sudo systemctl status  relay-etiquetas   # ver estado
sudo systemctl restart relay-etiquetas   # reiniciar
sudo systemctl stop    relay-etiquetas   # parar
sudo journalctl -u relay-etiquetas -f    # ver logs en vivo
```

---

## 🔄 Actualizar el código

Tras hacer cambios en tu ordenador:

```bash
rsync -avz app.py printer.py products.py static/ \
  n1ce@192.168.4.1:/home/n1ce/relay-etiquetas/
ssh n1ce@192.168.4.1 "sudo systemctl restart relay-etiquetas"
```

---

## 🩺 Resolución de problemas

| Problema | Solución |
|---|---|
| El frontend no carga | `sudo systemctl status relay-etiquetas` y revisa los logs |
| La impresora (red) no responde | `ping 192.168.34.133` desde la RPi; revisa cable y que `eth0` esté en `192.168.34.x` |
| `/dev/usb/lp0` no existe | `ls /dev/usb/` y `dmesg | grep -i usblp`; prueba el backend `escpos` |
| USB: "Sin permisos" | `sudo usermod -aG lp n1ce` y reinicia sesión |
| Serie no imprime | Verifica el puerto (`ls /dev/ttyUSB*`) y que `pyserial` esté instalado |
| Acentos mal impresos | En `printer.py` cambia `CP1252` (`\x1bt\x10`) por CP850 (`\x1bt\x02`) |
| No corta el papel | Comenta la línea `CUT` en `build_ticket()` de `printer.py` |
| El AP no aparece | `nmcli con show RealyetiquetasAP`; `sudo nmcli con up RealyetiquetasAP` |
| Perdí el SSH | Conéctate al WiFi `Realyetiquetas` y entra por `ssh n1ce@192.168.4.1` |

---

## 📂 Estructura del proyecto

```
EtiquetasCaducidad-rpi/
├── app.py                  # Servidor Flask (rutas HTTP)
├── printer.py              # Backend ESC/POS unificado (network/usb/serial/escpos) + build_ticket
├── products.py             # Presets de productos y sus días de caducidad
├── config.example.json     # Plantilla de configuración
├── requirements.txt        # Dependencias Python
├── static/
│   └── index.html          # Frontend completo (HTML+CSS+JS, sin frameworks)
└── setup/
    ├── install.sh             # Instalador completo
    ├── setup-ap.sh            # Configura el AP WiFi (wlan0)
    ├── setup-printer-net.sh   # Configura eth0 para la red de la impresora
    └── relay-etiquetas.service # Unidad systemd
```

---

## 🌐 Referencia de la API

| Método | Ruta | Descripción |
|---|---|---|
| `GET`  | `/` | Sirve el frontend (`static/index.html`) |
| `GET`  | `/health` | Estado del servicio (`{"ok": true}`) |
| `GET`  | `/products` | Lista de presets de productos (JSON) |
| `GET`  | `/config` | Configuración actual de la impresora |
| `POST` | `/config` | Guarda configuración (`backend`, `printer_ip`, `printer_port`, `usb_device`, `serial_port`, `serial_baud`...) |
| `POST` | `/print` | Imprime una etiqueta |

**Ejemplo `POST /print`:**

```bash
curl -X POST http://192.168.4.1/print -H 'Content-Type: application/json' -d '{
  "producto": "Tortilla",
  "realizacion": "16/06/2026",
  "envasado": "16/06/2026",
  "caducidad": "19/06/2026",
  "congelado": "",
  "copias": 1,
  "test": false
}'
```

Respuesta: `{"ok": true}` si imprimió, o `{"ok": false, "msg": "..."}` con el error.
