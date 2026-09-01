import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.users.roles import Role
from app.infrastructure.db.seed import PRODUCT_FAMILIES, division_id, run_seed
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
FAMILIES = "/api/v1/product-families"
REFERENCE = "/api/v1/reference-data"


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def test_families_are_listed_and_bundled_in_division_order(
    client: AsyncClient, users: Users
) -> None:
    rep = await users.create(Role.SALES_REP)

    listed = await client.get(FAMILIES, headers=users.headers(rep))
    bundle = await client.get(REFERENCE, headers=users.headers(rep))

    assert listed.status_code == 200
    codes = [f["code"] for f in listed.json()]
    assert codes[:2] == ["medios_cultivo", "micromanipulacion"]
    assert codes.index("dopplers") < codes.index("carros")
    assert len(bundle.json()["product_families"]) == len(PRODUCT_FAMILIES) >= 12
    assert bundle.json()["product_families"][0]["division_id"] == str(
        division_id("assisted_reproduction")
    )


async def test_admin_manages_families_and_etag_changes(
    client: AsyncClient, users: Users, admin_headers: dict[str, str]
) -> None:
    back_office = await users.create(Role.BACK_OFFICE)
    before = await client.get(REFERENCE, headers=admin_headers)
    etag = before.headers["etag"]

    created = await client.post(
        FAMILIES,
        json={"name": "Láser", "division_id": str(division_id("vascular"))},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["code"] == "laser"
    assert created.json()["sort_order"] == 30

    assert created.json()["outcome"] == "created"

    # Same name, same division: the existing family is reused.
    reused = await client.post(
        FAMILIES,
        json={"name": "dopplers", "division_id": str(division_id("vascular"))},
        headers=admin_headers,
    )
    assert reused.status_code == 201
    assert reused.json()["outcome"] == "reused"
    assert reused.json()["code"] == "dopplers"

    # A family code is unique catalogue-wide, so the same name under another division is
    # still refused: handing back the vascular family would misfile neurology products.
    elsewhere = await client.post(
        FAMILIES,
        json={"name": "Dopplers", "division_id": str(division_id("neurology"))},
        headers=admin_headers,
    )
    assert elsewhere.status_code == 409
    assert elsewhere.json()["code"] == "product_family_exists"

    renamed = await client.patch(
        f"{FAMILIES}/{created.json()['id']}",
        json={"name": "Láser quirúrgico", "sort_order": 5, "is_active": False},
        headers={**admin_headers, "If-Match": "1"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name_es"] == "Láser quirúrgico"
    assert renamed.json()["sort_order"] == 5 and renamed.json()["is_active"] is False

    immutable = await client.patch(
        f"{FAMILIES}/{created.json()['id']}",
        json={"division_id": str(division_id("neurology"))},
        headers={**admin_headers, "If-Match": "2"},
    )
    assert immutable.status_code == 422

    forbidden = await client.patch(
        f"{FAMILIES}/{created.json()['id']}",
        json={"name": "X"},
        headers={**users.headers(back_office), "If-Match": "2"},
    )
    assert forbidden.status_code == 403

    after = await client.get(REFERENCE, headers={**admin_headers, "If-None-Match": etag})
    assert after.status_code == 200
    assert after.headers["etag"] != etag
    assert any(f["code"] == "laser" for f in after.json()["product_families"])
