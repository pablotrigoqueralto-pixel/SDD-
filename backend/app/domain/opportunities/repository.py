"""Repository protocol for opportunities (implemented in infrastructure)."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.opportunities.entities import Opportunity, StageChange


class OpportunityRepository(Protocol):
    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        """Aggregate with its lines."""
        ...

    async def add(self, opportunity: Opportunity) -> None: ...

    async def save(self, opportunity: Opportunity, *, expected_version: int) -> None:
        """Persists scalar fields and synchronises the lines."""
        ...

    async def add_stage_change(self, change: StageChange) -> None: ...

    async def list_history(self, opportunity_id: UUID) -> list[StageChange]:
        """Newest first."""
        ...

    async def list_at_risk_candidate_ids(self, *, threshold: datetime) -> list[UUID]:
        """Won opportunities of pipelines with an at-risk stage, not yet flagged, whose
        latest done activity and `updated_at` are both older than the threshold."""
        ...
