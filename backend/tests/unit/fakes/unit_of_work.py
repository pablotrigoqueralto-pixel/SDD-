from types import TracebackType
from typing import Self

from app.application.shared.unit_of_work import AuditCollector
from app.domain.shared.audit import AuditEvent
from tests.unit.fakes.accounts import (
    InMemoryAccountRepository,
    InMemoryActivityRepository,
    InMemoryContactRepository,
    InMemoryJobTitleRepository,
    InMemoryPersonalDataAccessLog,
)
from tests.unit.fakes.catalogue import (
    InMemoryProductFamilyRepository,
    InMemoryProductRepository,
)
from tests.unit.fakes.opportunities import InMemoryOpportunityRepository
from tests.unit.fakes.reference import (
    InMemoryBrandRepository,
    InMemoryLossReasonRepository,
    InMemoryPipelineRepository,
    InMemoryReferenceReadRepository,
)
from tests.unit.fakes.repositories import (
    InMemoryDivisionRepository,
    InMemoryRefreshTokenRepository,
    InMemoryTerritoryRepository,
    InMemoryUserRepository,
)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.territories = InMemoryTerritoryRepository()
        self.divisions = InMemoryDivisionRepository()
        self.refresh_tokens = InMemoryRefreshTokenRepository()
        self.brands = InMemoryBrandRepository()
        self.loss_reasons = InMemoryLossReasonRepository()
        self.pipelines = InMemoryPipelineRepository()
        self.reference = InMemoryReferenceReadRepository()
        self.job_titles = InMemoryJobTitleRepository()
        self.product_families = InMemoryProductFamilyRepository()
        self.products = InMemoryProductRepository()
        self.accounts = InMemoryAccountRepository()
        self.contacts = InMemoryContactRepository()
        self.personal_data_access = InMemoryPersonalDataAccessLog()
        self.activities = InMemoryActivityRepository()
        self.accounts.activities = self.activities
        self.opportunities = InMemoryOpportunityRepository()
        self.opportunities.activities = self.activities
        self.audit = AuditCollector()
        self.committed_events: list[AuditEvent] = []
        self.commits = 0
        self.rollbacks = 0

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
        self.committed_events.extend(self.audit.drain())
        self.commits += 1

    async def rollback(self) -> None:
        self.audit.drain()
        self.rollbacks += 1

    def actions(self) -> list[str]:
        return [event.action for event in self.committed_events]
