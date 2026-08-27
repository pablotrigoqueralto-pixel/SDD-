"""Audit log writer (append-only INSERTs)."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.audit import AuditEvent
from app.domain.shared.ids import new_id
from app.infrastructure.db.models import AuditLogModel


class SqlAlchemyAuditLogWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(self, events: list[AuditEvent]) -> None:
        if not events:
            return
        self._session.add_all(
            AuditLogModel(
                id=new_id(),
                occurred_at=event.occurred_at or datetime.now(UTC),
                actor_id=event.actor_id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                action=event.action,
                changes=event.changes,
                trace_id=event.trace_id,
            )
            for event in events
        )
        await self._session.flush()
