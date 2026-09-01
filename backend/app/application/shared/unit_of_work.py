"""Unit of work protocol: one transaction, repositories and the audit collector."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.domain.accounts.repository import AccountRepository
from app.domain.activities.repository import ActivityRepository
from app.domain.catalogue.repository import ProductRepository
from app.domain.contacts.repository import ContactRepository, PersonalDataAccessLog
from app.domain.notifications.entities import Notification, NotificationKind
from app.domain.notifications.repository import NotificationRepository
from app.domain.opportunities.repository import OpportunityRepository
from app.domain.quotes.repository import (
    AppSettingsRepository,
    MailOutboxRepository,
    QuoteRepository,
)
from app.domain.reference.repository import (
    BrandRepository,
    JobTitleRepository,
    LossReasonRepository,
    PipelineRepository,
    ProductFamilyRepository,
    ReferenceReadRepository,
    SpecialtyRepository,
)
from app.domain.shared.audit import AuditEvent, FieldChange, JsonValue
from app.domain.shared.ids import new_id
from app.domain.territories.repository import DivisionRepository, TerritoryRepository
from app.domain.users.repository import RefreshTokenRepository, UserRepository
from app.infrastructure.logging import get_request_context


class AuditCollector:
    """Collects audit events during a use case; the unit of work persists them on commit."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(
        self,
        *,
        entity_type: str,
        entity_id: UUID | None,
        action: str,
        changes: dict[str, FieldChange] | None = None,
        actor_id: UUID | None = None,
    ) -> AuditEvent:
        context = get_request_context()
        resolved_actor = actor_id
        if resolved_actor is None and context.actor_id is not None:
            resolved_actor = UUID(context.actor_id)
        event = AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes or {},
            actor_id=resolved_actor,
            trace_id=context.trace_id,
            occurred_at=datetime.now(UTC),
        )
        self.events.append(event)
        return event

    def drain(self) -> list[AuditEvent]:
        events, self.events = self.events, []
        return events


class NotificationCollector:
    """Collects notices during a use case; the unit of work persists them on commit.

    Mirrors `AuditCollector` on purpose: a notice must be committed with the change that
    caused it, so it can never announce something that was rolled back.
    """

    def __init__(self) -> None:
        self.pending: list[Notification] = []

    def notify(
        self,
        *,
        user_id: UUID,
        kind: NotificationKind,
        entity_type: str,
        entity_id: UUID | None,
        actor_id: UUID | None,
        payload: dict[str, JsonValue] | None = None,
    ) -> Notification | None:
        """Queue a notice, unless the actor is the recipient.

        A rep plans their own week: if their own work filled the block, the one notice
        that came from somebody else would be lost in it.
        """
        if actor_id is not None and actor_id == user_id:
            return None
        notification = Notification(
            id=new_id(),
            user_id=user_id,
            kind=kind,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            payload=payload or {},
            created_at=datetime.now(UTC),
        )
        self.pending.append(notification)
        return notification

    def drain(self) -> list[Notification]:
        pending, self.pending = self.pending, []
        return pending


class UnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...

    @property
    def territories(self) -> TerritoryRepository: ...

    @property
    def divisions(self) -> DivisionRepository: ...

    @property
    def refresh_tokens(self) -> RefreshTokenRepository: ...

    @property
    def brands(self) -> BrandRepository: ...

    @property
    def loss_reasons(self) -> LossReasonRepository: ...

    @property
    def pipelines(self) -> PipelineRepository: ...

    @property
    def reference(self) -> ReferenceReadRepository: ...

    @property
    def job_titles(self) -> JobTitleRepository: ...

    @property
    def specialties(self) -> SpecialtyRepository: ...

    @property
    def notification_inbox(self) -> NotificationRepository: ...

    @property
    def product_families(self) -> ProductFamilyRepository: ...

    @property
    def products(self) -> ProductRepository: ...

    @property
    def accounts(self) -> AccountRepository: ...

    @property
    def contacts(self) -> ContactRepository: ...

    @property
    def personal_data_access(self) -> PersonalDataAccessLog: ...

    @property
    def activities(self) -> ActivityRepository: ...

    @property
    def opportunities(self) -> OpportunityRepository: ...

    @property
    def quotes(self) -> QuoteRepository: ...

    @property
    def mail_outbox(self) -> MailOutboxRepository: ...

    @property
    def app_settings(self) -> AppSettingsRepository: ...

    @property
    def audit(self) -> AuditCollector: ...

    @property
    def notifications(self) -> NotificationCollector: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
