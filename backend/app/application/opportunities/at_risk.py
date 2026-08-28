"""Automatic "En riesgo" scan: idempotent, never clears, system actor."""

from datetime import UTC, datetime, timedelta

from app.application.shared.unit_of_work import UnitOfWork
from app.domain.opportunities.entities import AtRiskSource
from app.infrastructure.logging import get_logger

logger = get_logger("opportunities.at_risk")


async def scan_at_risk(uow: UnitOfWork, *, after_days: int, now: datetime | None = None) -> int:
    """Flag silent won opportunities of at-risk pipelines; returns how many were flagged."""
    reference = now or datetime.now(UTC)
    threshold = reference - timedelta(days=after_days)
    flagged = 0
    async with uow:
        pipelines = {pipeline.id: pipeline for pipeline in await uow.pipelines.list_all()}
        candidate_ids = await uow.opportunities.list_at_risk_candidate_ids(threshold=threshold)
        for opportunity_id in candidate_ids:
            opportunity = await uow.opportunities.get(opportunity_id)
            if opportunity is None:
                continue
            pipeline = pipelines.get(opportunity.pipeline_id)
            if pipeline is None:
                continue
            change = opportunity.set_at_risk(
                pipeline, True, source=AtRiskSource.AUTOMATIC, actor_id=None, now=reference
            )
            if change is None:
                continue
            await uow.opportunities.save(opportunity, expected_version=opportunity.version)
            await uow.opportunities.add_stage_change(change)
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.at_risk_set",
                changes={"at_risk_source": {"before": None, "after": "automatic"}},
                actor_id=None,
            )
            flagged += 1
        await uow.commit()
    if flagged:
        logger.info("at_risk_scan_flagged", count=flagged, after_days=after_days)
    return flagged
