"""Accounts ("centros"): scoped list/detail, creation with smart defaults, updates."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, ExpectedVersion, SessionDep, UowDep, require_roles
from app.application.accounts.commands import (
    AddressInput,
    AssignAccount,
    CreateAccount,
    ReplaceAddresses,
    UpdateAccount,
)
from app.application.accounts.queries import (
    ACCOUNT_DEFAULT_SORT,
    ACCOUNT_MAX_PAGE_SIZE,
    ACCOUNT_SORT_FIELDS,
    AccountFilters,
    AccountQueries,
)
from app.application.accounts.service import AccountService, load_visible_account
from app.application.activities.queries import TimelineFilters, TimelineQueries
from app.application.contacts.commands import ConsentInput, CreateContact
from app.application.contacts.service import ContactService
from app.application.opportunities.queries import OpportunityQueries
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.application.shared.scope import user_scope_filter
from app.application.users.commands import UNSET
from app.domain.activities.entities import ActivityStatus
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.schemas.accounts import (
    AccountAssignment,
    AccountCreate,
    AccountRead,
    AccountSummaryRead,
    AccountUpdate,
    AddressesReplace,
)
from app.schemas.activities import TimelineEntryRead
from app.schemas.contacts import ContactCreate, ContactRead
from app.schemas.opportunities import OpportunitySummaryRead

router = APIRouter(prefix="/accounts", tags=["accounts"])

AccountPage = Annotated[
    PageParams, Depends(page_params_dependency(ACCOUNT_SORT_FIELDS, ACCOUNT_DEFAULT_SORT))
]
ManagerUser = Annotated[User, Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER))]
TimelinePage = Annotated[
    PageParams, Depends(page_params_dependency({"occurred_at"}, "-occurred_at"))
]


def get_account_service(uow: UowDep) -> AccountService:
    return AccountService(uow)


def get_contact_service(uow: UowDep) -> ContactService:
    return ContactService(uow)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]


@router.get("", response_model=Page[AccountSummaryRead], summary="List accounts (scoped)")
async def list_accounts(
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    params: AccountPage,
    q: Annotated[str | None, Query(max_length=100)] = None,
    account_type_id: Annotated[UUID | None, Query()] = None,
    territory_id: Annotated[UUID | None, Query()] = None,
    owner_id: Annotated[UUID | None, Query()] = None,
    division_id: Annotated[UUID | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = True,
    unassigned: Annotated[bool, Query()] = False,
) -> Page[AccountSummaryRead]:
    page_size = min(params.page_size, ACCOUNT_MAX_PAGE_SIZE)
    bounded = PageParams(page=params.page, page_size=page_size, sort=params.sort)
    result = await AccountQueries(session).list_page(
        bounded,
        AccountFilters(
            q=q,
            account_type_id=account_type_id,
            territory_id=territory_id,
            owner_id=owner_id,
            division_id=division_id,
            is_active=is_active,
            unassigned=unassigned,
        ),
        await user_scope_filter(uow, user),
    )
    return Page[AccountSummaryRead](
        items=[AccountSummaryRead.from_summary(item) for item in result.items],
        total=result.total,
        page=bounded.page,
        page_size=bounded.page_size,
    )


@router.post(
    "",
    response_model=AccountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create account (territory and owner derived from the province)",
)
async def create_account(
    payload: AccountCreate, user: CurrentUser, service: AccountServiceDep
) -> AccountRead:
    view = await service.create(
        CreateAccount(
            name=payload.name,
            account_type_id=payload.account_type_id,
            province_code=payload.province_code,
            details=payload.details(),
        ),
        actor=user,
    )
    return AccountRead.from_view(view)


@router.get("/{account_id}", response_model=AccountRead, summary="Read an account")
async def read_account(
    account_id: UUID, user: CurrentUser, service: AccountServiceDep
) -> AccountRead:
    return AccountRead.from_view(await service.get(account_id, actor=user))


@router.patch("/{account_id}", response_model=AccountRead, summary="Update an account")
async def update_account(
    account_id: UUID,
    payload: AccountUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: AccountServiceDep,
) -> AccountRead:
    view = await service.update(
        account_id,
        UpdateAccount(expected_version=expected_version, changes=payload.changes()),
        actor=user,
    )
    return AccountRead.from_view(view)


@router.put(
    "/{account_id}/assignment",
    response_model=AccountRead,
    summary="Reassign owner and/or territory (sales managers and admins)",
)
async def assign_account(
    account_id: UUID,
    payload: AccountAssignment,
    user: ManagerUser,
    expected_version: ExpectedVersion,
    service: AccountServiceDep,
) -> AccountRead:
    provided = payload.model_fields_set
    view = await service.assign(
        account_id,
        AssignAccount(
            expected_version=expected_version,
            owner_id=payload.owner_id if "owner_id" in provided else UNSET,
            territory_id=payload.territory_id if "territory_id" in provided else UNSET,
        ),
        actor=user,
    )
    return AccountRead.from_view(view)


@router.put(
    "/{account_id}/addresses",
    response_model=AccountRead,
    summary="Replace the additional addresses",
)
async def replace_addresses(
    account_id: UUID,
    payload: AddressesReplace,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: AccountServiceDep,
) -> AccountRead:
    view = await service.replace_addresses(
        account_id,
        ReplaceAddresses(
            expected_version=expected_version,
            addresses=[AddressInput(**a.model_dump()) for a in payload.addresses],
        ),
        actor=user,
    )
    return AccountRead.from_view(view)


@router.get(
    "/{account_id}/contacts",
    response_model=list[ContactRead],
    summary="Contacts of an account (primary first)",
)
async def list_account_contacts(
    account_id: UUID,
    user: CurrentUser,
    service: ContactServiceDep,
    include_inactive: Annotated[bool, Query()] = False,
) -> list[ContactRead]:
    contacts = await service.list_for_account(
        account_id, actor=user, include_inactive=include_inactive
    )
    return [ContactRead.from_entity(c) for c in contacts]


@router.post(
    "/{account_id}/contacts",
    response_model=ContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a contact in an account",
)
async def create_account_contact(
    account_id: UUID, payload: ContactCreate, user: CurrentUser, service: ContactServiceDep
) -> ContactRead:
    consent = (
        ConsentInput(payload.consent.status, payload.consent.at, payload.consent.source)
        if payload.consent
        else None
    )
    contact = await service.create(
        CreateContact(
            account_id=account_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            details=payload.details(),
            is_primary=payload.is_primary,
            consent=consent,
        ),
        actor=user,
    )
    return ContactRead.from_entity(contact)


@router.get(
    "/{account_id}/opportunities",
    response_model=list[OpportunitySummaryRead],
    summary="Opportunities of one account (open first)",
)
async def list_account_opportunities(
    account_id: UUID,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
) -> list[OpportunitySummaryRead]:
    async with uow:
        await load_visible_account(uow, account_id, user)
    rows = await OpportunityQueries(session).for_account(account_id)
    return [OpportunitySummaryRead.from_summary(row) for row in rows]


@router.get(
    "/{account_id}/timeline",
    response_model=Page[TimelineEntryRead],
    summary="Account timeline (activities now; more kinds in later changes)",
)
async def account_timeline(
    account_id: UUID,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    params: TimelinePage,
    kind: Annotated[str | None, Query(max_length=30)] = None,
    activity_type_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[ActivityStatus | None, Query(alias="status")] = None,
) -> Page[TimelineEntryRead]:
    await load_visible_account(uow, account_id, user)
    result = await TimelineQueries(session).list_page(
        account_id,
        params,
        TimelineFilters(kind=kind, activity_type_id=activity_type_id, status=status_filter),
    )
    return Page[TimelineEntryRead](
        items=[TimelineEntryRead.from_entry(entry) for entry in result.items],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )
