from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.application.opportunities.commands import CreateOpportunity
from app.application.opportunities.service import OpportunityService
from app.application.quotes.commands import (
    AcceptQuote,
    CreateQuote,
    QuoteLineInput,
    RejectQuote,
    SendQuote,
    UpdateQuoteDraft,
)
from app.application.quotes.service import (
    CONDITIONS_DEFAULTS_KEY,
    EMAIL_TEMPLATE_KEY,
    QuoteService,
    QuoteSettingsService,
)
from app.domain.catalogue.entities import Product, ProductKind
from app.domain.opportunities.entities import Opportunity, OpportunityStatus
from app.domain.opportunities.errors import OpportunityClosedError
from app.domain.quotes.entities import Quote, QuoteStatus
from app.domain.quotes.errors import (
    EmailRetryNotAvailableError,
    OpportunityAlreadyClosedError,
    QuoteActionForbiddenError,
    QuoteRecipientsRequiredError,
)
from app.domain.quotes.mail import MailRecipient, OutboxStatus
from app.domain.reference.entities import AccountType, Brand, LossReason, Pipeline, PipelineStage
from app.domain.shared.errors import PermissionDeniedError
from app.domain.shared.ids import new_id
from app.domain.territories.entities import Division, Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.quotes import FakeMailer, FakePdfRenderer
from tests.unit.fakes.reference import InMemoryReferenceReadRepository
from tests.unit.fakes.repositories import InMemoryDivisionRepository

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


class FixedClock(datetime):
    @classmethod
    def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
        return NOW


VASCULAR = Division(id=new_id(), code="vascular", name_es="Vascular", sort_order=40)
IVF = AccountType(new_id(), "ivf_clinic", "Clínica FIV", 10, False, True)
CENTRO = Territory.create(name="Centro", provinces=frozenset({"28"}))
HADECO = Brand.create(name="Hadeco", is_own=True, division_ids=frozenset({VASCULAR.id}))
PRICE_REASON = LossReason(new_id(), "price", "Precio", 10)


def stage(code: str, order: int, *, is_won: bool = False, is_lost: bool = False) -> PipelineStage:
    return PipelineStage(
        id=new_id(),
        code=code,
        name_es=code.title(),
        sort_order=order,
        probability=50,
        is_won=is_won,
        is_lost=is_lost,
        is_at_risk=False,
    )


EQUIPMENT = Pipeline(
    id=new_id(),
    code="equipment",
    name_es="Equipos",
    sort_order=10,
    division_ids=frozenset({VASCULAR.id}),
    stages=[
        stage("contact", 1),
        stage("demo", 2),
        stage("won", 3, is_won=True),
        stage("lost", 4, is_lost=True),
    ],
)


def make_user(role: Role, *, territories: frozenset[UUID] = frozenset()) -> User:
    return User.create(
        email=Email(f"{new_id()}@quermed.com"),
        full_name=role.value,
        role=role,
        password_hash="h",
        territory_ids=territories,
        division_ids=frozenset({VASCULAR.id}),
    )


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.divisions = InMemoryDivisionRepository([VASCULAR])
    uow.reference = InMemoryReferenceReadRepository(account_types=[IVF], activity_types=[])
    uow.territories.rows[CENTRO.id] = CENTRO
    uow.pipelines.rows = {EQUIPMENT.id: EQUIPMENT}
    uow.brands.rows[HADECO.id] = HADECO
    uow.loss_reasons.rows[PRICE_REASON.id] = PRICE_REASON
    uow.app_settings.rows[CONDITIONS_DEFAULTS_KEY] = {
        "validez_dias": 30,
        "plazo_entrega": "4-6 semanas",
        "forma_pago": "Transferencia a 30 días",
        "garantia": "2 años",
    }
    uow.app_settings.rows[EMAIL_TEMPLATE_KEY] = {
        "subject": "Presupuesto {numero}",
        "body": "Adjuntamos {numero} para {centro}. {comercial}",
    }
    return uow


@pytest.fixture
def rep(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.SALES_REP, territories=frozenset({CENTRO.id}))
    uow.users.rows[user.id] = user
    return user


@pytest.fixture
def back_office(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.BACK_OFFICE)
    uow.users.rows[user.id] = user
    return user


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def pdf() -> FakePdfRenderer:
    return FakePdfRenderer()


def quote_service(uow: FakeUnitOfWork, mailer: FakeMailer, pdf: FakePdfRenderer) -> QuoteService:
    return QuoteService(uow, mailer=mailer, pdf_renderer=pdf, clock=FixedClock)


@pytest.fixture
def product(uow: FakeUnitOfWork, back_office: User) -> Product:
    item = Product.create(
        sku="DP-3000",
        name="Doppler vascular DP-3000",
        brand_id=HADECO.id,
        family_id=new_id(),
        kind=ProductKind.EQUIPMENT,
        list_price="13000",
        cost_price="9000",
        created_by=back_office.id,
    )
    uow.products.rows[item.id] = item
    return item


@pytest.fixture
async def opportunity(uow: FakeUnitOfWork, rep: User, product: Product) -> Opportunity:
    from app.domain.accounts.entities import Account

    account = Account.create(
        name="Clínica Tambre",
        account_type_id=IVF.id,
        province_code="28",
        territory_id=CENTRO.id,
        owner_id=rep.id,
        details={"division_ids": frozenset({VASCULAR.id})},
    )
    uow.accounts.rows[account.id] = account
    service = OpportunityService(uow, clock=FixedClock)
    created = await service.create(
        CreateOpportunity(
            account_id=account.id, division_id=VASCULAR.id, estimated_amount=Decimal("30000")
        ),
        actor=rep,
    )
    stored = await uow.opportunities.get(created.id)
    assert stored is not None
    stored.add_line(product_id=product.id, quantity="2", unit_price="13000", product_active=True)
    await uow.opportunities.save(stored, expected_version=stored.version)
    uow.committed_events.clear()
    return stored


async def make_quote(
    uow: FakeUnitOfWork,
    mailer: FakeMailer,
    pdf: FakePdfRenderer,
    opportunity: Opportunity,
    actor: User,
) -> Quote:
    return await quote_service(uow, mailer, pdf).create(
        CreateQuote(opportunity_id=opportunity.id), actor=actor
    )


async def send_quote(
    uow: FakeUnitOfWork,
    mailer: FakeMailer,
    pdf: FakePdfRenderer,
    quote: Quote,
    actor: User,
    **overrides: object,
) -> Quote:
    values: dict[str, object] = {
        "expected_version": quote.version_lock,
        "recipients": [MailRecipient(email="dra@tambre.es", name="Dra. Ruiz")],
        "subject": "Presupuesto",
        "body": "Adjunto",
    }
    values.update(overrides)
    command = SendQuote(**values)  # type: ignore[arg-type]
    return await quote_service(uow, mailer, pdf).send(quote.id, command, actor=actor)


class TestCreation:
    async def test_copies_lines_with_snapshots_and_defaults(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)

        assert quote.display_number == "P-2026-0001"
        assert quote.status is QuoteStatus.DRAFT
        assert quote.owner_id == opportunity.owner_id
        line = quote.lines[0]
        assert line.description == "Doppler vascular DP-3000"
        assert line.product_code == "DP-3000"
        assert line.unit_cost == Decimal("9000.00")
        assert line.discount_percent == Decimal("0.00")
        assert line.vat_rate == Decimal("21.00")
        assert quote.total == Decimal("31460.00")
        assert quote.conditions.forma_pago == "Transferencia a 30 días"
        assert uow.actions() == ["quote.created"]

    async def test_closed_opportunity_rejected(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        stored = await uow.opportunities.get(opportunity.id)
        assert stored is not None
        stored.win(EQUIPMENT, actor_id=rep.id, now=NOW)
        await uow.opportunities.save(stored, expected_version=stored.version)

        with pytest.raises(OpportunityClosedError):
            await make_quote(uow, mailer, pdf, stored, rep)

    async def test_settings_copied_not_referenced(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        uow.app_settings.rows[CONDITIONS_DEFAULTS_KEY]["plazo_entrega"] = "10 semanas"

        stored = await uow.quotes.get(quote.id)
        assert stored is not None
        assert stored.conditions.plazo_entrega == "4-6 semanas"


class TestPermissions:
    async def test_back_office_prepares_but_never_sends(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        back_office: User,
    ) -> None:
        quote = await make_quote(uow, mailer, pdf, opportunity, back_office)

        updated = await quote_service(uow, mailer, pdf).update_draft(
            quote.id,
            UpdateQuoteDraft(
                expected_version=quote.version_lock,
                lines=[QuoteLineInput(description="Solo instalación", quantity=1, unit_price=500)],
            ),
            actor=back_office,
        )
        assert updated.total == Decimal("605.00")

        with pytest.raises(QuoteActionForbiddenError):
            await send_quote(uow, mailer, pdf, updated, back_office)

    async def test_non_owner_rep_denied(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        colleague = make_user(Role.SALES_REP, territories=frozenset({CENTRO.id}))
        uow.users.rows[colleague.id] = colleague

        with pytest.raises(PermissionDeniedError):
            await make_quote(uow, mailer, pdf, opportunity, colleague)


class TestSend:
    async def test_send_freezes_stores_pdf_and_records_outbox(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        sent = await send_quote(uow, mailer, pdf, quote, rep)

        assert sent.status is QuoteStatus.SENT
        assert sent.valid_until == date(2026, 9, 27)
        assert await uow.quotes.get_pdf(quote.id) == b"%PDF fake P-2026-0001"
        outbox = await uow.mail_outbox.latest_for_quote(quote.id)
        assert outbox is not None
        assert outbox.status is OutboxStatus.SENT
        assert outbox.sent_at == NOW
        assert mailer.sent[0]["sender_email"] == str(rep.email)
        assert mailer.sent[0]["attachment_name"] == "P-2026-0001.pdf"
        assert "quote.sent" in uow.actions()

    async def test_graph_failure_keeps_quote_sent(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        mailer.fail = True
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        sent = await send_quote(uow, mailer, pdf, quote, rep)

        assert sent.status is QuoteStatus.SENT
        outbox = await uow.mail_outbox.latest_for_quote(quote.id)
        assert outbox is not None
        assert outbox.status is OutboxStatus.FAILED
        assert outbox.error is not None and "500" in outbox.error
        assert "quote.email_failed" in uow.actions()

    async def test_skip_email_and_disabled_mailer_record_skipped(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        await send_quote(uow, mailer, pdf, quote, rep, recipients=[], skip_email=True)
        outbox = await uow.mail_outbox.latest_for_quote(quote.id)
        assert outbox is not None and outbox.status is OutboxStatus.SKIPPED
        assert mailer.sent == []

        disabled = FakeMailer(enabled=False)
        second = await make_quote(uow, disabled, pdf, opportunity, rep)
        await send_quote(uow, disabled, pdf, second, rep)
        outbox = await uow.mail_outbox.latest_for_quote(second.id)
        assert outbox is not None and outbox.status is OutboxStatus.SKIPPED

    async def test_recipients_required_when_emailing(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        with pytest.raises(QuoteRecipientsRequiredError):
            await send_quote(uow, mailer, pdf, quote, rep, recipients=[])
        stored = await uow.quotes.get(quote.id)
        assert stored is not None and stored.status is QuoteStatus.DRAFT


class TestAccept:
    async def test_accept_wins_opportunity_and_rejects_siblings(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        service = quote_service(uow, mailer, pdf)
        first = await make_quote(uow, mailer, pdf, opportunity, rep)
        second = await make_quote(uow, mailer, pdf, opportunity, rep)
        first_sent = await send_quote(uow, mailer, pdf, first, rep)
        await send_quote(uow, mailer, pdf, second, rep)

        accepted = await service.accept(
            first.id,
            AcceptQuote(expected_version=first_sent.version_lock, occurred_on=date(2026, 8, 28)),
            actor=rep,
        )

        assert accepted.status is QuoteStatus.ACCEPTED
        won = await uow.opportunities.get(opportunity.id)
        assert won is not None
        assert won.status is OpportunityStatus.WON
        assert won.won_amount == Decimal("31460.00")
        sibling = await uow.quotes.get(second.id)
        assert sibling is not None
        assert sibling.status is QuoteStatus.REJECTED
        assert sibling.rejection_note is not None and "P-2026-0001" in sibling.rejection_note
        actions = uow.actions()
        for expected in (
            "quote.accepted",
            "quote.auto_rejected",
            "opportunity.won",
            "opportunity.stage_changed",
        ):
            assert expected in actions

    async def test_accept_on_closed_opportunity(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        sent = await send_quote(uow, mailer, pdf, quote, rep)
        stored = await uow.opportunities.get(opportunity.id)
        assert stored is not None
        stored.win(EQUIPMENT, actor_id=rep.id, now=NOW)
        await uow.opportunities.save(stored, expected_version=stored.version)

        with pytest.raises(OpportunityAlreadyClosedError):
            await quote_service(uow, mailer, pdf).accept(
                quote.id, AcceptQuote(expected_version=sent.version_lock), actor=rep
            )


class TestRejectReviseRetry:
    async def test_reject_and_revise(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        service = quote_service(uow, mailer, pdf)
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        sent = await send_quote(uow, mailer, pdf, quote, rep)

        rejected = await service.reject(
            quote.id,
            RejectQuote(expected_version=sent.version_lock, note="Precio alto"),
            actor=rep,
        )
        assert rejected.status is QuoteStatus.REJECTED

        revision = await service.revise(quote.id, expected_version=rejected.version_lock, actor=rep)
        assert revision.version == 2
        assert revision.display_number == "P-2026-0001-v2"
        original = await uow.quotes.get(quote.id)
        assert original is not None and original.superseded_at is not None
        assert "quote.revised" in uow.actions()

    async def test_retry_email(
        self,
        uow: FakeUnitOfWork,
        mailer: FakeMailer,
        pdf: FakePdfRenderer,
        opportunity: Opportunity,
        rep: User,
    ) -> None:
        service = quote_service(uow, mailer, pdf)
        quote = await make_quote(uow, mailer, pdf, opportunity, rep)
        mailer.fail = True
        await send_quote(uow, mailer, pdf, quote, rep)

        mailer.fail = False
        await service.retry_email(quote.id, actor=rep)
        outbox = await uow.mail_outbox.latest_for_quote(quote.id)
        assert outbox is not None and outbox.status is OutboxStatus.SENT

        with pytest.raises(EmailRetryNotAvailableError):
            await service.retry_email(quote.id, actor=rep)


class TestSettings:
    async def test_admin_updates_and_others_denied(self, uow: FakeUnitOfWork) -> None:
        admin = make_user(Role.ADMIN)
        manager = make_user(Role.SALES_MANAGER)
        service = QuoteSettingsService(uow)

        settings = await service.get(actor=admin)
        assert settings.conditions_defaults["validez_dias"] == 30

        await service.update(
            conditions_defaults={"validez_dias": 15, "plazo_entrega": "2 semanas"},
            email_template={"subject": "S {numero}", "body": "B {centro}"},
            actor=admin,
        )
        updated = await service.get(actor=admin)
        assert updated.conditions_defaults["validez_dias"] == 15
        assert "quote_settings.updated" in uow.actions()

        with pytest.raises(PermissionDeniedError):
            await service.update(conditions_defaults={}, email_template={}, actor=manager)
