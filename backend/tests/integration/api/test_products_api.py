from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.users.roles import Role
from app.infrastructure.db.models import AuditLogModel, BrandDivisionModel
from app.infrastructure.db.seed import division_id, reference_id, run_seed
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
PRODUCTS = "/api/v1/products"
HADECO_ID: UUID = reference_id("brands", "hadeco")
VIASONIX_ID: UUID = reference_id("brands", "viasonix")
DOPPLERS_ID: UUID = reference_id("product_families", "dopplers")
CARROS_ID: UUID = reference_id("product_families", "carros")
VASCULAR_ID: UUID = division_id("vascular")


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


def payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "sku": "had-1000",
        "name": "Doppler ES-100",
        "brand_id": str(HADECO_ID),
        "family_id": str(DOPPLERS_ID),
        "kind": "equipment",
        "list_price": "1250.50",
    }
    body.update(overrides)
    return body


async def test_back_office_creates_with_defaults_and_cost_is_role_gated(
    client: AsyncClient, users: Users, session: AsyncSession
) -> None:
    back_office = await users.create(Role.BACK_OFFICE)
    manager = await users.create(Role.SALES_MANAGER)
    rep = await users.create(Role.SALES_REP)

    created = await client.post(
        PRODUCTS, json=payload(cost_price="800"), headers=users.headers(back_office)
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["sku"] == "HAD-1000"
    assert body["list_price"] == "1250.50" and body["unit"] == "ud"
    assert body["is_active"] is True and body["version"] == 1
    assert body["brand"] == {"id": str(HADECO_ID), "name": "Hadeco", "is_own": True}
    assert body["family"]["name"] == "Dopplers"
    assert body["family"]["division_id"] == str(VASCULAR_ID)
    assert "cost_price" not in body  # back office writes the cost but never reads it

    as_manager = await client.get(f"{PRODUCTS}/{body['id']}", headers=users.headers(manager))
    assert as_manager.json()["cost_price"] == "800.00"
    as_rep = await client.get(f"{PRODUCTS}/{body['id']}", headers=users.headers(rep))
    assert as_rep.status_code == 200 and "cost_price" not in as_rep.json()

    links = await session.execute(
        select(BrandDivisionModel).where(
            BrandDivisionModel.brand_id == HADECO_ID,
            BrandDivisionModel.division_id == VASCULAR_ID,
        )
    )
    assert links.scalar_one_or_none() is not None
    audit = await session.execute(
        select(AuditLogModel).where(AuditLogModel.action == "product.created")
    )
    row = audit.scalars().one()
    assert row.changes["cost_price"] == {"before": None, "after": "800.00"}


async def test_reps_and_managers_cannot_write(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)
    manager = await users.create(Role.SALES_MANAGER)

    for user in (rep, manager):
        response = await client.post(PRODUCTS, json=payload(), headers=users.headers(user))
        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"


async def test_duplicate_sku_reports_existing_product(client: AsyncClient, users: Users) -> None:
    admin = await users.create(Role.ADMIN)
    first = await client.post(PRODUCTS, json=payload(), headers=users.headers(admin))

    duplicate = await client.post(
        PRODUCTS, json=payload(sku=" HAD-1000 "), headers=users.headers(admin)
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "product_sku_exists"
    assert duplicate.json()["existing_product_id"] == first.json()["id"]


async def test_validation_errors(client: AsyncClient, users: Users) -> None:
    admin = await users.create(Role.ADMIN)

    negative = await client.post(
        PRODUCTS, json=payload(list_price="-1"), headers=users.headers(admin)
    )
    assert negative.status_code == 422
    unknown_brand = await client.post(
        PRODUCTS, json=payload(brand_id=str(uuid4())), headers=users.headers(admin)
    )
    assert unknown_brand.status_code == 422
    assert unknown_brand.json()["code"] == "brand_not_found"
    unknown_family = await client.post(
        PRODUCTS, json=payload(family_id=str(uuid4())), headers=users.headers(admin)
    )
    assert unknown_family.json()["code"] == "family_not_found"


async def test_patch_requires_if_match_and_audits(
    client: AsyncClient, users: Users, session: AsyncSession
) -> None:
    admin = await users.create(Role.ADMIN)
    created = (await client.post(PRODUCTS, json=payload(), headers=users.headers(admin))).json()
    url = f"{PRODUCTS}/{created['id']}"

    missing = await client.patch(url, json={"name": "X"}, headers=users.headers(admin))
    assert missing.status_code == 428

    updated = await client.patch(
        url,
        json={"list_price": "1300", "description": "Doppler bidireccional"},
        headers={**users.headers(admin), "If-Match": "1"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["list_price"] == "1300.00" and updated.json()["version"] == 2

    stale = await client.patch(
        url, json={"name": "Y"}, headers={**users.headers(admin), "If-Match": "1"}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"

    audit = await session.execute(
        select(AuditLogModel).where(AuditLogModel.action == "product.updated")
    )
    row = audit.scalars().one()
    assert row.changes["list_price"] == {"before": "1250.50", "after": "1300.00"}


async def test_deactivate_hides_from_reps_but_detail_stays_readable(
    client: AsyncClient, users: Users
) -> None:
    back_office = await users.create(Role.BACK_OFFICE)
    manager = await users.create(Role.SALES_MANAGER)
    rep = await users.create(Role.SALES_REP)
    created = (
        await client.post(PRODUCTS, json=payload(), headers=users.headers(back_office))
    ).json()
    url = f"{PRODUCTS}/{created['id']}"

    retired = await client.post(
        f"{url}/deactivate", headers={**users.headers(back_office), "If-Match": "1"}
    )
    assert retired.status_code == 200 and retired.json()["is_active"] is False
    again = await client.post(
        f"{url}/deactivate", headers={**users.headers(back_office), "If-Match": "2"}
    )
    assert again.status_code == 200 and again.json()["version"] == 2

    listed = await client.get(PRODUCTS, headers=users.headers(rep))
    assert listed.json()["total"] == 0
    detail = await client.get(url, headers=users.headers(rep))
    assert detail.status_code == 200 and detail.json()["is_active"] is False

    forbidden = await client.get(PRODUCTS, params={"is_active": "all"}, headers=users.headers(rep))
    assert forbidden.status_code == 403
    everything = await client.get(
        PRODUCTS, params={"is_active": "all"}, headers=users.headers(manager)
    )
    assert everything.json()["total"] == 1

    revived = await client.post(
        f"{url}/activate", headers={**users.headers(back_office), "If-Match": "2"}
    )
    assert revived.json()["is_active"] is True and revived.json()["version"] == 3

    denied = await client.post(f"{url}/deactivate", headers={**users.headers(rep), "If-Match": "3"})
    assert denied.status_code == 403


async def test_list_search_filters_sort_and_pagination(client: AsyncClient, users: Users) -> None:
    admin = await users.create(Role.ADMIN)
    rep = await users.create(Role.SALES_REP)
    headers = users.headers(admin)
    await client.post(PRODUCTS, json=payload(cost_price="600"), headers=headers)
    await client.post(
        PRODUCTS,
        json=payload(sku="HAD-1010", name="Sonda 8 MHz", kind="consumable"),
        headers=headers,
    )
    await client.post(
        PRODUCTS,
        json=payload(
            sku="VX-200", name="Doppler Falcon", brand_id=str(VIASONIX_ID), list_price="9000"
        ),
        headers=headers,
    )
    await client.post(
        PRODUCTS,
        json=payload(sku="CAR-1", name="Carro de anestesia", family_id=str(CARROS_ID)),
        headers=headers,
    )

    by_prefix = await client.get(PRODUCTS, params={"q": "had-10"}, headers=users.headers(rep))
    assert [i["sku"] for i in by_prefix.json()["items"]] == ["HAD-1000", "HAD-1010"]
    assert all("cost_price" not in i for i in by_prefix.json()["items"])

    by_name = await client.get(PRODUCTS, params={"q": "doppler"}, headers=headers)
    assert [i["name"] for i in by_name.json()["items"]] == ["Doppler ES-100", "Doppler Falcon"]
    assert by_name.json()["items"][0]["cost_price"] == "600.00"

    vascular = await client.get(PRODUCTS, params={"division_id": str(VASCULAR_ID)}, headers=headers)
    assert vascular.json()["total"] == 3
    kind = await client.get(PRODUCTS, params={"kind": "consumable"}, headers=headers)
    assert [i["sku"] for i in kind.json()["items"]] == ["HAD-1010"]
    own = await client.get(PRODUCTS, params={"own": "false"}, headers=headers)
    assert own.json()["total"] == 0

    priciest = await client.get(PRODUCTS, params={"sort": "-list_price"}, headers=headers)
    assert priciest.json()["items"][0]["sku"] == "VX-200"
    as_rep = await client.get(PRODUCTS, params={"sort": "cost_price"}, headers=users.headers(rep))
    assert as_rep.status_code == 422
    by_cost = await client.get(PRODUCTS, params={"sort": "cost_price"}, headers=headers)
    assert by_cost.json()["items"][0]["sku"] == "HAD-1000"

    page = await client.get(PRODUCTS, params={"page_size": 2, "page": 2}, headers=headers)
    assert page.json()["page_size"] == 2 and len(page.json()["items"]) == 2
    default_page = await client.get(PRODUCTS, headers=headers)
    assert default_page.json()["page_size"] == 25
    too_big = await client.get(PRODUCTS, params={"page_size": 101}, headers=headers)
    assert too_big.status_code == 422

    missing = await client.get(f"{PRODUCTS}/{uuid4()}", headers=headers)
    assert missing.status_code == 404
    anonymous = await client.get(PRODUCTS)
    assert anonymous.status_code == 401
