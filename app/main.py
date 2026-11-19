import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ble_controller import (
    BledomController,
    BluetoothUnavailableError,
    DeviceNotFoundError,
    BleCommunicationError,
    EFFECTS_MAP,
)
from app.models import (
    ColorRequest,
    BrightnessRequest,
    EffectRequest,
    StateResponse,
    HealthResponse,
)

# Configurar Logging estructurado
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bledom.api")

# Instancia global del controlador
controller = BledomController()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación FastAPI."""
    logger.info("=== BLEDOM LED Controller Microservice Iniciando ===")
    logger.info(f"Escuchando en http://{settings.HOST}:{settings.PORT}")
    logger.info(f"Filtro de dispositivo BLE: '{settings.DEVICE_NAME_FILTER}'")
    if settings.DEVICE_MAC:
        logger.info(f"Dirección MAC fija configurada: {settings.DEVICE_MAC}")

    ready, err = await controller.check_bluetooth_status()
    if not ready:
        logger.warning(f"ADVERTENCIA: Adaptador Bluetooth reporta estado: {err}")
    else:
        logger.info("Adaptador Bluetooth detectado y listo.")

    yield

    logger.info("Cerrando servicio BLEDOM...")
    await controller.close()
    logger.info("Servicio detenido limpiamente.")


app = FastAPI(
    title="BLEDOM LED Controller Microservice",
    description="Microservicio REST local para el control de tiras LED con protocolo BLEDOM (Lotus Lantern / duoCo Strip) vía BLE GATT.",
    version="1.0.0",
    lifespan=lifespan,
)

# Habilitar CORS para integración con cualquier cliente web o local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="x-api-key")) -> str:
    """Valida el token de autenticación en el header x-api-key."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado de autenticación 'x-api-key'.",
        )
    if x_api_key != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 'x-api-key' inválido o no autorizado.",
        )
    return x_api_key


# Exception Handlers para códigos HTTP semánticos
@app.exception_handler(BluetoothUnavailableError)
async def bluetooth_unavailable_handler(request: Request, exc: BluetoothUnavailableError):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc)},
    )


@app.exception_handler(DeviceNotFoundError)
async def device_not_found_handler(request: Request, exc: DeviceNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(BleCommunicationError)
async def ble_comm_error_handler(request: Request, exc: BleCommunicationError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc)},
    )


# --- Endpoints Públicos ---

@app.get("/", tags=["Info"])
async def root():
    """Ruta raíz de bienvenida y documentación."""
    return {
        "service": "BLEDOM LED Controller",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Diagnóstico"])
async def health_check():
    """
    Endpoint público de diagnóstico.
    Informa el estado del servicio, del adaptador Bluetooth y si el dispositivo está en caché.
    """
    bt_ready, bt_err = await controller.check_bluetooth_status()
    return HealthResponse(
        status="healthy" if bt_ready else "degraded",
        service="bledom-controller",
        bluetooth_ready=bt_ready,
        bluetooth_error=bt_err,
        device_cached=controller.cached_address is not None,
        device_address=controller.cached_address,
        device_name=controller.cached_name,
        is_connected=controller.is_connected,
        state=controller.state,
    )


@app.get("/led/effects-list", tags=["Control LED"], dependencies=[Depends(verify_api_key)])
async def list_effects():
    """Lista todos los efectos predefinidos disponibles por nombre y código."""
    return {
        "count": len(EFFECTS_MAP),
        "effects": EFFECTS_MAP,
    }


# --- Endpoints Protegidos (/led/*) ---

@app.post("/led/on", response_model=StateResponse, tags=["Control LED"], dependencies=[Depends(verify_api_key)])
async def turn_led_on():
    """Enciende la tira LED (trama 7e 00 04 f0 00 01 ff 00 ef)."""
    try:
        new_state = await controller.turn_on()
        return StateResponse(
            success=True,
            message="Tira LED encendida exitosamente.",
            state=new_state,
        )
    except (BluetoothUnavailableError, DeviceNotFoundError, BleCommunicationError):
        raise
    except Exception as ex:
        logger.error(f"Error inesperado al encender: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado: {ex}")


@app.post("/led/off", response_model=StateResponse, tags=["Control LED"], dependencies=[Depends(verify_api_key)])
async def turn_led_off():
    """Apaga la tira LED (trama 7e 00 04 00 00 00 ff 00 ef)."""
    try:
        new_state = await controller.turn_off()
        return StateResponse(
            success=True,
            message="Tira LED apagada exitosamente.",
            state=new_state,
        )
    except (BluetoothUnavailableError, DeviceNotFoundError, BleCommunicationError):
        raise
    except Exception as ex:
        logger.error(f"Error inesperado al apagar: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado: {ex}")


@app.post("/led/toggle", response_model=StateResponse, tags=["Control LED"], dependencies=[Depends(verify_api_key)])
async def toggle_led():
    """Alterna el estado de la tira LED (On <-> Off)."""
    try:
        new_state = await controller.toggle()
        action = "encendida" if new_state["is_on"] else "apagada"
        return StateResponse(
            success=True,
            message=f"Tira LED conmutada a {action}.",
            state=new_state,
        )
    except (BluetoothUnavailableError, DeviceNotFoundError, BleCommunicationError):
        raise
    except Exception as ex:
        logger.error(f"Error inesperado al alternar: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado: {ex}")


@app.post("/led/color", response_model=StateResponse, tags=["Control LED"], dependencies=[Depends(verify_api_key)])
async def set_led_color(payload: ColorRequest):
    """
    Establece el color RGB de la tira LED.
    Acepta tanto {"r": 255, "g": 85, "b": 0} como {"hex": "#FF5500"}.
    """
    try:
        new_state = await controller.set_color(
            r=payload.r,
            g=payload.g,
            b=payload.b,
            auto_on=payload.auto_on,
        )
        return StateResponse(
            success=True,
            message=f"Color aplicado: {payload.hex} (R={payload.r}, G={payload.g}, B={payload.b}).",
            state=new_state,
        )
    except (BluetoothUnavailableError, DeviceNotFoundError, BleCommunicationError):
        raise
    except Exception as ex:
        logger.error(f"Error inesperado al cambiar color: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado: {ex}")


@app.post("/led/brightness", response_model=StateResponse, tags=["Control LED"], dependencies=[Depends(verify_api_key)])
async def set_led_brightness(payload: BrightnessRequest):
    """Ajusta el nivel de brillo de la tira LED (0 a 100)."""
    try:
        new_state = await controller.set_brightness(level=payload.level)
        return StateResponse(
            success=True,
            message=f"Nivel de brillo ajustado al {payload.level}%.",
            state=new_state,
        )
    except (BluetoothUnavailableError, DeviceNotFoundError, BleCommunicationError):
        raise
    except Exception as ex:
        logger.error(f"Error inesperado al ajustar brillo: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado: {ex}")


@app.post("/led/effect", response_model=StateResponse, tags=["Control LED"], dependencies=[Depends(verify_api_key)])
async def set_led_effect(payload: EffectRequest):
    """
    Activa un efecto o modo predefinido (ej. 'fade_rgb', 'jump_7colors') y velocidad opcional (0-100).
    """
    try:
        new_state = await controller.set_effect(
            effect=payload.effect,
            speed=payload.speed,
        )
        speed_msg = f" a velocidad {payload.speed}%" if payload.speed is not None else ""
        return StateResponse(
            success=True,
            message=f"Efecto '{payload.effect}' activado{speed_msg}.",
            state=new_state,
        )
    except ValueError as val_ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_ex))
    except (BluetoothUnavailableError, DeviceNotFoundError, BleCommunicationError):
        raise
    except Exception as ex:
        logger.error(f"Error inesperado al aplicar efecto: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error inesperado: {ex}")
