"""Rooms, codes, tokens, REST errors, WS close codes, idle cleanup."""

from __future__ import annotations

import pytest

from app.rooms import is_guessable_pin, parse_picture_code
from app.schemas import ROOM_ICONS
from tests.helpers import (
    BASE_URL,
    DEFAULT_CONFIG,
    FakeClock,
    PinRng,
    auth,
    create_room,
    engine_of,
    join,
    make_client,
    ws_connect,
)


def _code(r) -> str:  # type: ignore[no-untyped-def]
    body = r.json()
    assert set(body) == {"code", "message"}, body
    return body["code"]


# ---------------------------------------------------------------- codes


@pytest.mark.parametrize("pin", ["1111", "9999", "1234", "6789", "9876", "3210", "4321"])
def test_guessable_pins(pin: str) -> None:
    assert is_guessable_pin(pin)


@pytest.mark.parametrize("pin", ["4729", "1235", "1212", "1000", "9870"])
def test_normal_pins(pin: str) -> None:
    assert not is_guessable_pin(pin)


def test_parse_picture_code() -> None:
    assert parse_picture_code("apple,star,fish") == ("apple", "star", "fish")
    assert parse_picture_code(" Apple , star,fish") == ("apple", "star", "fish")
    assert parse_picture_code("apple,apple,fish") is None
    assert parse_picture_code("apple,star") is None
    assert parse_picture_code("apple,star,dog") is None


def test_create_room_response_and_codes() -> None:
    with make_client() as client:
        room = create_room(client)
        assert set(room) == {"pin", "picture_code", "host_token", "screen_token", "join_url"}
        assert 1000 <= int(room["pin"]) <= 9999 and not is_guessable_pin(room["pin"])
        assert len(room["picture_code"]) == 3 and len(set(room["picture_code"])) == 3
        assert all(i in ROOM_ICONS for i in room["picture_code"])
        assert room["join_url"] == f"{BASE_URL}/play/{room['pin']}"
        assert len(room["host_token"]) >= 40 and room["host_token"] != room["screen_token"]
        r = client.get(f"/api/rooms/{room['pin']}")
        assert r.status_code == 200 and r.json() == {"phase": "lobby", "player_count": 0, "avatar_counts": {}}


def test_codes_unique_across_open_rooms() -> None:
    with make_client(MAX_ROOMS=20) as client:
        rooms = [create_room(client) for _ in range(20)]
        assert len({r["pin"] for r in rooms}) == 20
        assert len({tuple(r["picture_code"]) for r in rooms}) == 20
        r = client.post("/api/rooms", json={"config": DEFAULT_CONFIG, "join_base_url": BASE_URL})
        assert r.status_code == 503 and _code(r) == "too_many_rooms"
        # Closing one frees a slot.
        assert client.delete(f"/api/rooms/{rooms[0]['pin']}", headers=auth(rooms[0])).status_code == 200
        create_room(client)


def test_closed_pin_not_reissued_during_cooldown() -> None:
    clock = FakeClock()
    with make_client(rng=PinRng([4729, 4729, 5831, 4729]), clock=clock) as client:
        first = create_room(client)
        assert first["pin"] == "4729"
        client.delete("/api/rooms/4729", headers=auth(first))
        second = create_room(client)
        assert second["pin"] == "5831"  # 4729 skipped: in cooldown
        assert tuple(first["picture_code"]) in client.app.state.rooms._pictures_cooldown  # type: ignore[attr-defined]
        # After the cooldown the PIN may be used again.
        clock.advance(31 * 60)
        third = create_room(client)
        assert third["pin"] == "4729"


def test_old_tokens_do_not_work_in_new_room_with_same_pin() -> None:
    with make_client(rng=PinRng([4729, 4729]), CODE_COOLDOWN_MINUTES=0) as client:
        old = create_room(client)
        old_player = join(client, "4729", "An")
        client.delete("/api/rooms/4729", headers=auth(old))
        new = create_room(client)
        assert new["pin"] == "4729"
        r = client.post("/api/rooms/4729/start", headers=auth(old), json={"answerer_mode": "random"})
        assert r.status_code == 401 and _code(r) == "bad_token"
        with ws_connect(client, "4729", "host", old["host_token"]) as ws:
            assert ws.expect_close()[0] == 4401
        with ws_connect(client, "4729", "screen", old["screen_token"]) as ws:
            assert ws.expect_close()[0] == 4401
        with ws_connect(client, "4729", "player", old_player["player_token"]) as ws:
            assert ws.expect_close()[0] == 4401


def test_lookup_by_picture_code() -> None:
    with make_client() as client:
        a = create_room(client)
        b = create_room(client)
        for room in (a, b):
            r = client.get("/api/rooms/lookup", params={"pictures": ",".join(room["picture_code"])})
            assert r.status_code == 200 and r.json() == {"pin": room["pin"]}
        # Order matters.
        rev = list(reversed(a["picture_code"]))
        r = client.get("/api/rooms/lookup", params={"pictures": ",".join(rev)})
        if tuple(rev) != tuple(b["picture_code"]):
            assert r.status_code == 404 and _code(r) == "room_not_found"
        for bad in ("", "apple", "apple,apple,star", "x,y,z"):
            r = client.get("/api/rooms/lookup", params={"pictures": bad})
            assert r.status_code == 404 and _code(r) == "room_not_found"
        client.delete(f"/api/rooms/{a['pin']}", headers=auth(a))
        r = client.get("/api/rooms/lookup", params={"pictures": ",".join(a["picture_code"])})
        assert r.status_code == 404


def test_two_rooms_in_parallel_do_not_interfere() -> None:
    with make_client() as client:
        a = create_room(client)
        b = create_room(client)
        pa = join(client, a["pin"], "An")
        pb = join(client, b["pin"], "An")  # same nickname in another room is fine
        r = client.post(f"/api/rooms/{b['pin']}/start", headers=auth(a), json={"answerer_mode": "random"})
        assert r.status_code == 401 and _code(r) == "bad_token"
        with ws_connect(client, a["pin"], "host", a["host_token"]) as ha, \
             ws_connect(client, b["pin"], "host", b["host_token"]) as hb, \
             ws_connect(client, a["pin"], "player", pa["player_token"]), \
             ws_connect(client, b["pin"], "player", pb["player_token"]):
            ha.drain()
            hb.drain()
            assert client.post(f"/api/rooms/{a['pin']}/start", headers=auth(a),
                               json={"answerer_mode": "random"}).status_code == 200
            ha.recv_type("question")
            assert hb.drain() == []
            assert engine_of(client, b["pin"]).phase == "lobby"
            # Player token of room A is not valid in room B.
            with ws_connect(client, b["pin"], "player", pa["player_token"]) as ws:
                assert ws.expect_close()[0] == 4401
            # Screen token cannot act as host.
            r = client.post(f"/api/rooms/{a['pin']}/end", headers={"Authorization": f"Bearer {a['screen_token']}"})
            assert r.status_code == 401
            r = client.post(f"/api/rooms/{a['pin']}/end")
            assert r.status_code == 401 and _code(r) == "bad_token"
            assert client.post(f"/api/rooms/{a['pin']}/end", headers=auth(a)).status_code == 200
            assert engine_of(client, b["pin"]).phase == "lobby"


# ---------------------------------------------------------------- REST validation


@pytest.mark.parametrize(
    "ops",
    [
        {"add": False, "sub": False, "mul": False, "div": False},
        {"add": False, "sub": False, "mul": False, "div": True},
    ],
)
def test_invalid_config(ops: dict[str, bool]) -> None:
    with make_client() as client:
        r = client.post("/api/rooms", json={"config": {**DEFAULT_CONFIG, "operations": ops}, "join_base_url": BASE_URL})
        assert r.status_code == 422 and _code(r) == "invalid_config"


@pytest.mark.parametrize("field,value", [("timer_seconds", 3), ("timer_seconds", 121), ("max_wrong", 0),
                                         ("max_wrong", 6), ("reveal_seconds", 1), ("reveal_seconds", 16)])
def test_invalid_config_ranges(field: str, value: int) -> None:
    with make_client() as client:
        r = client.post("/api/rooms", json={"config": {**DEFAULT_CONFIG, field: value}, "join_base_url": BASE_URL})
        assert r.status_code == 422 and _code(r) == "invalid_config"


@pytest.mark.parametrize(
    "url",
    ["ftp://1.2.3.4", "192.168.1.15:8080", "http://", "http://host/play", "http://host?x=1",
     "http://host/#a", "http://host:99999", "", "http://a b"],
)
def test_invalid_join_url(url: str) -> None:
    with make_client() as client:
        r = client.post("/api/rooms", json={"config": DEFAULT_CONFIG, "join_base_url": url})
        assert r.status_code == 422 and _code(r) == "invalid_join_url"


def test_join_base_url_trailing_slash_and_update() -> None:
    with make_client() as client:
        r = client.post("/api/rooms", json={"config": DEFAULT_CONFIG, "join_base_url": "HTTPS://Bingo.local:8443/"})
        room = r.json()
        assert room["join_url"] == f"https://Bingo.local:8443/play/{room['pin']}"
        pin = room["pin"]
        with ws_connect(client, pin, "screen", room["screen_token"]) as screen:
            screen.recv_type("snapshot")
            r = client.put(f"/api/rooms/{pin}/join-base-url", headers=auth(room),
                           json={"join_base_url": "http://10.0.0.2:8080"})
            assert r.status_code == 200 and r.json() == {"join_url": f"http://10.0.0.2:8080/play/{pin}"}
            assert screen.recv() == {"type": "join_url_updated", "data": r.json()}
            r = client.put(f"/api/rooms/{pin}/join-base-url", headers=auth(room), json={"join_base_url": "http://x/y"})
            assert r.status_code == 422 and _code(r) == "invalid_join_url"


def test_join_validation() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        cases = [
            ({"nickname": "   ", "avatar_id": "cat"}, 422, "invalid_nickname"),
            ({"nickname": "x" * 21, "avatar_id": "cat"}, 422, "invalid_nickname"),
            ({"avatar_id": "cat"}, 422, "invalid_nickname"),
            ({"nickname": "An", "avatar_id": "kuromi"}, 422, "invalid_avatar"),
            ({"nickname": "An"}, 422, "invalid_avatar"),
        ]
        for body, status, code in cases:
            r = client.post(f"/api/rooms/{pin}/join", json=body)
            assert r.status_code == status and _code(r) == code, (body, r.text)
        p = join(client, pin, "  Bé An  ")
        assert set(p) == {"player_id", "player_token"}
        assert engine_of(client, pin).players[p["player_id"]].nickname == "Bé An"
        r = client.post(f"/api/rooms/{pin}/join", json={"nickname": "bé an", "avatar_id": "fox"})
        assert r.status_code == 409 and _code(r) == "nickname_taken"
        r = client.post("/api/rooms/1/join", json={"nickname": "X", "avatar_id": "cat"})
        assert r.status_code == 404 and _code(r) == "room_not_found"
        assert client.get(f"/api/rooms/{pin}").json() == {"phase": "lobby", "player_count": 1, "avatar_counts": {"cat": 1}}


def test_room_status_avatar_counts() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        join(client, pin, "An", "cat")
        b = join(client, pin, "Binh", "cat")
        join(client, pin, "Chi", "owl")
        status = client.get(f"/api/rooms/{pin}").json()
        assert status == {"phase": "lobby", "player_count": 3, "avatar_counts": {"cat": 2, "owl": 1}}
        # Kicked players are not counted; avatars with nobody left disappear.
        client.delete(f"/api/rooms/{pin}/players/{b['player_id']}", headers=auth(room))
        assert client.get(f"/api/rooms/{pin}").json()["avatar_counts"] == {"cat": 1, "owl": 1}
        c = engine_of(client, pin)
        chi = next(p.id for p in c.players.values() if p.nickname == "Chi")
        client.delete(f"/api/rooms/{pin}/players/{chi}", headers=auth(room))
        assert client.get(f"/api/rooms/{pin}").json() == {"phase": "lobby", "player_count": 1,
                                                         "avatar_counts": {"cat": 1}}


def test_room_full_and_game_in_progress() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        for i in range(30):
            join(client, pin, f"P{i}")
        r = client.post(f"/api/rooms/{pin}/join", json={"nickname": "late", "avatar_id": "cat"})
        assert r.status_code == 409 and _code(r) == "room_full"
        room2 = create_room(client)
        join(client, room2["pin"], "A")
        client.post(f"/api/rooms/{room2['pin']}/start", headers=auth(room2), json={"answerer_mode": "random"})
        r = client.post(f"/api/rooms/{room2['pin']}/join", json={"nickname": "late", "avatar_id": "cat"})
        assert r.status_code == 409 and _code(r) == "game_in_progress"


def test_start_errors() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        r = client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
        assert r.status_code == 422 and _code(r) == "no_players"
        join(client, pin, "A")
        for body in ({"answerer_mode": "fixed"}, {"answerer_mode": "fixed", "fixed_player_id": "nobody"}):
            r = client.post(f"/api/rooms/{pin}/start", headers=auth(room), json=body)
            assert r.status_code == 422 and _code(r) == "fixed_player_required"
        for path in ("next", "skip", "help", "end", "new-round"):
            r = client.post(f"/api/rooms/{pin}/{path}", headers=auth(room))
            assert r.status_code == 409 and _code(r) == "invalid_phase", path
        r = client.post("/api/rooms/1234/start", headers=auth(room), json={"answerer_mode": "random"})
        assert r.status_code == 404 and _code(r) == "room_not_found"


def test_kick() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        a = join(client, pin, "An")
        b = join(client, pin, "Binh")
        r = client.delete(f"/api/rooms/{pin}/players/nobody", headers=auth(room))
        assert r.status_code == 404 and _code(r) == "player_not_found"
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "player", a["player_token"]) as pa:
            pa.recv_type("snapshot")
            host.drain()
            assert client.delete(f"/api/rooms/{pin}/players/{a['player_id']}", headers=auth(room)).status_code == 200
            code, before = pa.expect_close()
            assert code == 4403 and before[-1] == {"type": "kicked", "data": {}}
            m = host.recv_type("players_updated")
            assert [p["id"] for p in m["data"]["players"]] == [b["player_id"]]
        with ws_connect(client, pin, "player", a["player_token"]) as again:
            assert again.expect_close()[0] == 4403
        # Nickname is free again.
        join(client, pin, "An")
        client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
        r = client.delete(f"/api/rooms/{pin}/players/{b['player_id']}", headers=auth(room))
        assert r.status_code == 409 and _code(r) == "invalid_phase"


# ---------------------------------------------------------------- WS close codes / closing


def test_ws_close_codes() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        with ws_connect(client, "9182", "host", "x") as ws:
            assert ws.expect_close()[0] == 4404
        with ws_connect(client, pin, "host", "wrong") as ws:
            assert ws.expect_close()[0] == 4401
        with ws_connect(client, pin, "admin", room["host_token"]) as ws:
            assert ws.expect_close()[0] == 4401
        with ws_connect(client, pin, "player", room["host_token"]) as ws:
            assert ws.expect_close()[0] == 4401


def test_close_room_by_host() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        p = join(client, pin, "An")
        with ws_connect(client, pin, "host", room["host_token"]) as host, \
             ws_connect(client, pin, "screen", room["screen_token"]) as screen, \
             ws_connect(client, pin, "player", p["player_token"]) as pw:
            for ws in (host, screen, pw):
                ws.recv_type("snapshot")
            client.post(f"/api/rooms/{pin}/start", headers=auth(room), json={"answerer_mode": "random"})
            assert client.delete(f"/api/rooms/{pin}", headers=auth(room)).json() == {"ok": True}
            for ws in (host, screen, pw):
                code, before = ws.expect_close()
                assert code == 4410
                assert before[-1] == {"type": "room_closed", "data": {"reason": "closed_by_host"}}
        r = client.get(f"/api/rooms/{pin}")
        assert r.status_code == 404 and _code(r) == "room_not_found"
        r = client.delete(f"/api/rooms/{pin}", headers=auth(room))
        assert r.status_code == 404
        # Old QR during cooldown: "room closed", not "not found".
        with ws_connect(client, pin, "player", p["player_token"]) as ws:
            code, before = ws.expect_close()
            assert code == 4410 and before == [{"type": "room_closed", "data": {"reason": "closed_by_host"}}]


def test_idle_room_is_cleaned_up() -> None:
    clock = FakeClock()
    with make_client(clock=clock, ROOM_IDLE_MINUTES=30) as client:
        idle = create_room(client)
        busy = create_room(client)
        manager = client.app.state.rooms  # type: ignore[attr-defined]
        with ws_connect(client, busy["pin"], "screen", busy["screen_token"]) as screen:
            screen.recv_type("snapshot")
            clock.advance(29 * 60)
            assert client.portal.call(manager.cleanup_idle) == 0  # type: ignore[union-attr]
            clock.advance(2 * 60)
            assert client.portal.call(manager.cleanup_idle) == 1  # type: ignore[union-attr]
            assert client.get(f"/api/rooms/{idle['pin']}").status_code == 404
            assert client.get(f"/api/rooms/{busy['pin']}").status_code == 200
            with ws_connect(client, idle["pin"], "host", idle["host_token"]) as ws:
                code, before = ws.expect_close()
                assert code == 4410 and before == [{"type": "room_closed", "data": {"reason": "expired"}}]
        # Idle timer starts when the last connection leaves.
        clock.advance(10 * 60)
        assert client.portal.call(manager.cleanup_idle) == 0  # type: ignore[union-attr]
        clock.advance(25 * 60)
        assert client.portal.call(manager.cleanup_idle) == 1  # type: ignore[union-attr]
        assert client.get(f"/api/rooms/{busy['pin']}").status_code == 404
        # Once the cooldown is over, the old PIN is simply unknown again.
        with ws_connect(client, idle["pin"], "host", idle["host_token"]) as ws:
            assert ws.expect_close()[0] == 4404


def test_expired_room_notifies_connected_clients() -> None:
    """Closing with reason `expired` sends room_closed{expired} then 4410 to anyone still there."""
    with make_client() as client:
        room = create_room(client)
        manager = client.app.state.rooms  # type: ignore[attr-defined]
        engine = engine_of(client, room["pin"])
        with ws_connect(client, room["pin"], "screen", room["screen_token"]) as screen:
            screen.recv_type("snapshot")
            client.portal.call(manager.close_room, engine, "expired")  # type: ignore[union-attr]
            code, before = screen.expect_close()
            assert code == 4410 and before[-1] == {"type": "room_closed", "data": {"reason": "expired"}}


# ---------------------------------------------------------------- public endpoints


def test_public_endpoints() -> None:
    with make_client() as client:
        assert client.get("/api/health").json() == {"ok": True}
        avatars = client.get("/api/avatars").json()
        assert len(avatars) >= 12
        ids = {a["id"] for a in avatars}
        assert {"capybara", "cat", "rabbit", "bear", "panda", "fox", "penguin", "frog", "duck",
                "unicorn", "dinosaur", "owl"} <= ids
        for a in avatars:
            assert set(a) == {"id", "name", "image_url", "win_animation_url", "color"}
            r = client.get(a["image_url"])
            assert r.status_code == 200 and b"<svg" in r.content
        net = client.get("/api/network").json()
        assert set(net) == {"ips", "port"} and isinstance(net["port"], int)
        r = client.get("/api/nope")
        assert r.status_code == 404 and _code(r) == "not_found"
        r = client.put("/api/health")
        assert r.status_code == 405 and _code(r) == "method_not_allowed"


def test_invalid_request_for_generic_bad_bodies() -> None:
    with make_client() as client:
        room = create_room(client)
        pin = room["pin"]
        join(client, pin, "An")
        for body in ({"answerer_mode": "sometimes"}, {}, None):
            r = client.post(f"/api/rooms/{pin}/start", headers=auth(room), json=body)
            assert r.status_code == 422 and _code(r) == "invalid_request", body
        r = client.post(f"/api/rooms/{pin}/join", content=b"{broken", headers={"Content-Type": "application/json"})
        assert r.status_code == 422 and _code(r) == "invalid_request"
        r = client.post("/api/rooms", json={"join_base_url": BASE_URL})
        assert r.status_code == 422 and _code(r) == "invalid_config"
        r = client.put(f"/api/rooms/{pin}/config", headers=auth(room), json={**DEFAULT_CONFIG, "max_wrong": 9})
        assert r.status_code == 422 and _code(r) == "invalid_config"


def test_network_uses_app_port_and_lan_ip() -> None:
    with make_client(APP_PORT=8080, LAN_IP="192.168.1.50") as client:
        net = client.get("/api/network").json()
        assert net["port"] == 8080 and net["ips"][0] == "192.168.1.50"
