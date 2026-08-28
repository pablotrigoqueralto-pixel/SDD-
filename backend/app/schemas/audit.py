from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    actor_id: UUID | None
    actor_name: str | None
    entity_type: str
    entity_id: UUID | None
    action: str
    changes: dict[str, Any]
    trace_id: str | None


class PersonalDataAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    user_id: UUID
    user_name: str | None
    contact_id: UUID
    trace_id: str | None
