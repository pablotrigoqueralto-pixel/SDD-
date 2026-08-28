from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from app.application.activities.commands import CreateActivity
from app.application.activities.service import ActivityService
from app.application.opportunities.at_risk import scan_at_risk
from app.application.opportunities.commands import (
    AddLine,
    CreateOpportunity,
    LoseOpportunity,
    UpdateLine,
    UpdateOpportunity,
    WinOpportunity,
)
from app.application.opportunities.service import OpportunityService
from app.domain.accounts.entities import Account
from app.domain.accounts.errors import AssignmentForbiddenError, OwnerNotSalesRepError
from app.domain.catalogue.entities import Product, ProductKind
from app.domain.opportunities.entities import AtRiskSource, OpportunityStatus
from app.domain.opportunities.errors import (
    LineProductInactiveError,
    LossReasonRequiresBrandError,
    OpportunityHasLinesError,
    OpportunityNotInAccountError,
    PipelineRequiredError,
    ReopenForbiddenError,
)
from app.domain.reference.entities import (
    AccountType,
    ActivityType,
    Brand,
    LossReason,
    Pipeline,
    PipelineStage,
)
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.shared.ids import new_id
from app.domain.territories.entities import Division, Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.reference import InMemoryReferenceReadRepository
from tests.unit.fakes.repositories import InMemoryDivisionRepository

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


class FixedClock(datetime):
    @classmethod
    def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
        return NOW


VASCULAR = Division(id=new_id(), code="vascular", name_es="Vascular", sort_order=40)
CONSUMABLES_DIVISION = Division(id=new_id(), code="consumables", name_es="Fungibles", sort_order=20)
IVF = AccountType(new_id(), "ivf_clinic", "Clínica FIV", 10, False, True)
HOSPITAL = AccountType(new_id(), "public_hospital", "Hospital público", 20, True, True)
VISIT = ActivityType(new_id(), "visit", "Visita", 10, "map-pin", True, True)
CENTRO = Territory.create(name="Centro", provinces=frozenset({"28"}))
COMPETITOR = Brand.create(name="Cook", is_own=False, division_ids=frozenset())
PRICE_REASON = LossReason(new_id(), "price", "Precio", 10)
COMPETITOR_REASON = LossReason(new_id(), "competitor", "Competidor", 20, requires_brand=True)
OTHER_REASON = LossReason(new_id(), "other", "Otro", 60, requires_note=True)


def stage(
    code: str,
    order: int,
    *,
    is_won: bool = False,
    is_lost: bool = False,
    is_at_risk: bool = False,
) -> PipelineStage:
    return PipelineStage(
        id=new_id(),
        code=code,
        name_es=code.title(),
        sort_order=order,
        probability=50,
        is_won=is_won,
        is_lost=is_lost,
        is_at_risk=is_at_risk,
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
CONSUMABLES = Pipeline(
    id=new_id(),
    code="consumables",
    name_es="Consumibles",
    sort_order=20,
    division_ids=frozenset({CONSUMABLES_DIVISION.id}),
    stages=[
        stage("trial", 1),
        stage("recurring", 2, is_won=True),
        stage("at_risk", 3, is_at_risk=True),
        stage("lost", 4, is_lost=True),
    ],
)


def by_code(pipeline: Pipeline, code: str) -> UUID:
    return next(s.id for s in pipeline.stages if s.code == code)


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
    uow.divisions = InMemoryDivisionRepository([VASCULAR, CONSUMABLES_DIVISION])
    uow.reference = InMemoryReferenceReadRepository(
        account_types=[IVF, HOSPITAL], activity_types=[VISIT]
    )
    uow.territories.rows[CENTRO.id] = CENTRO
    uow.pipelines.rows = {EQUIPMENT.id: EQUIPMENT, CONSUMABLES.id: CONSUMABLES}
    uow.brands.rows[COMPETITOR.id] = COMPETITOR
    for reason in (PRICE_REASON, COMPETITOR_REASON, OTHER_REASON):
        uow.loss_reasons.rows[reason.id] = reason
    uow.opportunities.at_risk_pipeline_ids = {CONSUMABLES.id}
    return uow


@pytest.fixture
def rep(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.SALES_REP, territories=frozenset({CENTRO.id}))
    uow.users.rows[user.id] = user
    return user


@pytest.fixture
def manager(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.SALES_MANAGER)
    uow.users.rows[user.id] = user
    return user


@pytest.fixture
def back_office(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.BACK_OFFICE)
    uow.users.rows[user.id] = user
    return user


def make_account(
    uow: FakeUnitOfWork,
    *,
    owner_id: UUID | None,
    account_type_id: UUID | None = None,
) -> Account:
    account = Account.create(
        name="Clínica Tambre",
        account_type_id=account_type_id or IVF.id,
        province_code="28",
        territory_id=CENTRO.id,
        owner_id=owner_id,
        details={"division_ids": frozenset({VASCULAR.id})},
    )
    uow.accounts.rows[account.id] = account
    return account


def service(uow: FakeUnitOfWork) -> OpportunityService:
    return OpportunityService(uow, clock=FixedClock)


async def create_default(
    uow: FakeUnitOfWork, actor: User, *, account: Account | None = None, **overrides: object
) -> object:
    account = account or make_account(uow, owner_id=actor.id)
    command = CreateOpportunity(
        account_id=account.id,
        division_id=VASCULAR.id,
        estimated_amount=Decimal("30000"),
        **overrides,  # type: ignore[arg-type]
    )
    return await service(uow).create(command, actor=actor)


async def test_create_defaults_owner_pipeline_and_audit(uow: FakeUnitOfWork, rep: User) -> None:
    opportunity = await create_default(uow, rep)

    assert opportunity.pipeline_id == EQUIPMENT.id  # type: ignore[attr-defined]
    assert opportunity.owner_id == rep.id  # type: ignore[attr-defined]
    assert opportunity.stage_id == by_code(EQUIPMENT, "contact")  # type: ignore[attr-defined]
    assert uow.actions() == ["opportunity.created"]
    assert len(uow.opportunities.history) == 1
    snapshot = uow.committed_events[0].changes
    assert snapshot["estimated_amount"] == {"before": None, "after": "30000.00"}


async def test_create_tender_default_from_account_type(uow: FakeUnitOfWork, rep: User) -> None:
    hospital = make_account(uow, owner_id=rep.id, account_type_id=HOSPITAL.id)
    opportunity = await create_default(uow, rep, account=hospital)
    assert opportunity.is_tender is True  # type: ignore[attr-defined]


async def test_create_division_without_pipeline(uow: FakeUnitOfWork, rep: User) -> None:
    other = Division(id=new_id(), code="x", name_es="X", sort_order=99)
    uow.divisions = InMemoryDivisionRepository([VASCULAR, CONSUMABLES_DIVISION, other])
    account = make_account(uow, owner_id=rep.id)
    with pytest.raises(PipelineRequiredError):
        await service(uow).create(
            CreateOpportunity(
                account_id=account.id, division_id=other.id, estimated_amount=Decimal("1")
            ),
            actor=rep,
        )


async def test_create_owner_rules(uow: FakeUnitOfWork, rep: User, manager: User) -> None:
    colleague = make_user(Role.SALES_REP, territories=frozenset({CENTRO.id}))
    uow.users.rows[colleague.id] = colleague
    account = make_account(uow, owner_id=colleague.id)

    with pytest.raises(AssignmentForbiddenError):
        await create_default(uow, rep, account=account, owner_id=colleague.id)

    managed = await create_default(uow, manager, account=account, owner_id=colleague.id)
    assert managed.owner_id == colleague.id  # type: ignore[attr-defined]

    with pytest.raises(OwnerNotSalesRepError):
        await create_default(uow, manager, owner_id=manager.id)

    from_manager = await create_default(uow, manager, account=account)
    assert from_manager.owner_id == colleague.id  # type: ignore[attr-defined]

    with pytest.raises(PermissionDeniedError):
        await create_default(uow, make_user(Role.BACK_OFFICE), account=account)


async def test_update_fields_and_tender_rules(uow: FakeUnitOfWork, rep: User) -> None:
    opportunity = await create_default(uow, rep)
    svc = service(uow)

    updated = await svc.update(
        opportunity.id,  # type: ignore[attr-defined]
        UpdateOpportunity(
            expected_version=1,
            changes={
                "name": "Doppler Tambre",
                "is_tender": True,
                "tender_reference": "EXP-1",
                "expected_close_date": date(2026, 10, 1),
            },
        ),
        actor=rep,
    )
    assert updated.name == "Doppler Tambre" and updated.tender_reference == "EXP-1"
    assert uow.actions() == ["opportunity.created", "opportunity.updated"]

    with pytest.raises(PermissionDeniedError):
        await svc.update(
            opportunity.id,  # type: ignore[attr-defined]
            UpdateOpportunity(expected_version=2, changes={"stage_id": new_id()}),
            actor=rep,
        )
    with pytest.raises(NotFoundError):
        await svc.update(
            new_id(), UpdateOpportunity(expected_version=1, changes={"name": "x"}), actor=rep
        )


async def test_lifecycle_commands_permissions_and_audit(
    uow: FakeUnitOfWork, rep: User, manager: User, back_office: User
) -> None:
    opportunity = await create_default(uow, rep)
    svc = service(uow)
    oid: UUID = opportunity.id  # type: ignore[attr-defined]

    other_rep = make_user(Role.SALES_REP, territories=frozenset({CENTRO.id}))
    uow.users.rows[other_rep.id] = other_rep
    with pytest.raises(PermissionDeniedError):
        await svc.move_stage(oid, by_code(EQUIPMENT, "demo"), expected_version=1, actor=other_rep)
    with pytest.raises(PermissionDeniedError):
        await svc.move_stage(oid, by_code(EQUIPMENT, "demo"), expected_version=1, actor=back_office)

    await svc.move_stage(oid, by_code(EQUIPMENT, "demo"), expected_version=1, actor=rep)
    won = await svc.win(
        oid, WinOpportunity(expected_version=2, won_amount=Decimal("24000")), actor=rep
    )
    assert won.status is OpportunityStatus.WON and won.won_amount == Decimal("24000.00")

    with pytest.raises(ReopenForbiddenError):
        await svc.reopen(oid, by_code(EQUIPMENT, "demo"), expected_version=3, actor=rep)
    reopened = await svc.reopen(oid, by_code(EQUIPMENT, "demo"), expected_version=3, actor=manager)
    assert reopened.status is OpportunityStatus.OPEN

    with pytest.raises(LossReasonRequiresBrandError):
        await svc.lose(
            oid,
            LoseOpportunity(expected_version=4, loss_reason_id=COMPETITOR_REASON.id),
            actor=rep,
        )
    lost = await svc.lose(
        oid,
        LoseOpportunity(
            expected_version=4,
            loss_reason_id=COMPETITOR_REASON.id,
            competitor_brand_id=COMPETITOR.id,
        ),
        actor=rep,
    )
    assert lost.status is OpportunityStatus.LOST

    assert uow.actions() == [
        "opportunity.created",
        "opportunity.stage_changed",
        "opportunity.won",
        "opportunity.reopened",
        "opportunity.lost",
    ]
    assert len(uow.opportunities.history) == 5

    with pytest.raises(AssignmentForbiddenError):
        await svc.assign(oid, other_rep.id, expected_version=5, actor=rep)
    assigned = await svc.assign(oid, other_rep.id, expected_version=5, actor=manager)
    assert assigned.owner_id == other_rep.id
    assert uow.actions()[-1] == "opportunity.reassigned"


async def test_lines_commands_and_audit(uow: FakeUnitOfWork, rep: User) -> None:
    opportunity = await create_default(uow, rep)
    svc = service(uow)
    oid: UUID = opportunity.id  # type: ignore[attr-defined]
    product = Product.create(
        sku="P-1",
        name="Doppler",
        brand_id=COMPETITOR.id,
        family_id=new_id(),
        kind=ProductKind.EQUIPMENT,
        list_price="12500",
        created_by=rep.id,
    )
    await uow.products.add(product)
    retired = Product.create(
        sku="P-2",
        name="Viejo",
        brand_id=COMPETITOR.id,
        family_id=new_id(),
        kind=ProductKind.EQUIPMENT,
        list_price="10",
        created_by=rep.id,
        is_active=False,
    )
    await uow.products.add(retired)

    with_line = await svc.add_line(
        oid, AddLine(expected_version=1, product_id=product.id, quantity=Decimal("2")), actor=rep
    )
    assert with_line.amount == Decimal("25000.00")
    assert with_line.lines[0].unit_price == Decimal("12500.00")

    with pytest.raises(LineProductInactiveError):
        await svc.add_line(
            oid,
            AddLine(expected_version=2, product_id=retired.id, quantity=Decimal("1")),
            actor=rep,
        )
    with pytest.raises(OpportunityHasLinesError):
        await svc.update(
            oid,
            UpdateOpportunity(expected_version=2, changes={"estimated_amount": Decimal("1")}),
            actor=rep,
        )

    line_id = with_line.lines[0].id
    updated = await svc.update_line(
        oid, line_id, UpdateLine(expected_version=2, quantity=Decimal("3")), actor=rep
    )
    assert updated.amount == Decimal("37500.00")
    removed = await svc.remove_line(oid, line_id, expected_version=3, actor=rep)
    assert removed.amount == Decimal("30000.00")
    assert uow.actions() == [
        "opportunity.created",
        "opportunity.line_added",
        "opportunity.line_updated",
        "opportunity.line_removed",
    ]


async def test_activity_link_and_automatic_at_risk_clearing(uow: FakeUnitOfWork, rep: User) -> None:
    account = make_account(uow, owner_id=rep.id)
    opportunity = await service(uow).create(
        CreateOpportunity(
            account_id=account.id,
            division_id=CONSUMABLES_DIVISION.id,
            estimated_amount=Decimal("800"),
        ),
        actor=rep,
    )
    oid: UUID = opportunity.id
    svc = service(uow)
    await svc.win(oid, WinOpportunity(expected_version=1), actor=rep)

    other_account = make_account(uow, owner_id=rep.id)
    activity_service = ActivityService(uow, clock=FixedClock)
    with pytest.raises(OpportunityNotInAccountError):
        await activity_service.create(
            CreateActivity(
                account_id=other_account.id, activity_type_id=VISIT.id, opportunity_id=oid
            ),
            actor=rep,
        )

    flagged = await scan_at_risk(uow, after_days=60, now=NOW + timedelta(days=61))
    assert flagged == 1
    assert (await uow.opportunities.get(oid)).at_risk_source is AtRiskSource.AUTOMATIC  # type: ignore[union-attr]
    again = await scan_at_risk(uow, after_days=60, now=NOW + timedelta(days=61))
    assert again == 0

    result = await activity_service.create(
        CreateActivity(account_id=account.id, activity_type_id=VISIT.id, opportunity_id=oid),
        actor=rep,
    )
    assert result.activity.opportunity_id == oid
    cleared = await uow.opportunities.get(oid)
    assert cleared is not None and cleared.is_at_risk is False
    assert cleared.stage_id == by_code(CONSUMABLES, "recurring")
    assert "opportunity.at_risk_set" in uow.actions()
    assert "opportunity.at_risk_cleared" in uow.actions()

    # A manual flag is not cleared by activities.
    await svc.set_at_risk(oid, True, expected_version=cleared.version, actor=rep)
    await activity_service.create(
        CreateActivity(account_id=account.id, activity_type_id=VISIT.id, opportunity_id=oid),
        actor=rep,
    )
    still = await uow.opportunities.get(oid)
    assert still is not None and still.is_at_risk is True

    # The scan never clears and never double-flags.
    assert await scan_at_risk(uow, after_days=60, now=NOW + timedelta(days=200)) == 0
