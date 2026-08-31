"""Activities: capture, plan, complete, cancel, reschedule (visibility follows the account)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, ExpectedVersion, SessionDep, UowDep
from app.application.activities.commands import (
    CancelActivity,
    CompleteActivity,
    CreateActivity,
    RescheduleActivity,
    UpdateActivity,
)
from app.application.activities.queries import (
    ACTIVITY_DEFAULT_SORT,
    ACTIVITY_SORT_FIELDS,
    ActivityFilters,
    ActivityQueries,
    load_activity_view,
)
from app.application.activities.service import ActivityService
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.application.shared.scope import user_scope_filter
from app.domain.activities.entities import ActivityStatus, NextAction
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.users.roles import ROLES_WITH_FULL_VISIBILITY
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.repositories.scope import scoped_accounts
from app.schemas.activities import (
    ActivityCancel,
    ActivityComplete,
    ActivityCreate,
    ActivityRead,
    ActivityReschedule,
    ActivityUpdate,
    CalendarRead,
    NextActionWrite,
)

router = APIRouter(prefix="/activities", tags=["activities"])

ActivityPage = Annotated[
    PageParams, Depends(page_params_dependency(ACTIVITY_SORT_FIELDS, ACTIVITY_DEFAULT_SORT))
]


def get_activity_service(uow: UowDep) -> ActivityService:
    return ActivityService(uow)


ActivityServiceDep = Annotated[ActivityService, Depends(get_activity_service)]


def _next_action(payload: NextActionWrite | None) -> NextAction | None:
    if payload is None:
        return None
    return NextAction(
        activity_type_id=payload.activity_type_id,
        scheduled_at=payload.scheduled_at,
        subject=payload.subject,
    )


async def _read(session: AsyncSession, activity_id: UUID, next_id: UUID | None) -> ActivityRead:
    view = await load_activity_view(session, activity_id)
    if view is None:
        raise NotFoundError("Activity not found")
    return ActivityRead.from_view(view, next_id)


@router.get(
    "/calendar",
    response_model=CalendarRead,
    summary="Month calendar of activities (team for staff, own for reps)",
)
async def activity_calendar(
    user: CurrentUser,
    session: SessionDep,
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    owner_id: Annotated[UUID | None, Query()] = None,
) -> CalendarRead:
    if user.role in ROLES_WITH_FULL_VISIBILITY:
        effective_owner = owner_id
    else:
        if owner_id is not None and owner_id != user.id:
            raise PermissionDeniedError("A sales rep can only read their own calendar")
        effective_owner = user.id
    result = await ActivityQueries(session).calendar(year, month, effective_owner)
    return CalendarRead.from_result(result)


@router.get("", response_model=Page[ActivityRead], summary="List activities (scoped)")
async def list_activities(
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    params: ActivityPage,
    account_id: Annotated[UUID | None, Query()] = None,
    opportunity_id: Annotated[UUID | None, Query()] = None,
    owner_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[ActivityStatus | None, Query(alias="status")] = None,
    activity_type_id: Annotated[UUID | None, Query()] = None,
    occurred_from: Annotated[datetime | None, Query(alias="from")] = None,
    occurred_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> Page[ActivityRead]:
    scope = await user_scope_filter(uow, user)
    account_ids = None if scope is None else scoped_accounts(select(AccountModel.id), scope)
    result = await ActivityQueries(session).list_page(
        params,
        ActivityFilters(
            account_id=account_id,
            opportunity_id=opportunity_id,
            owner_id=owner_id,
            status=status_filter,
            activity_type_id=activity_type_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        ),
        account_ids,
    )
    return Page[ActivityRead](
        items=[ActivityRead.from_view(v) for v in result.items],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record or plan an activity",
)
async def create_activity(
    payload: ActivityCreate, user: CurrentUser, service: ActivityServiceDep, session: SessionDep
) -> ActivityRead:
    result = await service.create(
        CreateActivity(
            account_id=payload.account_id,
            activity_type_id=payload.activity_type_id,
            opportunity_id=payload.opportunity_id,
            status=payload.status,
            scheduled_at=payload.scheduled_at,
            owner_id=payload.owner_id,
            details=payload.details(),
            next_action=_next_action(payload.next_action),
        ),
        actor=user,
    )
    next_id = result.next_activity.id if result.next_activity else None
    return await _read(session, result.activity.id, next_id)


@router.get("/{activity_id}", response_model=ActivityRead, summary="Read an activity")
async def read_activity(
    activity_id: UUID, user: CurrentUser, service: ActivityServiceDep, session: SessionDep
) -> ActivityRead:
    activity = await service.get(activity_id, actor=user)
    return await _read(session, activity.id, None)


@router.patch("/{activity_id}", response_model=ActivityRead, summary="Edit descriptive fields")
async def update_activity(
    activity_id: UUID,
    payload: ActivityUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: ActivityServiceDep,
    session: SessionDep,
) -> ActivityRead:
    activity = await service.update(
        activity_id, UpdateActivity(expected_version, payload.changes()), actor=user
    )
    return await _read(session, activity.id, None)


@router.post("/{activity_id}/complete", response_model=ActivityRead, summary="Mark as done")
async def complete_activity(
    activity_id: UUID,
    payload: ActivityComplete,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: ActivityServiceDep,
    session: SessionDep,
) -> ActivityRead:
    result = await service.complete(
        activity_id,
        CompleteActivity(
            expected_version=expected_version,
            done_at=payload.done_at,
            outcome=payload.outcome,
            notes=payload.notes,
            duration_minutes=payload.duration_minutes,
            next_action=_next_action(payload.next_action),
        ),
        actor=user,
    )
    next_id = result.next_activity.id if result.next_activity else None
    return await _read(session, result.activity.id, next_id)


@router.post("/{activity_id}/cancel", response_model=ActivityRead, summary="Cancel with a reason")
async def cancel_activity(
    activity_id: UUID,
    payload: ActivityCancel,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: ActivityServiceDep,
    session: SessionDep,
) -> ActivityRead:
    activity = await service.cancel(
        activity_id, CancelActivity(expected_version, payload.reason), actor=user
    )
    return await _read(session, activity.id, None)


@router.post(
    "/{activity_id}/reschedule", response_model=ActivityRead, summary="Move a planned activity"
)
async def reschedule_activity(
    activity_id: UUID,
    payload: ActivityReschedule,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: ActivityServiceDep,
    session: SessionDep,
) -> ActivityRead:
    activity = await service.reschedule(
        activity_id, RescheduleActivity(expected_version, payload.scheduled_at), actor=user
    )
    return await _read(session, activity.id, None)
