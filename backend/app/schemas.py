"""Pydantic v2 models matching *Hợp đồng REST API* and *Hợp đồng WebSocket* in docs/spec.md.

Field names are snake_case, exactly as in the contract. Do not rename.
"""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator, model_serializer, model_validator

from app.game.numbers import MIN_R_SIZE, available_numbers, enabled_ops

# ---------------------------------------------------------------------------
# Error codes and WS close codes
# ---------------------------------------------------------------------------

ERR_BAD_TOKEN = "bad_token"
ERR_ROOM_NOT_FOUND = "room_not_found"
ERR_INVALID_PHASE = "invalid_phase"
ERR_INVALID_CONFIG = "invalid_config"
ERR_INVALID_JOIN_URL = "invalid_join_url"
ERR_TOO_MANY_ROOMS = "too_many_rooms"
ERR_PLAYER_NOT_FOUND = "player_not_found"
ERR_NO_PLAYERS = "no_players"
ERR_FIXED_PLAYER_REQUIRED = "fixed_player_required"
ERR_NO_NUMBERS_LEFT = "no_numbers_left"
ERR_NICKNAME_TAKEN = "nickname_taken"
ERR_GAME_IN_PROGRESS = "game_in_progress"
ERR_ROOM_FULL = "room_full"
ERR_INVALID_NICKNAME = "invalid_nickname"
ERR_INVALID_AVATAR = "invalid_avatar"
ERR_NOT_YOUR_TURN = "not_your_turn"
ERR_STALE_QUESTION = "stale_question"
ERR_INVALID_MESSAGE = "invalid_message"  # WS: malformed JSON, unknown type, bad data

ERROR_CODES: frozenset[str] = frozenset(
    {
        ERR_BAD_TOKEN, ERR_ROOM_NOT_FOUND, ERR_INVALID_PHASE, ERR_INVALID_CONFIG,
        ERR_INVALID_JOIN_URL, ERR_TOO_MANY_ROOMS, ERR_PLAYER_NOT_FOUND, ERR_NO_PLAYERS,
        ERR_FIXED_PLAYER_REQUIRED, ERR_NO_NUMBERS_LEFT, ERR_NICKNAME_TAKEN,
        ERR_GAME_IN_PROGRESS, ERR_ROOM_FULL, ERR_INVALID_NICKNAME, ERR_INVALID_AVATAR,
        ERR_NOT_YOUR_TURN, ERR_STALE_QUESTION, ERR_INVALID_MESSAGE,
    }
)

WS_CLOSE_BAD_TOKEN = 4401
WS_CLOSE_ROOM_NOT_FOUND = 4404
WS_CLOSE_KICKED = 4403
WS_CLOSE_ROOM_CLOSED = 4410

MAX_PLAYERS_PER_ROOM = 30
NICKNAME_MAX_LEN = 20

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

Phase = Literal["lobby", "question", "reveal", "ready", "finished"]
RoomIcon = Literal[
    "apple", "banana", "star", "sun", "moon", "heart",
    "car", "plane", "ball", "flower", "umbrella", "fish",
]
ROOM_ICONS: tuple[str, ...] = (
    "apple", "banana", "star", "sun", "moon", "heart",
    "car", "plane", "ball", "flower", "umbrella", "fish",
)
OptionKey = Literal["A", "B", "C", "D"]
Operator = Literal["+", "-", "x", ":"]
AnswererMode = Literal["fixed", "random"]
LineType = Literal["row", "col", "diag"]
QuestionReason = Literal["new", "wrong", "help", "max_wrong", "timeout", "disconnect"]
GameOverReason = Literal["bingo", "ended_by_host"]
RoomClosedReason = Literal["closed_by_host", "expired"]

Card = list[list[int]]  # 5x5, card[row][col], 0 = FREE at [2][2]
Cell = tuple[int, int]  # [row, col], 0-based; serialized as a JSON array


class Operations(BaseModel):
    add: bool = True
    sub: bool = True
    mul: bool = True
    div: bool = True


class GameConfig(BaseModel):
    """Invalid values raise a ValidationError; the API layer maps it to 422 `invalid_config`."""

    operations: Operations = Field(default_factory=Operations)
    timer_seconds: int = 0
    max_wrong: int = Field(default=2, ge=1, le=5)
    reveal_seconds: int = Field(default=5, ge=2, le=15)
    draw_only_card_numbers: bool = True

    @field_validator("timer_seconds")
    @classmethod
    def _timer_range(cls, v: int) -> int:
        if v != 0 and not 5 <= v <= 120:
            raise ValueError("timer_seconds must be 0 (off) or 5-120")
        return v

    @model_validator(mode="after")
    def _enough_numbers(self) -> GameConfig:
        ops = self.enabled_ops()
        if not ops:
            raise ValueError("at least one operation must be enabled")
        if len(available_numbers(ops)) < MIN_R_SIZE:
            raise ValueError(f"enabled operations must produce at least {MIN_R_SIZE} numbers")
        return self

    def enabled_ops(self) -> frozenset[Any]:
        o = self.operations
        return enabled_ops(o.add, o.sub, o.mul, o.div)


class LocalizedName(BaseModel):
    vi: str
    en: str


class Avatar(BaseModel):
    id: str
    name: LocalizedName
    image_url: str
    win_animation_url: str | None = None
    color: str


class AvatarManifestEntry(BaseModel):
    """One entry of `backend/avatars/manifest.json` (not sent to clients as-is)."""

    id: str
    name: LocalizedName
    image: str
    win_animation: str | None = None
    color: str


class PlayerInfo(BaseModel):
    id: str
    nickname: str
    avatar_id: str
    connected: bool


class Line(BaseModel):
    type: LineType
    index: int  # diag 0: top-left -> bottom-right, 1: top-right -> bottom-left


class Option(BaseModel):
    key: OptionKey
    value: int


class Question(BaseModel):
    question_id: str
    attempt: int
    text: str
    operator: Operator
    a: int
    b: int
    options: list[Option]  # always A, B, C, D in order
    answerer: PlayerInfo
    deadline: str | None = None  # ISO 8601 UTC, None when the timer is off


class RevealItem(BaseModel):
    player_id: str
    nickname: str
    avatar_id: str
    card: Card
    marked_before: list[Cell]
    new_cell: Cell


class Reveal(BaseModel):
    number: int
    seconds_per_card: int
    started_at: str  # ISO 8601 UTC
    items: list[RevealItem]


class Winner(BaseModel):
    player_id: str
    nickname: str
    avatar_id: str
    card: Card
    marked: list[Cell]
    lines: list[Line]


class Snapshot(BaseModel):
    pin: str
    picture_code: list[RoomIcon]
    phase: Phase
    join_url: str
    config: GameConfig
    players: list[PlayerInfo]
    answerer_mode: AnswererMode | None = None
    fixed_player_id: str | None = None
    drawn: list[int]  # in draw order
    question: Question | None = None
    reveal: Reveal | None = None
    winners: list[Winner] = Field(default_factory=list)
    # Only present when role = player; omitted from JSON otherwise.
    me: PlayerInfo | None = None
    card: Card | None = None
    marked: list[Cell] | None = None

    @model_serializer(mode="wrap")
    def _omit_player_only(self, handler: Any) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        for key in ("me", "card", "marked"):
            if data.get(key) is None:
                data.pop(key, None)
        return data


# ---------------------------------------------------------------------------
# REST requests / responses
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    code: str
    message: str


class OkResponse(BaseModel):
    ok: bool = True


class CreateRoomRequest(BaseModel):
    config: GameConfig
    join_base_url: str


class CreateRoomResponse(BaseModel):
    pin: str
    picture_code: list[RoomIcon]
    host_token: str
    screen_token: str
    join_url: str


class RoomStatusResponse(BaseModel):
    phase: Phase
    player_count: int


class LookupResponse(BaseModel):
    pin: str


class JoinBaseUrlRequest(BaseModel):
    join_base_url: str


class JoinUrlResponse(BaseModel):
    join_url: str


class StartRequest(BaseModel):
    answerer_mode: AnswererMode
    fixed_player_id: str | None = None


class NewRoundRequest(BaseModel):
    join_base_url: str | None = None


class JoinRequest(BaseModel):
    nickname: str
    avatar_id: str


class JoinResponse(BaseModel):
    player_id: str
    player_token: str


class NetworkResponse(BaseModel):
    ips: list[str]
    port: int


class HealthResponse(BaseModel):
    ok: bool = True


# ---------------------------------------------------------------------------
# WebSocket envelope and message data
# ---------------------------------------------------------------------------

D = TypeVar("D", bound=BaseModel)


class WsMessage(BaseModel, Generic[D]):
    type: str
    data: D


class RawWsMessage(BaseModel):
    """Incoming envelope before `data` is validated against the type-specific model."""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class EmptyData(BaseModel):
    pass


# Server -> client


class PhaseChangedData(BaseModel):
    phase: Phase


class PlayersUpdatedData(BaseModel):
    players: list[PlayerInfo]


class ConfigUpdatedData(BaseModel):
    config: GameConfig


class JoinUrlUpdatedData(BaseModel):
    join_url: str


class YourCardData(BaseModel):
    card: Card
    marked: list[Cell]


class GameStartedData(BaseModel):
    answerer_mode: AnswererMode
    fixed_player_id: str | None = None


class QuestionData(BaseModel):
    question: Question
    reason: QuestionReason


class AnswerResultData(BaseModel):
    question_id: str
    attempt: int
    player_id: str
    key: OptionKey
    value: int
    correct: bool


class NumberDrawnData(BaseModel):
    number: int
    drawn: list[int]


class CellMarkedData(BaseModel):
    number: int
    cell: Cell


class QuestionSkippedData(BaseModel):
    question_id: str
    number: int


class GameOverData(BaseModel):
    reason: GameOverReason
    winners: list[Winner]


class KickedData(EmptyData):
    pass


class RoomClosedData(BaseModel):
    reason: RoomClosedReason


class ErrorData(BaseModel):
    code: str
    message: str


class PongData(EmptyData):
    pass


# Client -> server (role = player; host/screen only send ping)


class SubmitAnswerData(BaseModel):
    question_id: str
    attempt: int
    key: OptionKey


class RequestHelpData(BaseModel):
    question_id: str


class PingData(EmptyData):
    pass


# `type` -> data model. `snapshot` uses Snapshot, `reveal` uses Reveal.
SERVER_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    "snapshot": Snapshot,
    "phase_changed": PhaseChangedData,
    "players_updated": PlayersUpdatedData,
    "config_updated": ConfigUpdatedData,
    "join_url_updated": JoinUrlUpdatedData,
    "your_card": YourCardData,
    "game_started": GameStartedData,
    "question": QuestionData,
    "answer_result": AnswerResultData,
    "number_drawn": NumberDrawnData,
    "cell_marked": CellMarkedData,
    "reveal": Reveal,
    "question_skipped": QuestionSkippedData,
    "game_over": GameOverData,
    "kicked": KickedData,
    "room_closed": RoomClosedData,
    "error": ErrorData,
    "pong": PongData,
}

CLIENT_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    "submit_answer": SubmitAnswerData,
    "request_help": RequestHelpData,
    "ping": PingData,
}


def ws_message(type_: str, data: BaseModel) -> dict[str, Any]:
    """Build a `{"type", "data"}` dict ready for `send_json`."""
    expected = SERVER_MESSAGE_TYPES.get(type_)
    if expected is None:
        raise ValueError(f"unknown server message type: {type_!r}")
    if not isinstance(data, expected):
        raise TypeError(f"{type_!r} expects {expected.__name__}, got {type(data).__name__}")
    return {"type": type_, "data": data.model_dump(mode="json")}
