"""Opportunity use cases: creation with smart defaults, pipeline commands and lines."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.application.accounts.service import load_visible_account
from app.application.opportunities.commands import (
    AddLine,
    CreateOpportunity,
    LoseOpportunity,
    UpdateLine,
    UpdateOpportunity,
    WinOpportunity,
)
from app.application.shared.scope import user_scope
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.accounts.entities import Account
from app.domain.accounts.errors import AssignmentForbiddenError, OwnerNotSalesRepError
from app.domain.notifications.entities import NotificationKind
from app.domain.opportunities.entities import (
    AtRiskSource,
    Opportunity,
    StageChange,
)
from app.domain.opportunities.errors import PipelineRequiredError, ReopenForbiddenError
from app.domain.reference.entities import LossReason, Pipeline
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.shared.policies import VisibilityPolicy
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role

MANAGER_ROLES = frozenset({Role.ADMIN, Role.SALES_MANAGER})

UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "description",
        "estimated_amount",
        "expected_close_date",
        "is_tender",
        "tender_reference",
        "tender_deadline",
        "estimated_award_date",
    }
)


@dataclass(frozen=True)
class OpportunityDetail:
    opportunity: Opportunity
    history: list[StageChange]


def ensure_opportunity_writer(actor: User, opportunity: Opportunity) -> None:
    if actor.role in MANAGER_ROLES:
        return
    if actor.role == Role.SALES_REP and actor.id == opportunity.owner_id:
        return
    raise PermissionDeniedError("Only the owner or sales management can modify the opportunity")


def utc_now() -> datetime:
    return datetime.now(UTC)


class OpportunityService:
    def __init__(self, uow: UnitOfWork, *, clock: type[datetime] | None = None) -> None:
        self._uow = uow
        self._clock = clock

    def _now(self) -> datetime:
        return self._clock.now(UTC) if self._clock else utc_now()

    # --- reads -----------------------------------------------------------

    async def get(self, opportunity_id: UUID, *, actor: User) -> OpportunityDetail:
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            history = await uow.opportunities.list_history(opportunity.id)
            return OpportunityDetail(opportunity, history)

    # --- creation --------------------------------------------------------

    async def create(self, command: CreateOpportunity, *, actor: User) -> Opportunity:
        if actor.role == Role.BACK_OFFICE:
            raise PermissionDeniedError("Back office reads the pipeline but never writes it")
        now = self._now()
        async with self._uow as uow:
            account = await load_visible_account(uow, command.account_id, actor)
            division_name = await self._division_name(uow, command.division_id)
            pipeline = await self._pipeline_for(uow, command.pipeline_id, command.division_id)
            owner_id = await self._owner(uow, actor, account, command.owner_id)
            opportunity, change = Opportunity.create(
                account_id=account.id,
                account_name=account.name,
                buys_via_tender=await self._buys_via_tender(uow, account),
                division_id=command.division_id,
                division_name=division_name,
                pipeline=pipeline,
                estimated_amount=command.estimated_amount,
                owner_id=owner_id,
                created_by=actor.id,
                now=now,
                name=command.name,
                description=command.description,
                expected_close_date=command.expected_close_date,
                is_tender=command.is_tender,
                tender_reference=command.tender_reference,
                tender_deadline=command.tender_deadline,
                estimated_award_date=command.estimated_award_date,
            )
            await uow.opportunities.add(opportunity)
            await uow.opportunities.add_stage_change(change)
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.created",
                changes=diff_fields({}, opportunity.snapshot()),
                actor_id=actor.id,
            )
            await uow.commit()
            return opportunity

    # --- editing ---------------------------------------------------------

    async def update(
        self, opportunity_id: UUID, command: UpdateOpportunity, *, actor: User
    ) -> Opportunity:
        changes = dict(command.changes)
        unknown = set(changes) - UPDATABLE_FIELDS
        if unknown:
            raise PermissionDeniedError(
                f"Fields cannot be changed here: {', '.join(sorted(unknown))}"
            )
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            before = opportunity.snapshot()
            if "name" in changes and changes["name"] is not None:
                opportunity.rename(str(changes["name"]))
            if "description" in changes:
                opportunity.set_description(changes["description"])
            if "estimated_amount" in changes and changes["estimated_amount"] is not None:
                opportunity.set_estimated_amount(changes["estimated_amount"])
            if "expected_close_date" in changes and changes["expected_close_date"] is not None:
                opportunity.set_expected_close_date(changes["expected_close_date"])
            tender_keys = {
                "is_tender",
                "tender_reference",
                "tender_deadline",
                "estimated_award_date",
            }
            if tender_keys & changes.keys():
                opportunity.set_tender(
                    is_tender=changes.get("is_tender"),
                    tender_reference=changes.get("tender_reference", ...),
                    tender_deadline=changes.get("tender_deadline", ...),
                    estimated_award_date=changes.get("estimated_award_date", ...),
                )
            await uow.opportunities.save(opportunity, expected_version=command.expected_version)
            diff = diff_fields(before, opportunity.snapshot())
            if diff:
                uow.audit.record(
                    entity_type="opportunity",
                    entity_id=opportunity.id,
                    action="opportunity.updated",
                    changes=diff,
                    actor_id=actor.id,
                )
            await uow.commit()
            return opportunity

    # --- lifecycle -------------------------------------------------------

    async def move_stage(
        self, opportunity_id: UUID, stage_id: UUID, *, expected_version: int, actor: User
    ) -> Opportunity:
        now = self._now()
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            pipeline = await self._pipeline(uow, opportunity.pipeline_id)
            change = opportunity.move_stage(pipeline, stage_id, actor_id=actor.id, now=now)
            await self._persist_change(uow, opportunity, change, expected_version)
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.stage_changed",
                changes={"stage_id": {"before": str(change.from_stage_id), "after": str(stage_id)}},
                actor_id=actor.id,
            )
            await uow.commit()
            return opportunity

    async def win(
        self, opportunity_id: UUID, command: WinOpportunity, *, actor: User
    ) -> Opportunity:
        now = self._now()
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            pipeline = await self._pipeline(uow, opportunity.pipeline_id)
            change = opportunity.win(
                pipeline,
                actor_id=actor.id,
                now=now,
                won_amount=command.won_amount,
                won_at=command.won_at,
            )
            await self._persist_change(uow, opportunity, change, command.expected_version)
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.won",
                changes=diff_fields(
                    {"won_amount": None, "won_at": None},
                    {"won_amount": str(opportunity.won_amount), "won_at": opportunity.won_at},
                ),
                actor_id=actor.id,
            )
            await uow.commit()
            return opportunity

    async def lose(
        self, opportunity_id: UUID, command: LoseOpportunity, *, actor: User
    ) -> Opportunity:
        now = self._now()
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            pipeline = await self._pipeline(uow, opportunity.pipeline_id)
            reason = await self._loss_reason(uow, command.loss_reason_id)
            if command.competitor_brand_id is not None:
                brand = await uow.brands.get(command.competitor_brand_id)
                if brand is None:
                    raise UnknownReferenceError(
                        "competitor_brand_id", [str(command.competitor_brand_id)]
                    )
            change = opportunity.lose(
                pipeline,
                loss_reason_id=reason.id,
                requires_brand=reason.requires_brand,
                requires_note=reason.requires_note,
                actor_id=actor.id,
                now=now,
                competitor_brand_id=command.competitor_brand_id,
                note=command.note,
            )
            await self._persist_change(uow, opportunity, change, command.expected_version)
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.lost",
                changes=diff_fields(
                    {"loss_reason_id": None, "competitor_brand_id": None, "loss_note": None},
                    {
                        "loss_reason_id": opportunity.loss_reason_id,
                        "competitor_brand_id": opportunity.competitor_brand_id,
                        "loss_note": opportunity.loss_note,
                    },
                ),
                actor_id=actor.id,
            )
            await uow.commit()
            return opportunity

    async def reopen(
        self, opportunity_id: UUID, stage_id: UUID, *, expected_version: int, actor: User
    ) -> Opportunity:
        if actor.role not in MANAGER_ROLES:
            raise ReopenForbiddenError()
        now = self._now()
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            pipeline = await self._pipeline(uow, opportunity.pipeline_id)
            change = opportunity.reopen(pipeline, stage_id, actor_id=actor.id, now=now)
            await self._persist_change(uow, opportunity, change, expected_version)
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.reopened",
                changes={"stage_id": {"before": str(change.from_stage_id), "after": str(stage_id)}},
                actor_id=actor.id,
            )
            await uow.commit()
            return opportunity

    async def set_at_risk(
        self, opportunity_id: UUID, flag: bool, *, expected_version: int, actor: User
    ) -> Opportunity:
        now = self._now()
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            pipeline = await self._pipeline(uow, opportunity.pipeline_id)
            change = opportunity.set_at_risk(
                pipeline, flag, source=AtRiskSource.MANUAL, actor_id=actor.id, now=now
            )
            if change is None:
                return opportunity
            await self._persist_change(uow, opportunity, change, expected_version)
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.at_risk_set" if flag else "opportunity.at_risk_cleared",
                changes={"at_risk_source": {"before": None, "after": "manual"}},
                actor_id=actor.id,
            )
            await uow.commit()
            return opportunity

    async def assign(
        self, opportunity_id: UUID, owner_id: UUID, *, expected_version: int, actor: User
    ) -> Opportunity:
        if actor.role not in MANAGER_ROLES:
            raise AssignmentForbiddenError()
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            await self._ensure_sales_rep(uow, owner_id)
            before = opportunity.owner_id
            opportunity.owner_id = owner_id
            await uow.opportunities.save(opportunity, expected_version=expected_version)
            if owner_id != before:
                # Only the new owner: nothing was put on the previous one's plate.
                uow.notifications.notify(
                    user_id=owner_id,
                    kind=NotificationKind.OPPORTUNITY_ASSIGNED,
                    entity_type="opportunity",
                    entity_id=opportunity.id,
                    actor_id=actor.id,
                    payload={"name": opportunity.name},
                )
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.reassigned",
                changes={"owner_id": {"before": str(before), "after": str(owner_id)}},
                actor_id=actor.id,
            )
            await uow.commit()
            return opportunity

    # --- lines -----------------------------------------------------------

    async def add_line(self, opportunity_id: UUID, command: AddLine, *, actor: User) -> Opportunity:
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            product = await uow.products.get(command.product_id)
            if product is None:
                raise UnknownReferenceError("product_id", [str(command.product_id)])
            line = opportunity.add_line(
                product_id=product.id,
                quantity=command.quantity,
                unit_price=(
                    command.unit_price if command.unit_price is not None else product.list_price
                ),
                product_active=product.is_active,
            )
            await uow.opportunities.save(opportunity, expected_version=command.expected_version)
            self._audit_line(uow, opportunity, actor, "opportunity.line_added", line.id)
            await uow.commit()
            return opportunity

    async def update_line(
        self, opportunity_id: UUID, line_id: UUID, command: UpdateLine, *, actor: User
    ) -> Opportunity:
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            opportunity.update_line(
                line_id, quantity=command.quantity, unit_price=command.unit_price
            )
            await uow.opportunities.save(opportunity, expected_version=command.expected_version)
            self._audit_line(uow, opportunity, actor, "opportunity.line_updated", line_id)
            await uow.commit()
            return opportunity

    async def remove_line(
        self, opportunity_id: UUID, line_id: UUID, *, expected_version: int, actor: User
    ) -> Opportunity:
        async with self._uow as uow:
            opportunity, _ = await self._load(uow, opportunity_id, actor)
            ensure_opportunity_writer(actor, opportunity)
            opportunity.remove_line(line_id)
            await uow.opportunities.save(opportunity, expected_version=expected_version)
            self._audit_line(uow, opportunity, actor, "opportunity.line_removed", line_id)
            await uow.commit()
            return opportunity

    # --- helpers ---------------------------------------------------------

    @staticmethod
    async def _load(
        uow: UnitOfWork, opportunity_id: UUID, actor: User
    ) -> tuple[Opportunity, Account]:
        opportunity = await uow.opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError("Opportunity not found")
        try:
            account = await load_visible_account(uow, opportunity.account_id, actor)
        except NotFoundError as error:
            raise NotFoundError("Opportunity not found") from error
        return opportunity, account

    @staticmethod
    async def _persist_change(
        uow: UnitOfWork,
        opportunity: Opportunity,
        change: StageChange,
        expected_version: int,
    ) -> None:
        await uow.opportunities.save(opportunity, expected_version=expected_version)
        await uow.opportunities.add_stage_change(change)

    @staticmethod
    def _audit_line(
        uow: UnitOfWork, opportunity: Opportunity, actor: User, action: str, line_id: UUID
    ) -> None:
        uow.audit.record(
            entity_type="opportunity",
            entity_id=opportunity.id,
            action=action,
            changes={
                "line_id": {"before": None, "after": str(line_id)},
                "amount": {"before": None, "after": str(opportunity.amount)},
            },
            actor_id=actor.id,
        )

    @staticmethod
    async def _pipeline(uow: UnitOfWork, pipeline_id: UUID) -> Pipeline:
        pipeline = await uow.pipelines.get(pipeline_id)
        if pipeline is None:
            raise UnknownReferenceError("pipeline_id", [str(pipeline_id)])
        return pipeline

    @staticmethod
    async def _pipeline_for(
        uow: UnitOfWork, pipeline_id: UUID | None, division_id: UUID
    ) -> Pipeline:
        if pipeline_id is not None:
            return await OpportunityService._pipeline(uow, pipeline_id)
        for pipeline in await uow.pipelines.list_all():
            if division_id in pipeline.division_ids:
                return pipeline
        raise PipelineRequiredError()

    @staticmethod
    async def _division_name(uow: UnitOfWork, division_id: UUID) -> str:
        for division in await uow.divisions.list_all():
            if division.id == division_id:
                return division.name_es
        raise UnknownReferenceError("division_id", [str(division_id)])

    @staticmethod
    async def _buys_via_tender(uow: UnitOfWork, account: Account) -> bool:
        for account_type in await uow.reference.account_types():
            if account_type.id == account.account_type_id:
                return account_type.buys_via_tender
        return False

    @staticmethod
    async def _loss_reason(uow: UnitOfWork, loss_reason_id: UUID) -> LossReason:
        reason = await uow.loss_reasons.get(loss_reason_id)
        if reason is None:
            raise UnknownReferenceError("loss_reason_id", [str(loss_reason_id)])
        return reason

    @staticmethod
    async def _ensure_sales_rep(uow: UnitOfWork, owner_id: UUID) -> None:
        owner = await uow.users.get(owner_id)
        if owner is None or not owner.is_active or owner.role is not Role.SALES_REP:
            raise OwnerNotSalesRepError()

    async def _owner(
        self, uow: UnitOfWork, actor: User, account: Account, owner_id: UUID | None
    ) -> UUID:
        if owner_id is not None:
            if actor.role not in MANAGER_ROLES:
                raise AssignmentForbiddenError()
            await self._ensure_sales_rep(uow, owner_id)
            return owner_id
        if actor.role == Role.SALES_REP:
            scope = await user_scope(uow, actor)
            if VisibilityPolicy.can_write(actor, scope, account):
                return actor.id
            return account.owner_id or actor.id
        return account.owner_id or actor.id
