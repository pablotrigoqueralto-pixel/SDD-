"""Rate limiting (slowapi, in-memory storage — single instance in the MVP)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.errors import problem_response, trace_id_for

DEFAULT_AUTH_RATE_LIMIT = "10/minute"
DEFAULT_RATE_LIMIT = "300/minute"

limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE_LIMIT])

_auth_rate_limit = DEFAULT_AUTH_RATE_LIMIT


def auth_rate_limit() -> str:
    """Dynamic limit provider for /auth/* (slowapi calls it per request)."""
    return _auth_rate_limit


async def handle_rate_limit_exceeded(request: Request, exc: Exception) -> JSONResponse:
    retry_after = "60"
    if isinstance(exc, RateLimitExceeded) and exc.limit is not None:
        retry_after = str(exc.limit.limit.get_expiry())
    return problem_response(
        trace_id=trace_id_for(request),
        status=429,
        code="rate_limited",
        title="Too many requests",
        detail="Rate limit exceeded. Retry later.",
        headers={"Retry-After": retry_after},
    )


def register_rate_limiting(app: FastAPI) -> None:
    global _auth_rate_limit
    _auth_rate_limit = app.state.settings.auth_rate_limit
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, handle_rate_limit_exceeded)
