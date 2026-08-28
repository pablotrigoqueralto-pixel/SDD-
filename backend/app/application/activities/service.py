"""Activity use cases: capture, plan, complete, cancel, reschedule — all scoped by the account."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.application.accounts.service import ensure_account_writer, load_visible_account
from app.application.activities.commands import (
    CancelActivity,
    CompleteActivity,
    CreateActivity,
    RescheduleActivity,
    UpdateActivity,
)
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.accounts.entities import Account
from app.domain.accounts.errors import AssignmentForbiddenError, OwnerNotSalesRepError
from app.domain.activities.entities import Activity, ActivityKind, ActivityStatus, NextAction
from app.domain.activities.errors import ContactNotInAccountError
from app.domain.opportunities.entities import AtRiskSource
from app.domain.opportunities.errors import OpportunityNotInAccountError
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role

NOTE_CODE = "note"
MANAGER_ROLES = frozenset({Role.ADMIN, Role.SALES_MANAGER})


@dataclass(frozen=True)
class ActivityResult:
    activity: Activity
    next_activity: Activity | None = None


def utc_now() -> datetime:
    return datetime.now(UTC)


class ActivityService:
    def __init__(self, uow: UnitOfWork, *, clock: type[datetime] | None = None) -> None:
        self._uow = uow
        self._clock = clock

    def _now(self) -> datetime:
        return self._clock.now(UTC) if self._clock else utc_now()

    # --- reads -----------------------------------------------------------

    async def get(self, activity_id: UUID, *, actor: User) -> Activity:
        async with self._uow as uow:
            activity, _ = await self._load(uow, activity_id, actor)
            return activity

    # --- writes ----------------------------------------------------------

    async def create(self, command: CreateActivity, *, actor: User) -> ActivityResult:
        now = self._now()
        async with self._uow as uow:
            account = await load_visible_account(uow, command.account_id, actor)
            await ensure_account_writer(uow, actor, account)
            kind = await self._kind(uow, command.activity_type_id)
            owner_id = await self._owner(uow, actor, command.owner_id)
            await self._check_contacts(uow, account.id, command.details.get("contact_ids"))
            await self._check_opportunity(uow, account.id, command.opportunity_id)
            if command.status is ActivityStatus.PLANNED:
                activity = Activity.plan(
                    account_id=account.id,
                    kind=kind,
                    owner_id=owner_id,
                    created_by=actor.id,
                    scheduled_at=command.scheduled_at or now,
                    details=command.details,
                )
            else:
                activity = Activity.record_done(
                    account_id=account.id,
                    kind=kind,
                    owner_id=owner_id,
                    created_by=actor.id,
                    now=now,
                    scheduled_at=command.scheduled_at,
                    details=command.details,
                )
            activity.opportunity_id = command.opportunity_id
            await uow.activities.add(activity)
            self._audit_created(uow, activity, actor)
            follow_up = await self._follow_up(uow, activity, command.next_action, actor, now)
            if activity.status is ActivityStatus.DONE:
                await self._clear_automatic_at_risk(uow, activity.opportunity_id, actor, now)
            await uow.accounts.refresh_activity_summary(account.id)
            await uow.commit()
            return ActivityResult(activity, follow_up)

    async def update(self, activity_id: UUID, command: UpdateActivity, *, actor: User) -> Activity:
        now = self._now()
        async with self._uow as uow:
            activity, account = await self._load(uow, activity_id, actor)
            await ensure_account_writer(uow, actor, account)
            activity.ensure_editable(actor, now=now)
            changes = dict(command.changes)
            if "activity_type_id" in changes and changes["activity_type_id"] is not None:
                await self._kind(uow, changes["activity_type_id"])
            if "contact_ids" in changes:
                await self._check_contacts(uow, account.id, changes["contact_ids"])
            before = activity.snapshot()
            if "opportunity_id" in changes:
                await self._check_opportunity(uow, account.id, changes["opportunity_id"])
                activity.opportunity_id = changes["opportunity_id"]
            activity.update_details(changes)
            await uow.activities.save(activity, expected_version=command.expected_version)
            diff = diff_fields(before, activity.snapshot())
            if diff:
                uow.audit.record(
                    entity_type="activity",
                    entity_id=activity.id,
                    action="activity.updated",
                    changes=diff,
                    actor_id=actor.id,
                )
            await uow.accounts.refresh_activity_summary(account.id)
            await uow.commit()
            return activity

    async def complete(
        self, activity_id: UUID, command: CompleteActivity, *, actor: User
    ) -> ActivityResult:
        now = self._now()
        async with self._uow as uow:
            activity, account = await self._load(uow, activity_id, actor)
            await ensure_account_writer(uow, actor, account)
            activity.ensure_editable(actor, now=now)
            activity.complete(
                now=now,
                done_at=command.done_at,
                outcome=command.outcome,
                notes=command.notes,
                duration_minutes=command.duration_minutes,
            )
            await uow.activities.save(activity, expected_version=command.expected_version)
            uow.audit.record(
                entity_type="activity",
                entity_id=activity.id,
                action="activity.completed",
                changes=diff_fields(
                    {"status": ActivityStatus.PLANNED, "done_at": None, "outcome": None},
                    {
                        "status": activity.status,
                        "done_at": activity.done_at,
                        "outcome": activity.outcome,
                    },
                ),
                actor_id=actor.id,
            )
            follow_up = await self._follow_up(uow, activity, command.next_action, actor, now)
            await self._clear_automatic_at_risk(uow, activity.opportunity_id, actor, now)
            await uow.accounts.refresh_activity_summary(account.id)
            await uow.commit()
            return ActivityResult(activity, follow_up)

    async def cancel(self, activity_id: UUID, command: CancelActivity, *, actor: User) -> Activity:
        now = self._now()
        async with self._uow as uow:
            activity, account = await self._load(uow, activity_id, actor)
            await ensure_account_writer(uow, actor, account)
            activity.ensure_editable(actor, now=now)
            activity.cancel(command.reason)
            await uow.activities.save(activity, expected_version=command.expected_version)
            uow.audit.record(
                entity_type="activity",
                entity_id=activity.id,
                action="activity.cancelled",
                changes=diff_fields(
                    {"status": ActivityStatus.PLANNED, "cancel_reason": None},
                    {"status": activity.status, "cancel_reason": activity.cancel_reason},
                ),
                actor_id=actor.id,
            )
            await uow.accounts.refresh_activity_summary(account.id)
            await uow.commit()
            return activity

    async def reschedule(
        self, activity_id: UUID, command: RescheduleActivity, *, actor: User
    ) -> Activity:
        now = self._now()
        async with self._uow as uow:
            activity, account = await self._load(uow, activity_id, actor)
            await ensure_account_writer(uow, actor, account)
            activity.ensure_editable(actor, now=now)
            before = activity.scheduled_at
            activity.reschedule(command.scheduled_at)
            await uow.activities.save(activity, expected_version=command.expected_version)
            uow.audit.record(
                entity_type="activity",
                entity_id=activity.id,
                action="activity.rescheduled",
                changes=diff_fields(
                    {"scheduled_at": before}, {"scheduled_at": activity.scheduled_at}
                ),
                actor_id=actor.id,
            )
            await uow.accounts.refresh_activity_summary(account.id)
            await uow.commit()
            return activity

    # --- helpers ---------------------------------------------------------

    @staticmethod
    async def _load(uow: UnitOfWork, activity_id: UUID, actor: User) -> tuple[Activity, Account]:
        activity = await uow.activities.get(activity_id)
        if activity is None:
            raise NotFoundError("Activity not found")
        try:
            account = await load_visible_account(uow, activity.account_id, actor)
        except NotFoundError:
            raise NotFoundError("Activity not found") from None
        return activity, account

    @staticmethod
    async def _kind(uow: UnitOfWork, activity_type_id: UUID) -> ActivityKind:
        for activity_type in await uow.reference.activity_types():
            if activity_type.id == activity_type_id:
                return ActivityKind(
                    id=activity_type.id,
                    is_note=activity_type.code == NOTE_CODE,
                    counts_as_contact=activity_type.counts_as_contact,
                )
        raise UnknownReferenceError("activity_type_id", [str(activity_type_id)])

    @staticmethod
    async def _owner(uow: UnitOfWork, actor: User, owner_id: UUID | None) -> UUID:
        if owner_id is None or owner_id == actor.id:
            return actor.id
        if actor.role not in MANAGER_ROLES:
            raise AssignmentForbiddenError()
        owner = await uow.users.get(owner_id)
        if owner is None or not owner.is_active:
            raise OwnerNotSalesRepError()
        return owner.id

    @staticmethod
    async def _check_contacts(
        uow: UnitOfWork, account_id: UUID, contact_ids: Iterable[object] | None
    ) -> None:
        ids = [UUID(str(c)) for c in (contact_ids or [])]
        if ids and not await uow.activities.contacts_belong_to(account_id, ids):
            raise ContactNotInAccountError()

    async def _follow_up(
        self,
        uow: UnitOfWork,
        activity: Activity,
        next_action: NextAction | None,
        actor: User,
        now: datetime,
    ) -> Activity | None:
        if next_action is None:
            return None
        kind = await self._kind(uow, next_action.activity_type_id)
        follow_up = activity.follow_up(next_action, now=now, is_note=kind.is_note)
        await uow.activities.add(follow_up)
        self._audit_created(uow, follow_up, actor)
        return follow_up

    @staticmethod
    async def _check_opportunity(
        uow: UnitOfWork, account_id: UUID, opportunity_id: UUID | None
    ) -> None:
        if opportunity_id is None:
            return
        opportunity = await uow.opportunities.get(opportunity_id)
        if opportunity is None:
            raise UnknownReferenceError("opportunity_id", [str(opportunity_id)])
        if opportunity.account_id != account_id:
            raise OpportunityNotInAccountError()

    async def _clear_automatic_at_risk(
        self, uow: UnitOfWork, opportunity_id: UUID | None, actor: User, now: datetime
    ) -> None:
        """A done activity on an automatically flagged opportunity clears the flag."""
        if opportunity_id is None:
            return
        opportunity = await uow.opportunities.get(opportunity_id)
        if opportunity is None or opportunity.at_risk_source is not AtRiskSource.AUTOMATIC:
            return
        pipeline = await uow.pipelines.get(opportunity.pipeline_id)
        if pipeline is None:
            return
        change = opportunity.set_at_risk(
            pipeline, False, source=AtRiskSource.MANUAL, actor_id=actor.id, now=now
        )
        if change is None:
            return
        await uow.opportunities.save(opportunity, expected_version=opportunity.version)
        await uow.opportunities.add_stage_change(change)
        uow.audit.record(
            entity_type="opportunity",
            entity_id=opportunity.id,
            action="opportunity.at_risk_cleared",
            changes={"at_risk_source": {"before": "automatic", "after": None}},
            actor_id=actor.id,
        )

    @staticmethod
    def _audit_created(uow: UnitOfWork, activity: Activity, actor: User) -> None:
        uow.audit.record(
            entity_type="activity",
            entity_id=activity.id,
            action="activity.created",
            changes=diff_fields({}, activity.snapshot()),
            actor_id=actor.id,
        )
