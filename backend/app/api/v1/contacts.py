"""Contacts: detail, update and GDPR anonymisation (visibility follows the account)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, ExpectedVersion, SessionDep, UowDep, require_roles
from app.application.contacts.commands import ConsentInput, UpdateContact
from app.application.contacts.queries import (
    CONTACT_DEFAULT_SORT,
    CONTACT_MAX_PAGE_SIZE,
    CONTACT_SORT_FIELDS,
    ContactFilters,
    ContactQueries,
)
from app.application.contacts.service import ContactService
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.application.shared.scope import user_scope_filter
from app.application.users.commands import UNSET
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.schemas.contacts import ContactRead, ContactSummaryRead, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])
ManagerUser = Annotated[User, Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER))]
ContactPage = Annotated[
    PageParams, Depends(page_params_dependency(CONTACT_SORT_FIELDS, CONTACT_DEFAULT_SORT))
]


def get_contact_service(uow: UowDep) -> ContactService:
    return ContactService(uow)


ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]


@router.get(
    "",
    response_model=Page[ContactSummaryRead],
    summary="List contacts across every visible account (cumulative filters)",
)
async def list_contacts(
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    params: ContactPage,
    q: Annotated[str | None, Query(max_length=100)] = None,
    specialty_id: Annotated[list[UUID] | None, Query()] = None,
    account_id: Annotated[list[UUID] | None, Query()] = None,
    job_title_id: Annotated[UUID | None, Query()] = None,
    is_head_of_department: Annotated[bool | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = True,
) -> Page[ContactSummaryRead]:
    bounded = PageParams(
        page=params.page,
        page_size=min(params.page_size, CONTACT_MAX_PAGE_SIZE),
        sort=params.sort,
    )
    result = await ContactQueries(session).list_page(
        bounded,
        ContactFilters(
            q=q,
            specialty_ids=list(specialty_id or []),
            account_ids=list(account_id or []),
            job_title_id=job_title_id,
            is_head_of_department=is_head_of_department,
            is_active=is_active,
        ),
        await user_scope_filter(uow, user),
    )
    return Page[ContactSummaryRead](
        items=[ContactSummaryRead.from_summary(item) for item in result.items],
        total=result.total,
        page=bounded.page,
        page_size=bounded.page_size,
    )


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
