from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.entities import ConsentRecord, ConsentSource, ConsentStatus, Contact
from app.domain.reference.entities import JobTitle
from app.domain.reference.errors import JobTitleNameAlreadyExistsError
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import PersonalDataAccessLogModel
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.contacts import (
    SqlAlchemyContactRepository,
    SqlAlchemyPersonalDataAccessLog,
)
from app.infrastructure.db.repositories.reference import SqlAlchemyJobTitleRepository
from app.infrastructure.db.seed import APP_ROLE, reference_id
from tests.integration.repositories.conftest import World, make_account

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 28, 9, 0, tzinfo=UTC)


async def test_contact_round_trip_list_order_and_primary_swap(
    session: AsyncSession, accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    account = make_account("A", territory_id=world.centro.id, owner_id=world.rep.id)
    await accounts.add(account)
    contacts = SqlAlchemyContactRepository(session)
    ana = Contact.create(
        account_id=account.id,
        first_name="Ana",
        last_name="Zamora",
        is_primary=True,
        details={
            "email": "Ana@x.es",
            "mobile": "612345678",
            "preferred_channel": "mobile",
            "job_title_id": reference_id("job_titles", "gynaecologist"),
        },
        consent=ConsentRecord(ConsentStatus.GRANTED, NOW, ConsentSource.VERBAL, world.rep.id),
    )
    bea = Contact.create(account_id=account.id, first_name="Bea", last_name="Alonso")
    inactive = Contact.create(account_id=account.id, first_name="Carlos", last_name="Baja")
    inactive.deactivate()
    for contact in (ana, bea, inactive):
        await contacts.add(contact)

    loaded = await contacts.get(ana.id)
    assert loaded is not None
    assert loaded.consent == ConsentRecord(
        ConsentStatus.GRANTED, NOW, ConsentSource.VERBAL, world.rep.id
    )
    assert loaded.email == "ana@x.es" and loaded.mobile == "+34612345678"

    listed = await contacts.list_by_account(account.id)
    assert [c.first_name for c in listed] == ["Ana", "Bea"]  # primary first, then last name
    everyone = await contacts.list_by_account(account.id, include_inactive=True)
    assert [c.first_name for c in everyone] == ["Ana", "Bea", "Carlos"]

    primary = await contacts.find_primary(account.id)
    assert primary is not None and primary.id == ana.id
    primary.demote()
    await contacts.save(primary, expected_version=1)
    bea.make_primary()
    await contacts.save(bea, expected_version=1)
    assert (await contacts.find_primary(account.id)) is not None
    assert (await contacts.find_primary(account.id)).id == bea.id  # type: ignore[union-attr]
    with pytest.raises(ConcurrentModificationError):
        await contacts.save(bea, expected_version=1)


async def test_access_log_is_append_only_for_the_app_role(
    session: AsyncSession, accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    account = make_account("A", territory_id=None, owner_id=None)
    await accounts.add(account)
    contact = Contact.create(account_id=account.id, first_name="A", last_name="B")
    await SqlAlchemyContactRepository(session).add(contact)
    log = SqlAlchemyPersonalDataAccessLog(session)

    await log.record(user_id=world.back_office.id, contact_ids=[contact.id], trace_id="t-1")
    await log.record(user_id=world.back_office.id, contact_ids=[], trace_id=None)

    rows = (
        (
            await session.execute(
                select(PersonalDataAccessLogModel).where(
                    PersonalDataAccessLogModel.contact_id == contact.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1 and rows[0].trace_id == "t-1"

    await session.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    with pytest.raises(ProgrammingError):
        await session.execute(update(PersonalDataAccessLogModel).values(trace_id="x"))


async def test_job_title_repository(session: AsyncSession) -> None:
    titles = SqlAlchemyJobTitleRepository(session)

    listed = await titles.list_all()
    assert len(listed) == 11 and listed[0].code == "gynaecologist"
    assert await titles.next_sort_order() == 120
    assert await titles.existing_ids([listed[0].id, reference_id("x", "y")]) == frozenset(
        {listed[0].id}
    )

    created = JobTitle.create(name="Farmacia hospitalaria", sort_order=120)
    await titles.add(created)
    created.rename("Farmacia")
    await titles.save(created, expected_version=1)
    assert (await titles.get(created.id)) is not None
    assert (await titles.get(created.id)).name_es == "Farmacia"  # type: ignore[union-attr]

    with pytest.raises(JobTitleNameAlreadyExistsError):
        await titles.add(JobTitle.create(name="gerencia", sort_order=130))
