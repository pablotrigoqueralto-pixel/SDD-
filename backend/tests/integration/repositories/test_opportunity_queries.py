import time as time_module
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.activities.queries import (
    TIMELINE_KIND_ACTIVITY,
    TIMELINE_KIND_CLOSED,
    TIMELINE_KIND_STAGE,
    ActivityFilters,
    ActivityQueries,
    TimelineFilters,
    TimelineQueries,
)
from app.application.opportunities.queries import (
    BOARD_COLUMN_CAP,
    OpportunityFilters,
    OpportunityQueries,
)
from app.application.shared.pagination import PageParams, SortField
from app.domain.accounts.entities import Account
from app.domain.activities.entities import Activity, ActivityKind
from app.domain.opportunities.entities import Opportunity, OpportunityStatus
from app.domain.reference.entities import Pipeline
from app.domain.shared.policies import ScopeFilter
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.activities import SqlAlchemyActivityRepository
from app.infrastructure.db.repositories.opportunities import SqlAlchemyOpportunityRepository
from app.infrastructure.db.repositories.scope import scoped_accounts
from app.infrastructure.db.seed import reference_id
from tests.integration.repositories.conftest import NEUROLOGY_ID, VASCULAR_ID, World, make_account
from tests.integration.repositories.test_opportunity_repository import (
    CONSUMABLES_ID,
    EQUIPMENT_ID,
    VISIT_TYPE_ID,
    load_pipeline,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


def page(sort: str = "expected_close_date", *, page_size: int = 25) -> PageParams:
    descending = sort.startswith("-")
    return PageParams(page=1, page_size=page_size, sort=[SortField(sort.lstrip("-"), descending)])


@dataclass
class Data:
    in_scope: Account
    out_scope: Account
    contact: Opportunity
    demo: Opportunity
    tender: Opportunity
    won: Opportunity
    lost: Opportunity
    equipment: Pipeline
    consumables: Pipeline
    repo: SqlAlchemyOpportunityRepository


@pytest.fixture
async def world_data(session: AsyncSession, world: World) -> Data:
    accounts = SqlAlchemyAccountRepository(session)
    repo = SqlAlchemyOpportunityRepository(session)
    in_scope = make_account("Centro In", territory_id=world.centro.id, owner_id=world.rep.id)
    out_scope = make_account(
        "Centro Out", province="48", territory_id=world.norte.id, owner_id=world.other_rep.id
    )
    await accounts.add(in_scope)
    await accounts.add(out_scope)
    equipment = await load_pipeline(session, EQUIPMENT_ID)
    consumables = await load_pipeline(session, CONSUMABLES_ID)

    def build(account: Account, *, days_ago: int, amount: str, **overrides: object) -> Opportunity:
        opportunity, _ = Opportunity.create(
            account_id=account.id,
            account_name=account.name,
            buys_via_tender=False,
            division_id=VASCULAR_ID,
            division_name="Vascular",
            pipeline=equipment,
            estimated_amount=amount,
            owner_id=world.rep.id,
            created_by=world.rep.id,
            now=NOW - timedelta(days=days_ago),
            **overrides,  # type: ignore[arg-type]
        )
        return opportunity

    contact = build(in_scope, days_ago=10, amount="10000")
    demo = build(in_scope, days_ago=3, amount="20000")
    demo.move_stage(
        equipment,
        next(s.id for s in equipment.stages if s.code == "demo"),
        actor_id=world.rep.id,
        now=NOW - timedelta(days=2),
    )
    tender = build(
        in_scope,
        days_ago=1,
        amount="50000",
        is_tender=True,
        tender_deadline=NOW.date() + timedelta(days=3),
        expected_close_date=date(2026, 9, 1),
    )
    won = build(in_scope, days_ago=30, amount="15000")
    won.win(equipment, actor_id=world.rep.id, now=NOW - timedelta(days=4))
    lost = build(in_scope, days_ago=30, amount="9000")
    lost.lose(
        equipment,
        loss_reason_id=reference_id("loss_reasons", "price"),
        requires_brand=False,
        requires_note=False,
        actor_id=world.rep.id,
        now=NOW - timedelta(days=1),
    )
    foreign = build(out_scope, days_ago=5, amount="70000")
    foreign_opportunity, _ = Opportunity.create(
        account_id=out_scope.id,
        account_name=out_scope.name,
        buys_via_tender=False,
        division_id=NEUROLOGY_ID,
        division_name="Neurología",
        pipeline=consumables,
        estimated_amount="500",
        owner_id=world.other_rep.id,
        created_by=world.other_rep.id,
        now=NOW,
    )
    for row in (contact, demo, tender, won, lost, foreign, foreign_opportunity):
        await repo.add(row)
    return Data(
        in_scope=in_scope,
        out_scope=out_scope,
        contact=contact,
        demo=demo,
        tender=tender,
        won=won,
        lost=lost,
        equipment=equipment,
        consumables=consumables,
        repo=repo,
    )


def rep_scope(world: World) -> ScopeFilter:
    return ScopeFilter(
        user_id=world.rep.id,
        territory_ids=frozenset({world.centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )


async def test_list_scoped_filters_and_sort(
    session: AsyncSession, world: World, world_data: Data
) -> None:
    queries = OpportunityQueries(session, now=NOW)
    account_ids = scoped_accounts(select(AccountModel.id), rep_scope(world))

    default = await queries.list_page(page(), OpportunityFilters(), account_ids)
    assert [item.name for item in default.items] == [
        item.name for item in sorted(default.items, key=lambda i: i.expected_close_date)
    ]
    assert {item.status for item in default.items} == {OpportunityStatus.OPEN}
    assert default.total == 3  # the out-of-scope ones never appear

    unrestricted = await queries.list_page(page(), OpportunityFilters(), None)
    assert unrestricted.total == 5

    lost = await queries.list_page(
        page(), OpportunityFilters(status=OpportunityStatus.LOST), account_ids
    )
    assert lost.total == 1

    tenders = await queries.list_page(page(), OpportunityFilters(is_tender=True), account_ids)
    assert tenders.total == 1 and tenders.items[0].tender_deadline is not None

    by_amount = await queries.list_page(page("-amount"), OpportunityFilters(), account_ids)
    assert [str(item.amount) for item in by_amount.items] == ["50000.00", "20000.00", "10000.00"]

    demo = world_data.demo
    by_stage = await queries.list_page(
        page(),
        OpportunityFilters(stage_id=demo.stage_id),
        account_ids,
    )
    assert by_stage.total == 1 and by_stage.items[0].days_in_stage == 2
    assert by_stage.items[0].stage_name == "Demo"
    assert by_stage.items[0].account_name == "Centro In"

    searched = await queries.list_page(page(), OpportunityFilters(q="centro in"), account_ids)
    assert searched.total == 3


async def test_for_account_open_first_and_summary_scope(
    session: AsyncSession, world: World, world_data: Data
) -> None:
    queries = OpportunityQueries(session, now=NOW)
    in_scope = world_data.in_scope

    rows = await queries.for_account(in_scope.id)
    assert len(rows) == 5
    assert [row.status is OpportunityStatus.OPEN for row in rows[:3]] == [True, True, True]
    assert {rows[3].status, rows[4].status} == {OpportunityStatus.WON, OpportunityStatus.LOST}


async def test_board_totals_cap_and_closed_month(
    session: AsyncSession, world: World, world_data: Data
) -> None:
    equipment = world_data.equipment
    queries = OpportunityQueries(session, now=NOW)

    board = await queries.board(equipment, None)

    stages = {column.stage.code: column for column in board.columns}
    assert set(stages) == {"contact", "demo", "quote", "negotiation"}
    assert stages["contact"].count == 3  # in-scope contact + tender + foreign
    assert stages["contact"].total_amount == Decimal("130000.00")
    assert stages["demo"].count == 1 and stages["demo"].items[0].name.startswith("Centro In")
    assert board.closed_this_month.won_count == 1
    assert board.closed_this_month.won_amount == Decimal("15000.00")
    assert board.closed_this_month.lost_count == 1

    scoped = await queries.board(
        equipment,
        scoped_accounts(select(AccountModel.id), rep_scope(world)),
    )
    assert {c.stage.code: c.count for c in scoped.columns}["contact"] == 2


async def test_board_performance_with_500_open(
    session: AsyncSession, world: World, world_data: Data
) -> None:
    equipment = world_data.equipment
    in_scope = world_data.in_scope
    stage_id = next(s.id for s in equipment.stages if s.code == "quote")
    from sqlalchemy import text

    await session.execute(
        text(
            "INSERT INTO opportunities (id, account_id, pipeline_id, stage_id, division_id, "
            "owner_id, created_by, name, status, estimated_amount, amount, expected_close_date, "
            "is_tender, is_at_risk, stage_entered_at) "
            "SELECT gen_random_uuid(), :account, :pipeline, :stage, :division, :owner, :owner, "
            "'Oportunidad ' || g, 'open', 1000, 1000, :close, false, false, now() "
            "FROM generate_series(1, 500) AS g"
        ),
        {
            "account": in_scope.id,
            "pipeline": EQUIPMENT_ID,
            "stage": stage_id,
            "division": VASCULAR_ID,
            "owner": world.rep.id,
            "close": date(2026, 12, 1),
        },
    )
    await session.execute(text("ANALYZE opportunities"))
    queries = OpportunityQueries(session, now=NOW)

    started = time_module.perf_counter()
    board = await queries.board(equipment, None)
    elapsed = time_module.perf_counter() - started

    quote_column = next(c for c in board.columns if c.stage.code == "quote")
    assert quote_column.count == 500
    assert len(quote_column.items) == BOARD_COLUMN_CAP
    assert quote_column.has_more is True
    assert elapsed < 0.5, f"board took {elapsed:.3f}s"


async def test_timeline_union_and_activity_opportunity_filter(
    session: AsyncSession, world: World, world_data: Data
) -> None:
    repo = world_data.repo
    in_scope = world_data.in_scope
    demo = world_data.demo
    equipment = world_data.equipment
    activities = SqlAlchemyActivityRepository(session)

    move = demo.move_stage(
        equipment,
        next(s.id for s in equipment.stages if s.code == "quote"),
        actor_id=world.rep.id,
        now=NOW - timedelta(hours=3),
    )
    await repo.save(demo, expected_version=1)
    await repo.add_stage_change(move)
    win = demo.win(equipment, actor_id=world.rep.id, now=NOW - timedelta(hours=1))
    await repo.save(demo, expected_version=2)
    await repo.add_stage_change(win)

    visit = Activity.record_done(
        account_id=in_scope.id,
        kind=ActivityKind(id=VISIT_TYPE_ID, is_note=False, counts_as_contact=True),
        owner_id=world.rep.id,
        created_by=world.rep.id,
        now=NOW - timedelta(hours=2),
    )
    visit.opportunity_id = demo.id
    await activities.add(visit)

    timeline = TimelineQueries(session)
    result = await timeline.list_page(in_scope.id, page(page_size=10), TimelineFilters())

    kinds = [entry.kind for entry in result.items[:3]]
    assert kinds == [TIMELINE_KIND_CLOSED, TIMELINE_KIND_ACTIVITY, TIMELINE_KIND_STAGE]
    closed_entry = result.items[0]
    assert closed_entry.stage_change is not None
    assert closed_entry.stage_change.to_stage_name == "Ganada"
    assert closed_entry.title.startswith("Ganada · 20.000,00")
    stage_entry = result.items[2]
    assert stage_entry.stage_change is not None
    assert stage_entry.stage_change.from_stage_name == "Demo"
    assert stage_entry.title.endswith("→ Presupuesto")

    only_activities = await timeline.list_page(
        in_scope.id,
        page(page_size=10),
        TimelineFilters(kind=TIMELINE_KIND_ACTIVITY),
    )
    assert {entry.kind for entry in only_activities.items} == {TIMELINE_KIND_ACTIVITY}

    only_stage = await timeline.list_page(
        in_scope.id,
        page(page_size=10),
        TimelineFilters(kind=TIMELINE_KIND_STAGE),
    )
    assert all(e.kind == TIMELINE_KIND_STAGE for e in only_stage.items)
    assert only_stage.total == 1  # only the persisted move (creation changes stay in 4.x)

    unknown = await timeline.list_page(
        in_scope.id,
        page(),
        TimelineFilters(kind="quote"),
    )
    assert unknown.total == 0

    activity_list = await ActivityQueries(session).list_page(
        PageParams(page=1, page_size=10, sort=[SortField("scheduled_at", True)]),
        ActivityFilters(opportunity_id=demo.id),
        None,
    )
    assert activity_list.total == 1
    assert activity_list.items[0].opportunity_name == demo.name


async def test_today_opportunity_blocks(
    session: AsyncSession, world: World, world_data: Data
) -> None:
    queries = OpportunityQueries(session, now=NOW)
    repo = world_data.repo
    consumables = world_data.consumables
    in_scope = world_data.in_scope

    due = await queries.tenders_due(world.rep.id)
    assert [item.name for item in due] == [world_data.tender.name]

    from app.domain.opportunities.entities import AtRiskSource

    recurring, change = Opportunity.create(
        account_id=in_scope.id,
        account_name="Centro In",
        buys_via_tender=False,
        division_id=VASCULAR_ID,
        division_name="Vascular",
        pipeline=consumables,
        estimated_amount="800",
        owner_id=world.rep.id,
        created_by=world.rep.id,
        now=NOW - timedelta(days=90),
    )
    recurring.win(consumables, actor_id=world.rep.id, now=NOW - timedelta(days=80))
    recurring.set_at_risk(
        consumables,
        True,
        source=AtRiskSource.AUTOMATIC,
        actor_id=None,
        now=NOW - timedelta(days=2),
    )
    await repo.add(recurring)
    await repo.add_stage_change(change)

    at_risk = await queries.at_risk(world.rep.id)
    assert [item.id for item in at_risk] == [recurring.id]
    assert at_risk[0].is_at_risk is True
