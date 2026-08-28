"""Shared helpers for account/contact API tests."""

from typing import Any
from uuid import UUID

from httpx import AsyncClient

from app.infrastructure.db.seed import DIVISIONS, reference_id

ACCOUNTS = "/api/v1/accounts"
CONTACTS = "/api/v1/contacts"
IVF_CLINIC_ID: UUID = reference_id("account_types", "ivf_clinic")
HOSPITAL_ID: UUID = reference_id("account_types", "public_hospital")
VASCULAR_ID: UUID = next(d.id for d in DIVISIONS if d.code == "vascular")
NEUROLOGY_ID: UUID = next(d.id for d in DIVISIONS if d.code == "neurology")
GYNAECOLOGIST_ID: UUID = reference_id("job_titles", "gynaecologist")


async def create_account(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str = "Clínica Tambre",
    province: str = "28",
    **extra: Any,
) -> dict[str, Any]:
    response = await client.post(
        ACCOUNTS,
        json={
            "name": name,
            "account_type_id": str(IVF_CLINIC_ID),
            "province_code": province,
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def create_contact(
    client: AsyncClient,
    headers: dict[str, str],
    account_id: str,
    *,
    first_name: str = "Ana",
    last_name: str = "Pérez",
    **extra: Any,
) -> dict[str, Any]:
    response = await client.post(
        f"{ACCOUNTS}/{account_id}/contacts",
        json={"first_name": first_name, "last_name": last_name, **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def if_match(version: int) -> dict[str, str]:
    return {"If-Match": str(version)}
