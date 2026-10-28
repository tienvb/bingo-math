from __future__ import annotations

import pytest

from app.settings import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("MAX_ROOMS", "ROOM_IDLE_MINUTES", "CODE_COOLDOWN_MINUTES", "LAN_IP", "APP_PORT",
              "AVATARS_DIR", "STATIC_DIR"):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None)
    assert s.max_rooms == 20 and s.room_idle_minutes == 30 and s.code_cooldown_minutes == 30
    assert s.lan_ip is None and s.app_port is None and s.static_dir is None
    assert s.avatars_dir.name == "avatars"


def test_env_and_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_ROOMS", "3")
    monkeypatch.setenv("LAN_IP", "  ")
    monkeypatch.setenv("APP_PORT", "8080")
    s = Settings(_env_file=None)
    assert s.max_rooms == 3 and s.lan_ip is None and s.app_port == 8080
