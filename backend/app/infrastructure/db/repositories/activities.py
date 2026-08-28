"""SQLAlchemy implementation of ActivityRepository."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.activities.entities import Activity
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import ActivityContactModel, ActivityModel, ContactModel
from app.infrastructure.db.repositories.results import rowcount_of


def activity_to_entity(row: ActivityModel) -> Activity:
    return Activity(
        id=row.id,
        account_id=row.account_id,
        activity_type_id=row.activity_type_id,
        owner_id=row.owner_id,
        created_by=row.created_by,
        status=row.status,
        scheduled_at=row.scheduled_at,
        done_at=row.done_at,
        duration_minutes=row.duration_minutes,
        outcome=row.outcome,
        subject=row.subject,
        notes=row.notes,
        cancel_reason=row.cancel_reason,
        contact_ids=frozenset(link.contact_id for link in row.contact_links),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _values(activity: Activity) -> dict[str, object]:
    return {
        "account_id": activity.account_id,
        "activity_type_id": activity.activity_type_id,
        "owner_id": activity.owner_id,
        "created_by": activity.created_by,
        "status": activity.status,
        "scheduled_at": activity.scheduled_at,
        "done_at": activity.done_at,
        "duration_minutes": activity.duration_minutes,
        "outcome": activity.outcome,
        "subject": activity.subject,
        "notes": activity.notes,
        "cancel_reason": activity.cancel_reason,
    }


class SqlAlchemyActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, activity_id: UUID) -> Activity | None:
        statement = (
            select(ActivityModel)
            .options(selectinload(ActivityModel.contact_links))
            .where(ActivityModel.id == activity_id)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return activity_to_entity(row) if row else None

    async def add(self, activity: Activity) -> None:
        row = ActivityModel(id=activity.id, **_values(activity))
        row.contact_links = [
            ActivityContactModel(activity_id=activity.id, contact_id=c)
            for c in activity.contact_ids
        ]
        self._session.add(row)
        await self._session.flush()

    async def save(self, activity: Activity, *, expected_version: int) -> None:
        result = await self._session.execute(
            update(ActivityModel)
            .where(ActivityModel.id == activity.id, ActivityModel.version == expected_version)
            .values(**_values(activity), version=expected_version + 1)
        )
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        await self._session.execute(
            delete(ActivityContactModel).where(ActivityContactModel.activity_id == activity.id)
        )
        if activity.contact_ids:
            await self._session.execute(
                insert(ActivityContactModel),
                [{"activity_id": activity.id, "contact_id": c} for c in activity.contact_ids],
            )
        activity.version = expected_version + 1

    async def contacts_belong_to(self, account_id: UUID, contact_ids: Iterable[UUID]) -> bool:
        wanted = list(set(contact_ids))
        if not wanted:
            return True
        statement = (
            select(func.count())
            .select_from(ContactModel)
            .where(ContactModel.id.in_(wanted), ContactModel.account_id == account_id)
        )
        return int((await self._session.execute(statement)).scalar_one()) == len(wanted)
