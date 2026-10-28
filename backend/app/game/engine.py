"""GameEngine of one room: state machine, timers, answerer selection.

Unlike the other modules in `app/game/`, this one is stateful and async. Every public
coroutine takes the room's own `asyncio.Lock`; inside the lock everything is
synchronous (events are only enqueued on connections), so no two operations on the
same room interleave and events keep a fixed order. Timers are cancellable
`asyncio.Task`s that re-take the lock and check they are still the current timer.

Spec: *Luồng game và state machine*, *Thuật toán chi tiết* 3, 6, 7, 8, CHANGELOG 2026-10-28.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from app.errors import ApiError
from app.game.bingo import card_winning_lines, marked_cells
from app.game.cards import Card, card_numbers, find_cell, generate_card
from app.game.numbers import available_numbers, draw_number, draw_pool
from app.game.options import OPTION_KEYS, OptionSet, generate_options
from app.game.questions import Expression, generate_expression
from app.schemas import (
    ERR_FIXED_PLAYER_REQUIRED,
    ERR_GAME_IN_PROGRESS,
    ERR_INVALID_PHASE,
    ERR_NICKNAME_TAKEN,
    ERR_NO_NUMBERS_LEFT,
    ERR_NO_PLAYERS,
    ERR_NOT_YOUR_TURN,
    ERR_PLAYER_NOT_FOUND,
    ERR_ROOM_FULL,
    ERR_ROOM_NOT_FOUND,
    ERR_STALE_QUESTION,
    MAX_PLAYERS_PER_ROOM,
    WS_CLOSE_KICKED,
    WS_CLOSE_REPLACED,
    WS_CLOSE_ROOM_CLOSED,
    AnswererMode,
    AnswerResultData,
    CellMarkedData,
    ConfigUpdatedData,
    ErrorData,
    GameConfig,
    GameOverData,
    GameStartedData,
    JoinUrlUpdatedData,
    KickedData,
    Line,
    Option,
    Phase,
    PhaseChangedData,
    PlayerInfo,
    PlayersUpdatedData,
    Question,
    QuestionData,
    QuestionReason,
    QuestionSkippedData,
    Reveal,
    RevealItem,
    RoomClosedData,
    RoomClosedReason,
    Snapshot,
    SubmitAnswerData,
    RequestHelpData,
    NumberDrawnData,
    Winner,
    YourCardData,
    ws_message,
)
from app.tokens import new_token, tokens_equal
from app.ws.manager import Connection, RoomConnections

log = logging.getLogger("bingo")


@dataclass(frozen=True)
class Timings:
    """`time_scale` multiplies every sleep (tests use e.g. 0.01). Contract values sent to
    clients (`seconds_per_card`, `reveal_seconds`) stay unscaled; `deadline` is real."""

    time_scale: float = 1.0
    disconnect_grace_seconds: float = 10.0


@dataclass
class Player:
    id: str
    token: str
    nickname: str
    avatar_id: str
    card: Card


@dataclass
class QuestionState:
    question_id: str
    number: int
    expr: Expression
    answerer_id: str
    attempt: int = 0
    wrong_count: int = 0
    tried: set[str] = field(default_factory=set)
    used_wrong: set[int] = field(default_factory=set)
    options: OptionSet | None = None
    deadline: datetime | None = None


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _msg(type_: str, data: BaseModel) -> dict[str, Any]:
    return ws_message(type_, data)


class GameEngine:
    def __init__(
        self,
        *,
        room_id: str,
        pin: str,
        picture_code: list[str],
        join_base_url: str,
        join_url: str,
        config: GameConfig,
        host_token: str,
        screen_token: str,
        rng: random.Random,
        timings: Timings = Timings(),
        clock: Callable[[], float],
    ) -> None:
        self.room_id = room_id
        self.pin = pin
        self.picture_code = list(picture_code)
        self.join_base_url = join_base_url
        self.join_url = join_url
        self.config = config
        self.host_token = host_token
        self.screen_token = screen_token
        self.rng = rng
        self.timings = timings
        self.clock = clock

        self.lock = asyncio.Lock()
        self.connections = RoomConnections()
        self.closed = False
        self.closed_reason: RoomClosedReason = "closed_by_host"
        self.idle_since: float | None = clock()

        self.players: dict[str, Player] = {}  # insertion order = join order
        self.kicked_tokens: set[str] = set()
        self.phase: Phase = "lobby"
        self.answerer_mode: AnswererMode | None = None
        self.fixed_player_id: str | None = None
        self.drawn: list[int] = []
        self.last_skipped: int | None = None
        self.question: QuestionState | None = None
        self.reveal: Reveal | None = None
        self.winners: list[Winner] = []
        self._timers: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------ helpers

    def _log(self, msg: str, *args: Any) -> None:
        log.info(f"[PIN {self.pin}] {msg}", *args)

    def _ensure_open(self) -> None:
        if self.closed:
            raise ApiError(404, ERR_ROOM_NOT_FOUND, f"room {self.pin} is closed")

    def _require_phase(self, *phases: Phase) -> None:
        if self.phase not in phases:
            raise ApiError(409, ERR_INVALID_PHASE, f"not allowed in phase {self.phase!r}")

    def _r_numbers(self) -> list[int]:
        return available_numbers(self.config.enabled_ops())

    def _new_card(self) -> Card:
        return generate_card(self._r_numbers(), self.rng)

    def _broadcast(self, type_: str, data: BaseModel) -> None:
        self.connections.broadcast(_msg(type_, data))

    def _send_player(self, player_id: str, type_: str, data: BaseModel) -> None:
        self.connections.send_player(player_id, _msg(type_, data))

    def _connected_ids(self) -> list[str]:
        return [pid for pid in self.players if self.connections.is_player_connected(pid)]

    def player_info(self, player_id: str) -> PlayerInfo:
        p = self.players[player_id]
        return PlayerInfo(
            id=p.id,
            nickname=p.nickname,
            avatar_id=p.avatar_id,
            connected=self.connections.is_player_connected(p.id),
        )

    def players_info(self) -> list[PlayerInfo]:
        return [self.player_info(pid) for pid in self.players]

    def _broadcast_players(self) -> None:
        self._broadcast("players_updated", PlayersUpdatedData(players=self.players_info()))

    def _set_phase(self, phase: Phase) -> None:
        self.phase = phase
        self._broadcast("phase_changed", PhaseChangedData(phase=phase))
        self._log("phase -> %s", phase)

    def _marked(self, player: Player) -> list[tuple[int, int]]:
        return marked_cells(player.card, self.drawn)

    def player_by_token(self, token: str) -> Player | None:
        for p in self.players.values():
            if tokens_equal(token, p.token):
                return p
        return None

    def is_kicked_token(self, token: str) -> bool:
        return token in self.kicked_tokens

    # ------------------------------------------------------------------ timers

    def _start_timer(self, name: str, seconds: float, callback: Callable[[], None]) -> None:
        self._cancel_timer(name)
        delay = max(0.0, seconds * self.timings.time_scale)

        async def runner() -> None:
            await asyncio.sleep(delay)
            async with self.lock:
                if self._timers.get(name) is not asyncio.current_task() or self.closed:
                    return
                del self._timers[name]
                callback()

        self._timers[name] = asyncio.get_running_loop().create_task(runner(), name=f"{self.pin}:{name}")

    def _cancel_timer(self, name: str) -> None:
        task = self._timers.pop(name, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _cancel_all_timers(self) -> None:
        for name in list(self._timers):
            self._cancel_timer(name)

    def has_timer(self, name: str) -> bool:
        return name in self._timers

    # ------------------------------------------------------------------ snapshot

    def _question_model(self) -> Question | None:
        q = self.question
        if q is None or q.options is None:
            return None
        return Question(
            question_id=q.question_id,
            attempt=q.attempt,
            text=q.expr.text,
            operator=q.expr.operator,
            a=q.expr.a,
            b=q.expr.b,
            # Values only: which one is correct is never sent.
            options=[Option(key=k, value=v) for k, v in zip(OPTION_KEYS, q.options.values)],  # type: ignore[arg-type]
            answerer=self.player_info(q.answerer_id),
            deadline=iso_utc(q.deadline) if q.deadline else None,
        )

    def snapshot(self, conn: Connection) -> Snapshot:
        snap = Snapshot(
            pin=self.pin,
            picture_code=self.picture_code,  # type: ignore[arg-type]
            phase=self.phase,
            join_url=self.join_url,
            config=self.config,
            players=self.players_info(),
            answerer_mode=self.answerer_mode,
            fixed_player_id=self.fixed_player_id,
            drawn=list(self.drawn),
            question=self._question_model() if self.phase == "question" else None,
            reveal=self.reveal if self.phase == "reveal" else None,
            winners=list(self.winners),
        )
        if conn.role == "player" and conn.player_id in self.players:
            p = self.players[conn.player_id]
            snap.me = self.player_info(p.id)
            snap.card = p.card
            snap.marked = self._marked(p)
        return snap

    # ------------------------------------------------------------------ connections

    async def connect(self, conn: Connection) -> bool:
        """Register a socket and send it a `snapshot`. False if the room/player is gone."""
        async with self.lock:
            if self.closed:
                conn.send(_msg("room_closed", RoomClosedData(reason=self.closed_reason)))
                conn.close(WS_CLOSE_ROOM_CLOSED)
                return False
            if conn.role == "player" and conn.player_id not in self.players:
                conn.send(_msg("kicked", KickedData()))
                conn.close(WS_CLOSE_KICKED)
                return False
            old = self.connections.add(conn)
            if old is not None:
                old.close(WS_CLOSE_REPLACED, "replaced by a newer connection")
            self.idle_since = None
            conn.send(_msg("snapshot", self.snapshot(conn)))
            if conn.role == "player" and old is None:
                pid = conn.player_id
                assert pid is not None
                self._log("player %s connected", self.players[pid].nickname)
                self._broadcast_players()
                self._on_player_connected(pid)
            return True

    async def disconnect(self, conn: Connection) -> None:
        async with self.lock:
            if not self.connections.remove(conn):
                return
            self._after_connection_removed()
            if self.closed or conn.role != "player" or conn.player_id not in self.players:
                return
            pid = conn.player_id
            self._log("player %s disconnected", self.players[pid].nickname)
            self._broadcast_players()
            q = self.question
            if self.phase == "question" and q is not None and q.answerer_id == pid:
                self._maybe_start_disconnect_timer()

    def _after_connection_removed(self) -> None:
        if self.connections.count() == 0:
            self.idle_since = self.clock()

    def _on_player_connected(self, pid: str) -> None:
        q = self.question
        if self.phase != "question" or q is None:
            return
        if q.answerer_id == pid:
            self._cancel_timer("disconnect")
        else:
            self._maybe_start_disconnect_timer()

    def _maybe_start_disconnect_timer(self) -> None:
        """Answerer offline and someone else online: change answerer after the grace period."""
        q = self.question
        if q is None or self.has_timer("disconnect"):
            return
        if self.connections.is_player_connected(q.answerer_id):
            return
        if not any(pid != q.answerer_id for pid in self._connected_ids()):
            return
        self._start_timer("disconnect", self.timings.disconnect_grace_seconds, self._on_disconnect_timeout)

    def _on_disconnect_timeout(self) -> None:
        q = self.question
        if self.phase != "question" or q is None:
            return
        if self.connections.is_player_connected(q.answerer_id):
            return
        self._change_answerer("disconnect")

    # ------------------------------------------------------------------ lobby

    async def join(self, nickname: str, avatar_id: str) -> Player:
        """`nickname` already trimmed/validated, `avatar_id` already checked by the caller."""
        async with self.lock:
            self._ensure_open()
            if self.phase != "lobby":
                raise ApiError(409, ERR_GAME_IN_PROGRESS, "the game has already started")
            if len(self.players) >= MAX_PLAYERS_PER_ROOM:
                raise ApiError(409, ERR_ROOM_FULL, "the room is full")
            key = nickname.strip().casefold()
            if any(p.nickname.strip().casefold() == key for p in self.players.values()):
                raise ApiError(409, ERR_NICKNAME_TAKEN, "nickname already used in this room")
            player = Player(
                id=uuid.uuid4().hex,
                token=new_token(),
                nickname=nickname,
                avatar_id=avatar_id,
                card=self._new_card(),
            )
            self.players[player.id] = player
            self._log("player %s joined (%s), %d players", nickname, avatar_id, len(self.players))
            self._broadcast_players()
            return player

    async def kick(self, player_id: str) -> None:
        async with self.lock:
            self._ensure_open()
            self._require_phase("lobby")
            player = self.players.pop(player_id, None)
            if player is None:
                raise ApiError(404, ERR_PLAYER_NOT_FOUND, "player not found")
            self.kicked_tokens.add(player.token)
            conn = self.connections.pop_player(player_id)
            if conn is not None:
                conn.send(_msg("kicked", KickedData()))
                conn.close(WS_CLOSE_KICKED)
                self._after_connection_removed()
            if self.fixed_player_id == player_id:
                self.fixed_player_id = None
            self._log("player %s kicked", player.nickname)
            self._broadcast_players()

    async def update_config(self, config: GameConfig) -> GameConfig:
        async with self.lock:
            self._ensure_open()
            self._require_phase("lobby", "finished")
            self.config = config
            self._broadcast("config_updated", ConfigUpdatedData(config=config))
            if self.phase == "lobby":
                for p in self.players.values():
                    p.card = self._new_card()
                    self._send_player(p.id, "your_card", YourCardData(card=p.card, marked=[]))
            self._log("config updated")
            return config

    async def set_join_base_url(self, base: str, join_url: str) -> str:
        async with self.lock:
            self._ensure_open()
            self.join_base_url = base
            self.join_url = join_url
            self._broadcast("join_url_updated", JoinUrlUpdatedData(join_url=join_url))
            self._log("join url -> %s", join_url)
            return join_url

    # ------------------------------------------------------------------ game flow

    async def start(self, mode: AnswererMode, fixed_player_id: str | None) -> None:
        async with self.lock:
            self._ensure_open()
            self._require_phase("lobby")
            if not self.players:
                raise ApiError(422, ERR_NO_PLAYERS, "at least one player is required")
            if mode == "fixed":
                if not fixed_player_id or fixed_player_id not in self.players:
                    raise ApiError(422, ERR_FIXED_PLAYER_REQUIRED, "fixed mode needs a valid fixed_player_id")
            else:
                fixed_player_id = None
            pool = self._pool()
            if not pool:  # cannot happen with >= 1 card, but stay safe
                raise ApiError(409, ERR_NO_NUMBERS_LEFT, "no numbers left to draw")
            self.answerer_mode = mode
            self.fixed_player_id = fixed_player_id
            self._log("game started, mode=%s fixed=%s", mode, fixed_player_id)
            self._broadcast("game_started", GameStartedData(answerer_mode=mode, fixed_player_id=fixed_player_id))
            self._start_question()

    async def next_question(self) -> None:
        async with self.lock:
            self._ensure_open()
            self._require_phase("ready")
            if not self._pool():
                raise ApiError(409, ERR_NO_NUMBERS_LEFT, "no numbers left to draw")
            self._start_question()

    async def skip(self) -> None:
        async with self.lock:
            self._ensure_open()
            self._require_phase("question")
            q = self.question
            assert q is not None
            self._cancel_question_timers()
            self.question = None
            self.last_skipped = q.number  # back to the pool (it was never added to drawn)
            self._log("question %s skipped, number %d back to pool", q.question_id, q.number)
            self._broadcast("question_skipped", QuestionSkippedData(question_id=q.question_id, number=q.number))
            self._set_phase("ready")

    async def host_help(self) -> None:
        async with self.lock:
            self._ensure_open()
            self._require_phase("question")
            self._log("host help")
            self._change_answerer("help")

    async def end(self) -> None:
        async with self.lock:
            self._ensure_open()
            self._require_phase("question", "reveal", "ready")
            self._log("game ended by host")
            self._finish("ended_by_host", [])

    async def new_round(self, base: str | None, join_url: str | None) -> None:
        async with self.lock:
            self._ensure_open()
            self._require_phase("finished")
            self._cancel_all_timers()
            self.phase = "lobby"
            self.answerer_mode = None
            self.fixed_player_id = None
            self.drawn = []
            self.last_skipped = None
            self.question = None
            self.reveal = None
            self.winners = []
            for p in self.players.values():
                p.card = self._new_card()
            if base is not None and join_url is not None and join_url != self.join_url:
                self.join_base_url = base
                self.join_url = join_url
                self._broadcast("join_url_updated", JoinUrlUpdatedData(join_url=join_url))
            self._log("new round")
            for conn in self.connections.all():
                conn.send(_msg("snapshot", self.snapshot(conn)))

    # ------------------------------------------------------------------ player messages

    def _ws_error(self, conn: Connection, code: str, message: str) -> None:
        conn.send(_msg("error", ErrorData(code=code, message=message)))

    async def submit_answer(self, conn: Connection, data: SubmitAnswerData) -> None:
        async with self.lock:
            if self.closed:
                return
            q = self.question
            # CHANGELOG order: invalid_phase -> question_id -> not_your_turn -> attempt.
            if self.phase != "question" or q is None or q.options is None:
                return self._ws_error(conn, ERR_INVALID_PHASE, "no question is open")
            if data.question_id != q.question_id:
                return self._ws_error(conn, ERR_STALE_QUESTION, "question_id does not match")
            if conn.player_id != q.answerer_id:
                return self._ws_error(conn, ERR_NOT_YOUR_TURN, "you are not the answerer")
            if data.attempt != q.attempt:
                return self._ws_error(conn, ERR_STALE_QUESTION, "attempt does not match")

            idx = OPTION_KEYS.index(data.key)
            value = q.options.values[idx]
            correct = idx == q.options.correct_index
            nickname = self.players[q.answerer_id].nickname
            self._log("answer by %s: %s=%d (%s)", nickname, data.key, value, "correct" if correct else "wrong")
            self._broadcast(
                "answer_result",
                AnswerResultData(
                    question_id=q.question_id,
                    attempt=q.attempt,
                    player_id=q.answerer_id,
                    key=data.key,
                    value=value,
                    correct=correct,
                ),
            )
            if correct:
                self._on_correct()
            else:
                q.wrong_count += 1
                if q.wrong_count < self.config.max_wrong:
                    self._new_attempt("wrong")
                else:
                    self._change_answerer("max_wrong")

    async def request_help(self, conn: Connection, data: RequestHelpData) -> None:
        async with self.lock:
            if self.closed:
                return
            q = self.question
            if self.phase != "question" or q is None:
                return self._ws_error(conn, ERR_INVALID_PHASE, "no question is open")
            if data.question_id != q.question_id:
                return self._ws_error(conn, ERR_STALE_QUESTION, "question_id does not match")
            if conn.player_id != q.answerer_id:
                return self._ws_error(conn, ERR_NOT_YOUR_TURN, "you are not the answerer")
            self._log("help requested by %s", self.players[q.answerer_id].nickname)
            self._change_answerer("help")

    # ------------------------------------------------------------------ internals

    def _pool(self) -> list[int]:
        cards: set[int] | None = None
        if self.config.draw_only_card_numbers:
            cards = set()
            for p in self.players.values():
                cards |= card_numbers(p.card)
        return draw_pool(self._r_numbers(), self.drawn, cards)

    def _initial_answerer(self) -> str:
        connected = self._connected_ids()
        fixed = self.fixed_player_id
        if self.answerer_mode == "fixed" and fixed in self.players:
            assert fixed is not None
            if fixed in connected or not connected:
                return fixed
        return self.rng.choice(connected or list(self.players))

    def _start_question(self) -> None:
        n = draw_number(self._pool(), self.rng, avoid=self.last_skipped)
        assert n is not None
        self.last_skipped = None
        expr = generate_expression(n, self.config.enabled_ops(), self.rng)
        self.question = QuestionState(
            question_id=uuid.uuid4().hex,
            number=n,
            expr=expr,
            answerer_id=self._initial_answerer(),
        )
        self._set_phase("question")
        self._new_attempt("new")

    def _new_attempt(self, reason: QuestionReason) -> None:
        q = self.question
        assert q is not None
        q.attempt += 1
        prev = q.options.correct_index if q.options is not None else None
        q.options = generate_options(q.expr, self.rng, q.used_wrong, prev)
        q.used_wrong |= set(q.options.wrong_values)
        self._cancel_question_timers()
        if self.config.timer_seconds:
            seconds = self.config.timer_seconds
            q.deadline = _utcnow() + timedelta(seconds=seconds * self.timings.time_scale)
            self._start_timer("countdown", seconds, self._on_countdown_timeout)
        else:
            q.deadline = None
        self._maybe_start_disconnect_timer()
        self._log(
            "question %s attempt %d (%s): %s answerer=%s",
            q.question_id[:8], q.attempt, reason, q.expr.text, self.players[q.answerer_id].nickname,
        )
        question = self._question_model()
        assert question is not None
        self._broadcast("question", QuestionData(question=question, reason=reason))

    def _cancel_question_timers(self) -> None:
        self._cancel_timer("countdown")
        self._cancel_timer("disconnect")

    def _on_countdown_timeout(self) -> None:
        if self.phase == "question" and self.question is not None:
            self._log("countdown expired")
            self._change_answerer("timeout")

    def _change_answerer(self, reason: QuestionReason) -> None:
        """*Thuật toán* 6: random connected player not in `tried`; reset `tried` if none."""
        q = self.question
        assert q is not None
        q.tried.add(q.answerer_id)
        connected = self._connected_ids()
        candidates = [pid for pid in connected if pid not in q.tried]
        if not candidates:
            q.tried = {q.answerer_id}
            candidates = [pid for pid in connected if pid not in q.tried]
        if candidates:
            old = q.answerer_id
            q.answerer_id = self.rng.choice(candidates)
            self._log(
                "answerer %s -> %s (%s)", self.players[old].nickname, self.players[q.answerer_id].nickname, reason
            )
        q.wrong_count = 0
        self._new_attempt(reason)

    def _on_correct(self) -> None:
        q = self.question
        assert q is not None
        n = q.number
        self._cancel_question_timers()
        self.question = None
        before = list(self.drawn)
        self.drawn.append(n)
        self._broadcast("number_drawn", NumberDrawnData(number=n, drawn=list(self.drawn)))
        items: list[RevealItem] = []
        for p in self.players.values():
            cell = find_cell(p.card, n)
            if cell is None:
                continue
            self._send_player(p.id, "cell_marked", CellMarkedData(number=n, cell=cell))
            items.append(
                RevealItem(
                    player_id=p.id,
                    nickname=p.nickname,
                    avatar_id=p.avatar_id,
                    card=p.card,
                    marked_before=marked_cells(p.card, before),
                    new_cell=cell,
                )
            )
        self._log("number %d drawn, on %d cards", n, len(items))
        self._set_phase("reveal")
        self.reveal = Reveal(
            number=n,
            seconds_per_card=self.config.reveal_seconds,
            started_at=iso_utc(_utcnow()),
            items=items,
        )
        self._broadcast("reveal", self.reveal)
        duration = max(len(items), 1) * self.config.reveal_seconds
        self._start_timer("reveal", duration, self._on_reveal_end)

    def _compute_winners(self) -> list[Winner]:
        winners: list[Winner] = []
        for p in self.players.values():
            lines = card_winning_lines(p.card, self.drawn)
            if lines:
                winners.append(
                    Winner(
                        player_id=p.id,
                        nickname=p.nickname,
                        avatar_id=p.avatar_id,
                        card=p.card,
                        marked=self._marked(p),
                        lines=[Line(type=line.type, index=line.index) for line in lines],
                    )
                )
        return winners

    def _on_reveal_end(self) -> None:
        if self.phase != "reveal":
            return
        self.reveal = None
        winners = self._compute_winners()
        if winners:
            self._log("BINGO: %s", ", ".join(w.nickname for w in winners))
            self._finish("bingo", winners)
        else:
            self._set_phase("ready")

    def _finish(self, reason: str, winners: list[Winner]) -> None:
        self._cancel_all_timers()
        self.question = None
        self.reveal = None
        self.winners = winners
        self._set_phase("finished")
        self._broadcast("game_over", GameOverData(reason=reason, winners=winners))  # type: ignore[arg-type]

    # ------------------------------------------------------------------ closing

    async def close(self, reason: RoomClosedReason) -> bool:
        """Cancel timers, send `room_closed`, close every socket with 4410."""
        async with self.lock:
            if self.closed:
                return False
            self.closed = True
            self.closed_reason = reason
            self._cancel_all_timers()
            self._broadcast("room_closed", RoomClosedData(reason=reason))
            self.connections.close_all(WS_CLOSE_ROOM_CLOSED)
            self._log("room closed (%s)", reason)
            return True
