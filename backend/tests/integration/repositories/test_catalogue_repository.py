from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.catalogue.queries import ProductFilters, ProductQueries
from app.application.shared.pagination import PageParams, SortField
from app.domain.catalogue.entities import Product, ProductKind
from app.domain.catalogue.errors import SkuAlreadyExistsError
from app.domain.reference.entities import ProductFamily
from app.domain.reference.errors import ProductFamilyNameAlreadyExistsError
from app.domain.shared.errors import ConcurrentModificationError, InvalidSortFieldError
from app.infrastructure.db.repositories.catalogue import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.reference import (
    SqlAlchemyBrandRepository,
    SqlAlchemyProductFamilyRepository,
)
from app.infrastructure.db.seed import division_id, reference_id
from tests.integration.repositories.conftest import VASCULAR_ID, World

pytestmark = pytest.mark.integration

HADECO_ID: UUID = reference_id("brands", "hadeco")
VIASONIX_ID: UUID = reference_id("brands", "viasonix")
DOPPLERS_ID: UUID = reference_id("product_families", "dopplers")
CARROS_ID: UUID = reference_id("product_families", "carros")


def make_product(sku: str, name: str, actor: UUID, **overrides: object) -> Product:
    values: dict[str, object] = {
        "sku": sku,
        "name": name,
        "brand_id": HADECO_ID,
        "family_id": DOPPLERS_ID,
        "kind": ProductKind.EQUIPMENT,
        "list_price": "100",
        "created_by": actor,
    }
    values.update(overrides)
    return Product.create(**values)  # type: ignore[arg-type]


def page(sort: str = "name", *, page_size: int = 25, descending: bool = False) -> PageParams:
    return PageParams(page=1, page_size=page_size, sort=[SortField(sort, descending)])


async def test_product_round_trip_and_sku_lookup(session: AsyncSession, world: World) -> None:
    products = SqlAlchemyProductRepository(session)
    product = make_product("had-1000", "Doppler ES-100", world.back_office.id, cost_price="60.5")

    await products.add(product)

    stored = await products.get(product.id)
    assert stored is not None
    assert stored.sku == "HAD-1000"
    assert stored.list_price == Decimal("100.00") and stored.cost_price == Decimal("60.50")
    assert stored.kind is ProductKind.EQUIPMENT and stored.unit == "ud"
    by_sku = await products.get_by_sku("  had-1000 ")
    assert by_sku is not None and by_sku.id == product.id
    assert await products.get_by_sku("nope") is None
    assert await products.is_referenced(product.id) is False


async def test_product_save_conflicts_and_duplicate_sku(
    session: AsyncSession, world: World
) -> None:
    products = SqlAlchemyProductRepository(session)
    product = make_product("HAD-1000", "Doppler", world.back_office.id)
    await products.add(product)

    product.rename("Doppler ES-100 Plus")
    await products.save(product, expected_version=1)
    assert product.version == 2
    with pytest.raises(ConcurrentModificationError):
        await products.save(product, expected_version=1)

    with pytest.raises(SkuAlreadyExistsError):
        await products.add(make_product("had-1000", "Other", world.back_office.id))


async def test_family_repository_order_uniqueness_and_next_sort(session: AsyncSession) -> None:
    families = SqlAlchemyProductFamilyRepository(session)

    listed = await families.list_all()
    codes = [f.code for f in listed]
    assert codes.index("medios_cultivo") < codes.index("dopplers") < codes.index("carros")
    assert await families.next_sort_order(division_id("vascular")) == 30

    laser = ProductFamily.create(name="Láser", division_id=VASCULAR_ID, sort_order=30)
    await families.add(laser)
    assert (await families.get_by_code("laser")) is not None

    duplicate_name = ProductFamily.create(name="dopplers", division_id=VASCULAR_ID, sort_order=40)
    with pytest.raises(ProductFamilyNameAlreadyExistsError):
        async with session.begin_nested():
            await families.add(duplicate_name)

    # same slug code in another division: the code stays globally unique
    same_name_other_division = ProductFamily.create(
        name="Láser", division_id=division_id("neurology"), sort_order=30
    )
    with pytest.raises(ProductFamilyNameAlreadyExistsError):
        async with session.begin_nested():
            await families.add(same_name_other_division)

    stored = await families.get_by_code("dopplers")
    assert stored is not None
    stored.rename("Doppler vascular")
    await families.save(stored, expected_version=stored.version)
    with pytest.raises(ConcurrentModificationError):
        await families.save(stored, expected_version=1)


async def test_brand_ensure_division_is_idempotent(session: AsyncSession) -> None:
    brands = SqlAlchemyBrandRepository(session)

    assert await brands.ensure_division(HADECO_ID, VASCULAR_ID) is True
    assert await brands.ensure_division(HADECO_ID, VASCULAR_ID) is False
    brand = await brands.get(HADECO_ID)
    assert brand is not None and VASCULAR_ID in brand.division_ids


async def test_catalogue_search_filters_and_ranking(session: AsyncSession, world: World) -> None:
    products = SqlAlchemyProductRepository(session)
    actor = world.back_office.id
    await products.add(make_product("HAD-1000", "Doppler ES-100", actor, cost_price="60"))
    await products.add(make_product("HAD-1010", "Sonda 8 MHz", actor, kind=ProductKind.CONSUMABLE))
    await products.add(
        make_product("VX-200", "Doppler Falcon", actor, brand_id=VIASONIX_ID, list_price="9000")
    )
    await products.add(make_product("CAR-1", "Carro de anestesia", actor, family_id=CARROS_ID))
    retired = make_product("OLD-1", "Doppler antiguo", actor)
    retired.deactivate()
    await products.add(retired)
    queries = ProductQueries(session)

    by_prefix = await queries.list_page(page(), ProductFilters(q="had-10"), cost_viewer=False)
    assert [i.sku for i in by_prefix.items] == ["HAD-1000", "HAD-1010"]

    by_name = await queries.list_page(page(), ProductFilters(q="doppler"), cost_viewer=True)
    assert [i.name for i in by_name.items] == ["Doppler ES-100", "Doppler Falcon"]
    assert by_name.items[0].cost_price == Decimal("60.00")
    assert by_name.items[0].brand.name == "Hadeco" and by_name.items[0].family.name == "Dopplers"

    short = await queries.list_page(page(), ProductFilters(q="do"), cost_viewer=False)
    assert short.total == 0  # two characters: SKU prefix only, no name search

    vascular = await queries.list_page(
        page(), ProductFilters(division_id=VASCULAR_ID), cost_viewer=False
    )
    assert vascular.total == 3
    competitors = await queries.list_page(page(), ProductFilters(own=False), cost_viewer=False)
    assert competitors.total == 0
    consumables = await queries.list_page(
        page(), ProductFilters(kind=ProductKind.CONSUMABLE), cost_viewer=False
    )
    assert [i.sku for i in consumables.items] == ["HAD-1010"]
    everything = await queries.list_page(page(), ProductFilters(is_active=None), cost_viewer=True)
    assert everything.total == 5
    only_retired = await queries.list_page(
        page(), ProductFilters(is_active=False), cost_viewer=True
    )
    assert [i.sku for i in only_retired.items] == ["OLD-1"]

    priciest = await queries.list_page(
        page("list_price", descending=True), ProductFilters(), cost_viewer=False
    )
    assert priciest.items[0].sku == "VX-200"
    with pytest.raises(InvalidSortFieldError):
        await queries.list_page(page("cost_price"), ProductFilters(), cost_viewer=False)
    by_cost = await queries.list_page(page("cost_price"), ProductFilters(), cost_viewer=True)
    assert by_cost.items[0].sku == "HAD-1000"  # nulls last

    detail = await queries.get(retired.id)
    assert detail is not None and detail.is_active is False
    assert await queries.get(actor) is None


async def test_name_search_uses_trigram_index(session: AsyncSession, world: World) -> None:
    await session.execute(
        text(
            "INSERT INTO products (id, sku, name, brand_id, family_id, kind, list_price, "
            "created_by) SELECT gen_random_uuid(), 'SKU-' || g, 'Producto ' || g || ' ' || "
            "md5(g::text), :brand, :family, 'consumable', 10, :actor "
            "FROM generate_series(1, 3000) AS g"
        ),
        {"brand": HADECO_ID, "family": DOPPLERS_ID, "actor": world.back_office.id},
    )
    await session.execute(text("ANALYZE products"))

    await session.execute(text("SET enable_seqscan = off"))
    plan = await session.execute(
        text("EXPLAIN SELECT id FROM products WHERE name ILIKE '%tambre%'")
    )
    plan_text = "\n".join(row[0] for row in plan.all())
    await session.execute(text("SET enable_seqscan = on"))
    assert "ix_products_name_trgm" in plan_text, plan_text
