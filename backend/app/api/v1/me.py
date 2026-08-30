"""Self profile endpoints."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, ExpectedVersion, SessionDep, UowDep, get_user_service
from app.application.activities.queries import TodayQueries
from app.application.opportunities.queries import OpportunityQueries
from app.application.quotes.queries import QuoteQueries
from app.application.users.service import UserService
from app.domain.shared.errors import PermissionDeniedError
from app.domain.users.entities import User
from app.domain.users.roles import ROLES_WITH_FULL_VISIBILITY
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.schemas.activities import TodayRead
from app.schemas.opportunities import OpportunitySummaryRead
from app.schemas.quotes import QuoteSummaryRead
from app.schemas.users import MeRead, MeUpdate

router = APIRouter(prefix="/me", tags=["me"])


async def build_me(user: User, uow: SqlAlchemyUnitOfWork) -> MeRead:
    territories = await uow.territories.get_many(user.territory_ids)
    divisions = [
        division for division in await uow.divisions.list_all() if division.id in user.division_ids
    ]
    return MeRead.from_scope(user, sorted(territories, key=lambda t: t.name), divisions)


@router.get("", response_model=MeRead, summary="Read the own profile and scope")
async def read_me(user: CurrentUser, uow: UowDep) -> MeRead:
    return await build_me(user, uow)


@router.patch("", response_model=MeRead, summary="Rename the own profile")
async def update_me(
    payload: MeUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: Annotated[UserService, Depends(get_user_service)],
    uow: UowDep,
) -> MeRead:
    updated = await service.rename_self(
        user.id, payload.full_name, expected_version=expected_version
    )
    return await build_me(updated, uow)


@router.get("/today", response_model=TodayRead, summary="The rep's day: planned, overdue, week")
async def read_today(
    user: CurrentUser,
    session: SessionDep,
    user_id: Annotated[UUID | None, Query()] = None,
) -> TodayRead:
    target = user.id
    if user_id is not None and user_id != user.id:
        if user.role not in ROLES_WITH_FULL_VISIBILITY:
            raise PermissionDeniedError("Only managers can view another user's day")
        target = user_id
    now = datetime.now(UTC)
    result = await TodayQueries(session).for_user(target, now=now)
    opportunity_queries = OpportunityQueries(session, now=now)
    payload = TodayRead.from_result(result)
    payload.tenders_due = [
        OpportunitySummaryRead.from_summary(item)
        for item in await opportunity_queries.tenders_due(target)
    ]
    payload.at_risk = [
        OpportunitySummaryRead.from_summary(item)
        for item in await opportunity_queries.at_risk(target)
    ]
    payload.expiring_quotes = [
        QuoteSummaryRead.from_summary(item)
        for item in await QuoteQueries(session, now=now).expiring_for_owner(target)
    ]
    return payload
