import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError, BleakBluetoothNotAvailableError
from app.config import settings

logger = logging.getLogger("bledom.ble")

# Diccionario de efectos estándar Lotus Lantern / duoCo Strip / ELK-BLEDOM
EFFECTS_MAP: Dict[str, int] = {
    # Modos por saltos (Jumps)
    "jump_rgb": 0x80,
    "jump_7colors": 0x81,
    "jump_red_green": 0x8B,
    "jump_red_blue": 0x8C,
    "jump_green_blue": 0x8D,
    "jump_3colors": 0x80,

    # Modos por gradiente / desvanecimiento (Fades)
    "fade_rgb": 0x82,
    "fade_7colors": 0x83,
    "fade_red": 0x84,
    "fade_green": 0x85,
    "fade_blue": 0x86,
    "fade_yellow": 0x87,
    "fade_cyan": 0x88,
    "fade_purple": 0x89,
    "fade_white": 0x8A,

    # Modos estroboscópicos (Strobe / Flash)
    "strobe_7colors": 0x8E,
    "strobe_red": 0x8F,
    "strobe_green": 0x90,
    "strobe_blue": 0x91,
    "strobe_yellow": 0x92,
    "strobe_cyan": 0x93,
    "strobe_purple": 0x94,
    "strobe_white": 0x95,

    # Alias en español para facilidad de uso
    "arcoiris": 0x83,
    "gradiente_rgb": 0x82,
    "gradiente_7colores": 0x83,
    "salto_rgb": 0x80,
    "salto_7colores": 0x81,
    "estrobo_7colores": 0x8E,
    "estrobo_blanco": 0x95,
}


class BluetoothUnavailableError(Exception):
    """Excepción cuando el adaptador Bluetooth está apagado o no disponible."""
    pass


class DeviceNotFoundError(Exception):
    """Excepción cuando no se encuentra el dispositivo BLE."""
    pass


class BleCommunicationError(Exception):
    """Excepción cuando falla la escritura o conexión GATT."""
    pass


class BledomController:
    """Controlador asíncrono y resiliente para tiras LED con protocolo BLEDOM."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._client: Optional[BleakClient] = None
        self._cached_address: Optional[str] = (
            settings.DEVICE_MAC.strip() if settings.DEVICE_MAC and settings.DEVICE_MAC.strip() else None
        )
        self._cached_name: Optional[str] = None
        self._last_bluetooth_error: Optional[str] = None

        # Estado en memoria de la tira LED
        self.state: Dict[str, Any] = {
            "is_on": False,
            "brightness": 100,
            "color": {"r": 255, "g": 255, "b": 255, "hex": "#FFFFFF"},
            "last_effect": None,
            "last_speed": None,
        }

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    @property
    def cached_address(self) -> Optional[str]:
        return self._cached_address

    @property
    def cached_name(self) -> Optional[str]:
        return self._cached_name

    @property
    def last_error(self) -> Optional[str]:
        return self._last_bluetooth_error

    def _on_disconnected(self, client: BleakClient) -> None:
        """Callback cuando la conexión BLE se pierde inesperadamente."""
        logger.warning(f"Dispositivo BLE desconectado: {client.address}")
        self._client = None

    async def check_bluetooth_status(self) -> Tuple[bool, Optional[str]]:
        """Verifica si el adaptador Bluetooth de Windows está disponible y encendido."""
        try:
            # Prueba rápida de inicialización del scanner
            scanner = BleakScanner()
            self._last_bluetooth_error = None
            return True, None
        except BleakBluetoothNotAvailableError as ex:
            msg = f"Adaptador Bluetooth no disponible o apagado: {ex}"
            self._last_bluetooth_error = msg
            logger.warning(msg)
            return False, msg
        except Exception as ex:
            msg = f"Error al verificar Bluetooth: {ex}"
            self._last_bluetooth_error = msg
            logger.warning(msg)
            return False, msg

    async def _scan_for_device(self) -> Tuple[str, str]:
        """Escanea dispositivos BLE en busca del controlador BLEDOM."""
        logger.info(
            f"Iniciando escaneo BLE (timeout={settings.BLE_TIMEOUT}s) buscando '{settings.DEVICE_NAME_FILTER}'..."
        )
        try:
            devices = await BleakScanner.discover(timeout=settings.BLE_TIMEOUT, return_adv=True)
        except BleakBluetoothNotAvailableError as ex:
            self._last_bluetooth_error = str(ex)
            raise BluetoothUnavailableError(
                "El adaptador Bluetooth de Windows está apagado. Actívalo en la configuración de Windows y vuelve a intentarlo."
            ) from ex
        except Exception as ex:
            self._last_bluetooth_error = str(ex)
            raise BleCommunicationError(f"Error durante el escaneo BLE: {ex}") from ex

        filter_str = settings.DEVICE_NAME_FILTER.lower()
        for device, adv_data in devices.values():
            name = (device.name or adv_data.local_name or "").strip()
            if filter_str in name.lower():
                logger.info(f"Dispositivo BLEDOM detectado: '{name}' en dirección '{device.address}'")
                return device.address, name

        # Búsqueda alternativa por servicios anunciados comunes de BLEDOM (FFF0)
        for device, adv_data in devices.values():
            service_uuids = [u.lower() for u in (adv_data.service_uuids or [])]
            if any("fff0" in u for u in service_uuids):
                name = (device.name or adv_data.local_name or "BLEDOM-Device").strip()
                logger.info(f"Dispositivo detectado por servicio FFF0: '{name}' en '{device.address}'")
                return device.address, name

        raise DeviceNotFoundError(
            f"No se encontró ningún dispositivo BLE con nombre similar a '{settings.DEVICE_NAME_FILTER}'. "
            "Asegúrate de que la tira LED esté energizada y cerca del equipo."
        )

    async def _get_connected_client(self) -> BleakClient:
        """Obtiene un cliente Bleak conectado de forma persistente o lo reconecta."""
        # 1. Si ya hay cliente conectado, devolverlo inmediatamente (<300ms)
        if self._client and self._client.is_connected:
            return self._client

        # 2. Si hay dirección en caché o en settings, intentar conectar directamente
        target_address = self._cached_address or settings.DEVICE_MAC
        if target_address:
            try:
                logger.info(f"Intentando conexión rápida a dirección guardada: {target_address}")
                client = BleakClient(
                    target_address,
                    timeout=settings.BLE_TIMEOUT,
                    disconnected_callback=self._on_disconnected
                )
                await client.connect()
                if client.is_connected:
                    self._client = client
                    self._cached_address = target_address
                    self._last_bluetooth_error = None
                    logger.info("Conexión BLE establecida exitosamente con dispositivo guardado.")
                    return client
            except BleakBluetoothNotAvailableError as ex:
                self._last_bluetooth_error = str(ex)
                raise BluetoothUnavailableError(
                    "El adaptador Bluetooth de Windows está apagado. Actívalo y vuelve a intentarlo."
                ) from ex
            except Exception as ex:
                logger.warning(f"No se pudo conectar a la dirección en caché ({target_address}): {ex}. Procediendo a nuevo escaneo.")
                self._client = None
                if not settings.DEVICE_MAC:
                    self._cached_address = None

        # 3. Escanear en busca del dispositivo
        address, name = await self._scan_for_device()
        self._cached_address = address
        self._cached_name = name

        # 4. Conectar al dispositivo encontrado
        try:
            logger.info(f"Conectando a {name} ({address})...")
            client = BleakClient(
                address,
                timeout=settings.BLE_TIMEOUT,
                disconnected_callback=self._on_disconnected
            )
            await client.connect()
            if not client.is_connected:
                raise BleCommunicationError(f"No se pudo establecer la conexión BLE con {address}.")

            self._client = client
            self._last_bluetooth_error = None
            logger.info("Conexión BLE establecida exitosamente.")
            return client
        except BleakBluetoothNotAvailableError as ex:
            self._last_bluetooth_error = str(ex)
            raise BluetoothUnavailableError("El adaptador Bluetooth de Windows está apagado.") from ex
        except Exception as ex:
            self._client = None
            self._last_bluetooth_error = str(ex)
            raise BleCommunicationError(f"Fallo al conectar con el dispositivo {address}: {ex}") from ex

    async def send_command(self, payload: bytes, retry: bool = True) -> None:
        """
        Envía una trama de 9 bytes a la característica GATT con lock de concurrencia
        y reintento automático si falla la conexión.
        """
        async with self._lock:
            try:
                client = await self._get_connected_client()
                char_uuid = settings.GATT_CHARACTERISTIC_UUID

                logger.debug(f"Escribiendo trama BLE [{payload.hex(' ')}] en {char_uuid}")
                # Escribir sin respuesta (write-without-response) típico de Lotus Lantern / BLEDOM
                try:
                    await client.write_gatt_char(char_uuid, payload, response=False)
                except BleakError:
                    # Fallback si el controlador exige respuesta
                    await client.write_gatt_char(char_uuid, payload, response=True)

            except (BluetoothUnavailableError, DeviceNotFoundError):
                # Errores irrecuperables de hardware o dispositivo ausente
                raise
            except Exception as ex:
                logger.warning(f"Error al enviar comando BLE ({ex}).")
                # Limpiar cliente y caché si corresponde
                if self._client:
                    try:
                        await self._client.disconnect()
                    except Exception:
                        pass
                self._client = None

                if retry:
                    logger.info("Ejecutando reintento automático de conexión y envío...")
                    if not settings.DEVICE_MAC:
                        self._cached_address = None  # Forzar reescaneo fresco
                    await asyncio.sleep(0.5)

                    # Reintento (retry=False para evitar bucle infinito)
                    try:
                        client = await self._get_connected_client()
                        char_uuid = settings.GATT_CHARACTERISTIC_UUID
                        try:
                            await client.write_gatt_char(char_uuid, payload, response=False)
                        except BleakError:
                            await client.write_gatt_char(char_uuid, payload, response=True)
                        logger.info("Reintento exitoso: comando BLE entregado.")
                        return
                    except Exception as retry_ex:
                        logger.error(f"El reintento BLE también falló: {retry_ex}")
                        self._last_bluetooth_error = str(retry_ex)
                        raise BleCommunicationError(
                            f"Fallo en la comunicación BLE tras reintento: {retry_ex}"
                        ) from retry_ex
                else:
                    self._last_bluetooth_error = str(ex)
                    raise BleCommunicationError(f"Fallo en la comunicación BLE: {ex}") from ex

    async def turn_on(self) -> Dict[str, Any]:
        """Encender tira LED: 7e 00 04 f0 00 01 ff 00 ef"""
        payload = bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])
        await self.send_command(payload)
        self.state["is_on"] = True
        return self.state

    async def turn_off(self) -> Dict[str, Any]:
        """Apagar tira LED: 7e 00 04 00 00 00 ff 00 ef"""
        payload = bytes([0x7E, 0x00, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF])
        await self.send_command(payload)
        self.state["is_on"] = False
        return self.state

    async def toggle(self) -> Dict[str, Any]:
        """Alterna el estado encendido/apagado en base a la memoria local."""
        if self.state["is_on"]:
            return await self.turn_off()
        else:
            return await self.turn_on()

    async def set_color(self, r: int, g: int, b: int, auto_on: bool = True) -> Dict[str, Any]:
        """
        Color RGB: [0x7E, 0x00, 0x05, 0x03, R, G, B, 0x00, 0xEF]
        """
        if auto_on and not self.state["is_on"]:
            await self.turn_on()

        payload = bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])
        await self.send_command(payload)

        self.state["is_on"] = True
        self.state["color"] = {
            "r": r,
            "g": g,
            "b": b,
            "hex": f"#{r:02X}{g:02X}{b:02X}"
        }
        return self.state

    async def set_brightness(self, level: int) -> Dict[str, Any]:
        """
        Brillo (0-100): [0x7E, 0x00, 0x01, LEVEL, 0x00, 0x00, 0x00, 0x00, 0xEF]
        """
        clamped_level = max(0, min(100, level))
        payload = bytes([0x7E, 0x00, 0x01, clamped_level, 0x00, 0x00, 0x00, 0x00, 0xEF])
        await self.send_command(payload)

        self.state["brightness"] = clamped_level
        return self.state

    def resolve_effect_code(self, effect_input: str) -> int:
        """Convierte nombre o valor textual en código de efecto hexadecimal de 1 byte."""
        clean = effect_input.strip().lower()
        if clean in EFFECTS_MAP:
            return EFFECTS_MAP[clean]

        # Intentar parsear como hex ('0x80') o decimal ('128')
        try:
            if clean.startswith("0x"):
                code = int(clean, 16)
            else:
                code = int(clean)
            if 0 <= code <= 255:
                return code
        except ValueError:
            pass

        available = ", ".join(list(EFFECTS_MAP.keys())[:8]) + ", etc."
        raise ValueError(
            f"Efecto '{effect_input}' no reconocido. Puedes usar nombres ({available}) o códigos hex como '0x80'."
        )

    async def set_effect(self, effect: str, speed: Optional[int] = None) -> Dict[str, Any]:
        """
        Efecto: [0x7E, 0x00, 0x03, MODE_CODE, 0x03, 0x00, 0x00, 0x00, 0xEF]
        Velocidad: [0x7E, 0x00, 0x02, SPEED, 0x00, 0x00, 0x00, 0x00, 0xEF]
        """
        mode_code = self.resolve_effect_code(effect)
        payload_mode = bytes([0x7E, 0x00, 0x03, mode_code, 0x03, 0x00, 0x00, 0x00, 0xEF])

        # Asegurar encendido
        if not self.state["is_on"]:
            await self.turn_on()

        await self.send_command(payload_mode)
        self.state["last_effect"] = effect

        if speed is not None:
            clamped_speed = max(0, min(100, speed))
            payload_speed = bytes([0x7E, 0x00, 0x02, clamped_speed, 0x00, 0x00, 0x00, 0x00, 0xEF])
            await self.send_command(payload_speed)
            self.state["last_speed"] = clamped_speed

        return self.state

    async def close(self) -> None:
        """Cierra la conexión BLE al apagar el servidor."""
        async with self._lock:
            if self._client:
                try:
                    logger.info("Cerrando conexión BLE activa...")
                    await self._client.disconnect()
                except Exception as ex:
                    logger.debug(f"Error al desconectar cliente: {ex}")
                finally:
                    self._client = None
