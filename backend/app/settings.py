"""Runtime settings, read from environment variables (and `.env` if present)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    max_rooms: int = Field(default=20, ge=1, validation_alias="MAX_ROOMS")
    room_idle_minutes: float = Field(default=30, gt=0, validation_alias="ROOM_IDLE_MINUTES")
    code_cooldown_minutes: float = Field(default=30, ge=0, validation_alias="CODE_COOLDOWN_MINUTES")
    lan_ip: str | None = Field(default=None, validation_alias="LAN_IP")
    app_port: int | None = Field(default=None, validation_alias="APP_PORT")
    avatars_dir: Path = Field(default=BACKEND_DIR / "avatars", validation_alias="AVATARS_DIR")
    static_dir: Path | None = Field(default=None, validation_alias="STATIC_DIR")

    @field_validator("lan_ip", "app_port", "static_dir", mode="before")
    @classmethod
    def _blank_is_none(cls, v: object) -> object:
        # `.env` lines like `LAN_IP=` give an empty string: treat as unset.
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
