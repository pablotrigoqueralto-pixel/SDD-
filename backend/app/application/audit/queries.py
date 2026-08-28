"""Read side for the audit log (admin only)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.pagination import PageParams
from app.infrastructure.db.models import AuditLogModel, PersonalDataAccessLogModel, UserModel

AUDIT_SORT_FIELDS: set[str] = {"occurred_at"}
AUDIT_DEFAULT_SORT = "-occurred_at"


@dataclass(frozen=True)
class AuditFilters:
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor_id: UUID | None = None
    action: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None


@dataclass(frozen=True)
class AuditEntry:
    id: UUID
    occurred_at: datetime
    actor_id: UUID | None
    actor_name: str | None
    entity_type: str
    entity_id: UUID | None
    action: str
    changes: dict[str, Any]
    trace_id: str | None


@dataclass(frozen=True)
class AuditListResult:
    items: list[AuditEntry]
    total: int


class AuditQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(self, params: PageParams, filters: AuditFilters) -> AuditListResult:
        base = self._apply_filters(
            select(AuditLogModel, UserModel.full_name).outerjoin(
                UserModel, UserModel.id == AuditLogModel.actor_id
            ),
            filters,
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        order = [
            AuditLogModel.occurred_at.desc()
            if field.descending
            else AuditLogModel.occurred_at.asc()
            for field in params.sort
        ]
        statement = (
            base.order_by(*order, AuditLogModel.id.desc()).offset(params.offset).limit(params.limit)
        )
        rows = (await self._session.execute(statement)).all()
        return AuditListResult(
            items=[
                AuditEntry(
                    id=row[0].id,
                    occurred_at=row[0].occurred_at,
                    actor_id=row[0].actor_id,
                    actor_name=row[1],
                    entity_type=row[0].entity_type,
                    entity_id=row[0].entity_id,
                    action=row[0].action,
                    changes=row[0].changes,
                    trace_id=row[0].trace_id,
                )
                for row in rows
            ],
            total=int(total or 0),
        )

    @staticmethod
    def _apply_filters(statement: Select[Any], filters: AuditFilters) -> Select[Any]:
        if filters.entity_type:
            statement = statement.where(AuditLogModel.entity_type == filters.entity_type)
        if filters.entity_id:
            statement = statement.where(AuditLogModel.entity_id == filters.entity_id)
        if filters.actor_id:
            statement = statement.where(AuditLogModel.actor_id == filters.actor_id)
        if filters.action:
            statement = statement.where(AuditLogModel.action == filters.action)
        if filters.occurred_from:
            statement = statement.where(AuditLogModel.occurred_at >= filters.occurred_from)
        if filters.occurred_to:
            statement = statement.where(AuditLogModel.occurred_at <= filters.occurred_to)
        return statement


@dataclass(frozen=True)
class PersonalDataAccessFilters:
    contact_id: UUID | None = None
    user_id: UUID | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None


@dataclass(frozen=True)
class PersonalDataAccessEntry:
    id: UUID
    occurred_at: datetime
    user_id: UUID
    user_name: str | None
    contact_id: UUID
    trace_id: str | None


@dataclass(frozen=True)
class PersonalDataAccessListResult:
    items: list[PersonalDataAccessEntry]
    total: int


class PersonalDataAccessQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self, params: PageParams, filters: PersonalDataAccessFilters
    ) -> PersonalDataAccessListResult:
        base = select(PersonalDataAccessLogModel, UserModel.full_name).outerjoin(
            UserModel, UserModel.id == PersonalDataAccessLogModel.user_id
        )
        if filters.contact_id:
            base = base.where(PersonalDataAccessLogModel.contact_id == filters.contact_id)
        if filters.user_id:
            base = base.where(PersonalDataAccessLogModel.user_id == filters.user_id)
        if filters.occurred_from:
            base = base.where(PersonalDataAccessLogModel.occurred_at >= filters.occurred_from)
        if filters.occurred_to:
            base = base.where(PersonalDataAccessLogModel.occurred_at <= filters.occurred_to)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        order = [
            PersonalDataAccessLogModel.occurred_at.desc()
            if field.descending
            else PersonalDataAccessLogModel.occurred_at.asc()
            for field in params.sort
        ]
        statement = (
            base.order_by(*order, PersonalDataAccessLogModel.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(statement)).all()
        return PersonalDataAccessListResult(
            items=[
                PersonalDataAccessEntry(
                    id=row[0].id,
                    occurred_at=row[0].occurred_at,
                    user_id=row[0].user_id,
                    user_name=row[1],
                    contact_id=row[0].contact_id,
                    trace_id=row[0].trace_id,
                )
                for row in rows
            ],
            total=int(total or 0),
        )
