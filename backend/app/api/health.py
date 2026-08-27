"""Liveness and readiness endpoints (outside /api/v1, unauthenticated)."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

ReadinessProbe = Callable[[], Awaitable[bool]]

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe (checks the database)")
async def ready(request: Request) -> JSONResponse:
    probe: ReadinessProbe = request.app.state.readiness_probe
    if await probe():
        return JSONResponse({"status": "ok", "database": "available"})
    return JSONResponse({"status": "degraded", "database": "unavailable"}, status_code=503)
