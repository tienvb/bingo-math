"""`next_mode` (auto/manual) and `max_number` end to end (CHANGELOG 2026-10-29)."""

from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient

from app.game.cards import card_numbers
from tests.helpers import (
    DEFAULT_CONFIG,
    WS,
    auth,
    correct_key,
    create_room,
    engine_of,
    join,
    make_client,
    ws_connect,
)

AUTO = {**DEFAULT_CONFIG, "next_mode": "auto"}
MANUAL = {**DEFAULT_CONFIG, "next_mode": "manual"}


def _answer(ws: WS, q: dict[str, Any], key: str) -> None:
    ws.send("submit_answer", {"question_id": q["question_id"], "attempt": q["attempt"], "key": key})


def _setup(client: TestClient, config: dict[str, Any], names: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    room = create_room(client, config)
    return room, [join(client, room["pin"], n, "cat") for n in names]


def _start(client: TestClient, room: dict[str, Any], host: WS) -> dict[str, Any]:
    host.drain()
    r = client.post(f"/api/rooms/{room['pin']}/start", headers=auth(room), json={"answerer_mode": "random"})
    assert r.status_code == 200, r.text
    return host.recv_type("question")["data"]["question"]


def _check_question_within_m(q: dict[str, Any], m: int) -> None:
    assert 1 <= q["a"] <= m and 1 <= q["b"] <= m
    assert all(1 <= o["value"] <= m for o in q["options"])


# --------------------------------------------------------------------- auto


def test_auto_reveal_goes_straight_to_next_question_until_bingo() -> None:
    with make_client() as client:
        room, joined = _setup(client, AUTO, ["An", "Binh", "Chi"])
        pin = room["pin"]
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", joined[0]["player_token"]) as p1, \
             ws_connect(client, pin, "player", joined[1]["player_token"]) as p2, \
             ws_connect(client, pin, "player", joined[2]["player_token"]) as p3:
            players = {joined[0]["player_id"]: p1, joined[1]["player_id"]: p2, joined[2]["player_id"]: p3}
            q: dict[str, Any] | None = _start(client, room, host)
            questions = 0
            over = None
            for _ in range(2000):
                if q is not None:
                    questions += 1
                    _answer(players[q["answerer"]["id"]], q, correct_key(client, pin))
                    q = None
                m = host.recv()
                assert not (m["type"] == "phase_changed" and m["data"]["phase"] == "ready"), "auto never waits in ready"
                if m["type"] == "reveal":
                    after = host.recv()
                    if after["type"] == "phase_changed" and after["data"]["phase"] == "question":
                        nxt = host.recv()
                        assert nxt["type"] == "question" and nxt["data"]["reason"] == "new"
                        q = nxt["data"]["question"]
                    else:
                        assert after == {"type": "phase_changed", "data": {"phase": "finished"}}
                        over = host.recv()
                        break
            assert over is not None and over["type"] == "game_over"
            assert over["data"]["reason"] == "bingo" and over["data"]["winners"]
            assert questions >= 4 and engine_of(client, pin).phase == "finished"


def test_auto_skip_opens_new_question_without_phase_change() -> None:
    with make_client() as client:
        room, joined = _setup(client, AUTO, ["An"])
        pin = room["pin"]
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", joined[0]["player_token"]):
            q = _start(client, room, host)
            skipped = engine_of(client, pin).question.number  # type: ignore[union-attr]
            assert client.post(f"/api/rooms/{pin}/skip", headers=auth(room)).status_code == 200
            m1, m2 = host.recv(), host.recv()
            assert m1 == {"type": "question_skipped", "data": {"question_id": q["question_id"], "number": skipped}}
            assert m2["type"] == "question" and m2["data"]["reason"] == "new"
            assert m2["data"]["question"]["question_id"] != q["question_id"]
            assert host.drain() == []
            engine = engine_of(client, pin)
            assert engine.phase == "question" and engine.drawn == []
            assert engine.question is not None and engine.question.number != skipped
            # /next is only for `ready`.
            r = client.post(f"/api/rooms/{pin}/next", headers=auth(room))
            assert r.status_code == 409 and r.json()["code"] == "invalid_phase"


def test_auto_empty_pool_goes_to_ready() -> None:
    with make_client() as client:
        room, joined = _setup(client, AUTO, ["An"])
        pin = room["pin"]
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", joined[0]["player_token"]) as pw:
            q = _start(client, room, host)
            engine = engine_of(client, pin)
            assert engine.question is not None
            n = engine.question.number
            # Every other card number is already out, and nobody wins: after this number
            # the pool is empty.
            engine.drawn = sorted(card_numbers(engine.players[joined[0]["player_id"]].card) - {n})
            engine._compute_winners = lambda: []  # type: ignore[method-assign]

            # Skipping with only the skipped number left re-asks it (it is back in the pool).
            assert client.post(f"/api/rooms/{pin}/skip", headers=auth(room)).status_code == 200
            m1, m2 = host.recv(), host.recv()
            assert m1["type"] == "question_skipped" and m2["type"] == "question"
            assert engine.question is not None and engine.question.number == n
            q = m2["data"]["question"]

            _answer(pw, q, correct_key(client, pin))
            host.recv_type("reveal")
            assert host.recv() == {"type": "phase_changed", "data": {"phase": "ready"}}
            assert host.drain() == []
            r = client.post(f"/api/rooms/{pin}/next", headers=auth(room))
            assert r.status_code == 409 and r.json()["code"] == "no_numbers_left"
            assert client.post(f"/api/rooms/{pin}/end", headers=auth(room)).status_code == 200
            assert host.recv() == {"type": "phase_changed", "data": {"phase": "finished"}}


# --------------------------------------------------------------------- manual


def test_manual_reveal_and_skip_wait_in_ready() -> None:
    with make_client() as client:
        room, joined = _setup(client, MANUAL, ["An", "Binh"])
        pin = room["pin"]
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", joined[0]["player_token"]) as p1, \
             ws_connect(client, pin, "player", joined[1]["player_token"]) as p2:
            players = {joined[0]["player_id"]: p1, joined[1]["player_id"]: p2}
            q = _start(client, room, host)
            _answer(players[q["answerer"]["id"]], q, correct_key(client, pin))
            host.recv_type("reveal")
            assert host.recv() == {"type": "phase_changed", "data": {"phase": "ready"}}
            assert host.drain(0.1) == []  # nothing until the host presses Next
            assert client.post(f"/api/rooms/{pin}/next", headers=auth(room)).status_code == 200
            assert host.recv() == {"type": "phase_changed", "data": {"phase": "question"}}
            q = host.recv()["data"]["question"]
            assert client.post(f"/api/rooms/{pin}/skip", headers=auth(room)).status_code == 200
            assert host.recv()["type"] == "question_skipped"
            assert host.recv() == {"type": "phase_changed", "data": {"phase": "ready"}}
            assert host.drain(0.1) == []


# --------------------------------------------------------------------- defaults


def test_missing_new_fields_use_defaults() -> None:
    legacy = {k: v for k, v in DEFAULT_CONFIG.items() if k not in ("max_number", "next_mode", "reveal_seconds")}
    with make_client() as client:
        room = create_room(client, legacy)
        with ws_connect(client, room["pin"], "host", room["host_token"]) as host:
            cfg = host.recv_type("snapshot")["data"]["config"]
        assert cfg["max_number"] == 100 and cfg["next_mode"] == "auto" and cfg["reveal_seconds"] == 3
        r = client.post("/api/rooms", json={"config": {}, "join_base_url": "http://192.168.1.15:8080"})
        assert r.status_code == 200


def test_invalid_max_number_rejected() -> None:
    with make_client() as client:
        for bad in (
            {**DEFAULT_CONFIG, "max_number": 30},
            {**DEFAULT_CONFIG, "max_number": -1},
            {**DEFAULT_CONFIG, "max_number": "big"},
            {**DEFAULT_CONFIG, "max_number": 2**53},
            {**DEFAULT_CONFIG, "next_mode": "later"},
            {**DEFAULT_CONFIG, "max_number": 31,
             "operations": {"add": False, "sub": False, "mul": True, "div": True}},  # |R| = 22
        ):
            r = client.post("/api/rooms", json={"config": bad, "join_base_url": "http://192.168.1.15:8080"})
            assert r.status_code == 422 and r.json()["code"] == "invalid_config", (bad, r.text)
        room = create_room(client)
        r = client.put(f"/api/rooms/{room['pin']}/config", headers=auth(room),
                       json={**DEFAULT_CONFIG, "max_number": 20})
        assert r.status_code == 422 and r.json()["code"] == "invalid_config"


# --------------------------------------------------------------------- max_number


def _play_some(client: TestClient, config: dict[str, Any], m: int, rounds: int) -> None:
    room, joined = _setup(client, config, ["An", "Binh"])
    pin = room["pin"]
    engine = engine_of(client, pin)
    for p in engine.players.values():
        assert all(1 <= v <= m for v in card_numbers(p.card))
    with ws_connect(client, pin, "host", room["host_token"]) as host, \
         ws_connect(client, pin, "player", joined[0]["player_token"]) as p1, \
         ws_connect(client, pin, "player", joined[1]["player_token"]) as p2:
        players = {joined[0]["player_id"]: p1, joined[1]["player_id"]: p2}
        q: dict[str, Any] | None = _start(client, room, host)
        done = 0
        while done < rounds:
            if q is not None:
                _check_question_within_m(q, m)
                _answer(players[q["answerer"]["id"]], q, correct_key(client, pin))
                done += 1
                q = None
            msg = host.recv()
            if msg["type"] == "question":
                q = msg["data"]["question"]
            elif msg["type"] == "number_drawn":
                assert 1 <= msg["data"]["number"] <= m
            elif msg["type"] == "game_over":
                break
        assert len(set(engine.drawn)) == len(engine.drawn)
        if engine.phase != "finished":
            assert client.post(f"/api/rooms/{pin}/end", headers=auth(room)).status_code == 200


def test_max_number_small_and_large() -> None:
    with make_client() as client:
        for m in (31, 50, 1000):
            _play_some(client, {**AUTO, "max_number": m}, m, 8)
        _play_some(client, {**AUTO, "max_number": 50,
                            "operations": {"add": False, "sub": False, "mul": True, "div": True}}, 50, 8)


def test_huge_max_number_is_fast() -> None:
    m = 10**9
    t0 = time.perf_counter()
    with make_client() as client:
        for draw_only in (True, False):
            _play_some(client, {**AUTO, "max_number": m, "draw_only_card_numbers": draw_only}, m, 10)
        room = create_room(client, {**AUTO, "max_number": m})
        with ws_connect(client, room["pin"], "host", room["host_token"]) as host:
            assert host.recv_type("snapshot")["data"]["config"]["max_number"] == m
        # Technical cap 2**53 - 1 is accepted and playable.
        _play_some(client, {**AUTO, "max_number": 2**53 - 1, "draw_only_card_numbers": False}, 2**53 - 1, 5)
    assert time.perf_counter() - t0 < 5.0
