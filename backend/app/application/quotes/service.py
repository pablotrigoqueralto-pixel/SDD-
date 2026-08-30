"""Quote use cases: creation from an opportunity, drafts, send, accept, versions."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.accounts.service import load_visible_account
from app.application.quotes.commands import (
    AcceptQuote,
    CreateQuote,
    QuoteLineInput,
    RejectQuote,
    SendQuote,
    UpdateQuoteDraft,
)
from app.application.quotes.mailer import QuoteMailer
from app.application.quotes.pdf import PdfLine, QuotePdfDocument, QuotePdfRenderer
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.accounts.entities import Account
from app.domain.opportunities.entities import Opportunity, OpportunityStatus
from app.domain.opportunities.errors import OpportunityClosedError
from app.domain.quotes.entities import Quote, QuoteConditions, QuoteLineDraft
from app.domain.quotes.errors import (
    EmailRetryNotAvailableError,
    OpportunityAlreadyClosedError,
    QuoteActionForbiddenError,
    QuoteRecipientsRequiredError,
)
from app.domain.quotes.mail import MailRecipient, OutboxEntry, OutboxStatus
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import (
    FieldError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role

MANAGER_ROLES = frozenset({Role.ADMIN, Role.SALES_MANAGER})
MADRID = ZoneInfo("Europe/Madrid")

CONDITIONS_DEFAULTS_KEY = "quote_conditions_defaults"
EMAIL_TEMPLATE_KEY = "quote_email_template"


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_quote_writer(actor: User, opportunity: Opportunity, *, lifecycle: bool) -> None:
    """Draft work admits back office; lifecycle actions belong to the owner and management."""
    if actor.role in MANAGER_ROLES:
        return
    if actor.role == Role.SALES_REP and actor.id == opportunity.owner_id:
        return
    if actor.role == Role.BACK_OFFICE:
        if lifecycle:
            raise QuoteActionForbiddenError()
        return
    raise PermissionDeniedError("Only the owner or sales management can work on quotes")


def conditions_from(raw: dict[str, object] | None) -> QuoteConditions:
    values = raw or {}
    return QuoteConditions(
        validez_dias=int(str(values.get("validez_dias") or 30)),
        plazo_entrega=_optional_str(values.get("plazo_entrega")),
        forma_pago=_optional_str(values.get("forma_pago")),
        garantia=_optional_str(values.get("garantia")),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def build_pdf_document(uow: UnitOfWork, quote: Quote, account: Account) -> QuotePdfDocument:
    owner = await uow.users.get(quote.owner_id)
    contact_name: str | None = None
    if quote.contact_id is not None:
        contact = await uow.contacts.get(quote.contact_id)
        if contact is not None:
            contact_name = contact.full_name
    return QuotePdfDocument(
        display_number=quote.display_number,
        issued_on=(quote.sent_at or quote.created_at or utc_now()).astimezone(MADRID).date(),
        valid_until=quote.valid_until,
        account_name=account.name,
        account_province=account.province_code,
        contact_name=contact_name,
        owner_name=owner.full_name if owner else "",
        owner_email=str(owner.email) if owner else "",
        conditions=quote.conditions,
        lines=[
            PdfLine(
                description=line.description,
                product_code=line.product_code,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                vat_rate=line.vat_rate,
                base=line.base,
            )
            for line in quote.lines
        ],
        vat_breakdown=quote.vat_breakdown(),
        total_base=quote.total_base,
        total_vat=quote.total_vat,
        total=quote.total,
    )


class QuoteService:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        mailer: QuoteMailer,
        pdf_renderer: QuotePdfRenderer,
        clock: type[datetime] | None = None,
    ) -> None:
        self._uow = uow
        self._mailer = mailer
        self._pdf_renderer = pdf_renderer
        self._clock = clock

    def _now(self) -> datetime:
        return self._clock.now(UTC) if self._clock else utc_now()

    # --- reads -----------------------------------------------------------

    async def get(self, quote_id: UUID, *, actor: User) -> tuple[Quote, Opportunity, Account]:
        async with self._uow as uow:
            return await self._load(uow, quote_id, actor)

    async def ensure_opportunity_visible(self, opportunity_id: UUID, *, actor: User) -> None:
        async with self._uow as uow:
            await self._load_opportunity(uow, opportunity_id, actor)

    # --- creation --------------------------------------------------------

    async def create(self, command: CreateQuote, *, actor: User) -> Quote:
        now = self._now()
        async with self._uow as uow:
            opportunity, _ = await self._load_opportunity(uow, command.opportunity_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=False)
            if opportunity.status is not OpportunityStatus.OPEN:
                raise OpportunityClosedError()
            drafts: list[QuoteLineDraft] = []
            for line in opportunity.lines:
                product = await uow.products.get(line.product_id)
                drafts.append(
                    QuoteLineDraft(
                        description=product.name if product else "Producto",
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        product_id=line.product_id,
                        product_code=product.sku if product else None,
                        unit_cost=product.cost_price if product else None,
                    )
                )
            year = now.astimezone(MADRID).year
            number = await uow.quotes.allocate_number(year)
            quote = Quote.create(
                opportunity_id=opportunity.id,
                owner_id=opportunity.owner_id,
                created_by=actor.id,
                year=year,
                number=number,
                conditions=conditions_from(await uow.app_settings.get(CONDITIONS_DEFAULTS_KEY)),
                lines=drafts,
                now=now,
                contact_id=command.contact_id,
            )
            await uow.quotes.add(quote)
            uow.audit.record(
                entity_type="quote",
                entity_id=quote.id,
                action="quote.created",
                changes=diff_fields({}, quote.snapshot()),
                actor_id=actor.id,
            )
            await uow.commit()
            return quote

    # --- draft editing ---------------------------------------------------

    async def update_draft(
        self, quote_id: UUID, command: UpdateQuoteDraft, *, actor: User
    ) -> Quote:
        async with self._uow as uow:
            quote, opportunity, _ = await self._load(uow, quote_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=False)
            before = quote.snapshot()
            quote.update_draft(
                contact_id=command.contact_id,
                conditions=command.conditions,
                valid_until=command.valid_until,
            )
            if command.lines is not None:
                quote.replace_lines(await self._line_drafts(uow, command.lines))
            await uow.quotes.save(quote, expected_version=command.expected_version)
            diff = diff_fields(before, quote.snapshot())
            if diff:
                uow.audit.record(
                    entity_type="quote",
                    entity_id=quote.id,
                    action="quote.updated",
                    changes=diff,
                    actor_id=actor.id,
                )
            await uow.commit()
            return quote

    async def delete_draft(self, quote_id: UUID, *, actor: User) -> None:
        async with self._uow as uow:
            quote, opportunity, _ = await self._load(uow, quote_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=False)
            quote.ensure_deletable()
            await uow.quotes.delete(quote)
            uow.audit.record(
                entity_type="quote",
                entity_id=quote.id,
                action="quote.deleted",
                changes=diff_fields(quote.snapshot(), {}),
                actor_id=actor.id,
            )
            await uow.commit()

    # --- lifecycle -------------------------------------------------------

    async def send(self, quote_id: UUID, command: SendQuote, *, actor: User) -> Quote:
        now = self._now()
        emailing = self._mailer.enabled and not command.skip_email
        async with self._uow as uow:
            quote, opportunity, account = await self._load(uow, quote_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=True)
            if emailing and not command.recipients:
                raise QuoteRecipientsRequiredError()
            quote.send(now=now, valid_until=command.valid_until)
            await uow.quotes.save(quote, expected_version=command.expected_version)
            content = self._pdf_renderer.render(await build_pdf_document(uow, quote, account))
            await uow.quotes.store_pdf(quote.id, content)
            uow.audit.record(
                entity_type="quote",
                entity_id=quote.id,
                action="quote.sent",
                changes={
                    "status": {"before": "draft", "after": "sent"},
                    "valid_until": {"before": None, "after": str(quote.valid_until)},
                    "recipients": {"before": None, "after": str(len(command.recipients))},
                    "skip_email": {"before": None, "after": str(not emailing)},
                },
                actor_id=actor.id,
            )
            if not emailing:
                await uow.mail_outbox.add(
                    OutboxEntry(
                        quote_id=quote.id,
                        recipients=list(command.recipients),
                        subject=command.subject,
                        body=command.body,
                        status=OutboxStatus.SKIPPED,
                    )
                )
                await uow.commit()
                return quote
            # The Graph call happens outside the freezing transaction: a mail failure
            # must never roll back the sent version.
            await uow.commit()
            await self._deliver(
                uow,
                quote,
                actor=actor,
                recipients=list(command.recipients),
                subject=command.subject,
                body=command.body,
                attachment=content,
            )
            await uow.commit()
            return quote

    async def accept(self, quote_id: UUID, command: AcceptQuote, *, actor: User) -> Quote:
        now = self._now()
        async with self._uow as uow:
            quote, opportunity, _ = await self._load(uow, quote_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=True)
            if opportunity.status is not OpportunityStatus.OPEN:
                raise OpportunityAlreadyClosedError()
            quote.accept(now=now)
            await uow.quotes.save(quote, expected_version=command.expected_version)
            pipeline = await uow.pipelines.get(opportunity.pipeline_id)
            if pipeline is None:
                raise UnknownReferenceError("pipeline_id", [str(opportunity.pipeline_id)])
            won_at = now if command.occurred_on is None else _noon_utc(command.occurred_on)
            change = opportunity.win(
                pipeline, actor_id=actor.id, now=now, won_amount=quote.total, won_at=won_at
            )
            await uow.opportunities.save(opportunity, expected_version=opportunity.version)
            await uow.opportunities.add_stage_change(change)
            note = f"superseded by accepted quote {quote.display_number}"
            for sibling in await uow.quotes.list_current_for_opportunity(opportunity.id):
                if sibling.id == quote.id:
                    continue
                if sibling.supersede_by_accept(now=now, note=note):
                    await uow.quotes.save(sibling, expected_version=sibling.version_lock)
                    uow.audit.record(
                        entity_type="quote",
                        entity_id=sibling.id,
                        action="quote.auto_rejected",
                        changes={
                            "rejection_note": {"before": None, "after": note},
                        },
                        actor_id=actor.id,
                    )
            uow.audit.record(
                entity_type="quote",
                entity_id=quote.id,
                action="quote.accepted",
                changes={
                    "status": {"before": "sent", "after": "accepted"},
                    "total": {"before": None, "after": str(quote.total)},
                },
                actor_id=actor.id,
            )
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
            uow.audit.record(
                entity_type="opportunity",
                entity_id=opportunity.id,
                action="opportunity.stage_changed",
                changes={
                    "stage_id": {
                        "before": str(change.from_stage_id),
                        "after": str(change.to_stage_id),
                    }
                },
                actor_id=actor.id,
            )
            await uow.commit()
            return quote

    async def reject(self, quote_id: UUID, command: RejectQuote, *, actor: User) -> Quote:
        now = self._now()
        async with self._uow as uow:
            quote, opportunity, _ = await self._load(uow, quote_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=True)
            quote.reject(now=now, note=command.note)
            await uow.quotes.save(quote, expected_version=command.expected_version)
            uow.audit.record(
                entity_type="quote",
                entity_id=quote.id,
                action="quote.rejected",
                changes={
                    "status": {"before": "sent", "after": "rejected"},
                    "rejection_note": {"before": None, "after": quote.rejection_note},
                },
                actor_id=actor.id,
            )
            await uow.commit()
            return quote

    async def revise(self, quote_id: UUID, *, expected_version: int, actor: User) -> Quote:
        now = self._now()
        async with self._uow as uow:
            quote, opportunity, _ = await self._load(uow, quote_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=True)
            revision = quote.revise(created_by=actor.id, now=now)
            await uow.quotes.save(quote, expected_version=expected_version)
            await uow.quotes.add(revision)
            uow.audit.record(
                entity_type="quote",
                entity_id=revision.id,
                action="quote.revised",
                changes={
                    "version": {"before": str(quote.version), "after": str(revision.version)},
                },
                actor_id=actor.id,
            )
            await uow.commit()
            return revision

    async def retry_email(self, quote_id: UUID, *, actor: User) -> Quote:
        async with self._uow as uow:
            quote, opportunity, _ = await self._load(uow, quote_id, actor)
            ensure_quote_writer(actor, opportunity, lifecycle=True)
            latest = await uow.mail_outbox.latest_for_quote(quote.id)
            if latest is None or latest.status is not OutboxStatus.FAILED:
                raise EmailRetryNotAvailableError()
            content = await uow.quotes.get_pdf(quote.id)
            if content is None:
                raise EmailRetryNotAvailableError()
            await self._deliver(
                uow,
                quote,
                actor=actor,
                recipients=latest.recipients,
                subject=latest.subject,
                body=latest.body,
                attachment=content,
            )
            await uow.commit()
            return quote

    # --- helpers ---------------------------------------------------------

    async def _deliver(
        self,
        uow: UnitOfWork,
        quote: Quote,
        *,
        actor: User,
        recipients: list[MailRecipient],
        subject: str,
        body: str,
        attachment: bytes,
    ) -> None:
        now = self._now()
        entry = OutboxEntry(
            quote_id=quote.id,
            recipients=recipients,
            subject=subject,
            body=body,
            status=OutboxStatus.SENT,
            sent_at=now,
        )
        try:
            await self._mailer.send(
                sender_email=str(actor.email),
                recipients=recipients,
                subject=subject,
                body=body,
                attachment_name=f"{quote.display_number}.pdf",
                attachment=attachment,
            )
        except Exception as error:  # any delivery failure lands in the outbox
            entry.status = OutboxStatus.FAILED
            entry.error = str(error)
            entry.sent_at = None
            uow.audit.record(
                entity_type="quote",
                entity_id=quote.id,
                action="quote.email_failed",
                changes={"error": {"before": None, "after": entry.error}},
                actor_id=actor.id,
            )
        await uow.mail_outbox.add(entry)

    async def _line_drafts(
        self, uow: UnitOfWork, inputs: list[QuoteLineInput]
    ) -> list[QuoteLineDraft]:
        drafts: list[QuoteLineDraft] = []
        for line in inputs:
            product_code: str | None = None
            unit_cost: object = None
            unit_price = line.unit_price
            if line.product_id is not None:
                product = await uow.products.get(line.product_id)
                if product is None:
                    raise UnknownReferenceError("product_id", [str(line.product_id)])
                product_code = product.sku
                unit_cost = product.cost_price
                if unit_price is None:
                    unit_price = product.list_price
            if unit_price is None:
                raise ValidationFailedError(
                    [
                        {
                            "field": "unit_price",
                            "message": "Free-text lines need a unit price",
                            "code": "unit_price_required",
                        }
                    ]
                )
            drafts.append(
                QuoteLineDraft(
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=unit_price,
                    discount_percent=line.discount_percent,
                    vat_rate=line.vat_rate,
                    product_id=line.product_id,
                    product_code=product_code,
                    unit_cost=unit_cost,  # type: ignore[arg-type]
                )
            )
        return drafts

    @staticmethod
    async def _load_opportunity(
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

    async def _load(
        self, uow: UnitOfWork, quote_id: UUID, actor: User
    ) -> tuple[Quote, Opportunity, Account]:
        quote = await uow.quotes.get(quote_id)
        if quote is None:
            raise NotFoundError("Quote not found")
        try:
            opportunity, account = await self._load_opportunity(uow, quote.opportunity_id, actor)
        except NotFoundError as error:
            raise NotFoundError("Quote not found") from error
        return quote, opportunity, account


def _noon_utc(value: date) -> datetime:
    return datetime.combine(value, time(12, 0), tzinfo=UTC)


@dataclass(frozen=True)
class QuoteSettings:
    conditions_defaults: dict[str, object]
    email_template: dict[str, object]


class QuoteSettingsService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def get(self, *, actor: User) -> QuoteSettings:
        # Readable by every authenticated user: the send dialog interpolates the template.
        async with self._uow as uow:
            return QuoteSettings(
                conditions_defaults=await uow.app_settings.get(CONDITIONS_DEFAULTS_KEY) or {},
                email_template=await uow.app_settings.get(EMAIL_TEMPLATE_KEY) or {},
            )

    async def update(
        self,
        *,
        conditions_defaults: dict[str, object],
        email_template: dict[str, object],
        actor: User,
    ) -> QuoteSettings:
        _ensure_admin(actor)
        _validate_settings(conditions_defaults, email_template)
        async with self._uow as uow:
            before = QuoteSettings(
                conditions_defaults=await uow.app_settings.get(CONDITIONS_DEFAULTS_KEY) or {},
                email_template=await uow.app_settings.get(EMAIL_TEMPLATE_KEY) or {},
            )
            await uow.app_settings.put(CONDITIONS_DEFAULTS_KEY, conditions_defaults)
            await uow.app_settings.put(EMAIL_TEMPLATE_KEY, email_template)
            uow.audit.record(
                entity_type="quote_settings",
                entity_id=None,
                action="quote_settings.updated",
                changes=diff_fields(
                    {
                        "conditions_defaults": str(before.conditions_defaults),
                        "email_template": str(before.email_template),
                    },
                    {
                        "conditions_defaults": str(conditions_defaults),
                        "email_template": str(email_template),
                    },
                ),
                actor_id=actor.id,
            )
            await uow.commit()
            return QuoteSettings(
                conditions_defaults=conditions_defaults, email_template=email_template
            )


def _ensure_admin(actor: User) -> None:
    if actor.role is not Role.ADMIN:
        raise PermissionDeniedError("Quote settings are managed by administrators")


def _validate_settings(
    conditions_defaults: dict[str, object], email_template: dict[str, object]
) -> None:
    issues: list[FieldError] = []
    try:
        days = int(str(conditions_defaults.get("validez_dias") or 0))
    except ValueError:
        days = 0
    if days < 1:
        issues.append(
            {
                "field": "conditions_defaults.validez_dias",
                "message": "Validity must be at least one day",
                "code": "validez_dias_invalid",
            }
        )
    for key in ("subject", "body"):
        if not str(email_template.get(key) or "").strip():
            issues.append(
                {
                    "field": f"email_template.{key}",
                    "message": "The email template needs a subject and a body",
                    "code": f"{key}_required",
                }
            )
    if issues:
        raise ValidationFailedError(issues)
