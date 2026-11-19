# Microservicio Local BLEDOM LED Controller (BLE GATT)

Microservicio HTTP local en Python de alto rendimiento y resiliente para controlar tiras LED equipadas con controladores **BLEDOM** (protocolo GATT estándar de las aplicaciones **Lotus Lantern** y **duoCo Strip**) mediante Bluetooth Low Energy en Windows.

Diseñado específicamente para ser consumido desde **Atajos de iOS (iPhone Shortcuts)**, automatizaciones en **n8n**, Home Assistant, scripts locales o cualquier cliente HTTP.

---

## 📑 Tabla de Contenidos
- [Características Principales](#-características-principales)
- [Arquitectura y Estructura](#-arquitectura-y-estructura)
- [Especificaciones del Protocolo BLEDOM](#-especificaciones-del-protocolo-bledom-ble-gatt)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación Rápida](#-instalación-rápida)
- [Configuración (.env)](#-configuración-env)
- [Ejecución en Windows](#-ejecución-en-windows)
  - [Modo Consola (Primer Plano)](#1-modo-consola-primer-plano)
  - [Modo Oculto en Segundo Plano](#2-modo-oculto-en-segundo-plano)
  - [Inicio Automático con Windows (Task Scheduler o Startup)](#3-inicio-automático-con-windows)
  - [Configuración del Firewall de Windows](#4-abrir-puerto-en-firewall-de-windows-red-local)
- [Catálogo de Endpoints de la API](#-catálogo-de-endpoints-de-la-api)
  - [Ejemplos con cURL](#ejemplos-con-curl)
- [Configuración en iOS Shortcuts (Atajos de iPhone)](#-configuración-en-ios-shortcuts-atajos-de-iphone)
- [Diagnóstico y Logs](#-diagnóstico-y-logs)

---

## 🚀 Características Principales

- **Baja Latencia (<300 ms):** Reutiliza la conexión GATT activa y almacena en caché la dirección del dispositivo tras el primer escaneo.
- **Resiliencia Automática y Auto-Recuperación:** Si Windows desconecta el handle BLE o la tira entra en suspensión, el controlador limpia la caché, reescanea automáticamente y reintenta el comando antes de reportar error.
- **Concurrencia Segura (`asyncio.Lock`):** Serializa las peticiones entrantes para evitar condiciones de carrera o colisiones en la radio Bluetooth de Windows.
- **Seguridad por Header `x-api-key`:** Protege todos los endpoints de control contra accesos no autorizados en la red local.
- **Compatibilidad con formatos de Color:** Acepta tanto componentes enteros `{"r": 255, "g": 100, "b": 0}` como códigos hexadecimales directos `{"hex": "#FF6400"}`.
- **Modos Predefinidos Integrados:** Incluye 30 modos estándar (gradientes, saltos RGB, estroboscópicos, etc.) con control de velocidad (0-100%).

---

## 📁 Arquitectura y Estructura

```
Control Tira LED/
├── app/
│   ├── __init__.py           # Inicializador del módulo
│   ├── config.py             # Configuración vía pydantic-settings y lectura de .env
│   ├── ble_controller.py     # Lógica BLE (Bleak), tramas GATT de 9 bytes, Lock y reintentos
│   ├── models.py             # Modelos Pydantic v2 de validación de entrada/salida
│   └── main.py               # Servidor FastAPI, middleware de seguridad y endpoints
├── scripts/
│   ├── run_server.bat        # Script para ejecutar Uvicorn en Windows
│   ├── start_hidden.vbs      # Script VBScript para arrancar sin ventana de consola
│   └── test_endpoints.py     # Script de diagnóstico e integración de rutas
├── .env.example              # Plantilla de variables de entorno
├── .env                      # Variables locales activas (con token de seguridad)
├── requirements.txt          # Dependencias de Python
└── README.md                 # Documentación técnica completa
```

---

## 📡 Especificaciones del Protocolo BLEDOM (BLE GATT)

Los controladores BLEDOM operan enviando tramas fijas de **9 bytes** con cabecera `0x7E` y terminador `0xEF` sobre la característica GATT:
`0000fff3-0000-1000-8000-00805f9b34fb` (Servicio `0000fff0...`).

| Acción | Estructura de la Trama (9 Bytes) | Ejemplo Hexadecimal |
|---|---|---|
| **Encender (`ON`)** | `[0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF]` | `7e 00 04 f0 00 01 ff 00 ef` |
| **Apagar (`OFF`)** | `[0x7E, 0x00, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF]` | `7e 00 04 00 00 00 ff 00 ef` |
| **Color RGB** | `[0x7E, 0x00, 0x05, 0x03, R, G, B, 0x00, 0xEF]` | `7e 00 05 03 ff 55 00 00 ef` |
| **Brillo (0-100)** | `[0x7E, 0x00, 0x01, LEVEL, 0x00, 0x00, 0x00, 0x00, 0xEF]` | `7e 00 01 64 00 00 00 00 ef` (100%) |
| **Efecto / Modo** | `[0x7E, 0x00, 0x03, MODE_CODE, 0x03, 0x00, 0x00, 0x00, 0xEF]` | `7e 00 03 82 03 00 00 00 ef` (`fade_rgb`) |
| **Velocidad Efecto** | `[0x7E, 0x00, 0x02, SPEED, 0x00, 0x00, 0x00, 0x00, 0xEF]` | `7e 00 02 32 00 00 00 00 ef` (50%) |

---

## ⚙️ Requisitos Previos

1. **Windows 10 / 11** con adaptador Bluetooth 4.0+ habilitado.
2. **Python 3.10 o superior** instalado y añadido al PATH.
3. Tira LED conectada a la corriente y dentro del rango de alcance Bluetooth del PC.

---

## 📦 Instalación Rápida

1. Abre una consola de PowerShell en la carpeta del proyecto:
   ```powershell
   cd "d:\Nueva carpeta\Carpetas Comunes\Antigravity\Control Tira LED"
   ```

2. Crea el entorno virtual e instala las dependencias:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. El archivo de configuración `.env` ya viene creado con un token por defecto. Puedes personalizarlo editándolo con el bloc de notas o cualquier editor.

---

## 🔐 Configuración (`.env`)

```ini
# Token secreto para validar el header 'x-api-key' en peticiones protegidas
API_TOKEN=bledom_a8f9c2d1e4b7036a

# Dirección IP y puerto de escucha (0.0.0.0 permite peticiones desde la red WiFi local)
HOST=0.0.0.0
PORT=8085

# Filtro de búsqueda para descubrir el controlador BLE (BLEDOM o ELK-BLEDOM)
DEVICE_NAME_FILTER=BLEDOM

# Dirección MAC opcional (si se conoce, evita el escaneo inicial conectando directamente)
# Ejemplo: DEVICE_MAC=BE:89:E0:12:34:56
DEVICE_MAC=

# Timeout en segundos para escaneo y conexiones BLE
BLE_TIMEOUT=8.0

# Característica GATT de escritura
GATT_CHARACTERISTIC_UUID=0000fff3-0000-1000-8000-00805f9b34fb

# Nivel de detalle de los logs (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

---

## 🖥️ Ejecución en Windows

### 1. Modo Consola (Primer Plano)
Para iniciar el servidor viendo los logs en tiempo real:
```powershell
.\scripts\run_server.bat
```
La consola mostrará el inicio de FastAPI en `http://0.0.0.0:8085`.

### 2. Modo Oculto en Segundo Plano
Para ejecutar el microservicio silenciosamente sin ninguna ventana emergente en pantalla:
- Haz doble clic sobre `scripts\start_hidden.vbs`, o
- Ejecuta en PowerShell: `wscript.exe .\scripts\start_hidden.vbs`

*(Para detener el proceso en segundo plano en cualquier momento: `taskkill /f /im python.exe` o finaliza el proceso de Python en el Administrador de Tareas).*

### 3. Inicio Automático con Windows

#### Opción A: Carpeta Inicio de Windows (Recomendada y más sencilla)
1. Presiona `Win + R`, escribe `shell:startup` y presiona Enter.
2. Crea un **Acceso Directo** al archivo `scripts\start_hidden.vbs` dentro de esa carpeta.
3. El servicio se levantará automáticamente cada vez que inicies sesión en Windows.

#### Opción B: Programador de Tareas (Task Scheduler)
1. Abre el **Programador de Tareas** (`taskschd.msc`).
2. Haz clic en **Crear tarea básica...**
   - Nombre: `Bledom LED Microservice`.
   - Desencadenador: **Al iniciar la sesión** o **Al iniciar el equipo**.
   - Acción: **Iniciar un programa**.
   - Programa o script: `wscript.exe`
   - Agregar argumentos: `"D:\Nueva carpeta\Carpetas Comunes\Antigravity\Control Tira LED\scripts\start_hidden.vbs"`
   - Iniciar en: `"D:\Nueva carpeta\Carpetas Comunes\Antigravity\Control Tira LED"`
3. Guarda la tarea.

### 4. Abrir Puerto en Firewall de Windows (Red Local)
Para que tu iPhone u otros dispositivos de tu red WiFi puedan alcanzar el microservicio, ejecuta en PowerShell como Administrador:
```powershell
New-NetFirewallRule -DisplayName "BLEDOM LED Controller (Port 8085)" -Direction Inbound -LocalPort 8085 -Protocol TCP -Action Allow
```

---

## 🌐 Catálogo de Endpoints de la API

La documentación interactiva Swagger está disponible en: `http://localhost:8085/docs`.

### Resumen de Rutas

| Método | Endpoint | Autenticación | Descripción |
|---|---|---|---|
| `GET` | `/health` | Pública | Estado del microservicio, adaptador Bluetooth y caché. |
| `GET` | `/led/effects-list` | `x-api-key` | Lista los 30 efectos y códigos disponibles. |
| `POST` | `/led/on` | `x-api-key` | Enciende la tira LED. |
| `POST` | `/led/off` | `x-api-key` | Apaga la tira LED. |
| `POST` | `/led/toggle` | `x-api-key` | Alterna entre encendido y apagado según estado en memoria. |
| `POST` | `/led/color` | `x-api-key` | Establece el color (`{"r":255,"g":0,"b":0}` o `{"hex":"#FF0000"}`). |
| `POST` | `/led/brightness` | `x-api-key` | Ajusta el nivel de brillo (`{"level": 0..100}`). |
| `POST` | `/led/effect` | `x-api-key` | Activa un efecto (`{"effect": "fade_rgb", "speed": 80}`). |

---

### Ejemplos con cURL

> Reemplaza `TU_IP_WINDOWS` con la IP local de tu PC (ej. `192.168.1.50`) y `TU_TOKEN` con el valor de `API_TOKEN` en tu `.env`.

#### 1. Diagnóstico de Salud
```bash
curl -X GET "http://192.168.1.50:8085/health"
```

#### 2. Encender
```bash
curl -X POST "http://192.168.1.50:8085/led/on" \
     -H "x-api-key: bledom_a8f9c2d1e4b7036a"
```

#### 3. Apagar
```bash
curl -X POST "http://192.168.1.50:8085/led/off" \
     -H "x-api-key: bledom_a8f9c2d1e4b7036a"
```

#### 4. Alternar Encendido / Apagado (Toggle)
```bash
curl -X POST "http://192.168.1.50:8085/led/toggle" \
     -H "x-api-key: bledom_a8f9c2d1e4b7036a"
```

#### 5. Cambiar Color (Formato Hexadecimal o RGB)
```bash
# Formato Hexadecimal
curl -X POST "http://192.168.1.50:8085/led/color" \
     -H "x-api-key: bledom_a8f9c2d1e4b7036a" \
     -H "Content-Type: application/json" \
     -d '{"hex": "#FF5500", "auto_on": true}'

# Formato RGB
curl -X POST "http://192.168.1.50:8085/led/color" \
     -H "x-api-key: bledom_a8f9c2d1e4b7036a" \
     -H "Content-Type: application/json" \
     -d '{"r": 0, "g": 200, "b": 255}'
```

#### 6. Ajustar Brillo (0 al 100%)
```bash
curl -X POST "http://192.168.1.50:8085/led/brightness" \
     -H "x-api-key: bledom_a8f9c2d1e4b7036a" \
     -H "Content-Type: application/json" \
     -d '{"level": 50}'
```

#### 7. Activar Modo o Efecto
```bash
curl -X POST "http://192.168.1.50:8085/led/effect" \
     -H "x-api-key: bledom_a8f9c2d1e4b7036a" \
     -H "Content-Type: application/json" \
     -d '{"effect": "fade_rgb", "speed": 60}'
```

---

## 📱 Configuración en iOS Shortcuts (Atajos de iPhone)

Con la app **Atajos** de iOS puedes controlar tu tira LED desde widgets, el Centro de Control o mediante comandos de voz con **Siri** ("Oye Siri, enciende el LED", "Oye Siri, alterna la tira LED").

### Paso a Paso: Crear Atajo "Alternar Luz LED" (Toggle)

1. Abre la app **Atajos** en tu iPhone y pulsa el botón **`+`** (Crear nuevo atajo).
2. Asigna un nombre (ej. `Alternar LED`).
3. Toca **Añadir acción** y busca la acción **"Obtener contenido de URL"** (*Get Contents of URL*).
4. Configura los campos exactamente así:
   - **URL:** `http://192.168.1.50:8085/led/toggle` *(reemplaza con la IP fija de tu PC Windows)*
   - Pulsa en **Mostrar más** (o flecha hacia abajo):
     - **Método:** `POST`
     - **Encabezados (Headers):**
       - Toca **Añadir nuevo encabezado**:
         - Clave: `x-api-key`
         - Texto: `bledom_a8f9c2d1e4b7036a`
5. *(Opcional)* Añade la acción **"Vibración"** o **"Mostrar notificación"** si deseas feedback táctil en el teléfono.
6. Pulsa **Listo**. ¡Ya puedes añadir el atajo como Widget en tu pantalla de inicio o pedirle a Siri "Alternar LED"!

---

### Paso a Paso: Crear Atajo para Cambiar Color o Brillo

Para endpoints que envían datos (`/led/color`, `/led/brightness`, `/led/effect`):

1. En la acción **"Obtener contenido de URL"**:
   - **URL:** `http://192.168.1.50:8085/led/color`
   - **Método:** `POST`
   - **Encabezados:**
     - Clave: `x-api-key` | Valor: `bledom_a8f9c2d1e4b7036a`
     - Clave: `Content-Type` | Valor: `application/json`
   - **Cuerpo de la petición (Request Body):** Selecciona **JSON**.
   - Toca **Añadir nuevo campo**:
     - Tipo: **Texto**
     - Clave: `hex`
     - Valor: `#00E5FF` (o usa la variable "Preguntar cada vez" para elegir el color interactivamente)
     - Tipo: **Booleano**
     - Clave: `auto_on`
     - Valor: `True`

---

## 🔍 Diagnóstico y Logs

El microservicio incluye un script de prueba de extremo a extremo que puedes ejecutar en cualquier momento:

```powershell
.\.venv\Scripts\python.exe scripts\test_endpoints.py
```

### Respuestas de Estado Semánticas
- **HTTP 200 OK:** Comando transmitido exitosamente por BLE GATT a la tira LED.
- **HTTP 401 Unauthorized:** Header `x-api-key` ausente o no coincide con el token del `.env`.
- **HTTP 404 Not Found:** La tira BLEDOM no fue encontrada en el escaneo (asegúrate de que esté energizada).
- **HTTP 502 Bad Gateway:** Error de comunicación GATT tras el reintento automático.
- **HTTP 503 Service Unavailable:** El adaptador Bluetooth de Windows está apagado o deshabilitado en el sistema operativo.
