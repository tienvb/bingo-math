"""FastAPI app: routers, `/ws`, `/avatars`, optional static SPA, error format."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import host, public, rooms
from app.avatars import load_avatars
from app.errors import ApiError
from app.game.engine import Timings
from app.rooms import RoomManager
from app.schemas import (
    ERR_INVALID_AVATAR,
    ERR_INVALID_CONFIG,
    ERR_INVALID_JOIN_URL,
    ERR_INVALID_REQUEST,
    ERR_METHOD_NOT_ALLOWED,
    ERR_NOT_FOUND,
    ERR_INVALID_NICKNAME,
    ERR_FIXED_PLAYER_REQUIRED,
)
from app.settings import BACKEND_DIR, Settings, get_settings
from app.ws.handler import websocket_endpoint

log = logging.getLogger("bingo")

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
SPA_ROUTES = ["/", "/create", "/host/{rest:path}", "/screen/{rest:path}", "/play", "/play/{rest:path}"]

_CONFIG_FIELDS = {"config", "operations", "timer_seconds", "max_wrong", "reveal_seconds", "draw_only_card_numbers",
                  "max_number", "next_mode"}
# Body field -> error code when Pydantic rejects the request body.
_FIELD_CODES = {
    "join_base_url": ERR_INVALID_JOIN_URL,
    "nickname": ERR_INVALID_NICKNAME,
    "avatar_id": ERR_INVALID_AVATAR,
    "fixed_player_id": ERR_FIXED_PLAYER_REQUIRED,
}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def _validation_code(request: Request, errors: list[Any]) -> str:
    for err in errors:
        for part in err.get("loc", ()):
            if part in _CONFIG_FIELDS:
                return ERR_INVALID_CONFIG
            if part in _FIELD_CODES:
                return _FIELD_CODES[part]
    # PUT /config: the body *is* a GameConfig, so model-level errors have no field name.
    if request.method == "PUT" and request.url.path.endswith("/config"):
        return ERR_INVALID_CONFIG
    return ERR_INVALID_REQUEST


def _setup_logging() -> None:
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
    log.setLevel(logging.INFO)


def create_app(
    settings: Settings | None = None,
    *,
    manager: RoomManager | None = None,
    timings: Timings | None = None,
    cleanup_interval: float = 60.0,
) -> FastAPI:
    settings = settings or get_settings()
    _setup_logging()
    avatars = load_avatars(settings.avatars_dir)
    room_manager = manager or RoomManager(settings, timings=timings or Timings())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        room_manager.start_cleanup(cleanup_interval)
        yield
        await room_manager.shutdown()

    app = FastAPI(title="Bingo Math", lifespan=lifespan)
    app.state.settings = settings
    app.state.rooms = room_manager
    app.state.avatars = avatars
    app.state.avatar_ids = {a.id for a in avatars}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = list(exc.errors())
        msg = "; ".join(f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg')}" for e in errors)
        return _error(422, _validation_code(request, errors), msg or "invalid request")

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: ERR_NOT_FOUND, 405: ERR_METHOD_NOT_ALLOWED}.get(exc.status_code, ERR_INVALID_REQUEST)
        return _error(exc.status_code, code, str(exc.detail))

    app.include_router(rooms.router)
    app.include_router(host.router)
    app.include_router(public.router)
    app.add_api_websocket_route("/ws", websocket_endpoint)
    app.mount("/avatars", StaticFiles(directory=settings.avatars_dir), name="avatars")

    static_dir = settings.static_dir
    if static_dir is not None:
        static_dir = static_dir if static_dir.is_absolute() else (BACKEND_DIR / static_dir)
        _mount_spa(app, static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    index = static_dir / "index.html"
    if not index.is_file():
        log.warning("STATIC_DIR %s has no index.html, not serving the frontend", static_dir)
        return

    async def spa_index() -> FileResponse:
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    for route in SPA_ROUTES:
        app.add_api_route(route, spa_index, methods=["GET"], include_in_schema=False)
    app.mount("/", StaticFiles(directory=static_dir), name="static")
    log.info("serving frontend from %s", static_dir)


app = create_app()
