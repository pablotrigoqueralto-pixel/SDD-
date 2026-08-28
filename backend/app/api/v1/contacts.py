"""Contacts: detail, update and GDPR anonymisation (visibility follows the account)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, ExpectedVersion, UowDep, require_roles
from app.application.contacts.commands import ConsentInput, UpdateContact
from app.application.contacts.service import ContactService
from app.application.users.commands import UNSET
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.schemas.contacts import ContactRead, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])
ManagerUser = Annotated[User, Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER))]


def get_contact_service(uow: UowDep) -> ContactService:
    return ContactService(uow)


ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]


@router.get("/{contact_id}", response_model=ContactRead, summary="Read a contact")
async def read_contact(
    contact_id: UUID, user: CurrentUser, service: ContactServiceDep
) -> ContactRead:
    contact, account = await service.get(contact_id, actor=user)
    return ContactRead.from_entity(contact, account)


@router.patch("/{contact_id}", response_model=ContactRead, summary="Update a contact")
async def update_contact(
    contact_id: UUID,
    payload: ContactUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: ContactServiceDep,
) -> ContactRead:
    consent = (
        ConsentInput(payload.consent.status, payload.consent.at, payload.consent.source)
        if payload.consent
        else None
    )
    contact = await service.update(
        contact_id,
        UpdateContact(
            expected_version=expected_version,
            changes=payload.changes(),
            is_primary=payload.is_primary if payload.is_primary is not None else UNSET,
            is_active=payload.is_active if payload.is_active is not None else UNSET,
            consent=consent,
        ),
        actor=user,
    )
    return ContactRead.from_entity(contact)


@router.post(
    "/{contact_id}/anonymise",
    response_model=ContactRead,
    summary="Erase the contact's personal data (GDPR right to erasure)",
)
async def anonymise_contact(
    contact_id: UUID,
    user: ManagerUser,
    expected_version: ExpectedVersion,
    service: ContactServiceDep,
) -> ContactRead:
    contact = await service.anonymise(contact_id, expected_version=expected_version, actor=user)
    return ContactRead.from_entity(contact)
