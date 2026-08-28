"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.api.errors import register_exception_handlers
from app.api.health import ReadinessProbe
from app.api.health import router as health_router
from app.api.middleware import SecurityHeadersMiddleware
from app.api.rate_limit import register_rate_limiting
from app.api.v1.router import api_v1_router
from app.infrastructure.logging import RequestContextMiddleware, configure_logging
from app.infrastructure.security.jwt import AccessTokenCodec
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.settings import Settings

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run the at-risk scan at start and on an interval (design D6); 0 disables it."""
    settings: Settings = app.state.settings
    task: asyncio.Task[None] | None = None
    if settings.at_risk_scan_interval_hours > 0:
        from app.tooling.at_risk_scan import run_once

        async def loop() -> None:
            while True:
                try:
                    await run_once()
                except Exception:  # pragma: no cover - the loop must survive db hiccups
                    configure_logging(settings.log_level, json_output=not settings.is_dev)
                await asyncio.sleep(settings.at_risk_scan_interval_hours * 3600)

        task = asyncio.create_task(loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


def create_app(settings: Settings, *, readiness_probe: ReadinessProbe | None = None) -> FastAPI:
    configure_logging(settings.log_level, json_output=not settings.is_dev)

    app = FastAPI(
        lifespan=_lifespan,
        title="Quermed CRM API",
        version="1.0.0",
        openapi_url=f"{API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.codec = AccessTokenCodec(settings.jwt_secret, settings.access_token_ttl_seconds)
    app.state.hasher = Argon2PasswordHasher()

    if readiness_probe is None:
        from app.infrastructure.db.session import database_is_reachable

        readiness_probe = database_is_reachable
    app.state.readiness_probe = readiness_probe

    # Middleware order: outermost first. Security headers and trace id wrap everything,
    # CORS must run before routing so preflight requests get answered.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin for origin in settings.cors_origins if "*" not in origin],
        allow_origin_regex=_origin_regex(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "If-Match", "X-Request-ID"],
        expose_headers=["X-Request-ID", "ETag"],
    )

    register_exception_handlers(app)
    register_rate_limiting(app)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=API_V1_PREFIX)
    return app


def _origin_regex(origins: list[str]) -> str | None:
    """Turn wildcard origins such as http://*.local:5173 into a single anchored regex."""
    import re

    patterns = [
        "^" + re.escape(origin).replace(r"\*", r"[a-zA-Z0-9-]+") + "$"
        for origin in origins
        if "*" in origin
    ]
    return "|".join(patterns) if patterns else None
