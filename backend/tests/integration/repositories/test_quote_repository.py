from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.catalogue.entities import Product, ProductKind
from app.domain.opportunities.entities import Opportunity
from app.domain.quotes.entities import Quote, QuoteConditions, QuoteLineDraft
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.repositories.catalogue import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.opportunities import SqlAlchemyOpportunityRepository
from app.infrastructure.db.repositories.quotes import SqlAlchemyQuoteRepository
from app.infrastructure.db.seed import reference_id
from tests.integration.repositories.conftest import World
from tests.integration.repositories.test_opportunity_repository import make_opportunity

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


async def stored_opportunity(session: AsyncSession, world: World, marker: str) -> Opportunity:
    repo = SqlAlchemyOpportunityRepository(session)
    opportunity, change, _ = await make_opportunity(session, world, marker=marker)
    await repo.add(opportunity)
    await repo.add_stage_change(change)
    return opportunity


def draft_quote(opportunity: Opportunity, *, number: int, world: World) -> Quote:
    return Quote.create(
        opportunity_id=opportunity.id,
        owner_id=world.rep.id,
        created_by=world.rep.id,
        year=2026,
        number=number,
        conditions=QuoteConditions(validez_dias=30, forma_pago="Transferencia a 30 días"),
        lines=[
            QuoteLineDraft(
                description="Doppler vascular",
                quantity="2",
                unit_price="13000",
                unit_cost="9000",
                product_code="DP-3000",
            ),
            QuoteLineDraft(
                description="Instalación", quantity="1", unit_price="500", vat_rate="10"
            ),
        ],
        now=NOW,
    )


async def test_allocate_number_is_transactional_and_gapless(
    session: AsyncSession, world: World
) -> None:
    repo = SqlAlchemyQuoteRepository(session)

    first = await repo.allocate_number(2026)
    second = await repo.allocate_number(2026)
    assert second == first + 1
    assert await repo.allocate_number(2027) == 1

    # A failed creation rolls its allocation back: the number is handed out again.
    async with session.begin_nested() as savepoint:
        rolled_back = await repo.allocate_number(2026)
        assert rolled_back == second + 1
        await savepoint.rollback()
    assert await repo.allocate_number(2026) == second + 1


async def test_round_trip_lines_sync_and_conflict(session: AsyncSession, world: World) -> None:
    repo = SqlAlchemyQuoteRepository(session)
    opportunity = await stored_opportunity(session, world, "Q1")
    quote = draft_quote(opportunity, number=await repo.allocate_number(2026), world=world)

    await repo.add(quote)

    stored = await repo.get(quote.id)
    assert stored is not None
    assert stored.quote_number == quote.quote_number
    assert stored.conditions.forma_pago == "Transferencia a 30 días"
    assert stored.total_base == Decimal("26500.00")
    assert stored.total_vat == Decimal("5510.00")
    assert stored.total == Decimal("32010.00")
    assert [line.description for line in stored.lines] == ["Doppler vascular", "Instalación"]
    assert stored.lines[0].unit_cost == Decimal("9000.00")
    assert stored.lines[1].product_id is None

    stored.replace_lines([QuoteLineDraft(description="Solo doppler", quantity=1, unit_price=100)])
    await repo.save(stored, expected_version=1)

    reloaded = await repo.get(quote.id)
    assert reloaded is not None
    assert [line.description for line in reloaded.lines] == ["Solo doppler"]
    assert reloaded.total == Decimal("121.00")
    assert reloaded.version_lock == 2

    with pytest.raises(ConcurrentModificationError):
        await repo.save(reloaded, expected_version=1)


async def test_current_version_filtering(session: AsyncSession, world: World) -> None:
    repo = SqlAlchemyQuoteRepository(session)
    opportunity = await stored_opportunity(session, world, "Q2")

    original = draft_quote(opportunity, number=await repo.allocate_number(2026), world=world)
    await repo.add(original)
    original.send(now=NOW)
    await repo.save(original, expected_version=1)

    revision = original.revise(created_by=world.rep.id, now=NOW)
    await repo.save(original, expected_version=2)
    await repo.add(revision)

    other = draft_quote(opportunity, number=await repo.allocate_number(2026), world=world)
    await repo.add(other)

    current = await repo.list_current_for_opportunity(opportunity.id)
    assert {quote.id for quote in current} == {revision.id, other.id}
    assert all(quote.superseded_at is None for quote in current)


async def test_pdf_store_round_trip(session: AsyncSession, world: World) -> None:
    repo = SqlAlchemyQuoteRepository(session)
    opportunity = await stored_opportunity(session, world, "Q3")
    quote = draft_quote(opportunity, number=await repo.allocate_number(2026), world=world)
    await repo.add(quote)

    assert await repo.get_pdf(quote.id) is None
    await repo.store_pdf(quote.id, b"%PDF-1.7 fake")
    assert await repo.get_pdf(quote.id) == b"%PDF-1.7 fake"


async def test_quote_line_marks_product_referenced(session: AsyncSession, world: World) -> None:
    repo = SqlAlchemyQuoteRepository(session)
    products = SqlAlchemyProductRepository(session)
    product = Product.create(
        sku="QUO-1",
        name="Doppler",
        brand_id=reference_id("brands", "hadeco"),
        family_id=reference_id("product_families", "dopplers"),
        kind=ProductKind.EQUIPMENT,
        list_price="12500",
        created_by=world.back_office.id,
    )
    await products.add(product)
    opportunity = await stored_opportunity(session, world, "Q4")
    quote = draft_quote(opportunity, number=await repo.allocate_number(2026), world=world)
    quote.replace_lines(
        [
            QuoteLineDraft(
                description="Doppler", quantity=1, unit_price="12500", product_id=product.id
            )
        ]
    )

    assert await products.is_referenced(product.id) is False
    await repo.add(quote)
    assert await products.is_referenced(product.id) is True

    await repo.delete(quote)
    assert await products.is_referenced(product.id) is False
