from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.search.queries import SearchQueries, SearchResults
from app.application.search.router import parse_query
from app.domain.accounts.entities import Account, PhoneEntry
from app.domain.contacts.entities import Contact
from app.domain.opportunities.entities import Opportunity
from app.domain.quotes.entities import Quote, QuoteConditions, QuoteLineDraft
from app.domain.shared.policies import ScopeFilter
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.contacts import SqlAlchemyContactRepository
from app.infrastructure.db.repositories.opportunities import SqlAlchemyOpportunityRepository
from app.infrastructure.db.repositories.quotes import SqlAlchemyQuoteRepository
from app.infrastructure.db.repositories.scope import scoped_accounts
from tests.integration.repositories.conftest import World, make_account
from tests.integration.repositories.test_opportunity_repository import make_opportunity

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


def scope_for(world: World) -> Select[tuple[object]]:
    scope = ScopeFilter(
        user_id=world.rep.id,
        territory_ids=frozenset({world.centro.id}),
        division_ids=frozenset(),
    )
    return scoped_accounts(select(AccountModel.id), scope)


async def search(
    session: AsyncSession, term: str, account_ids: Select[tuple[object]] | None = None
) -> SearchResults:
    parsed = parse_query(term)
    assert parsed is not None
    return await SearchQueries(session).search(parsed, account_ids)


@dataclass
class Seeded:
    account: Account
    contact: Contact
    opportunity: Opportunity
    quote: Quote
    revision: Quote


async def seed_world(session: AsyncSession, world: World) -> Seeded:
    accounts = SqlAlchemyAccountRepository(session)
    contacts = SqlAlchemyContactRepository(session)
    opportunities = SqlAlchemyOpportunityRepository(session)
    quotes = SqlAlchemyQuoteRepository(session)

    perez_clinic = make_account(
        "Clínica Pérez",
        territory_id=world.centro.id,
        owner_id=world.rep.id,
        tax_id="12345678Z",
        phone="+34910111222",
    )
    await accounts.add(perez_clinic)

    contact = Contact.create(
        account_id=perez_clinic.id,
        first_name="Ana",
        last_name="Perez",
        details={
            "email": "ana@perez.es",
            "phones": [PhoneEntry.create(label="Móvil", number="+34612345678")],
        },
    )
    await contacts.add(contact)

    opportunity, change, _pipeline = await make_opportunity(
        session,
        world,
        marker="S",
        name="Doppler búsqueda",
        is_tender=True,
        tender_reference="EXP-2026/99",
    )
    await opportunities.add(opportunity)
    await opportunities.add_stage_change(change)

    quote = Quote.create(
        opportunity_id=opportunity.id,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        year=2026,
        number=await quotes.allocate_number(2026),
        conditions=QuoteConditions(),
        lines=[QuoteLineDraft(description="Doppler", quantity=1, unit_price="1000")],
        now=NOW,
    )
    await quotes.add(quote)
    quote.send(now=NOW)
    await quotes.save(quote, expected_version=1)
    superseded = quote.revise(created_by=world.rep.id, now=NOW)
    await quotes.save(quote, expected_version=2)
    await quotes.add(superseded)

    return Seeded(
        account=perez_clinic,
        contact=contact,
        opportunity=opportunity,
        quote=quote,
        revision=superseded,
    )


async def test_accent_tolerance_both_ways(session: AsyncSession, world: World) -> None:
    data = await seed_world(session, world)

    unaccented = await search(session, "perez")
    assert any(hit.id == data.account.id for hit in unaccented.accounts.items)
    assert any(hit.id == data.contact.id for hit in unaccented.contacts.items)

    accented = await search(session, "Pérez")
    assert any(hit.id == data.contact.id for hit in accented.contacts.items)


async def test_caps_totals_and_has_more(session: AsyncSession, world: World) -> None:
    accounts = SqlAlchemyAccountRepository(session)
    for index in range(7):
        await accounts.add(
            make_account(
                f"Centro Búsqueda {index}", territory_id=world.centro.id, owner_id=world.rep.id
            )
        )

    result = await search(session, "búsqueda")

    assert len(result.accounts.items) == 5
    assert result.accounts.total == 7
    assert result.accounts.has_more is True
    assert result.contacts.total == 0 and result.contacts.has_more is False


async def test_scope_filters_every_group(session: AsyncSession, world: World) -> None:
    data = await seed_world(session, world)
    accounts = SqlAlchemyAccountRepository(session)
    foreign = make_account("Clínica Pérez Norte", territory_id=world.norte.id, owner_id=None)
    await accounts.add(foreign)

    scoped = await search(session, "perez", scope_for(world))
    assert {hit.id for hit in scoped.accounts.items} == {data.account.id}

    unscoped = await search(session, "perez")
    assert {hit.id for hit in unscoped.accounts.items} >= {data.account.id, foreign.id}


async def test_quote_number_and_current_versions_only(session: AsyncSession, world: World) -> None:
    data = await seed_world(session, world)
    quote = data.quote
    revision = data.revision

    result = await search(session, f"P-2026-{quote.number:04d}")
    ids = {hit.id for hit in result.quotes.items}
    assert revision.id in ids
    assert quote.id not in ids

    partial = await search(session, "P-2026")
    assert revision.id in {hit.id for hit in partial.quotes.items}


async def test_phone_email_and_tender_routes(session: AsyncSession, world: World) -> None:
    data = await seed_world(session, world)

    by_phone = await search(session, "612 34 56 78")
    assert any(hit.id == data.contact.id for hit in by_phone.contacts.items)

    by_email = await search(session, "ana@perez.es")
    assert any(hit.id == data.contact.id for hit in by_email.contacts.items)

    by_cif = await search(session, "12345678-z")
    assert any(hit.id == data.account.id for hit in by_cif.accounts.items)

    by_tender = await search(session, "EXP-2026")
    assert any(hit.id == data.opportunity.id for hit in by_tender.opportunities.items)
