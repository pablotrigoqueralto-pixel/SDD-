"""The unit of work persists audit rows in the same transaction as the data."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.audit import diff_fields
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from app.infrastructure.db.models import AuditLogModel, UserModel
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


async def count(session: AsyncSession, model: type[AuditLogModel] | type[UserModel]) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def test_commit_writes_data_and_audit_rows_together(session: AsyncSession) -> None:
    user = User.create(
        email=Email("ana@quermed.com"), full_name="Ana", role=Role.ADMIN, password_hash="h"
    )

    async with SqlAlchemyUnitOfWork(session) as uow:
        await uow.users.add(user)
        uow.audit.record(
            entity_type="user",
            entity_id=user.id,
            action="user.created",
            changes=diff_fields({}, {"full_name": "Ana", "password_hash": "h"}),
            actor_id=user.id,
        )
        await uow.commit()

    assert await count(session, UserModel) == 1
    row = (await session.execute(select(AuditLogModel))).scalar_one()
    assert row.action == "user.created"
    assert row.actor_id == user.id
    assert row.entity_id == user.id
    assert row.changes["full_name"] == {"before": None, "after": "Ana"}
    assert row.changes["password_hash"] == {"before": "[redacted]", "after": "[redacted]"}


async def test_rollback_discards_data_and_audit_rows(session: AsyncSession) -> None:
    user = User.create(
        email=Email("ana@quermed.com"), full_name="Ana", role=Role.ADMIN, password_hash="h"
    )

    async with SqlAlchemyUnitOfWork(session) as uow:
        await uow.users.add(user)
        uow.audit.record(entity_type="user", entity_id=user.id, action="user.created")
        await uow.rollback()

    assert await count(session, UserModel) == 0
    assert await count(session, AuditLogModel) == 0


async def test_exception_inside_unit_of_work_rolls_back(session: AsyncSession) -> None:
    user = User.create(
        email=Email("ana@quermed.com"), full_name="Ana", role=Role.ADMIN, password_hash="h"
    )

    with pytest.raises(RuntimeError):
        async with SqlAlchemyUnitOfWork(session) as uow:
            await uow.users.add(user)
            uow.audit.record(entity_type="user", entity_id=user.id, action="user.created")
            raise RuntimeError("boom")

    assert await count(session, UserModel) == 0
    assert await count(session, AuditLogModel) == 0
