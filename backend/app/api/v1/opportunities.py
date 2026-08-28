"""Opportunities: scoped reads, board, creation with defaults and pipeline commands."""

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import Select, select

from app.api.deps import CurrentUser, ExpectedVersion, SessionDep, UowDep
from app.application.opportunities.commands import (
    AddLine,
    CreateOpportunity,
    LoseOpportunity,
    UpdateLine,
    UpdateOpportunity,
    WinOpportunity,
)
from app.application.opportunities.queries import (
    OPPORTUNITY_DEFAULT_SORT,
    OPPORTUNITY_MAX_PAGE_SIZE,
    OPPORTUNITY_SORT_FIELDS,
    OpportunityFilters,
    OpportunityQueries,
)
from app.application.opportunities.service import OpportunityDetail, OpportunityService
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.application.shared.scope import user_scope_filter
from app.domain.shared.errors import NotFoundError
from app.domain.users.entities import User
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.repositories.scope import scoped_accounts
from app.schemas.opportunities import (
    AtRiskToggle,
    BoardRead,
    LineCreate,
    LineUpdate,
    Opportunity,
    OpportunityAssignment,
    OpportunityCreate,
    OpportunityLose,
    OpportunityRead,
    OpportunityReopen,
    OpportunitySummaryRead,
    OpportunityUpdate,
    OpportunityWin,
    StageMove,
    status_filter,
)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

OpportunityPage = Annotated[
    PageParams,
    Depends(page_params_dependency(OPPORTUNITY_SORT_FIELDS, OPPORTUNITY_DEFAULT_SORT)),
]


def get_opportunity_service(uow: UowDep) -> OpportunityService:
    return OpportunityService(uow)


OpportunityServiceDep = Annotated[OpportunityService, Depends(get_opportunity_service)]


async def _account_ids(uow: UowDep, user: User) -> Select[tuple[UUID]] | None:
    scope = await user_scope_filter(uow, user)
    return None if scope is None else scoped_accounts(select(AccountModel.id), scope)


async def _read(
    uow: UowDep, session: SessionDep, user: User, detail: OpportunityDetail
) -> OpportunityRead:
    opportunity = detail.opportunity
    account = await uow.accounts.get(opportunity.account_id)
    pipeline = await uow.pipelines.get(opportunity.pipeline_id)
    owner = await uow.users.get(opportunity.owner_id)
    if account is None or pipeline is None:
        raise NotFoundError("Opportunity not found")
    stage_name = next(
        (stage.name_es for stage in pipeline.stages if stage.id == opportunity.stage_id), ""
    )
    return OpportunityRead.build(
        detail,
        account_name=account.name,
        pipeline_name=pipeline.name_es,
        stage_name=stage_name,
        owner_name=owner.full_name if owner else "",
        now=datetime.now(UTC),
    )


async def _detail_response(
    uow: UowDep,
    session: SessionDep,
    user: User,
    service: OpportunityService,
    opportunity: Opportunity,
) -> OpportunityRead:
    detail = await service.get(opportunity.id, actor=user)
    return await _read(uow, session, user, detail)


@router.get("", response_model=Page[OpportunitySummaryRead], summary="List opportunities (scoped)")
async def list_opportunities(
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    params: OpportunityPage,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    pipeline_id: Annotated[UUID | None, Query()] = None,
    stage_id: Annotated[UUID | None, Query()] = None,
    division_id: Annotated[UUID | None, Query()] = None,
    owner_id: Annotated[UUID | None, Query()] = None,
    account_id: Annotated[UUID | None, Query()] = None,
    is_tender: Annotated[bool | None, Query()] = None,
    is_at_risk: Annotated[bool | None, Query()] = None,
    close_from: Annotated[date | None, Query()] = None,
    close_to: Annotated[date | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[OpportunitySummaryRead]:
    page_size = min(params.page_size, OPPORTUNITY_MAX_PAGE_SIZE)
    bounded = PageParams(page=params.page, page_size=page_size, sort=params.sort)
    result = await OpportunityQueries(session).list_page(
        bounded,
        OpportunityFilters(
            status=status_filter(status_value),
            pipeline_id=pipeline_id,
            stage_id=stage_id,
            division_id=division_id,
            owner_id=owner_id,
            account_id=account_id,
            is_tender=is_tender,
            is_at_risk=is_at_risk,
            close_from=close_from,
            close_to=close_to,
            q=q,
        ),
        await _account_ids(uow, user),
    )
    return Page[OpportunitySummaryRead](
        items=[OpportunitySummaryRead.from_summary(item) for item in result.items],
        total=result.total,
        page=bounded.page,
        page_size=bounded.page_size,
    )


@router.get("/board", response_model=BoardRead, summary="Kanban board of one pipeline")
async def board(
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    pipeline_id: Annotated[UUID, Query()],
    division_id: Annotated[UUID | None, Query()] = None,
    owner_id: Annotated[UUID | None, Query()] = None,
) -> BoardRead:
    pipeline = await uow.pipelines.get(pipeline_id)
    if pipeline is None:
        raise NotFoundError("Pipeline not found")
    result = await OpportunityQueries(session).board(
        pipeline,
        await _account_ids(uow, user),
        division_id=division_id,
        owner_id=owner_id,
    )
    return BoardRead.from_result(result)


@router.get("/{opportunity_id}", response_model=OpportunityRead, summary="Opportunity detail")
async def read_opportunity(
    opportunity_id: UUID,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    detail = await service.get(opportunity_id, actor=user)
    return await _read(uow, session, user, detail)


@router.post(
    "",
    response_model=OpportunityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an opportunity (three fields, smart defaults)",
)
async def create_opportunity(
    payload: OpportunityCreate,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.create(
        CreateOpportunity(
            account_id=payload.account_id,
            division_id=payload.division_id,
            estimated_amount=payload.estimated_amount,
            pipeline_id=payload.pipeline_id,
            name=payload.name,
            description=payload.description,
            expected_close_date=payload.expected_close_date,
            is_tender=payload.is_tender,
            tender_reference=payload.tender_reference,
            tender_deadline=payload.tender_deadline,
            estimated_award_date=payload.estimated_award_date,
            owner_id=payload.owner_id,
        ),
        actor=user,
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.patch(
    "/{opportunity_id}", response_model=OpportunityRead, summary="Update descriptive fields"
)
async def update_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.update(
        opportunity_id,
        UpdateOpportunity(expected_version=expected_version, changes=payload.changes()),
        actor=user,
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.post(
    "/{opportunity_id}/stage", response_model=OpportunityRead, summary="Move to an open stage"
)
async def move_stage(
    opportunity_id: UUID,
    payload: StageMove,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.move_stage(
        opportunity_id, payload.stage_id, expected_version=expected_version, actor=user
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.post("/{opportunity_id}/win", response_model=OpportunityRead, summary="Win the opportunity")
async def win_opportunity(
    opportunity_id: UUID,
    payload: OpportunityWin,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.win(
        opportunity_id,
        WinOpportunity(
            expected_version=expected_version,
            won_amount=payload.won_amount,
            won_at=payload.won_at,
        ),
        actor=user,
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.post("/{opportunity_id}/lose", response_model=OpportunityRead, summary="Lose with a reason")
async def lose_opportunity(
    opportunity_id: UUID,
    payload: OpportunityLose,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.lose(
        opportunity_id,
        LoseOpportunity(
            expected_version=expected_version,
            loss_reason_id=payload.loss_reason_id,
            competitor_brand_id=payload.competitor_brand_id,
            note=payload.note,
        ),
        actor=user,
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.post(
    "/{opportunity_id}/reopen",
    response_model=OpportunityRead,
    summary="Reopen a closed opportunity (sales management)",
)
async def reopen_opportunity(
    opportunity_id: UUID,
    payload: OpportunityReopen,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.reopen(
        opportunity_id, payload.stage_id, expected_version=expected_version, actor=user
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.post(
    "/{opportunity_id}/at-risk",
    response_model=OpportunityRead,
    summary="Flag or clear En riesgo (consumables)",
)
async def toggle_at_risk(
    opportunity_id: UUID,
    payload: AtRiskToggle,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.set_at_risk(
        opportunity_id, payload.flag, expected_version=expected_version, actor=user
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.put(
    "/{opportunity_id}/assignment",
    response_model=OpportunityRead,
    summary="Reassign the owner (sales management)",
)
async def assign_opportunity(
    opportunity_id: UUID,
    payload: OpportunityAssignment,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.assign(
        opportunity_id, payload.owner_id, expected_version=expected_version, actor=user
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.post(
    "/{opportunity_id}/lines",
    response_model=OpportunityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product line",
)
async def add_line(
    opportunity_id: UUID,
    payload: LineCreate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.add_line(
        opportunity_id,
        AddLine(
            expected_version=expected_version,
            product_id=payload.product_id,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
        ),
        actor=user,
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.patch(
    "/{opportunity_id}/lines/{line_id}",
    response_model=OpportunityRead,
    summary="Update a product line",
)
async def update_line(
    opportunity_id: UUID,
    line_id: UUID,
    payload: LineUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: OpportunityServiceDep,
) -> OpportunityRead:
    opportunity = await service.update_line(
        opportunity_id,
        line_id,
        UpdateLine(
            expected_version=expected_version,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
        ),
        actor=user,
    )
    return await _detail_response(uow, session, user, service, opportunity)


@router.delete(
    "/{opportunity_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a product line",
)
async def remove_line(
    opportunity_id: UUID,
    line_id: UUID,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: OpportunityServiceDep,
) -> None:
    await service.remove_line(
        opportunity_id, line_id, expected_version=expected_version, actor=user
    )
