"""Host-only endpoints (Bearer host token of that room)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request

from app.game.engine import GameEngine
from app.joinurl import build_join_url, normalize_join_base_url
from app.schemas import (
    GameConfig,
    JoinBaseUrlRequest,
    JoinUrlResponse,
    NewRoundRequest,
    OkResponse,
    StartRequest,
)
from app.tokens import get_manager, require_host

router = APIRouter(prefix="/api/rooms/{pin}", tags=["host"])

HostEngine = Depends(require_host)


@router.delete("", response_model=OkResponse)
async def close_room(request: Request, engine: GameEngine = HostEngine) -> OkResponse:
    await get_manager(request).close_room(engine, "closed_by_host")
    return OkResponse()


@router.put("/config", response_model=GameConfig)
async def update_config(config: GameConfig, engine: GameEngine = HostEngine) -> GameConfig:
    return await engine.update_config(config)


@router.put("/join-base-url", response_model=JoinUrlResponse)
async def set_join_base_url(body: JoinBaseUrlRequest, engine: GameEngine = HostEngine) -> JoinUrlResponse:
    base = normalize_join_base_url(body.join_base_url)
    join_url = await engine.set_join_base_url(base, build_join_url(base, engine.pin))
    return JoinUrlResponse(join_url=join_url)


@router.delete("/players/{player_id}", response_model=OkResponse)
async def kick(player_id: str, engine: GameEngine = HostEngine) -> OkResponse:
    await engine.kick(player_id)
    return OkResponse()


@router.post("/start", response_model=OkResponse)
async def start(body: StartRequest, engine: GameEngine = HostEngine) -> OkResponse:
    await engine.start(body.answerer_mode, body.fixed_player_id)
    return OkResponse()


@router.post("/next", response_model=OkResponse)
async def next_question(engine: GameEngine = HostEngine) -> OkResponse:
    await engine.next_question()
    return OkResponse()


@router.post("/skip", response_model=OkResponse)
async def skip(engine: GameEngine = HostEngine) -> OkResponse:
    await engine.skip()
    return OkResponse()


@router.post("/help", response_model=OkResponse)
async def host_help(engine: GameEngine = HostEngine) -> OkResponse:
    await engine.host_help()
    return OkResponse()


@router.post("/end", response_model=OkResponse)
async def end(engine: GameEngine = HostEngine) -> OkResponse:
    await engine.end()
    return OkResponse()


@router.post("/new-round", response_model=OkResponse)
async def new_round(
    body: NewRoundRequest | None = Body(default=None),
    engine: GameEngine = HostEngine,
) -> OkResponse:
    base = join_url = None
    if body is not None and body.join_base_url is not None:
        base = normalize_join_base_url(body.join_base_url)
        join_url = build_join_url(base, engine.pin)
    await engine.new_round(base, join_url)
    return OkResponse()
