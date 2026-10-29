"""Play a whole game against a running server (not a pytest test).

Usage:
    .venv/bin/python tests/manual_client.py http://localhost:8000
    .venv/bin/python tests/manual_client.py http://localhost:8080   # through nginx
    .venv/bin/python tests/manual_client.py http://localhost:8000 --next-mode manual --max-number 50

Creates a room, lets a few bot players join, starts in random mode and plays until
bingo. Bots work out the answer from `a`, `operator`, `b` (only this test bot does
that; the real FE never computes answers) and sometimes answer wrong or ask for help
on purpose to exercise those paths. Exit code 0 on success.

`--next-mode auto` (default): the host never calls /next; the server opens the next
question by itself after each reveal. `--next-mode manual`: the host presses Next
on every `ready`. `--max-number M`: omitted -> server default (100); every operand,
option and card number is checked to be <= M.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from typing import Any

import httpx
from websockets.asyncio.client import ClientConnection, connect

NAMES = [("Bé An", "capybara"), ("Bé Bình", "cat"), ("Bé Chi", "unicorn"), ("Bé Dũng", "dinosaur")]
CONFIG: dict[str, Any] = {
    "operations": {"add": True, "sub": True, "mul": True, "div": True},
    "timer_seconds": 0,
    "max_wrong": 2,
    "reveal_seconds": 2,  # minimum allowed, keeps the run short (server default is 3)
    "draw_only_card_numbers": True,
}
DEFAULT_MAX_NUMBER = 100


def log(msg: str) -> None:
    print(msg, flush=True)


def solve(q: dict[str, Any]) -> int:
    a, b, op = q["a"], q["b"], q["operator"]
    return {"+": a + b, "-": a - b, "x": a * b, ":": a // b if b else 0}[op]


class Bot:
    def __init__(self, name: str, avatar: str, player_id: str, token: str, wrong_rate: float) -> None:
        self.name = name
        self.avatar = avatar
        self.player_id = player_id
        self.token = token
        self.wrong_rate = wrong_rate
        self.ws: ClientConnection | None = None
        self.marked = 0

    async def run(self, ws_base: str, pin: str, rng: random.Random) -> None:
        async with connect(f"{ws_base}/ws?pin={pin}&role=player&token={self.token}") as ws:
            self.ws = ws
            async for raw in ws:
                msg = json.loads(raw)
                t, d = msg["type"], msg["data"]
                if t == "snapshot":
                    assert d["me"]["id"] == self.player_id and len(d["card"]) == 5
                    m = d["config"]["max_number"]
                    assert all(0 <= v <= m for row in d["card"] for v in row), d["card"]
                elif t == "cell_marked":
                    self.marked += 1
                elif t == "question" and d["question"]["answerer"]["id"] == self.player_id:
                    await self.answer(ws, d["question"], d["reason"], rng)
                elif t == "error":
                    log(f"  ! {self.name} got error {d}")
                elif t in ("game_over", "room_closed"):
                    return

    async def answer(self, ws: ClientConnection, q: dict[str, Any], reason: str, rng: random.Random) -> None:
        await asyncio.sleep(0.05)
        if reason == "new" and rng.random() < 0.1:
            await ws.send(json.dumps({"type": "request_help", "data": {"question_id": q["question_id"]}}))
            log(f"    {self.name} asks for help")
            return
        good = solve(q)
        options = {o["key"]: o["value"] for o in q["options"]}
        right = next(k for k, v in options.items() if v == good)
        key = right
        if rng.random() < self.wrong_rate:
            key = rng.choice([k for k in options if k != right])
        await ws.send(json.dumps(
            {"type": "submit_answer", "data": {"question_id": q["question_id"], "attempt": q["attempt"], "key": key}}
        ))


async def play(
    base: str, players: int, seed: int | None, timeout: float, next_mode: str, max_number: int | None
) -> int:
    rng = random.Random(seed)
    config = {**CONFIG, "next_mode": next_mode}
    if max_number is not None:
        config["max_number"] = max_number
    m = max_number or DEFAULT_MAX_NUMBER
    ws_base = "ws" + base[len("http"):] if base.startswith("http") else base
    async with httpx.AsyncClient(base_url=base, timeout=10) as http:
        health = (await http.get("/api/health")).json()
        assert health == {"ok": True}, health
        avatars = {a["id"] for a in (await http.get("/api/avatars")).json()}
        log(f"server ok, {len(avatars)} avatars")

        r = await http.post("/api/rooms", json={"config": config, "join_base_url": base})
        r.raise_for_status()
        room = r.json()
        pin = room["pin"]
        headers = {"Authorization": f"Bearer {room['host_token']}"}
        log(f"room PIN {pin}, pictures {'-'.join(room['picture_code'])}, join_url {room['join_url']}")
        lookup = (await http.get("/api/rooms/lookup", params={"pictures": ",".join(room["picture_code"])})).json()
        assert lookup == {"pin": pin}, lookup

        bots: list[Bot] = []
        for i, (name, avatar) in enumerate(NAMES[:players]):
            avatar = avatar if avatar in avatars else sorted(avatars)[0]
            j = await http.post(f"/api/rooms/{pin}/join", json={"nickname": name, "avatar_id": avatar})
            j.raise_for_status()
            data = j.json()
            bots.append(Bot(name, avatar, data["player_id"], data["player_token"], wrong_rate=0.25 if i else 0.0))
            log(f"  {name} joined as {avatar}")
        names = {b.player_id: b.name for b in bots}

        async with connect(f"{ws_base}/ws?pin={pin}&role=host&token={room['host_token']}") as host:
            bot_tasks = [asyncio.create_task(b.run(ws_base, pin, rng)) for b in bots]
            questions = 0
            next_calls = 0
            result = 1
            started = False
            try:
                async with asyncio.timeout(timeout):
                    async for raw in host:
                        msg = json.loads(raw)
                        t, d = msg["type"], msg["data"]
                        if t == "snapshot":
                            cfg = d["config"]
                            log(f"host snapshot: phase={d['phase']}, players={len(d['players'])}, "
                                f"next_mode={cfg['next_mode']}, max_number={cfg['max_number']}, "
                                f"reveal_seconds={cfg['reveal_seconds']}")
                            assert cfg["next_mode"] == next_mode and cfg["max_number"] == m, cfg
                        elif t == "players_updated":
                            online = sum(p["connected"] for p in d["players"])
                            if not started and online == len(bots):
                                started = True
                                r = await http.post(f"/api/rooms/{pin}/start", headers=headers,
                                                    json={"answerer_mode": "random"})
                                r.raise_for_status()
                                log("game started (random)")
                        elif t == "question":
                            q = d["question"]
                            assert 1 <= q["a"] <= m and 1 <= q["b"] <= m, q
                            assert all(1 <= o["value"] <= m for o in q["options"]), q
                            if d["reason"] == "new":
                                questions += 1
                            log(f"  Q{questions} [{d['reason']}] {q['text']}  "
                                f"{' '.join(o['key'] + '=' + str(o['value']) for o in q['options'])}"
                                f"  -> {names.get(q['answerer']['id'])}")
                        elif t == "answer_result":
                            log(f"    {names.get(d['player_id'])} chose {d['key']}={d['value']}: "
                                f"{'correct' if d['correct'] else 'wrong'}")
                        elif t == "reveal":
                            who = ", ".join(i["nickname"] for i in d["items"]) or "nobody"
                            log(f"    number {d['number']} on: {who}")
                        elif t == "phase_changed" and d["phase"] == "ready":
                            r = await http.post(f"/api/rooms/{pin}/next", headers=headers)
                            if next_mode == "auto":
                                # Auto only waits in `ready` when the pool is empty.
                                log(f"    ready in auto mode, /next -> {r.status_code} {r.json()}")
                                assert r.status_code == 409 and r.json()["code"] == "no_numbers_left"
                                await http.post(f"/api/rooms/{pin}/end", headers=headers)
                            else:
                                r.raise_for_status()
                                next_calls += 1
                        elif t == "game_over":
                            for w in d["winners"]:
                                lines = ", ".join(f"{ln['type']} {ln['index']}" for ln in w["lines"])
                                log(f"BINGO! {w['nickname']} ({w['avatar_id']}) on {lines}")
                            log(f"game over ({d['reason']}) after {questions} questions, "
                                f"{next_calls} /next calls ({next_mode})")
                            if next_mode == "auto":
                                assert next_calls == 0
                            result = 0 if d["reason"] == "bingo" and d["winners"] else 1
                            break
                        elif t == "error":
                            log(f"host error: {d}")
            except TimeoutError:
                log(f"timeout after {timeout}s")
                result = 1
            finally:
                await asyncio.wait(bot_tasks, timeout=5)
                for task in bot_tasks:
                    task.cancel()

        status = (await http.get(f"/api/rooms/{pin}")).json()
        log(f"room status: {status}")
        r = await http.delete(f"/api/rooms/{pin}", headers=headers)
        log(f"room closed: {r.json()}")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base_url", nargs="?", default="http://localhost:8000")
    parser.add_argument("--players", type=int, default=3, choices=range(1, len(NAMES) + 1))
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--next-mode", choices=("auto", "manual"), default="auto")
    parser.add_argument("--max-number", type=int, default=None, help="31..9007199254740991; omitted = server default (100)")
    args = parser.parse_args()
    try:
        return asyncio.run(play(args.base_url.rstrip("/"), args.players, args.seed, args.timeout,
                                args.next_mode, args.max_number))
    except Exception as exc:  # noqa: BLE001
        log(f"FAILED: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
