"""Every endpoint x every role: proves the role gates from design D6."""

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

ALL = frozenset(Role)
STAFF = frozenset({Role.ADMIN, Role.SALES_MANAGER, Role.BACK_OFFICE})
ADMIN_ONLY = frozenset({Role.ADMIN})


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: Callable[[User, Territory], str]
    allowed: frozenset[Role]
    body: Callable[[User, Territory], dict[str, object] | None] = lambda _u, _t: None
    if_match: bool = False


ENDPOINTS: list[Endpoint] = [
    Endpoint("GET", lambda u, t: "/api/v1/me", ALL),
    Endpoint("PATCH", lambda u, t: "/api/v1/me", ALL, lambda u, t: {"full_name": "N"}, True),
    Endpoint("GET", lambda u, t: "/api/v1/users", STAFF),
    Endpoint(
        "POST",
        lambda u, t: "/api/v1/users",
        ADMIN_ONLY,
        lambda u, t: {
            "email": "z@quermed.com",
            "full_name": "Z",
            "role": "sales_rep",
            "password": "correct-horse-battery",
        },
    ),
    Endpoint("GET", lambda u, t: f"/api/v1/users/{u.id}", STAFF),
    Endpoint(
        "PATCH",
        lambda u, t: f"/api/v1/users/{u.id}",
        ADMIN_ONLY,
        lambda u, t: {"full_name": "N"},
        True,
    ),
    Endpoint("GET", lambda u, t: "/api/v1/territories", STAFF),
    Endpoint(
        "POST",
        lambda u, t: "/api/v1/territories",
        ADMIN_ONLY,
        lambda u, t: {"name": "Norte", "provinces": ["48"]},
    ),
    Endpoint("GET", lambda u, t: f"/api/v1/territories/{t.id}", STAFF),
    Endpoint(
        "PATCH",
        lambda u, t: f"/api/v1/territories/{t.id}",
        ADMIN_ONLY,
        lambda u, t: {"name": "Centro 2"},
        True,
    ),
    Endpoint("GET", lambda u, t: "/api/v1/divisions", ALL),
    Endpoint("GET", lambda u, t: "/api/v1/audit-log", ADMIN_ONLY),
]


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda e: f"{e.method}")
async def test_role_gate(
    client: AsyncClient, users: Users, centro: Territory, role: Role, endpoint: Endpoint
) -> None:
    other_admin = await users.create(Role.ADMIN, email="other-admin@quermed.com")
    actor = await users.create(role, email=f"{role.value}-actor@quermed.com")
    headers = users.headers(actor)
    if endpoint.if_match:
        headers["If-Match"] = "1"
    target_user = other_admin if endpoint.method == "PATCH" else actor

    response = await client.request(
        endpoint.method,
        endpoint.path(target_user, centro),
        json=endpoint.body(target_user, centro),
        headers=headers,
    )

    if role in endpoint.allowed:
        assert response.status_code in {200, 201}, response.text
    else:
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "forbidden"


async def test_anonymous_is_unauthenticated_everywhere(client: AsyncClient) -> None:
    for static_path in (
        "/api/v1/me",
        "/api/v1/users",
        "/api/v1/territories",
        "/api/v1/divisions",
        "/api/v1/audit-log",
    ):
        response = await client.get(static_path)
        assert response.status_code == 401
        assert response.json()["code"] == "unauthenticated"
