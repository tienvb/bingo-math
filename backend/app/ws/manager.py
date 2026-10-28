"""WebSocket connections of one room, keyed by role and `player_id`.

Every connection has an outbound queue drained by its own sender task, so the engine
can enqueue events synchronously while holding the room lock: events reach each
socket in exactly the order the engine produced them, and a slow socket never blocks
the room.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import WebSocket

Role = Literal["host", "screen", "player"]
ROLES: tuple[str, ...] = ("host", "screen", "player")

log = logging.getLogger("bingo.ws")


@dataclass(frozen=True)
class _Close:
    code: int
    reason: str = ""


class Connection:
    def __init__(self, websocket: WebSocket | None, role: Role, player_id: str | None = None) -> None:
        self.websocket = websocket
        self.role: Role = role
        self.player_id = player_id
        self.queue: asyncio.Queue[dict[str, Any] | _Close] = asyncio.Queue()
        self.closing = False

    def send(self, message: dict[str, Any]) -> None:
        if not self.closing:
            self.queue.put_nowait(message)

    def close(self, code: int, reason: str = "") -> None:
        """Send everything queued so far, then close the socket with `code`."""
        if not self.closing:
            self.closing = True
            self.queue.put_nowait(_Close(code, reason))

    async def run_sender(self) -> None:
        assert self.websocket is not None
        while True:
            item = await self.queue.get()
            if isinstance(item, _Close):
                with contextlib.suppress(Exception):
                    await self.websocket.close(code=item.code, reason=item.reason or None)
                return
            try:
                await self.websocket.send_json(item)
            except Exception:  # socket already gone
                return


class RoomConnections:
    def __init__(self) -> None:
        self.hosts: list[Connection] = []
        self.screens: list[Connection] = []
        self.players: dict[str, Connection] = {}

    def add(self, conn: Connection) -> Connection | None:
        """Register `conn`. A player reconnecting replaces (and returns) the old socket."""
        if conn.role == "host":
            self.hosts.append(conn)
        elif conn.role == "screen":
            self.screens.append(conn)
        else:
            assert conn.player_id is not None
            old = self.players.get(conn.player_id)
            self.players[conn.player_id] = conn
            return old
        return None

    def remove(self, conn: Connection) -> bool:
        """Unregister `conn`; False if it was not registered (e.g. already replaced)."""
        if conn.role == "host":
            if conn in self.hosts:
                self.hosts.remove(conn)
                return True
        elif conn.role == "screen":
            if conn in self.screens:
                self.screens.remove(conn)
                return True
        elif conn.player_id is not None and self.players.get(conn.player_id) is conn:
            del self.players[conn.player_id]
            return True
        return False

    def pop_player(self, player_id: str) -> Connection | None:
        return self.players.pop(player_id, None)

    def all(self) -> list[Connection]:
        return [*self.hosts, *self.screens, *self.players.values()]

    def count(self) -> int:
        return len(self.hosts) + len(self.screens) + len(self.players)

    def is_player_connected(self, player_id: str) -> bool:
        return player_id in self.players

    def broadcast(self, message: dict[str, Any]) -> None:
        for conn in self.all():
            conn.send(message)

    def send_player(self, player_id: str, message: dict[str, Any]) -> None:
        conn = self.players.get(player_id)
        if conn is not None:
            conn.send(message)

    def close_all(self, code: int, reason: str = "") -> None:
        for conn in self.all():
            conn.close(code, reason)
        self.hosts.clear()
        self.screens.clear()
        self.players.clear()
