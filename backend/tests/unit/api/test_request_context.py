import uuid

import structlog
from fastapi import FastAPI
from httpx import AsyncClient

from app.infrastructure.logging import get_request_context


async def test_trace_id_from_x_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["x-request-id"] == "abc-123"


async def test_trace_id_is_generated_when_missing(client: AsyncClient) -> None:
    response = await client.get("/health")

    trace_id = response.headers["x-request-id"]
    assert uuid.UUID(trace_id)


async def test_request_context_is_available_inside_handlers(
    app: FastAPI, client: AsyncClient
) -> None:
    @app.get("/context-probe")
    async def probe() -> dict[str, str | None]:
        context = get_request_context()
        return {"trace_id": context.trace_id, "actor_id": context.actor_id}

    response = await client.get("/context-probe", headers={"X-Request-ID": "trace-xyz"})

    assert response.json() == {"trace_id": "trace-xyz", "actor_id": None}


async def test_request_completed_log_has_structured_fields_and_no_personal_data(
    app: FastAPI, client: AsyncClient
) -> None:
    @app.get("/log-probe")
    async def probe(email: str) -> dict[str, str]:
        return {"ok": email}

    with structlog.testing.capture_logs() as logs:
        await client.get(
            "/log-probe",
            params={"email": "ana@quermed.com"},
            headers={"X-Request-ID": "trace-log"},
        )

    completed = [entry for entry in logs if entry["event"] == "request_completed"]
    assert len(completed) == 1
    entry = completed[0]
    assert entry["trace_id"] == "trace-log"
    assert entry["method"] == "GET"
    assert entry["path"] == "/log-probe"
    assert entry["status"] == 200
    assert isinstance(entry["duration_ms"], float)
    assert "ana@quermed.com" not in str(entry)
