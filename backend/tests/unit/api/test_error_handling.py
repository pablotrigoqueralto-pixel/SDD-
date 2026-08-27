from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel

from app.domain.shared.errors import (
    ConcurrentModificationError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)

PROBLEM_JSON = "application/problem+json"


def register_probe_routes(app: FastAPI) -> None:
    class Payload(BaseModel):
        name: str
        age: int

    @app.get("/probe/not-found")
    async def not_found() -> None:
        raise NotFoundError("Territory not found")

    @app.get("/probe/forbidden")
    async def forbidden() -> None:
        raise PermissionDeniedError()

    @app.get("/probe/conflict")
    async def conflict() -> None:
        raise ConcurrentModificationError()

    @app.get("/probe/domain-rule")
    async def domain_rule() -> None:
        raise DomainError("Cannot demote yourself", code="cannot_demote_self")

    @app.get("/probe/field-errors")
    async def field_errors() -> None:
        raise ValidationFailedError(
            [{"field": "new_password", "message": "Too short", "code": "password_too_short"}]
        )

    @app.post("/probe/validate")
    async def validate(payload: Payload) -> Payload:
        return payload

    @app.get("/probe/boom")
    async def boom() -> None:
        msg = "secret database password leaked"
        raise RuntimeError(msg)


async def test_domain_error_maps_to_problem_json(app: FastAPI, client: AsyncClient) -> None:
    register_probe_routes(app)

    response = await client.get("/probe/not-found", headers={"X-Request-ID": "t1"})

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    body = response.json()
    assert body["code"] == "not_found"
    assert body["status"] == 404
    assert body["title"] == "Not found"
    assert body["detail"] == "Territory not found"
    assert body["trace_id"] == "t1"
    assert body["type"].endswith("/problems/not-found")


async def test_permission_and_conflict_status_codes(app: FastAPI, client: AsyncClient) -> None:
    register_probe_routes(app)

    forbidden = await client.get("/probe/forbidden")
    conflict = await client.get("/probe/conflict")
    rule = await client.get("/probe/domain-rule")

    assert (forbidden.status_code, forbidden.json()["code"]) == (403, "forbidden")
    assert (conflict.status_code, conflict.json()["code"]) == (409, "conflict")
    assert (rule.status_code, rule.json()["code"]) == (400, "cannot_demote_self")


async def test_domain_validation_error_carries_field_errors(
    app: FastAPI, client: AsyncClient
) -> None:
    register_probe_routes(app)

    response = await client.get("/probe/field-errors")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"] == [
        {"field": "new_password", "message": "Too short", "code": "password_too_short"}
    ]


async def test_request_validation_error_lists_each_invalid_field(
    app: FastAPI, client: AsyncClient
) -> None:
    register_probe_routes(app)

    response = await client.post("/probe/validate", json={"age": "not-a-number"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    fields = {error["field"] for error in body["errors"]}
    assert fields == {"name", "age"}
    for error in body["errors"]:
        assert error["message"]
        assert error["code"]


async def test_unhandled_exception_returns_500_without_details(
    app: FastAPI, client: AsyncClient
) -> None:
    register_probe_routes(app)

    response = await client.get("/probe/boom", headers={"X-Request-ID": "t500"})

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert body["trace_id"] == "t500"
    assert "secret" not in response.text
    assert "Traceback" not in response.text
