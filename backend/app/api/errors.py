"""RFC 7807 problem+json exception handlers."""

from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.shared.errors import DomainError, FieldError
from app.infrastructure.logging import REQUEST_ID_HEADER, get_logger, get_request_context

PROBLEM_TYPE_BASE = "https://crm.quermed.com/problems"
PROBLEM_MEDIA_TYPE = "application/problem+json"

logger = get_logger("api.errors")


def trace_id_for(request: Request) -> str | None:
    """Trace id from the request state (survives the outermost error middleware)."""
    from_state = getattr(request.state, "trace_id", None)
    return from_state if isinstance(from_state, str) else get_request_context().trace_id


def problem_response(
    *,
    trace_id: str | None,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
    extensions: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_BASE}/{code.replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "trace_id": trace_id,
    }
    if errors:
        body["errors"] = errors
    if extensions:
        body.update(extensions)
    response_headers = dict(headers or {})
    if trace_id:
        response_headers.setdefault(REQUEST_ID_HEADER, trace_id)
    return JSONResponse(
        status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE, headers=response_headers
    )


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(DomainError, exc)
    return problem_response(
        trace_id=trace_id_for(request),
        status=error.status,
        code=error.code,
        title=error.title,
        detail=error.detail,
        errors=error.errors or None,
        extensions=error.extensions or None,
    )


def _field_path(location: tuple[int | str, ...]) -> str:
    # Drop the container ("body", "query", "path") and join nested keys with dots.
    parts = [str(part) for part in location[1:]] or [str(part) for part in location]
    return ".".join(parts)


async def handle_request_validation_error(request: Request, exc: Exception) -> JSONResponse:
    validation_error = cast(RequestValidationError, exc)
    errors: list[FieldError] = [
        {
            "field": _field_path(tuple(error["loc"])),
            "message": error["msg"],
            "code": error["type"],
        }
        for error in validation_error.errors()
    ]
    return problem_response(
        trace_id=trace_id_for(request),
        status=422,
        code="validation_error",
        title="Validation error",
        detail="One or more fields are invalid.",
        errors=errors,
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    http_error = cast(StarletteHTTPException, exc)
    code = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}
    return problem_response(
        trace_id=trace_id_for(request),
        status=http_error.status_code,
        code=code.get(http_error.status_code, "http_error"),
        title=str(http_error.detail),
        detail=str(http_error.detail),
        headers=dict(http_error.headers) if http_error.headers else None,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    trace_id = trace_id_for(request)
    logger.error("unhandled_exception", trace_id=trace_id, exc_info=exc)
    return problem_response(
        trace_id=trace_id,
        status=500,
        code="internal_error",
        title="Internal server error",
        detail="An unexpected error occurred. Please retry or contact support with the trace id.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
