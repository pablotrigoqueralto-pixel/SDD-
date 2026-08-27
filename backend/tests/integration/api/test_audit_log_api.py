import pytest
from httpx import AsyncClient

from app.domain.users.entities import User
from app.domain.users.roles import Role
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

AUDIT = "/api/v1/audit-log"


async def test_admin_reads_audit_trail_of_a_user(
    client: AsyncClient, admin: User, admin_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/users",
        json={
            "email": "nueva@quermed.com",
            "full_name": "Nueva",
            "role": "sales_rep",
            "password": "correct-horse-battery",
        },
        headers=admin_headers,
    )
    user_id = created.json()["id"]
    await client.patch(
        f"/api/v1/users/{user_id}",
        json={"full_name": "Nueva Renombrada"},
        headers={**admin_headers, "If-Match": "1"},
    )

    response = await client.get(
        AUDIT, params={"entity_type": "user", "entity_id": user_id}, headers=admin_headers
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["action"] for item in items] == ["user.updated", "user.created"]
    assert items[0]["actor_id"] == str(admin.id)
    assert items[0]["actor_name"] == admin.full_name
    assert items[0]["changes"]["full_name"] == {"before": "Nueva", "after": "Nueva Renombrada"}
    assert items[1]["changes"]["password_hash"] == {"before": "[redacted]", "after": "[redacted]"}
    assert items[0]["trace_id"]


async def test_audit_filters_by_action_and_actor(
    client: AsyncClient, admin: User, admin_headers: dict[str, str]
) -> None:
    await client.post(
        "/api/v1/territories", json={"name": "Sur", "provinces": ["41"]}, headers=admin_headers
    )

    by_action = await client.get(
        AUDIT, params={"action": "territory.created"}, headers=admin_headers
    )
    by_actor = await client.get(AUDIT, params={"actor_id": str(admin.id)}, headers=admin_headers)

    assert by_action.json()["total"] == 1
    assert by_actor.json()["total"] >= 1
    assert all(item["actor_id"] == str(admin.id) for item in by_actor.json()["items"])


async def test_only_admin_reads_audit_log(client: AsyncClient, users: Users) -> None:
    manager = await users.create(Role.SALES_MANAGER)

    response = await client.get(AUDIT, headers=users.headers(manager))

    assert response.status_code == 403
