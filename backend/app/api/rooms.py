"""Public room endpoints: create, lookup, status, join."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Query, Request

from app.errors import ApiError
from app.schemas import (
    ERR_INVALID_AVATAR,
    ERR_INVALID_NICKNAME,
    ERR_ROOM_NOT_FOUND,
    NICKNAME_MAX_LEN,
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRequest,
    JoinResponse,
    LookupResponse,
    RoomStatusResponse,
)
from app.tokens import get_manager, room_or_404

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.post("", response_model=CreateRoomResponse)
async def create_room(body: CreateRoomRequest, request: Request) -> CreateRoomResponse:
    engine = get_manager(request).create_room(body.config, body.join_base_url)
    return CreateRoomResponse(
        pin=engine.pin,
        picture_code=engine.picture_code,  # type: ignore[arg-type]
        host_token=engine.host_token,
        screen_token=engine.screen_token,
        join_url=engine.join_url,
    )


# Declared before `/{pin}` so it is not swallowed by the path parameter.
@router.get("/lookup", response_model=LookupResponse)
async def lookup(request: Request, pictures: str = Query(default="")) -> LookupResponse:
    engine = get_manager(request).lookup_pictures(pictures)
    if engine is None:
        raise ApiError(404, ERR_ROOM_NOT_FOUND, "no open room has this picture code")
    return LookupResponse(pin=engine.pin)


@router.get("/{pin}", response_model=RoomStatusResponse)
async def room_status(pin: str, request: Request) -> RoomStatusResponse:
    engine = room_or_404(request, pin)
    counts = Counter(p.avatar_id for p in engine.players.values())
    return RoomStatusResponse(phase=engine.phase, player_count=len(engine.players), avatar_counts=dict(counts))


@router.post("/{pin}/join", response_model=JoinResponse)
async def join(pin: str, body: JoinRequest, request: Request) -> JoinResponse:
    engine = room_or_404(request, pin)
    nickname = body.nickname.strip()
    if not 1 <= len(nickname) <= NICKNAME_MAX_LEN:
        raise ApiError(422, ERR_INVALID_NICKNAME, f"nickname must be 1-{NICKNAME_MAX_LEN} characters")
    if body.avatar_id not in request.app.state.avatar_ids:
        raise ApiError(422, ERR_INVALID_AVATAR, f"unknown avatar {body.avatar_id!r}")
    player = await engine.join(nickname, body.avatar_id)
    return JoinResponse(player_id=player.id, player_token=player.token)
