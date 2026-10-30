"""RoomManager: `room_id` <- PIN / picture code, cooldown, MAX_ROOMS, idle cleanup.

Spec: *Phòng chơi*, *Mã phòng*.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import secrets
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.errors import ApiError
from app.game.engine import GameEngine, Timings
from app.joinurl import build_join_url, normalize_join_base_url
from app.schemas import ERR_TOO_MANY_ROOMS, ROOM_ICONS, GameConfig, RoomClosedReason
from app.settings import Settings
from app.tokens import new_token

log = logging.getLogger("bingo")

PICTURE_CODE_LEN = 3
_MAX_CODE_TRIES = 10_000


def is_guessable_pin(pin: str) -> bool:
    """All digits equal (1111) or a run of consecutive ascending/descending digits (1234, 9876)."""
    d = [int(ch) for ch in pin]
    if len(set(d)) == 1:
        return True
    steps = {b - a for a, b in zip(d, d[1:])}
    return steps == {1} or steps == {-1}


def parse_picture_code(value: str | Sequence[str]) -> tuple[str, ...] | None:
    """`apple,star,fish` -> tuple; None unless exactly 3 distinct known icons."""
    items = value.split(",") if isinstance(value, str) else list(value)
    icons = tuple(s.strip().lower() for s in items)
    if len(icons) != PICTURE_CODE_LEN or len(set(icons)) != PICTURE_CODE_LEN:
        return None
    if any(i not in ROOM_ICONS for i in icons):
        return None
    return icons


@dataclass
class _Cooldown:
    until: float
    reason: RoomClosedReason


class RoomManager:
    def __init__(
        self,
        settings: Settings,
        *,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
        timings: Timings = Timings(),
    ) -> None:
        self.settings = settings
        self.rng = rng or secrets.SystemRandom()
        self.clock = clock
        self.timings = timings
        self.rooms: dict[str, GameEngine] = {}  # room_id -> engine
        self._by_pin: dict[str, str] = {}
        self._by_pictures: dict[tuple[str, ...], str] = {}
        self._pin_cooldown: dict[str, _Cooldown] = {}
        self._pictures_cooldown: dict[tuple[str, ...], float] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ codes

    def _purge_cooldowns(self) -> None:
        now = self.clock()
        for pin in [p for p, c in self._pin_cooldown.items() if c.until <= now]:
            del self._pin_cooldown[pin]
        for pics in [p for p, until in self._pictures_cooldown.items() if until <= now]:
            del self._pictures_cooldown[pics]

    def _pin_taken(self, pin: str) -> bool:
        return pin in self._by_pin or pin in self._pin_cooldown

    def _pictures_taken(self, pics: tuple[str, ...]) -> bool:
        return pics in self._by_pictures or pics in self._pictures_cooldown

    def _new_pin(self) -> str:
        for _ in range(_MAX_CODE_TRIES):
            pin = str(self.rng.randint(1000, 9999))
            if not is_guessable_pin(pin) and not self._pin_taken(pin):
                return pin
        raise RuntimeError("could not find a free PIN")

    def _new_pictures(self) -> tuple[str, ...]:
        for _ in range(_MAX_CODE_TRIES):
            pics = tuple(self.rng.sample(ROOM_ICONS, PICTURE_CODE_LEN))
            if not self._pictures_taken(pics):
                return pics
        raise RuntimeError("could not find a free picture code")

    # ------------------------------------------------------------------ rooms

    def create_room(self, config: GameConfig, join_base_url: str) -> GameEngine:
        base = normalize_join_base_url(join_base_url)
        if len(self.rooms) >= self.settings.max_rooms:
            raise ApiError(503, ERR_TOO_MANY_ROOMS, f"at most {self.settings.max_rooms} rooms")
        self._purge_cooldowns()
        pin = self._new_pin()
        pics = self._new_pictures()
        room_id = uuid.uuid4().hex
        engine = GameEngine(
            room_id=room_id,
            pin=pin,
            picture_code=list(pics),
            join_base_url=base,
            join_url=build_join_url(base, pin),
            config=config,
            host_token=new_token(),
            screen_token=new_token(),
            rng=self.rng,  # type: ignore[arg-type]
            timings=self.timings,
            clock=self.clock,
        )
        self.rooms[room_id] = engine
        self._by_pin[pin] = room_id
        self._by_pictures[pics] = room_id
        log.info("[PIN %s] room created (%s), %d rooms open", pin, "-".join(pics), len(self.rooms))
        return engine

    def get_by_pin(self, pin: str) -> GameEngine | None:
        room_id = self._by_pin.get(pin)
        return self.rooms.get(room_id) if room_id else None

    def lookup_pictures(self, pictures: str | Sequence[str]) -> GameEngine | None:
        pics = parse_picture_code(pictures)
        if pics is None:
            return None
        room_id = self._by_pictures.get(pics)
        return self.rooms.get(room_id) if room_id else None

    def closed_reason(self, pin: str) -> RoomClosedReason | None:
        """Reason if `pin` belongs to a recently closed room (still in cooldown)."""
        self._purge_cooldowns()
        cd = self._pin_cooldown.get(pin)
        return cd.reason if cd else None

    async def close_room(self, engine: GameEngine, reason: RoomClosedReason) -> None:
        await engine.close(reason)
        if self.rooms.get(engine.room_id) is not engine:
            return
        del self.rooms[engine.room_id]
        self._by_pin.pop(engine.pin, None)
        pics = tuple(engine.picture_code)
        self._by_pictures.pop(pics, None)
        cooldown = self.settings.code_cooldown_minutes * 60
        if cooldown > 0:
            until = self.clock() + cooldown
            self._pin_cooldown[engine.pin] = _Cooldown(until, reason)
            self._pictures_cooldown[pics] = until

    async def cleanup_idle(self) -> int:
        """Close rooms with no connection for ROOM_IDLE_MINUTES. Returns how many were closed."""
        self._purge_cooldowns()
        limit = self.settings.room_idle_minutes * 60
        now = self.clock()
        expired = [
            e
            for e in list(self.rooms.values())
            if e.connections.count() == 0 and e.idle_since is not None and now - e.idle_since >= limit
        ]
        for engine in expired:
            await self.close_room(engine, "expired")
        return len(expired)

    async def _cleanup_loop(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await self.cleanup_idle()
            except Exception:  # never let the background task die
                log.exception("idle cleanup failed")

    def start_cleanup(self, interval: float = 60.0) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.get_running_loop().create_task(self._cleanup_loop(interval))

    async def shutdown(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
        for engine in list(self.rooms.values()):
            async with engine.lock:
                engine._cancel_all_timers()
