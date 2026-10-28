"""Helpers for integration tests: app factory, timed WebSocket reads, game driving."""

from __future__ import annotations

import json
import random
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import anyio
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.game.engine import GameEngine, Timings
from app.game.options import OPTION_KEYS
from app.main import create_app
from app.rooms import RoomManager
from app.settings import Settings

FAST = Timings(time_scale=0.01, disconnect_grace_seconds=10.0)
DEFAULT_CONFIG: dict[str, Any] = {
    "operations": {"add": True, "sub": True, "mul": True, "div": True},
    "timer_seconds": 0,
    "max_wrong": 2,
    "reveal_seconds": 2,
    "draw_only_card_numbers": True,
}
BASE_URL = "http://192.168.1.15:8080"


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class PinRng(random.Random):
    """Seeded Random whose PIN draws come from a scripted list first."""

    def __init__(self, pins: list[int], seed: int = 7) -> None:
        super().__init__(seed)
        self.pins = list(pins)

    def randint(self, a: int, b: int) -> int:
        if (a, b) == (1000, 9999) and self.pins:
            return self.pins.pop(0)
        return super().randint(a, b)


@contextmanager
def make_client(
    *,
    timings: Timings = FAST,
    clock: Callable[[], float] | None = None,
    rng: random.Random | None = None,
    **settings: Any,
) -> Iterator[TestClient]:
    env = {"MAX_ROOMS": 20, "ROOM_IDLE_MINUTES": 30, "CODE_COOLDOWN_MINUTES": 30, **settings}
    cfg = Settings(**env)
    kwargs: dict[str, Any] = {"timings": timings, "rng": rng or random.Random(42)}
    if clock is not None:
        kwargs["clock"] = clock
    manager = RoomManager(cfg, **kwargs)
    app = create_app(cfg, manager=manager)
    with TestClient(app) as client:
        yield client


class WS:
    """Wraps a TestClient WebSocket session with timed receives (tests never hang)."""

    def __init__(self, session: Any) -> None:
        self.s = session
        self.log: list[dict[str, Any]] = []

    def recv(self, timeout: float = 5.0) -> dict[str, Any]:
        async def _r() -> Any:
            with anyio.fail_after(timeout):
                return await self.s._send_rx.receive()

        msg = self.s.portal.call(_r)
        if msg["type"] == "websocket.close":
            raise WebSocketDisconnect(code=msg.get("code", 1000), reason=msg.get("reason", ""))
        data = json.loads(msg["text"])
        self.log.append(data)
        return data

    def recv_type(self, type_: str, timeout: float = 5.0) -> dict[str, Any]:
        """Skip messages until one of `type_` arrives."""
        while True:
            m = self.recv(timeout)
            if m["type"] == type_:
                return m

    def drain(self, quiet: float = 0.05) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        while True:
            try:
                out.append(self.recv(quiet))
            except TimeoutError:
                return out

    def expect_close(self, timeout: float = 5.0) -> tuple[int, list[dict[str, Any]]]:
        """Read until the server closes; returns (close code, messages before it)."""
        before: list[dict[str, Any]] = []
        while True:
            try:
                before.append(self.recv(timeout))
            except WebSocketDisconnect as exc:
                return exc.code, before

    def send(self, type_: str, data: dict[str, Any] | None = None) -> None:
        self.s.send_json({"type": type_, "data": data or {}})


@contextmanager
def ws_connect(client: TestClient, pin: str, role: str, token: str) -> Iterator[WS]:
    with client.websocket_connect(f"/ws?pin={pin}&role={role}&token={token}") as s:
        yield WS(s)


def create_room(client: TestClient, config: dict[str, Any] | None = None, base: str = BASE_URL) -> dict[str, Any]:
    r = client.post("/api/rooms", json={"config": config or DEFAULT_CONFIG, "join_base_url": base})
    assert r.status_code == 200, r.text
    return r.json()


def auth(room: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {room['host_token']}"}


def join(client: TestClient, pin: str, nickname: str, avatar_id: str = "cat") -> dict[str, Any]:
    r = client.post(f"/api/rooms/{pin}/join", json={"nickname": nickname, "avatar_id": avatar_id})
    assert r.status_code == 200, r.text
    return r.json()


def engine_of(client: TestClient, pin: str) -> GameEngine:
    engine = client.app.state.rooms.get_by_pin(pin)  # type: ignore[attr-defined]
    assert engine is not None
    return engine


def correct_key(client: TestClient, pin: str) -> str:
    q = engine_of(client, pin).question
    assert q is not None and q.options is not None
    return OPTION_KEYS[q.options.correct_index]


def wrong_key(client: TestClient, pin: str) -> str:
    good = correct_key(client, pin)
    return next(k for k in OPTION_KEYS if k != good)


def types(messages: list[dict[str, Any]]) -> list[str]:
    return [m["type"] for m in messages]


def is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(any(x == y for y in it) for x in needle)
