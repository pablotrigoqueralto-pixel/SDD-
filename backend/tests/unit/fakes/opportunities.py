from copy import deepcopy
from datetime import datetime
from uuid import UUID

from app.domain.activities.entities import ActivityStatus
from app.domain.opportunities.entities import Opportunity, OpportunityStatus, StageChange
from app.domain.shared.errors import ConcurrentModificationError
from tests.unit.fakes.accounts import InMemoryActivityRepository


class InMemoryOpportunityRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Opportunity] = {}
        self.history: list[StageChange] = []
        # Wired by FakeUnitOfWork so the at-risk rule can look at done activities.
        self.activities: InMemoryActivityRepository | None = None
        # Pipelines whose stages include an at-risk one (set by tests / service fixtures).
        self.at_risk_pipeline_ids: set[UUID] = set()

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        row = self.rows.get(opportunity_id)
        return deepcopy(row) if row else None

    async def add(self, opportunity: Opportunity) -> None:
        self.rows[opportunity.id] = deepcopy(opportunity)

    async def save(self, opportunity: Opportunity, *, expected_version: int) -> None:
        current = self.rows.get(opportunity.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        opportunity.version = expected_version + 1
        self.rows[opportunity.id] = deepcopy(opportunity)

    async def add_stage_change(self, change: StageChange) -> None:
        self.history.append(change)

    async def list_history(self, opportunity_id: UUID) -> list[StageChange]:
        rows = [c for c in self.history if c.opportunity_id == opportunity_id]
        return sorted(rows, key=lambda c: c.occurred_at, reverse=True)

    async def list_at_risk_candidate_ids(self, *, threshold: datetime) -> list[UUID]:
        candidates: list[UUID] = []
        for row in self.rows.values():
            if (
                row.status is not OpportunityStatus.WON
                or row.is_at_risk
                or row.pipeline_id not in self.at_risk_pipeline_ids
            ):
                continue
            updated = row.updated_at or row.stage_entered_at
            if updated >= threshold:
                continue
            if self._latest_done_activity(row.id) is not None:
                latest = self._latest_done_activity(row.id)
                if latest is not None and latest >= threshold:
                    continue
            candidates.append(row.id)
        return candidates

    def _latest_done_activity(self, opportunity_id: UUID) -> datetime | None:
        if self.activities is None:
            return None
        stamps = [
            activity.done_at or activity.scheduled_at
            for activity in self.activities.rows.values()
            if getattr(activity, "opportunity_id", None) == opportunity_id
            and activity.status is ActivityStatus.DONE
        ]
        return max(stamps, default=None)
