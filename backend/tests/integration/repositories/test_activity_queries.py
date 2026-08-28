from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.accounts.queries import AccountFilters, AccountQueries
from app.application.activities.queries import (
    TimelineFilters,
    TimelineQueries,
    TodayQueries,
    day_bounds,
    week_bounds,
)
from app.application.shared.pagination import PageParams, SortField
from app.domain.activities.entities import Activity, ActivityKind, ActivityStatus
from app.domain.contacts.entities import Contact
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.activities import SqlAlchemyActivityRepository
from app.infrastructure.db.repositories.contacts import SqlAlchemyContactRepository
from app.infrastructure.db.seed import reference_id
from tests.integration.repositories.conftest import World, make_account

pytestmark = pytest.mark.integration

# Thursday 28 Aug 2026 10:00 in Madrid (08:00 UTC)
NOW = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)
VISIT_ID = reference_id("activity_types", "visit")
CALL_ID = reference_id("activity_types", "call")
NOTE_ID = reference_id("activity_types", "note")
VISIT = ActivityKind(VISIT_ID, is_note=False, counts_as_contact=True)
CALL = ActivityKind(CALL_ID, is_note=False, counts_as_contact=True)
NOTE = ActivityKind(NOTE_ID, is_note=True, counts_as_contact=False)


def page(**overrides: object) -> PageParams:
    values: dict[str, object] = {
        "page": 1,
        "page_size": 50,
        "sort": [SortField("scheduled_at", True)],
    }
    values.update(overrides)
    return PageParams(**values)  # type: ignore[arg-type]


def done(
    account_id: UUID, owner: UUID, kind: ActivityKind, when: datetime, **d: object
) -> Activity:
    return Activity.record_done(
        account_id=account_id,
        kind=kind,
        owner_id=owner,
        created_by=owner,
        now=NOW,
        scheduled_at=when,
        details=d,
    )


def planned(account_id: UUID, owner: UUID, kind: ActivityKind, when: datetime) -> Activity:
    return Activity.plan(
        account_id=account_id, kind=kind, owner_id=owner, created_by=owner, scheduled_at=when
    )


def test_day_and_week_bounds_in_madrid() -> None:
    start, end, today = day_bounds(datetime(2026, 8, 28, 22, 30, tzinfo=UTC))  # 00:30 Madrid, 29th
    assert today.isoformat() == "2026-08-29"
    assert start.astimezone(UTC) == datetime(2026, 8, 28, 22, 0, tzinfo=UTC)
    assert end - start == timedelta(days=1)
    week_start, week_end = week_bounds(datetime(2026, 8, 30, 21, 0, tzinfo=UTC))  # Sunday 23:00
    assert week_start.date().isoformat() == "2026-08-24"  # Monday
    assert week_end.date().isoformat() == "2026-08-31"


async def test_timeline_order_titles_contacts_and_filters(
    session: AsyncSession, accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    account = make_account("A", territory_id=world.centro.id, owner_id=world.rep.id)
    await accounts.add(account)
    ana = Contact.create(account_id=account.id, first_name="Ana", last_name="Pérez")
    await SqlAlchemyContactRepository(session).add(ana)
    activities = SqlAlchemyActivityRepository(session)
    visit = done(
        account.id,
        world.rep.id,
        VISIT,
        NOW - timedelta(days=1),
        contact_ids=[ana.id],
        subject="Demo",
    )
    note = done(account.id, world.rep.id, NOTE, NOW)
    call = planned(account.id, world.rep.id, CALL, NOW + timedelta(days=1))
    for activity in (visit, note, call):
        await activities.add(activity)

    result = await TimelineQueries(session).list_page(account.id, page(), TimelineFilters())

    assert result.total == 3
    views = [e.activity for e in result.items]
    assert all(view is not None for view in views)
    assert [view.activity.id for view in views if view] == [call.id, note.id, visit.id]
    assert [e.kind for e in result.items] == ["activity"] * 3
    assert result.items[2].title == "Demo" and result.items[1].title == "Nota"
    oldest = result.items[2].activity
    assert oldest is not None
    assert oldest.contacts[0].name == "Ana Pérez"
    assert oldest.owner_name == "rep"
    assert oldest.account_name == "A"

    only_planned = await TimelineQueries(session).list_page(
        account.id, page(), TimelineFilters(status=ActivityStatus.PLANNED)
    )
    assert [e.id for e in only_planned.items] == [call.id]
    unknown_kind = await TimelineQueries(session).list_page(
        account.id, page(), TimelineFilters(kind="quote")
    )
    assert unknown_kind.total == 0
    second_page = await TimelineQueries(session).list_page(
        account.id, page(page=2, page_size=2), TimelineFilters()
    )
    assert [e.id for e in second_page.items] == [visit.id]


async def test_today_buckets_and_week_counters(
    session: AsyncSession, accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    account = make_account("A", territory_id=world.centro.id, owner_id=world.rep.id)
    await accounts.add(account)
    activities = SqlAlchemyActivityRepository(session)
    madrid_2330 = datetime(2026, 8, 28, 21, 30, tzinfo=UTC)  # 23:30 Madrid today
    madrid_0030_tomorrow = datetime(2026, 8, 28, 22, 30, tzinfo=UTC)  # 00:30 Madrid tomorrow
    rows = [
        planned(account.id, world.rep.id, VISIT, NOW + timedelta(hours=1)),  # today 11:00
        planned(account.id, world.rep.id, CALL, madrid_2330),  # today 23:30
        planned(account.id, world.rep.id, CALL, madrid_0030_tomorrow),  # tomorrow -> remaining
        planned(account.id, world.rep.id, CALL, NOW - timedelta(days=3)),  # overdue (Monday)
        planned(account.id, world.rep.id, VISIT, NOW + timedelta(days=5)),  # next week: not counted
        planned(account.id, world.other_rep.id, VISIT, NOW + timedelta(hours=2)),  # other rep
        done(account.id, world.rep.id, VISIT, NOW - timedelta(days=1)),
        done(account.id, world.rep.id, VISIT, NOW - timedelta(days=2)),
        done(account.id, world.rep.id, CALL, NOW - timedelta(days=2)),
        done(account.id, world.rep.id, VISIT, NOW - timedelta(days=8)),  # last week
    ]
    for activity in rows:
        await activities.add(activity)

    result = await TodayQueries(session).for_user(world.rep.id, now=NOW)

    assert result.date.isoformat() == "2026-08-28"
    assert [v.activity.id for v in result.today] == [rows[0].id, rows[1].id]
    assert [v.activity.id for v in result.overdue] == [rows[3].id]
    assert result.week.done_by_type == {VISIT_ID: 2, CALL_ID: 1}
    assert result.week.planned_remaining == 1  # tomorrow 00:30; next week's visit is outside


async def test_account_list_exposes_and_sorts_by_last_contact(
    session: AsyncSession, accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    never = make_account("Never", territory_id=world.centro.id, owner_id=world.rep.id)
    old = make_account("Old", territory_id=world.centro.id, owner_id=world.rep.id)
    recent = make_account("Recent", territory_id=world.centro.id, owner_id=world.rep.id)
    for account in (never, old, recent):
        await accounts.add(account)
    activities = SqlAlchemyActivityRepository(session)
    await activities.add(done(old.id, world.rep.id, VISIT, NOW - timedelta(days=30)))
    await activities.add(done(recent.id, world.rep.id, VISIT, NOW - timedelta(days=1)))
    await activities.add(planned(recent.id, world.rep.id, CALL, NOW + timedelta(days=2)))
    for account in (old, recent):
        await accounts.refresh_activity_summary(account.id)

    result = await AccountQueries(session).list_page(
        PageParams(page=1, page_size=50, sort=[SortField("last_contact_at", False)]),
        AccountFilters(),
        None,
    )

    assert [i.name for i in result.items] == ["Old", "Recent", "Never"]
    assert result.items[1].next_activity_at == NOW + timedelta(days=2)
    assert result.items[2].last_contact_at is None
