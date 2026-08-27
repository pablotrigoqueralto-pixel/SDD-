"""Structured logging (structlog) and the per-request context (trace id, actor)."""

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, replace

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "x-request-id"


@dataclass(frozen=True)
class RequestContext:
    trace_id: str | None = None
    actor_id: str | None = None


_request_context: ContextVar[RequestContext] = ContextVar("request_context")
_EMPTY_CONTEXT = RequestContext()


def get_request_context() -> RequestContext:
    return _request_context.get(_EMPTY_CONTEXT)


def set_actor_id(actor_id: str | None) -> None:
    """Bind the authenticated user id to the current request context."""
    _request_context.set(replace(get_request_context(), actor_id=actor_id))
    structlog.contextvars.bind_contextvars(user_id=actor_id)


def configure_logging(level: str, *, json_output: bool) -> None:
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


class RequestContextMiddleware:
    """Pure ASGI middleware: trace id in/out, request context, request log line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = get_logger("request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1"): value.decode("latin-1") for key, value in scope["headers"]
        }
        trace_id = headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        scope.setdefault("state", {})["trace_id"] = trace_id
        token = _request_context.set(RequestContext(trace_id=trace_id))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_trace_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((REQUEST_ID_HEADER.encode(), trace_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace_id)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            self.logger.info(
                "request_completed",
                trace_id=trace_id,
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=duration_ms,
            )
            _request_context.reset(token)
            structlog.contextvars.clear_contextvars()
