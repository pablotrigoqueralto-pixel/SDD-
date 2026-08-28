"""Input DTOs for activity use cases."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.activities.entities import ActivityOutcome, ActivityStatus, NextAction


@dataclass(frozen=True)
class CreateActivity:
    account_id: UUID
    activity_type_id: UUID
    status: ActivityStatus = ActivityStatus.DONE
    scheduled_at: datetime | None = None
    owner_id: UUID | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    next_action: NextAction | None = None


@dataclass(frozen=True)
class UpdateActivity:
    expected_version: int
    changes: Mapping[str, Any]


@dataclass(frozen=True)
class CompleteActivity:
    expected_version: int
    done_at: datetime | None = None
    outcome: ActivityOutcome | None = None
    notes: str | None = None
    duration_minutes: int | None = None
    next_action: NextAction | None = None


@dataclass(frozen=True)
class CancelActivity:
    expected_version: int
    reason: str


@dataclass(frozen=True)
class RescheduleActivity:
    expected_version: int
    scheduled_at: datetime
