from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del microservicio BLEDOM."""

    HOST: str = "0.0.0.0"
    PORT: int = 8085
    API_TOKEN: str = "bledom_secure_key_changeme"
    DEVICE_NAME_FILTER: str = "BLEDOM"
    DEVICE_MAC: Optional[str] = None
    BLE_TIMEOUT: float = 8.0
    GATT_CHARACTERISTIC_UUID: str = "0000fff3-0000-1000-8000-00805f9b34fb"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("DEVICE_MAC", mode="before")
    @classmethod
    def clean_empty_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


settings = Settings()
