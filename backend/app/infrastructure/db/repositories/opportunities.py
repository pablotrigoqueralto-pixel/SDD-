"""SQLAlchemy implementation of the opportunity repository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.activities.entities import ActivityStatus
from app.domain.opportunities.entities import (
    Opportunity,
    OpportunityLine,
    OpportunityStatus,
    StageChange,
)
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import (
    ActivityModel,
    OpportunityLineModel,
    OpportunityModel,
    OpportunityStageHistoryModel,
    PipelineModel,
    PipelineStageModel,
)
from app.infrastructure.db.repositories.results import rowcount_of


def line_to_entity(row: OpportunityLineModel) -> OpportunityLine:
    return OpportunityLine(
        id=row.id,
        product_id=row.product_id,
        quantity=row.quantity,
        unit_price=row.unit_price,
        sort_order=row.sort_order,
    )


def opportunity_to_entity(row: OpportunityModel) -> Opportunity:
    return Opportunity(
        id=row.id,
        account_id=row.account_id,
        pipeline_id=row.pipeline_id,
        stage_id=row.stage_id,
        division_id=row.division_id,
        owner_id=row.owner_id,
        created_by=row.created_by,
        name=row.name,
        description=row.description,
        status=row.status,
        estimated_amount=row.estimated_amount,
        amount=row.amount,
        expected_close_date=row.expected_close_date,
        won_amount=row.won_amount,
        won_at=row.won_at,
        lost_at=row.lost_at,
        loss_reason_id=row.loss_reason_id,
        competitor_brand_id=row.competitor_brand_id,
        loss_note=row.loss_note,
        is_tender=row.is_tender,
        tender_reference=row.tender_reference,
        tender_deadline=row.tender_deadline,
        estimated_award_date=row.estimated_award_date,
        is_at_risk=row.is_at_risk,
        at_risk_since=row.at_risk_since,
        at_risk_source=row.at_risk_source,
        stage_entered_at=row.stage_entered_at,
        lines=[line_to_entity(line) for line in row.lines],
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _scalar_values(opportunity: Opportunity) -> dict[str, object]:
    return {
        "stage_id": opportunity.stage_id,
        "owner_id": opportunity.owner_id,
        "name": opportunity.name,
        "description": opportunity.description,
        "status": opportunity.status,
        "estimated_amount": opportunity.estimated_amount,
        "amount": opportunity.amount,
        "expected_close_date": opportunity.expected_close_date,
        "won_amount": opportunity.won_amount,
        "won_at": opportunity.won_at,
        "lost_at": opportunity.lost_at,
        "loss_reason_id": opportunity.loss_reason_id,
        "competitor_brand_id": opportunity.competitor_brand_id,
        "loss_note": opportunity.loss_note,
        "is_tender": opportunity.is_tender,
        "tender_reference": opportunity.tender_reference,
        "tender_deadline": opportunity.tender_deadline,
        "estimated_award_date": opportunity.estimated_award_date,
        "is_at_risk": opportunity.is_at_risk,
        "at_risk_since": opportunity.at_risk_since,
        "at_risk_source": opportunity.at_risk_source,
        "stage_entered_at": opportunity.stage_entered_at,
    }


class SqlAlchemyOpportunityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        statement = (
            select(OpportunityModel)
            .options(selectinload(OpportunityModel.lines))
            .where(OpportunityModel.id == opportunity_id)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return opportunity_to_entity(row) if row else None

    async def add(self, opportunity: Opportunity) -> None:
        self._session.add(
            OpportunityModel(
                id=opportunity.id,
                account_id=opportunity.account_id,
                pipeline_id=opportunity.pipeline_id,
                division_id=opportunity.division_id,
                created_by=opportunity.created_by,
                **_scalar_values(opportunity),
            )
        )
        await self._session.flush()

    async def save(self, opportunity: Opportunity, *, expected_version: int) -> None:
        statement = (
            update(OpportunityModel)
            .where(
                OpportunityModel.id == opportunity.id,
                OpportunityModel.version == expected_version,
            )
            .values(version=expected_version + 1, **_scalar_values(opportunity))
        )
        result = await self._session.execute(statement)
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        await self._sync_lines(opportunity)
        opportunity.version = expected_version + 1

    async def add_stage_change(self, change: StageChange) -> None:
        self._session.add(
            OpportunityStageHistoryModel(
                opportunity_id=change.opportunity_id,
                from_stage_id=change.from_stage_id,
                to_stage_id=change.to_stage_id,
                actor_id=change.actor_id,
                occurred_at=change.occurred_at,
                seconds_in_previous_stage=change.seconds_in_previous_stage,
            )
        )
        await self._session.flush()

    async def list_history(self, opportunity_id: UUID) -> list[StageChange]:
        statement = (
            select(OpportunityStageHistoryModel)
            .where(OpportunityStageHistoryModel.opportunity_id == opportunity_id)
            .order_by(OpportunityStageHistoryModel.occurred_at.desc())
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [
            StageChange(
                opportunity_id=row.opportunity_id,
                from_stage_id=row.from_stage_id,
                to_stage_id=row.to_stage_id,
                occurred_at=row.occurred_at,
                actor_id=row.actor_id,
                seconds_in_previous_stage=row.seconds_in_previous_stage,
            )
            for row in rows
        ]

    async def list_at_risk_candidate_ids(self, *, threshold: datetime) -> list[UUID]:
        at_risk_pipelines = (
            select(PipelineStageModel.pipeline_id)
            .where(PipelineStageModel.is_at_risk.is_(True))
            .scalar_subquery()
        )
        latest_activity = (
            select(func.max(func.coalesce(ActivityModel.done_at, ActivityModel.scheduled_at)))
            .where(
                ActivityModel.opportunity_id == OpportunityModel.id,
                ActivityModel.status == ActivityStatus.DONE,
            )
            .correlate(OpportunityModel)
            .scalar_subquery()
        )
        statement = (
            select(OpportunityModel.id)
            .join(PipelineModel, PipelineModel.id == OpportunityModel.pipeline_id)
            .where(
                OpportunityModel.status == OpportunityStatus.WON,
                OpportunityModel.is_at_risk.is_(False),
                OpportunityModel.pipeline_id.in_(at_risk_pipelines),
                OpportunityModel.updated_at < threshold,
                func.coalesce(latest_activity, OpportunityModel.updated_at) < threshold,
            )
            .order_by(OpportunityModel.updated_at)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def _sync_lines(self, opportunity: Opportunity) -> None:
        kept = {line.id for line in opportunity.lines}
        removal = delete(OpportunityLineModel).where(
            OpportunityLineModel.opportunity_id == opportunity.id
        )
        if kept:
            removal = removal.where(OpportunityLineModel.id.not_in(kept))
        await self._session.execute(removal)
        existing = set(
            (
                await self._session.execute(
                    select(OpportunityLineModel.id).where(
                        OpportunityLineModel.opportunity_id == opportunity.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for line in opportunity.lines:
            if line.id in existing:
                await self._session.execute(
                    update(OpportunityLineModel)
                    .where(OpportunityLineModel.id == line.id)
                    .values(
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        sort_order=line.sort_order,
                    )
                )
            else:
                self._session.add(
                    OpportunityLineModel(
                        id=line.id,
                        opportunity_id=opportunity.id,
                        product_id=line.product_id,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        sort_order=line.sort_order,
                    )
                )
        await self._session.flush()
