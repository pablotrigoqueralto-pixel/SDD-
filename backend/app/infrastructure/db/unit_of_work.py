"""SQLAlchemy unit of work: one session, one transaction, audit flushed on commit."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.unit_of_work import AuditCollector
from app.infrastructure.db.repositories.audit import SqlAlchemyAuditLogWriter
from app.infrastructure.db.repositories.territories import (
    SqlAlchemyDivisionRepository,
    SqlAlchemyTerritoryRepository,
)
from app.infrastructure.db.repositories.users import (
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = SqlAlchemyUserRepository(session)
        self.territories = SqlAlchemyTerritoryRepository(session)
        self.divisions = SqlAlchemyDivisionRepository(session)
        self.refresh_tokens = SqlAlchemyRefreshTokenRepository(session)
        self.audit = AuditCollector()
        self._audit_writer = SqlAlchemyAuditLogWriter(session)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        # Audit rows share the transaction with the data they describe.
        await self._audit_writer.write(self.audit.drain())
        await self._session.commit()

    async def rollback(self) -> None:
        self.audit.drain()
        await self._session.rollback()
