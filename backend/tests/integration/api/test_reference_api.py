from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.users.roles import Role
from app.infrastructure.db.seed import DIVISIONS, run_seed
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

REFERENCE = "/api/v1/reference-data"
VASCULAR_ID = next(d.id for d in DIVISIONS if d.code == "vascular")


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def pipelines_by_code(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/api/v1/pipelines", headers=headers)
    assert response.status_code == 200
    return {p["code"]: p for p in response.json()}


async def test_bundle_for_sales_rep_with_etag(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)

    response = await client.get(REFERENCE, headers=users.headers(rep))

    assert response.status_code == 200
    body = response.json()
    assert len(body["account_types"]) == 6
    assert len(body["activity_types"]) == 6
    assert len(body["divisions"]) == 7
    assert len(body["brands"]) >= 13
    assert len(body["loss_reasons"]) >= 6
    assert [p["code"] for p in body["pipelines"]] == ["equipment", "consumables"]
    equipment = body["pipelines"][0]
    assert [s["sort_order"] for s in equipment["stages"]] == list(
        range(1, len(equipment["stages"]) + 1)
    )
    etag = response.headers["etag"]
    assert etag.startswith('"')

    cached = await client.get(REFERENCE, headers={**users.headers(rep), "If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""


async def test_bundle_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(REFERENCE)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


async def test_per_master_reads_and_brand_filters(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)
    headers = users.headers(rep)

    account_types = await client.get("/api/v1/account-types", headers=headers)
    activity_types = await client.get("/api/v1/activity-types", headers=headers)
    own = await client.get("/api/v1/brands", params={"is_own": "true"}, headers=headers)
    prefix = await client.get("/api/v1/brands", params={"q": "ha"}, headers=headers)
    reasons = await client.get("/api/v1/loss-reasons", headers=headers)

    assert [t["code"] for t in account_types.json()][:2] == ["ivf_clinic", "public_hospital"]
    assert account_types.json()[1]["buys_via_tender"] is True
    assert activity_types.json()[-1] == {
        **activity_types.json()[-1],
        "code": "note",
        "counts_as_contact": False,
        "icon": "sticky-note",
    }
    assert all(b["is_own"] for b in own.json()) and len(own.json()) >= 13
    assert [b["name"] for b in prefix.json()] == ["Hadeco"]
    assert [r["code"] for r in reasons.json() if r["requires_brand"]] == ["competitor"]


async def test_admin_creates_and_updates_brand(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/v1/brands",
        json={"name": "Cook Medical", "is_own": False, "division_ids": [str(VASCULAR_ID)]},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["code"] == "cook_medical"
    assert body["is_own"] is False
    assert body["division_ids"] == [str(VASCULAR_ID)]

    duplicate = await client.post(
        "/api/v1/brands", json={"name": "cook medical", "is_own": False}, headers=admin_headers
    )
    unknown = await client.post(
        "/api/v1/brands",
        json={"name": "Other", "is_own": False, "division_ids": [str(uuid4())]},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "brand_name_already_exists"
    assert unknown.status_code == 422 and unknown.json()["errors"][0]["field"] == "division_ids"

    missing_version = await client.patch(
        f"/api/v1/brands/{body['id']}", json={"name": "Cook"}, headers=admin_headers
    )
    updated = await client.patch(
        f"/api/v1/brands/{body['id']}",
        json={"name": "Cook Medical Europe", "is_active": False},
        headers={**admin_headers, "If-Match": '"1"'},
    )
    stale = await client.patch(
        f"/api/v1/brands/{body['id']}",
        json={"name": "Again"},
        headers={**admin_headers, "If-Match": '"1"'},
    )
    assert missing_version.status_code == 428
    assert updated.status_code == 200
    assert updated.json()["name"] == "Cook Medical Europe"
    assert updated.json()["is_active"] is False
    assert updated.json()["version"] == 2
    assert stale.status_code == 409

    audit = await client.get(
        "/api/v1/audit-log",
        params={"entity_type": "brand", "entity_id": body["id"]},
        headers=admin_headers,
    )
    assert [e["action"] for e in audit.json()["items"]] == [
        "brand.deactivated",
        "brand.updated",
        "brand.created",
    ]


async def test_non_admins_cannot_write_reference_data(client: AsyncClient, users: Users) -> None:
    manager = await users.create(Role.SALES_MANAGER)
    headers = users.headers(manager)

    brand = await client.post("/api/v1/brands", json={"name": "X", "is_own": True}, headers=headers)
    reason = await client.post("/api/v1/loss-reasons", json={"name": "X"}, headers=headers)

    assert brand.status_code == 403
    assert reason.status_code == 403


async def test_loss_reason_administration(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    before = (await client.get("/api/v1/loss-reasons", headers=admin_headers)).json()

    created = await client.post(
        "/api/v1/loss-reasons", json={"name": "Cambio de proveedor"}, headers=admin_headers
    )
    duplicate = await client.post(
        "/api/v1/loss-reasons", json={"name": "precio"}, headers=admin_headers
    )

    assert created.status_code == 201
    assert created.json()["code"] == "cambio_de_proveedor"
    assert created.json()["sort_order"] > max(r["sort_order"] for r in before)
    assert not created.json()["requires_brand"] and not created.json()["requires_note"]
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "loss_reason_name_already_exists"

    updated = await client.patch(
        f"/api/v1/loss-reasons/{created.json()['id']}",
        json={"name": "Cambio de distribuidor", "is_active": False},
        headers={**admin_headers, "If-Match": "1"},
    )
    assert updated.status_code == 200
    assert updated.json()["name_es"] == "Cambio de distribuidor"
    assert updated.json()["is_active"] is False


async def test_pipeline_administration(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    pipelines = await pipelines_by_code(client, admin_headers)
    equipment = pipelines["equipment"]
    stages: dict[str, Any] = {s["code"]: s for s in equipment["stages"]}
    demo = stages["demo"]
    base = f"/api/v1/pipelines/{equipment['id']}"

    renamed = await client.patch(
        base,
        json={"name": "Equipamiento"},
        headers={**admin_headers, "If-Match": str(equipment["version"])},
    )
    assert renamed.status_code == 200 and renamed.json()["name_es"] == "Equipamiento"

    tuned = await client.patch(
        f"{base}/stages/{demo['id']}",
        json={"probability": 40},
        headers={**admin_headers, "If-Match": str(demo["version"])},
    )
    assert tuned.status_code == 200
    tuned_demo = next(s for s in tuned.json()["stages"] if s["code"] == "demo")
    assert tuned_demo["probability"] == 40 and tuned_demo["version"] == demo["version"] + 1

    out_of_range = await client.patch(
        f"{base}/stages/{demo['id']}",
        json={"probability": 120},
        headers={**admin_headers, "If-Match": str(tuned_demo["version"])},
    )
    flag = await client.patch(
        f"{base}/stages/{demo['id']}",
        json={"is_won": True},
        headers={**admin_headers, "If-Match": str(tuned_demo["version"])},
    )
    stale = await client.patch(
        f"{base}/stages/{demo['id']}",
        json={"name": "X"},
        headers={**admin_headers, "If-Match": str(demo["version"])},
    )
    assert out_of_range.status_code == 422
    assert out_of_range.json()["code"] == "stage_probability_invalid"
    assert flag.status_code == 400 and flag.json()["code"] == "stage_flag_immutable"
    assert stale.status_code == 409

    # Deactivate every open stage but one, then the last one must be refused.
    open_codes = ["contact", "quote", "negotiation"]
    for code in open_codes:
        stage = stages[code]
        response = await client.patch(
            f"{base}/stages/{stage['id']}",
            json={"is_active": False},
            headers={**admin_headers, "If-Match": str(stage["version"])},
        )
        assert response.status_code == 200, response.text
    last = await client.patch(
        f"{base}/stages/{demo['id']}",
        json={"is_active": False},
        headers={**admin_headers, "If-Match": str(tuned_demo["version"])},
    )
    assert last.status_code == 400 and last.json()["code"] == "last_active_stage"

    current = (await client.get(base, headers=admin_headers)).json()
    order = [s["id"] for s in current["stages"]]
    swapped = [order[1], order[0], *order[2:]]
    reordered = await client.put(
        f"{base}/stages/order",
        json={"stage_ids": swapped},
        headers={**admin_headers, "If-Match": str(current["version"])},
    )
    assert reordered.status_code == 200, reordered.text
    assert [s["id"] for s in reordered.json()["stages"]] == swapped
    assert reordered.json()["version"] == current["version"] + 1

    invalid = await client.put(
        f"{base}/stages/order",
        json={"stage_ids": swapped[:-1]},
        headers={**admin_headers, "If-Match": str(reordered.json()["version"])},
    )
    stale_order = await client.put(
        f"{base}/stages/order",
        json={"stage_ids": order},
        headers={**admin_headers, "If-Match": str(current["version"])},
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "stage_order_invalid"
    assert stale_order.status_code == 409

    audit = await client.get(
        "/api/v1/audit-log",
        params={"entity_type": "pipeline", "entity_id": equipment["id"]},
        headers=admin_headers,
    )
    actions = [e["action"] for e in audit.json()["items"]]
    assert actions[0] == "pipeline_stages.reordered"
    assert "pipeline.updated" in actions
    reorder_event = audit.json()["items"][0]
    assert reorder_event["changes"]["order"]["after"] == swapped
