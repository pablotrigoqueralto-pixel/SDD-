from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.activities.entities import Activity, ActivityKind, ActivityOutcome
from app.domain.contacts.entities import Contact
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.activities import SqlAlchemyActivityRepository
from app.infrastructure.db.repositories.contacts import SqlAlchemyContactRepository
from app.infrastructure.db.seed import reference_id
from tests.integration.repositories.conftest import World, make_account

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
VISIT = ActivityKind(reference_id("activity_types", "visit"), is_note=False, counts_as_contact=True)
NOTE = ActivityKind(reference_id("activity_types", "note"), is_note=True, counts_as_contact=False)
CALL = ActivityKind(reference_id("activity_types", "call"), is_note=False, counts_as_contact=True)


async def test_activity_round_trip_contacts_and_version(
    session: AsyncSession, accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    account = make_account("A", territory_id=world.centro.id, owner_id=world.rep.id)
    other = make_account("B", territory_id=world.centro.id, owner_id=world.rep.id)
    await accounts.add(account)
    await accounts.add(other)
    contacts = SqlAlchemyContactRepository(session)
    ana = Contact.create(account_id=account.id, first_name="Ana", last_name="P")
    stranger = Contact.create(account_id=other.id, first_name="X", last_name="Y")
    await contacts.add(ana)
    await contacts.add(stranger)
    activities = SqlAlchemyActivityRepository(session)

    assert await activities.contacts_belong_to(account.id, [ana.id]) is True
    assert await activities.contacts_belong_to(account.id, [ana.id, stranger.id]) is False
    assert await activities.contacts_belong_to(account.id, []) is True

    visit = Activity.record_done(
        account_id=account.id,
        kind=VISIT,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        now=NOW,
        details={"contact_ids": [ana.id], "outcome": "positive", "subject": "Primera visita"},
    )
    await activities.add(visit)
    loaded = await activities.get(visit.id)
    assert loaded is not None
    assert loaded.contact_ids == frozenset({ana.id})
    assert loaded.outcome is ActivityOutcome.POSITIVE and loaded.done_at == NOW

    loaded.update_details({"notes": "ok", "contact_ids": []})
    await activities.save(loaded, expected_version=1)
    reloaded = await activities.get(visit.id)
    assert reloaded is not None and reloaded.version == 2
    assert reloaded.notes == "ok" and reloaded.contact_ids == frozenset()
    with pytest.raises(ConcurrentModificationError):
        await activities.save(reloaded, expected_version=1)


async def test_refresh_activity_summary(
    session: AsyncSession, accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    account = make_account("A", territory_id=world.centro.id, owner_id=world.rep.id)
    await accounts.add(account)
    activities = SqlAlchemyActivityRepository(session)

    await accounts.refresh_activity_summary(account.id)
    empty = await accounts.get(account.id)
    assert empty is not None
    assert empty.last_contact_at is None and empty.next_activity_at is None

    note = Activity.record_done(
        account_id=account.id, kind=NOTE, owner_id=world.rep.id, created_by=world.rep.id, now=NOW
    )
    old_visit = Activity.record_done(
        account_id=account.id,
        kind=VISIT,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        now=NOW,
        scheduled_at=NOW - timedelta(days=10),
    )
    recent_visit = Activity.record_done(
        account_id=account.id,
        kind=VISIT,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        now=NOW,
        scheduled_at=NOW - timedelta(days=2),
    )
    later_call = Activity.plan(
        account_id=account.id,
        kind=CALL,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        scheduled_at=NOW + timedelta(days=5),
    )
    soon_call = Activity.plan(
        account_id=account.id,
        kind=CALL,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        scheduled_at=NOW + timedelta(days=1),
    )
    cancelled = Activity.plan(
        account_id=account.id,
        kind=CALL,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        scheduled_at=NOW + timedelta(hours=1),
    )
    cancelled.cancel("no")
    for activity in (note, old_visit, recent_visit, later_call, soon_call, cancelled):
        await activities.add(activity)

    await accounts.refresh_activity_summary(account.id)

    refreshed = await accounts.get(account.id)
    assert refreshed is not None
    assert refreshed.last_contact_at == NOW - timedelta(days=2)  # note excluded
    assert refreshed.next_activity_at == NOW + timedelta(days=1)  # cancelled excluded
