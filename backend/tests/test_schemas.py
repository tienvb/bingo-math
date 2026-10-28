from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.schemas import (
    CLIENT_MESSAGE_TYPES,
    GameConfig,
    Option,
    PlayerInfo,
    Question,
    QuestionData,
    Reveal,
    RevealItem,
    Snapshot,
    SubmitAnswerData,
    ws_message,
)

PLAYER = PlayerInfo(id="p1", nickname="Bé An", avatar_id="cat", connected=True)


def _question() -> Question:
    return Question(
        question_id="q1",
        attempt=1,
        text="7 × 8 = ?",
        operator="x",
        a=7,
        b=8,
        options=[Option(key=k, value=v) for k, v in zip("ABCD", [54, 56, 57, 64])],
        answerer=PLAYER,
        deadline=None,
    )


def test_question_field_names() -> None:
    data = _question().model_dump(mode="json")
    assert set(data) == {
        "question_id", "attempt", "text", "operator", "a", "b", "options", "answerer", "deadline",
    }
    assert data["options"][0] == {"key": "A", "value": 54}
    assert set(data["answerer"]) == {"id", "nickname", "avatar_id", "connected"}
    assert data["deadline"] is None
    assert "correct" not in json.dumps(data)


def test_operator_literal() -> None:
    with pytest.raises(ValidationError):
        Question(**{**_question().model_dump(), "operator": "×"})


def _snapshot(**extra) -> Snapshot:
    return Snapshot(
        pin="4729",
        picture_code=["apple", "star", "fish"],
        phase="lobby",
        join_url="http://192.168.1.15:8080/play/4729",
        config=GameConfig(),
        players=[PLAYER],
        drawn=[],
        **extra,
    )


SNAPSHOT_KEYS = {
    "pin", "picture_code", "phase", "join_url", "config", "players", "answerer_mode",
    "fixed_player_id", "drawn", "question", "reveal", "winners",
}


def test_snapshot_without_player_fields() -> None:
    data = _snapshot().model_dump(mode="json")
    assert set(data) == SNAPSHOT_KEYS
    assert data["question"] is None and data["reveal"] is None and data["winners"] == []
    assert data["answerer_mode"] is None and data["fixed_player_id"] is None
    assert data["config"] == {
        "operations": {"add": True, "sub": True, "mul": True, "div": True},
        "timer_seconds": 0,
        "max_wrong": 2,
        "reveal_seconds": 5,
        "draw_only_card_numbers": True,
    }


def test_snapshot_for_player() -> None:
    card = [[1, 21, 41, 61, 81]] * 2 + [[2, 22, 0, 62, 82]] + [[3, 23, 43, 63, 83]] * 2
    snap = _snapshot(me=PLAYER, card=card, marked=[(0, 1)], question=_question())
    data = json.loads(snap.model_dump_json())
    assert set(data) == SNAPSHOT_KEYS | {"me", "card", "marked"}
    assert data["marked"] == [[0, 1]]
    assert data["question"]["operator"] == "x"


def test_ws_envelope() -> None:
    msg = ws_message("question", QuestionData(question=_question(), reason="new"))
    assert msg["type"] == "question" and set(msg["data"]) == {"question", "reason"}
    reveal = Reveal(
        number=56, seconds_per_card=5, started_at="2026-10-28T10:00:00Z",
        items=[RevealItem(player_id="p1", nickname="An", avatar_id="cat",
                          card=[[0] * 5] * 5, marked_before=[(0, 0)], new_cell=(1, 2))],
    )
    msg = ws_message("reveal", reveal)
    assert msg["data"]["items"][0]["new_cell"] == [1, 2]
    with pytest.raises(TypeError):
        ws_message("reveal", QuestionData(question=_question(), reason="new"))
    with pytest.raises(ValueError):
        ws_message("nope", reveal)


def test_client_messages() -> None:
    assert set(CLIENT_MESSAGE_TYPES) == {"submit_answer", "request_help", "ping"}
    SubmitAnswerData(question_id="q", attempt=1, key="B")
    with pytest.raises(ValidationError):
        SubmitAnswerData(question_id="q", attempt=1, key="E")


@pytest.mark.parametrize(
    "bad",
    [
        {"operations": {"add": False, "sub": False, "mul": False, "div": False}},
        {"operations": {"add": False, "sub": False, "mul": False, "div": True}},
        {"timer_seconds": 3},
        {"timer_seconds": 121},
        {"max_wrong": 0},
        {"max_wrong": 6},
        {"reveal_seconds": 1},
        {"reveal_seconds": 16},
    ],
)
def test_invalid_config(bad: dict) -> None:
    with pytest.raises(ValidationError):
        GameConfig(**bad)


def test_valid_configs() -> None:
    GameConfig(operations={"add": False, "sub": False, "mul": True, "div": False})
    GameConfig(timer_seconds=5)
    GameConfig(timer_seconds=120, max_wrong=5, reveal_seconds=15)


def test_error_codes_match_contract() -> None:
    from app.schemas import ERROR_CODES

    assert ERROR_CODES == {
        "bad_token", "room_not_found", "invalid_phase", "invalid_config", "invalid_join_url",
        "too_many_rooms", "player_not_found", "no_players", "fixed_player_required",
        "no_numbers_left", "nickname_taken", "game_in_progress", "room_full",
        "invalid_nickname", "invalid_avatar", "not_your_turn", "stale_question",
        "invalid_message",
    }
