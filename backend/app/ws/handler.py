"""`/ws?pin&role&token`: authenticate, register, then pump messages both ways."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

import anyio
from typing import TYPE_CHECKING

from fastapi import WebSocket
from pydantic import ValidationError

from app.schemas import (
    CLIENT_MESSAGE_TYPES,
    ERR_INVALID_MESSAGE,
    WS_CLOSE_BAD_TOKEN,
    WS_CLOSE_KICKED,
    WS_CLOSE_ROOM_CLOSED,
    WS_CLOSE_ROOM_NOT_FOUND,
    ErrorData,
    KickedData,
    PongData,
    RawWsMessage,
    RequestHelpData,
    RoomClosedData,
    SubmitAnswerData,
    ws_message,
)
from app.tokens import tokens_equal
from app.ws.manager import ROLES, Connection

if TYPE_CHECKING:
    from app.game.engine import GameEngine
    from app.rooms import RoomManager

log = logging.getLogger("bingo.ws")


def _error(code: str, message: str) -> dict[str, object]:
    return ws_message("error", ErrorData(code=code, message=message))


async def _reject(websocket: WebSocket, code: int, first: dict[str, object] | None = None) -> None:
    with contextlib.suppress(Exception):
        if first is not None:
            await websocket.send_json(first)
        await websocket.close(code=code)


async def websocket_endpoint(websocket: WebSocket) -> None:
    manager: RoomManager = websocket.app.state.rooms
    params = websocket.query_params
    pin = params.get("pin", "")
    role = params.get("role", "")
    token = params.get("token", "")

    # Accept first: a close code sent before accept never reaches the browser.
    await websocket.accept()

    engine = manager.get_by_pin(pin)
    if engine is None:
        reason = manager.closed_reason(pin)
        if reason is not None:
            await _reject(websocket, WS_CLOSE_ROOM_CLOSED, ws_message("room_closed", RoomClosedData(reason=reason)))
        else:
            await _reject(websocket, WS_CLOSE_ROOM_NOT_FOUND)
        return

    player_id: str | None = None
    if role not in ROLES:
        await _reject(websocket, WS_CLOSE_BAD_TOKEN)
        return
    if role == "host":
        ok = tokens_equal(token, engine.host_token)
    elif role == "screen":
        ok = tokens_equal(token, engine.screen_token)
    else:
        player = engine.player_by_token(token)
        ok = player is not None
        if player is not None:
            player_id = player.id
        elif engine.is_kicked_token(token):
            await _reject(websocket, WS_CLOSE_KICKED, ws_message("kicked", KickedData()))
            return
    if not ok:
        await _reject(websocket, WS_CLOSE_BAD_TOKEN)
        return

    conn = Connection(websocket, role, player_id)  # type: ignore[arg-type]
    await engine.connect(conn)
    sender = asyncio.create_task(conn.run_sender())
    receiver = asyncio.create_task(_receive_loop(websocket, engine, conn))
    try:
        await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (sender, receiver):
            task.cancel()
        # Shielded: the socket may be torn down by cancellation, but the room must
        # still learn that this connection is gone.
        with anyio.CancelScope(shield=True):
            for task in (sender, receiver):
                with contextlib.suppress(BaseException):
                    await task
            await engine.disconnect(conn)


async def _receive_loop(websocket: WebSocket, engine: GameEngine, conn: Connection) -> None:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
        text = message.get("text")
        if text is None and message.get("bytes") is not None:
            text = message["bytes"].decode("utf-8", errors="replace")
        await _handle_text(text or "", engine, conn)


async def _handle_text(text: str, engine: GameEngine, conn: Connection) -> None:
    try:
        raw = RawWsMessage.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        conn.send(_error(ERR_INVALID_MESSAGE, "message must be {\"type\": str, \"data\": object}"))
        return
    model = CLIENT_MESSAGE_TYPES.get(raw.type)
    if model is None:
        conn.send(_error(ERR_INVALID_MESSAGE, f"unknown message type {raw.type!r}"))
        return
    if raw.type != "ping" and conn.role != "player":
        conn.send(_error(ERR_INVALID_MESSAGE, f"role {conn.role!r} cannot send {raw.type!r}"))
        return
    try:
        data = model.model_validate(raw.data)
    except ValidationError as exc:
        conn.send(_error(ERR_INVALID_MESSAGE, f"invalid data for {raw.type!r}: {exc.errors()[0]['msg']}"))
        return
    if isinstance(data, SubmitAnswerData):
        await engine.submit_answer(conn, data)
    elif isinstance(data, RequestHelpData):
        await engine.request_help(conn, data)
    else:
        conn.send(ws_message("pong", PongData()))
