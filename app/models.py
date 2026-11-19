import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class ColorRequest(BaseModel):
    """Modelo para cambio de color RGB o Hexadecimal."""
    r: Optional[int] = Field(default=None, ge=0, le=255, description="Canal Rojo (0-255)")
    g: Optional[int] = Field(default=None, ge=0, le=255, description="Canal Verde (0-255)")
    b: Optional[int] = Field(default=None, ge=0, le=255, description="Canal Azul (0-255)")
    hex: Optional[str] = Field(default=None, description="Color en código hexadecimal (#RRGGBB o RRGGBB)")
    auto_on: bool = Field(default=True, description="Enciende la tira antes de aplicar color si está apagada")

    @model_validator(mode="after")
    def validate_and_convert(self) -> "ColorRequest":
        if self.hex is not None:
            clean_hex = self.hex.strip().lstrip("#")
            if not re.fullmatch(r"^[0-9a-fA-F]{6}$", clean_hex):
                raise ValueError("El formato hex debe ser un código de 6 caracteres hexadecimales (ej. #FF5500 o FF5500).")
            self.r = int(clean_hex[0:2], 16)
            self.g = int(clean_hex[2:4], 16)
            self.b = int(clean_hex[4:6], 16)
            self.hex = f"#{clean_hex.upper()}"
        elif self.r is not None and self.g is not None and self.b is not None:
            self.hex = f"#{self.r:02X}{self.g:02X}{self.b:02X}"
        else:
            raise ValueError("Debes proporcionar 'hex' (ej: '#FF5500') o la terna completa ('r', 'g', 'b').")

        return self


class BrightnessRequest(BaseModel):
    """Modelo para ajuste de brillo."""
    level: int = Field(..., ge=0, le=100, description="Nivel de brillo en porcentaje (0-100)")


class EffectRequest(BaseModel):
    """Modelo para activar efectos predefinidos y velocidad."""
    effect: str = Field(..., description="Nombre del efecto (ej. 'fade_rgb', 'jump_7colors') o código (ej. '0x80', '128')")
    speed: Optional[int] = Field(default=None, ge=0, le=100, description="Velocidad del efecto (0-100)")


class StateResponse(BaseModel):
    """Respuesta general con el estado del dispositivo."""
    success: bool
    message: str
    state: Dict[str, Any]


class HealthResponse(BaseModel):
    """Respuesta del endpoint de salud y diagnóstico."""
    status: str
    service: str
    bluetooth_ready: bool
    bluetooth_error: Optional[str] = None
    device_cached: bool
    device_address: Optional[str] = None
    device_name: Optional[str] = None
    is_connected: bool
    state: Dict[str, Any]
