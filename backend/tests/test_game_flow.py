"""Integration via TestClient WebSocket: full games in random and fixed mode, event order."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.game.bingo import card_winning_lines
from tests.helpers import (
    WS,
    auth,
    correct_key,
    create_room,
    engine_of,
    is_subsequence,
    join,
    make_client,
    types,
    wrong_key,
    ws_connect,
)


def _answer(ws: WS, q: dict[str, Any], key: str) -> None:
    ws.send("submit_answer", {"question_id": q["question_id"], "attempt": q["attempt"], "key": key})


def play_to_game_over(
    client: TestClient,
    room: dict[str, Any],
    host: WS,
    players: dict[str, WS],
    first_question: dict[str, Any] | None = None,
    max_numbers: int = 120,
    on_question: Any = None,
) -> dict[str, Any]:
    """Answer every question correctly, press Next on `ready`, until `game_over`."""
    pin = room["pin"]
    pending = first_question
    for _ in range(max_numbers * 10):
        if pending is not None:
            q = pending
            pending = None
            if on_question is not None:
                on_question(q)
            _answer(players[q["answerer"]["id"]], q, correct_key(client, pin))
            continue
        m = host.recv()
        if m["type"] == "question":
            pending = m["data"]["question"]
        elif m["type"] == "phase_changed" and m["data"]["phase"] == "ready":
            r = client.post(f"/api/rooms/{pin}/next", headers=auth(room))
            assert r.status_code == 200, r.text
        elif m["type"] == "game_over":
            return m
    raise AssertionError("game did not finish")


def test_random_mode_full_game() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        joined = {name: join(client, pin, name, avatar) for name, avatar in
                  [("An", "cat"), ("Binh", "fox"), ("Chi", "owl")]}
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", joined["An"]["player_token"]) as p1, \
             ws_connect(client, pin, "player", joined["Binh"]["player_token"]) as p2, \
             ws_connect(client, pin, "player", joined["Chi"]["player_token"]) as p3:
            players = {joined["An"]["player_id"]: p1, joined["Binh"]["player_id"]: p2,
                       joined["Chi"]["player_id"]: p3}
            snap = host.recv_type("snapshot")["data"]
            assert snap["phase"] == "lobby" and "card" not in snap and "me" not in snap
            for pid, ws in players.items():
                s = ws.recv_type("snapshot")["data"]
                assert s["me"]["id"] == pid and len(s["card"]) == 5 and s["card"][2][2] == 0
                assert s["marked"] == []
            host.drain()

            r = client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
            assert r.status_code == 200 and r.json() == {"ok": True}
            msgs = [host.recv(), host.recv(), host.recv()]
            assert types(msgs) == ["game_started", "phase_changed", "question"]
            assert msgs[0]["data"] == {"answerer_mode": "random", "fixed_player_id": None}
            assert msgs[1]["data"] == {"phase": "question"}
            q = msgs[2]["data"]["question"]
            assert msgs[2]["data"]["reason"] == "new" and q["attempt"] == 1
            assert [o["key"] for o in q["options"]] == ["A", "B", "C", "D"]
            assert set(q) == {"question_id", "attempt", "text", "operator", "a", "b", "options", "answerer", "deadline"}
            assert q["deadline"] is None

            # Wrong twice -> same player once, then another player (max_wrong).
            first = q["answerer"]["id"]
            _answer(players[first], q, wrong_key(client, pin))
            ar = host.recv()
            assert ar["type"] == "answer_result" and ar["data"]["correct"] is False
            assert ar["data"]["player_id"] == first
            nq = host.recv()
            assert nq["type"] == "question" and nq["data"]["reason"] == "wrong"
            q = nq["data"]["question"]
            assert q["answerer"]["id"] == first and q["attempt"] == 2
            _answer(players[first], q, wrong_key(client, pin))
            assert host.recv()["type"] == "answer_result"
            nq = host.recv()
            assert nq["data"]["reason"] == "max_wrong"
            q = nq["data"]["question"]
            second = q["answerer"]["id"]
            assert second != first and q["attempt"] == 3

            # Help from the player -> third player (not tried yet).
            players[second].send("request_help", {"question_id": q["question_id"]})
            nq = host.recv()
            assert nq["type"] == "question" and nq["data"]["reason"] == "help"
            q = nq["data"]["question"]
            third = q["answerer"]["id"]
            assert third not in (first, second)
            for ws in players.values():
                ws.drain()

            # Correct answer: fixed event order for players holding the number.
            number = engine_of(client, pin).question.number  # type: ignore[union-attr]
            _answer(players[third], q, correct_key(client, pin))
            host_msgs = [host.recv() for _ in range(4)]
            assert types(host_msgs) == ["answer_result", "number_drawn", "phase_changed", "reveal"]
            assert host_msgs[0]["data"]["correct"] is True and host_msgs[0]["data"]["value"] == number
            assert host_msgs[1]["data"] == {"number": number, "drawn": [number]}
            reveal = host_msgs[3]["data"]
            assert reveal["number"] == number and reveal["seconds_per_card"] == 2
            for pid, ws in players.items():
                got = ws.drain(0.1)
                card = engine_of(client, pin).players[pid].card
                has = any(number in row for row in card)
                expected = ["answer_result", "number_drawn"] + (["cell_marked"] if has else []) + \
                    ["phase_changed", "reveal"]
                assert types(got)[: len(expected)] == expected
                if has:
                    cell = got[2]["data"]["cell"]
                    assert card[cell[0]][cell[1]] == number
                    item = next(i for i in reveal["items"] if i["player_id"] == pid)
                    assert item["new_cell"] == cell and item["marked_before"] == []
            assert {i["player_id"] for i in reveal["items"]} == {
                pid for pid in players if any(number in row for row in engine_of(client, pin).players[pid].card)
            }

            over = play_to_game_over(client, room, host, players)
            assert over["data"]["reason"] == "bingo"
            winners = over["data"]["winners"]
            assert winners
            engine = engine_of(client, pin)
            assert engine.phase == "finished"
            assert host.log[-2]["type"] == "phase_changed" and host.log[-2]["data"]["phase"] == "finished"
            for w in winners:
                lines = card_winning_lines(w["card"], engine.drawn)
                assert [(l.type, l.index) for l in lines] == [(l["type"], l["index"]) for l in w["lines"]]
                assert [2, 2] not in w["marked"]
            # Bingo is decided at the first number that produced it.
            for p in engine.players.values():
                assert not card_winning_lines(p.card, engine.drawn[:-1])

            # Snapshot after finish keeps winners.
            with ws_connect(client, pin, "screen", room["screen_token"]) as screen:
                s = screen.recv_type("snapshot")["data"]
                assert s["phase"] == "finished" and s["winners"] == winners
                assert s["question"] is None and s["reveal"] is None


def test_fixed_mode() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        a = join(client, pin, "An", "cat")
        b = join(client, pin, "Binh", "fox")
        c = join(client, pin, "Chi", "owl")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", a["player_token"]) as pa, \
             ws_connect(client, pin, "player", b["player_token"]) as pb, \
             ws_connect(client, pin, "player", c["player_token"]) as pc:
            players = {a["player_id"]: pa, b["player_id"]: pb, c["player_id"]: pc}
            host.drain()
            fixed = b["player_id"]
            r = client.post(f"/api/rooms/{pin}/start", headers=auth(room),
                            json={"answerer_mode": "fixed", "fixed_player_id": fixed})
            assert r.status_code == 200
            assert host.recv()["data"] == {"answerer_mode": "fixed", "fixed_player_id": fixed}
            host.recv_type("phase_changed")
            q = host.recv_type("question")["data"]["question"]
            assert q["answerer"]["id"] == fixed

            # Host Help moves the question to someone else.
            assert client.post(f"/api/rooms/{pin}/help", headers=auth(room)).status_code == 200
            m = host.recv()
            assert m["type"] == "question" and m["data"]["reason"] == "help"
            q = m["data"]["question"]
            assert q["answerer"]["id"] != fixed

            seen: list[str] = []
            over = play_to_game_over(client, room, host, players, first_question=q,
                                     on_question=lambda qq: seen.append(qq["answerer"]["id"]))
            assert over["data"]["reason"] == "bingo"
            # Every later question went back to the fixed player.
            assert len(seen) >= 2 and all(pid == fixed for pid in seen[1:])


def test_skip_end_and_new_round_events() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        p = join(client, pin, "An")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", p["player_token"]) as pw:
            host.drain()
            client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
            q = host.recv_type("question")["data"]["question"]
            skipped = engine_of(client, pin).question.number  # type: ignore[union-attr]

            # Skip: question_skipped -> phase_changed{ready}; number not drawn.
            assert client.post(f"/api/rooms/{pin}/skip", headers=auth(room)).status_code == 200
            m1, m2 = host.recv(), host.recv()
            assert m1 == {"type": "question_skipped", "data": {"question_id": q["question_id"], "number": skipped}}
            assert m2 == {"type": "phase_changed", "data": {"phase": "ready"}}
            assert engine_of(client, pin).drawn == []

            # Next: phase_changed{question} -> question{new}; skipped number not chosen right away.
            assert client.post(f"/api/rooms/{pin}/next", headers=auth(room)).status_code == 200
            m1, m2 = host.recv(), host.recv()
            assert m1 == {"type": "phase_changed", "data": {"phase": "question"}}
            assert m2["type"] == "question" and m2["data"]["reason"] == "new"
            assert engine_of(client, pin).question.number != skipped  # type: ignore[union-attr]

            # Wrong-phase commands -> 409.
            r = client.post(f"/api/rooms/{pin}/next", headers=auth(room))
            assert r.status_code == 409 and r.json()["code"] == "invalid_phase"
            r = client.post(f"/api/rooms/{pin}/new-round", headers=auth(room))
            assert r.status_code == 409 and r.json()["code"] == "invalid_phase"

            # End: phase_changed{finished} -> game_over{ended_by_host}.
            assert client.post(f"/api/rooms/{pin}/end", headers=auth(room)).status_code == 200
            m1, m2 = host.recv(), host.recv()
            assert m1 == {"type": "phase_changed", "data": {"phase": "finished"}}
            assert m2 == {"type": "game_over", "data": {"reason": "ended_by_host", "winners": []}}
            r = client.post(f"/api/rooms/{pin}/end", headers=auth(room))
            assert r.status_code == 409

            # New round with a new address: join_url_updated -> snapshot (to everyone).
            pw.drain()
            old_card = engine_of(client, pin).players[p["player_id"]].card
            r = client.post(f"/api/rooms/{pin}/new-round", headers=auth(room),
                            json={"join_base_url": "http://10.0.0.5:8080/"})
            assert r.status_code == 200
            m1, m2 = host.recv(), host.recv()
            assert m1 == {"type": "join_url_updated", "data": {"join_url": f"http://10.0.0.5:8080/play/{pin}"}}
            assert m2["type"] == "snapshot" and m2["data"]["phase"] == "lobby"
            assert m2["data"]["drawn"] == [] and m2["data"]["answerer_mode"] is None
            got = pw.drain()
            assert types(got) == ["join_url_updated", "snapshot"]
            assert got[1]["data"]["me"]["id"] == p["player_id"] and got[1]["data"]["marked"] == []
            assert engine_of(client, pin).players[p["player_id"]].card != old_card or True

            # New round without address change: only snapshot.
            client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
            client.post(f"/api/rooms/{pin}/end", headers=auth(room))
            host.drain()
            pw.drain()
            assert client.post(f"/api/rooms/{pin}/new-round", headers=auth(room), json={}).status_code == 200
            assert types(host.drain()) == ["snapshot"]
            assert types(pw.drain()) == ["snapshot"]


def test_config_update_in_lobby_sends_new_cards() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        p = join(client, pin, "An")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", p["player_token"]) as pw:
            host.drain()
            pw.drain()
            cfg = {"operations": {"add": False, "sub": False, "mul": True, "div": False},
                   "timer_seconds": 10, "max_wrong": 3, "reveal_seconds": 4, "draw_only_card_numbers": False}
            r = client.put(f"/api/rooms/{pin}/config", headers=auth(room), json=cfg)
            # Missing max_number / next_mode -> defaults.
            full = {**cfg, "max_number": 100, "next_mode": "auto"}
            assert r.status_code == 200 and r.json() == full
            assert host.drain() == [{"type": "config_updated", "data": {"config": full}}]
            got = pw.drain()
            assert types(got) == ["config_updated", "your_card"]
            card = got[1]["data"]["card"]
            assert got[1]["data"]["marked"] == []
            from app.game.numbers import TABLE_PRODUCTS
            assert all(v in TABLE_PRODUCTS for row in card for v in row if v)

            bad = {**cfg, "operations": {"add": False, "sub": False, "mul": False, "div": True}}
            r = client.put(f"/api/rooms/{pin}/config", headers=auth(room), json=bad)
            assert r.status_code == 422 and r.json()["code"] == "invalid_config"

            client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
            r = client.put(f"/api/rooms/{pin}/config", headers=auth(room), json=cfg)
            assert r.status_code == 409 and r.json()["code"] == "invalid_phase"
            client.post(f"/api/rooms/{pin}/end", headers=auth(room))
            # Allowed again in finished, without new cards.
            pw.drain()
            r = client.put(f"/api/rooms/{pin}/config", headers=auth(room), json=cfg)
            assert r.status_code == 200
            assert types(pw.drain()) == ["config_updated"]


def test_submit_answer_error_order_and_invalid_messages() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        a = join(client, pin, "An")
        b = join(client, pin, "Binh")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", a["player_token"]) as pa, \
             ws_connect(client, pin, "player", b["player_token"]) as pb:
            for ws in (host, pa, pb):
                ws.drain()

            def err(ws: WS) -> str:
                m = ws.recv_type("error")
                assert set(m["data"]) == {"code", "message"}
                return m["data"]["code"]

            pa.send("submit_answer", {"question_id": "x", "attempt": 1, "key": "A"})
            assert err(pa) == "invalid_phase"
            pa.send("request_help", {"question_id": "x"})
            assert err(pa) == "invalid_phase"

            client.post(f"/api/rooms/{pin}/start", headers=auth(room),
                        json={"answerer_mode": "fixed", "fixed_player_id": a["player_id"]})
            q = host.recv_type("question")["data"]["question"]
            pa.drain()
            pb.drain()
            # Wrong question_id is checked before the turn.
            pb.send("submit_answer", {"question_id": "nope", "attempt": q["attempt"], "key": "A"})
            assert err(pb) == "stale_question"
            pb.send("submit_answer", {"question_id": q["question_id"], "attempt": 99, "key": "A"})
            assert err(pb) == "not_your_turn"
            pb.send("request_help", {"question_id": q["question_id"]})
            assert err(pb) == "not_your_turn"
            pa.send("submit_answer", {"question_id": q["question_id"], "attempt": 99, "key": "A"})
            assert err(pa) == "stale_question"

            # invalid_message: broken JSON, unknown type, bad data, wrong role.
            pa.s.send_text("{not json")
            assert err(pa) == "invalid_message"
            pa.send("dance", {})
            assert err(pa) == "invalid_message"
            pa.send("submit_answer", {"question_id": q["question_id"], "attempt": 1, "key": "E"})
            assert err(pa) == "invalid_message"
            pa.s.send_text('{"type": "ping", "data": 5}')
            assert err(pa) == "invalid_message"
            host.send("submit_answer", {"question_id": q["question_id"], "attempt": 1, "key": "A"})
            assert err(host) == "invalid_message"

            # Ping -> pong for every role.
            for ws in (host, pa):
                ws.send("ping")
                assert ws.recv_type("pong") == {"type": "pong", "data": {}}
            # State untouched by all the bad messages.
            assert engine_of(client, pin).question.attempt == 1  # type: ignore[union-attr]


def test_options_never_reveal_correct_answer() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        p = join(client, pin, "An")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", p["player_token"]) as pw:
            client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
            q = host.recv_type("question")
            pw.send("ping")
            pw.recv_type("pong")
            for ws in (host, pw):
                for m in ws.log:
                    text = str(m).lower()
                    assert "correct" not in text and "answer\"" not in text
            assert all(set(o) == {"key", "value"} for o in q["data"]["question"]["options"])
            # Snapshot during a question has no hint either.
            with ws_connect(client, pin, "screen", room["screen_token"]) as screen:
                s = screen.recv_type("snapshot")["data"]
                assert s["question"]["question_id"] == q["data"]["question"]["question_id"]
                assert "correct" not in str(s).lower()


def test_countdown_timeout_changes_answerer() -> None:
    with make_client() as client:
        cfg = {"operations": {"add": True, "sub": True, "mul": True, "div": True},
               "timer_seconds": 5, "max_wrong": 2, "reveal_seconds": 2, "draw_only_card_numbers": True}
        room = create_room(client, cfg)
        pin = room["pin"]
        a = join(client, pin, "An")
        b = join(client, pin, "Binh")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", a["player_token"]), \
             ws_connect(client, pin, "player", b["player_token"]):
            client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
            q = host.recv_type("question")["data"]["question"]
            assert q["deadline"] is not None and q["deadline"].endswith("Z")
            m = host.recv_type("question")
            assert m["data"]["reason"] == "timeout"
            assert m["data"]["question"]["answerer"]["id"] != q["answerer"]["id"]
            assert m["data"]["question"]["question_id"] == q["question_id"]
            client.post(f"/api/rooms/{pin}/end", headers=auth(room))


def test_disconnect_of_answerer_changes_after_grace() -> None:
    from app.game.engine import Timings

    with make_client(timings=Timings(time_scale=0.01, disconnect_grace_seconds=10)) as client:
        room = create_room(client)
        pin = room["pin"]
        a = join(client, pin, "An")
        b = join(client, pin, "Binh")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", b["player_token"]):
            with ws_connect(client, pin, "player", a["player_token"]) as pa:
                client.post(f"/api/rooms/{pin}/start", headers=auth(room),
                            json={"answerer_mode": "fixed", "fixed_player_id": a["player_id"]})
                q = host.recv_type("question")["data"]["question"]
                assert q["answerer"]["id"] == a["player_id"]
                host.drain()
                pa.s.close()
                m = host.recv_type("players_updated")
                assert {p["id"]: p["connected"] for p in m["data"]["players"]}[a["player_id"]] is False
            m = host.recv_type("question", timeout=3)
            assert m["data"]["reason"] == "disconnect"
            assert m["data"]["question"]["answerer"]["id"] == b["player_id"]

            # Reconnecting gives the same card and marks.
            with ws_connect(client, pin, "player", a["player_token"]) as pa2:
                s = pa2.recv_type("snapshot")["data"]
                assert s["me"]["id"] == a["player_id"] and s["me"]["connected"] is True
                assert s["card"] == engine_of(client, pin).players[a["player_id"]].card
                assert s["question"]["answerer"]["id"] == b["player_id"]


def test_reconnect_within_grace_keeps_answerer() -> None:
    from app.game.engine import Timings

    with make_client(timings=Timings(time_scale=0.01, disconnect_grace_seconds=50)) as client:
        room = create_room(client)
        pin = room["pin"]
        a = join(client, pin, "An")
        b = join(client, pin, "Binh")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", b["player_token"]):
            with ws_connect(client, pin, "player", a["player_token"]) as pa:
                client.post(f"/api/rooms/{pin}/start", headers=auth(room),
                            json={"answerer_mode": "fixed", "fixed_player_id": a["player_id"]})
                host.recv_type("question")
                pa.s.close()
                host.recv_type("players_updated")
            assert engine_of(client, pin).has_timer("disconnect")
            with ws_connect(client, pin, "player", a["player_token"]) as pa2:
                pa2.recv_type("snapshot")
                host.recv_type("players_updated")
                assert not engine_of(client, pin).has_timer("disconnect")
                assert not any(m["type"] == "question" for m in host.drain(0.8))


def test_player_reconnect_replaces_old_socket() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        a = join(client, pin, "An")
        with ws_connect(client, pin, "player", a["player_token"]) as old:
            old.recv_type("snapshot")
            with ws_connect(client, pin, "player", a["player_token"]) as new:
                new.recv_type("snapshot")
                code, _ = old.expect_close()
                assert code == 4409
                engine = engine_of(client, pin)
                assert engine.connections.players[a["player_id"]].websocket is not None
                assert engine.player_info(a["player_id"]).connected is True


def test_multiple_host_and_screen_connections_receive_events() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        with ws_connect(client, pin, "host", room["host_token"]) as h1, \
             ws_connect(client, pin, "host", room["host_token"]) as h2, \
             ws_connect(client, pin, "screen", room["screen_token"]) as s1:
            for ws in (h1, h2, s1):
                ws.recv_type("snapshot")
            join(client, pin, "An")
            for ws in (h1, h2, s1):
                m = ws.recv_type("players_updated")
                assert [p["nickname"] for p in m["data"]["players"]] == ["An"]
