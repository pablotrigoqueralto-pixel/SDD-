import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AuditLogModel
from app.infrastructure.db.seed import reference_id, run_seed
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

PRODUCTS_IMPORT = "/api/v1/products/import"
ACCOUNTS_IMPORT = "/api/v1/accounts/import"

PRODUCT_CSV = (
    "Código;Nombre;Marca;Familia;Tipo;PVP\n"
    "IMP-API-1;Doppler importado;Hadeco;Dopplers;equipo;1.250,50\n"
    "IMP-API-2;Sin marca;NoExiste;Dopplers;equipo;10\n"
)


def upload(content: str, filename: str = "datos.csv") -> dict[str, tuple[str, bytes, str]]:
    return {"file": (filename, content.encode(), "text/csv")}


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


@pytest.fixture
async def back_office(users: Users) -> User:
    return await users.create(Role.BACK_OFFICE, email="bo@quermed.com")


async def test_role_gate(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP, email="rep@quermed.com")
    manager = await users.create(Role.SALES_MANAGER, email="mgr@quermed.com")
    for headers in (users.headers(rep), users.headers(manager)):
        response = await client.post(PRODUCTS_IMPORT, files=upload(PRODUCT_CSV), headers=headers)
        assert response.status_code == 403


async def test_products_dry_run_then_apply_with_audit(
    client: AsyncClient, users: Users, back_office: User, session: AsyncSession
) -> None:
    headers = users.headers(back_office)

    preview = await client.post(PRODUCTS_IMPORT, files=upload(PRODUCT_CSV), headers=headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["dry_run"] is True
    assert body["created"] == 1 and body["errors"] == 1
    outcomes = {row["label"]: row["outcome"] for row in body["rows"]}
    assert outcomes["IMP-API-1"] == "created"
    assert outcomes["IMP-API-2"] == "error"

    listed = await client.get("/api/v1/products", params={"q": "IMP-API-1"}, headers=headers)
    assert listed.json()["total"] == 0  # dry run wrote nothing

    applied = await client.post(
        PRODUCTS_IMPORT,
        params={"dry_run": "false"},
        files=upload(PRODUCT_CSV),
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["dry_run"] is False
    assert applied.json()["created"] == 1

    listed = await client.get("/api/v1/products", params={"q": "IMP-API-1"}, headers=headers)
    assert listed.json()["total"] == 1

    audit_rows = (
        await session.execute(
            select(AuditLogModel.action).where(AuditLogModel.entity_type == "import")
        )
    ).scalars()
    assert list(audit_rows) == ["import.products_executed"]  # only the confirmed run


async def test_unreadable_and_missing_headers_fail_fast(
    client: AsyncClient, users: Users, back_office: User
) -> None:
    headers = users.headers(back_office)

    missing = await client.post(PRODUCTS_IMPORT, files=upload("Nombre;PVP\nX;1\n"), headers=headers)
    assert missing.status_code == 422
    assert "sku" in missing.text

    unreadable = await client.post(
        PRODUCTS_IMPORT,
        files={"file": ("datos.xlsx", b"not an excel", "application/vnd.ms-excel")},
        headers=headers,
    )
    assert unreadable.status_code == 422


async def test_accounts_import_creates_and_is_idempotent(
    client: AsyncClient, users: Users, back_office: User, centro: Territory
) -> None:
    headers = users.headers(back_office)
    csv = (
        "Nombre;CIF;Provincia;Teléfono;Contacto nombre;Contacto apellidos;Contacto email\n"
        "Clínica Import API;12345678Z;28;+34910000001;Ana;Pérez;ana@import.es\n"
    )

    applied = await client.post(
        ACCOUNTS_IMPORT, params={"dry_run": "false"}, files=upload(csv), headers=headers
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["created"] == 1

    accounts = await client.get("/api/v1/accounts", params={"q": "Import API"}, headers=headers)
    assert accounts.json()["total"] == 1
    account = accounts.json()["items"][0]

    contacts = await client.get(f"/api/v1/accounts/{account['id']}/contacts", headers=headers)
    assert [contact["email"] for contact in contacts.json()] == ["ana@import.es"]

    rerun = await client.post(
        ACCOUNTS_IMPORT, params={"dry_run": "false"}, files=upload(csv), headers=headers
    )
    assert rerun.json()["unchanged"] == 1 and rerun.json()["created"] == 0


async def test_accounts_import_resolves_the_contact_specialty(
    client: AsyncClient, users: Users, back_office: User, centro: Territory
) -> None:
    headers = users.headers(back_office)
    csv = (
        "Nombre;CIF;Provincia;Contacto nombre;Contacto apellidos;Contacto email;Especialidad\n"
        # The accent and the case are missing on purpose: names are matched normalised.
        "Clínica Especialidad;B86107174;28;Marta;Vidal;marta@import.es;cirugia vascular\n"
        "Clínica Sin Especialidad;A28017895;28;Luis;Soto;luis@import.es;Traumatología\n"
    )

    applied = await client.post(
        ACCOUNTS_IMPORT, params={"dry_run": "false"}, files=upload(csv), headers=headers
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["created"] == 2 and body["errors"] == 0

    listed = await client.get("/api/v1/contacts", params={"q": "vidal"}, headers=headers)
    assert listed.json()["items"][0]["specialty_id"] == str(
        reference_id("specialties", "vascular_surgery")
    )

    # An unknown specialty is a message on the row, not an error: the contact is created.
    unknown_row = next(r for r in body["rows"] if "Sin Especialidad" in r["label"])
    assert unknown_row["outcome"] == "created"
    assert "especialidad no encontrada: Traumatología" in unknown_row["message"]

    without = await client.get("/api/v1/contacts", params={"q": "soto"}, headers=headers)
    assert without.json()["items"][0]["specialty_id"] is None
