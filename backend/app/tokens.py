"""Tokens (*Hợp đồng REST API* — Token) and the host-token dependency."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from fastapi import Header, Request

from app.errors import ApiError
from app.schemas import ERR_BAD_TOKEN, ERR_ROOM_NOT_FOUND

if TYPE_CHECKING:
    from app.game.engine import GameEngine
    from app.rooms import RoomManager


def new_token() -> str:
    """Random 32-byte url-safe token."""
    return secrets.token_urlsafe(32)


def tokens_equal(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return secrets.compare_digest(a.encode(), b.encode())


def get_manager(request: Request) -> RoomManager:
    return request.app.state.rooms  # type: ignore[no-any-return]


def room_or_404(request: Request, pin: str) -> GameEngine:
    engine = get_manager(request).get_by_pin(pin)
    if engine is None:
        raise ApiError(404, ERR_ROOM_NOT_FOUND, f"room {pin} not found")
    return engine


def bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def require_host(
    pin: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> GameEngine:
    """FastAPI dependency: room by PIN (404) whose host token matches the Bearer header (401).

    Tokens belong to a `room_id`, so a token from room A (or from an old room that had
    the same PIN) never matches room B.
    """
    engine = room_or_404(request, pin)
    if not tokens_equal(bearer(authorization), engine.host_token):
        raise ApiError(401, ERR_BAD_TOKEN, "missing or invalid host token")
    return engine
