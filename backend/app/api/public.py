"""Public misc endpoints: avatars, network hints, health."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.network import suggested_ips
from app.schemas import Avatar, HealthResponse, NetworkResponse

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/avatars", response_model=list[Avatar])
async def avatars(request: Request) -> list[Avatar]:
    return list(request.app.state.avatars)


@router.get("/network", response_model=NetworkResponse)
async def network(request: Request) -> NetworkResponse:
    settings = request.app.state.settings
    port = settings.app_port
    if port is None:
        server = request.scope.get("server")
        port = server[1] if server and server[1] else (request.url.port or 80)
    return NetworkResponse(ips=suggested_ips(settings.lan_ip), port=int(port))


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()
