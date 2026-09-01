from decimal import Decimal
from uuid import UUID

import pytest

from app.application.catalogue.commands import CreateProduct, ImportProduct, UpdateProduct
from app.application.catalogue.service import ProductService, UpsertOutcome
from app.application.reference.catalogue_entry import CatalogueOutcome
from app.application.reference.commands import CreateProductFamily, UpdateProductFamily
from app.application.reference.service import ProductFamilyService
from app.domain.catalogue.entities import ProductKind
from app.domain.catalogue.errors import (
    BrandNotFoundError,
    FamilyNotFoundError,
    SkuAlreadyExistsError,
    SkuLockedError,
)
from app.domain.reference.entities import Brand, ProductFamily
from app.domain.shared.errors import (
    ConcurrentModificationError,
    NotFoundError,
    PermissionDeniedError,
)
from app.domain.shared.ids import new_id
from app.domain.territories.entities import Division
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.catalogue import InMemoryProductFamilyRepository
from tests.unit.fakes.repositories import InMemoryDivisionRepository

VASCULAR = Division(id=new_id(), code="vascular", name_es="Vascular", sort_order=40)
NEUROLOGY = Division(id=new_id(), code="neurology", name_es="Neurología", sort_order=50)
HADECO = Brand.create(name="Hadeco", is_own=True, division_ids=frozenset())
VINNO = Brand.create(name="Vinno", is_own=False, division_ids=frozenset())
DOPPLERS = ProductFamily.create(name="Dopplers", division_id=VASCULAR.id, sort_order=10)
EEG = ProductFamily.create(name="Electroencefalografía", division_id=NEUROLOGY.id, sort_order=10)


def make_user(role: Role) -> User:
    return User.create(
        email=Email(f"{new_id()}@quermed.com"),
        full_name=role.value,
        role=role,
        password_hash="h",
        territory_ids=frozenset(),
        division_ids=frozenset(),
    )


BACK_OFFICE = make_user(Role.BACK_OFFICE)
ADMIN = make_user(Role.ADMIN)
REP = make_user(Role.SALES_REP)
MANAGER = make_user(Role.SALES_MANAGER)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.divisions = InMemoryDivisionRepository([VASCULAR, NEUROLOGY])
    uow.brands.rows = {HADECO.id: HADECO, VINNO.id: VINNO}
    uow.product_families = InMemoryProductFamilyRepository([DOPPLERS, EEG])
    return uow


def create_command(**overrides: object) -> CreateProduct:
    values: dict[str, object] = {
        "sku": "had-1000",
        "name": "Doppler ES-100",
        "brand_id": HADECO.id,
        "family_id": DOPPLERS.id,
        "kind": ProductKind.EQUIPMENT,
        "list_price": Decimal("1250.50"),
    }
    values.update(overrides)
    return CreateProduct(**values)  # type: ignore[arg-type]


async def test_create_normalises_links_brand_division_and_audits(uow: FakeUnitOfWork) -> None:
    product = await ProductService(uow).create(
        create_command(cost_price=Decimal("800")), actor=BACK_OFFICE
    )

    assert product.sku == "HAD-1000" and product.created_by == BACK_OFFICE.id
    assert product.cost_price == Decimal("800.00")
    assert uow.actions() == ["product.created"]
    snapshot = uow.committed_events[0].changes
    assert snapshot["cost_price"] == {"before": None, "after": "800.00"}
    assert snapshot["kind"] == {"before": None, "after": "equipment"}
    assert VASCULAR.id in uow.brands.rows[HADECO.id].division_ids


@pytest.mark.parametrize("actor", [REP, MANAGER])
async def test_only_admin_and_back_office_write(uow: FakeUnitOfWork, actor: User) -> None:
    with pytest.raises(PermissionDeniedError):
        await ProductService(uow).create(create_command(), actor=actor)
    assert uow.actions() == []


async def test_create_rejects_duplicate_sku_with_existing_id(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)
    first = await service.create(create_command(), actor=ADMIN)

    with pytest.raises(SkuAlreadyExistsError) as error:
        await service.create(create_command(sku=" HAD-1000 "), actor=ADMIN)
    assert error.value.existing_product_id == first.id
    assert error.value.extensions == {"existing_product_id": str(first.id)}


async def test_create_rejects_unknown_brand_and_family(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)
    with pytest.raises(BrandNotFoundError):
        await service.create(create_command(brand_id=new_id()), actor=ADMIN)
    with pytest.raises(FamilyNotFoundError):
        await service.create(create_command(family_id=new_id()), actor=ADMIN)


async def test_update_audits_diffs_and_relinks_brand(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)
    product = await service.create(create_command(), actor=BACK_OFFICE)

    updated = await service.update(
        product.id,
        UpdateProduct(
            expected_version=1,
            changes={"list_price": "1300", "family_id": EEG.id, "brand_id": VINNO.id},
        ),
        actor=BACK_OFFICE,
    )

    assert updated.version == 2 and updated.list_price == Decimal("1300.00")
    assert uow.actions() == ["product.created", "product.updated"]
    changes = uow.committed_events[1].changes
    assert changes["list_price"] == {"before": "1250.50", "after": "1300.00"}
    assert NEUROLOGY.id in uow.brands.rows[VINNO.id].division_ids

    with pytest.raises(ConcurrentModificationError):
        await service.update(
            product.id, UpdateProduct(expected_version=1, changes={"name": "x"}), actor=ADMIN
        )
    with pytest.raises(NotFoundError):
        await service.update(
            new_id(), UpdateProduct(expected_version=1, changes={"name": "x"}), actor=ADMIN
        )


async def test_update_without_changes_records_nothing(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)
    product = await service.create(create_command(), actor=ADMIN)

    await service.update(
        product.id,
        UpdateProduct(expected_version=1, changes={"name": "Doppler ES-100"}),
        actor=ADMIN,
    )

    assert uow.actions() == ["product.created"]


async def test_update_sku_locked_when_referenced(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)
    product = await service.create(create_command(), actor=ADMIN)
    await service.update(
        product.id, UpdateProduct(expected_version=1, changes={"sku": "had-100o"}), actor=ADMIN
    )
    assert (await uow.products.get(product.id)).sku == "HAD-100O"  # type: ignore[union-attr]

    uow.products.referenced.add(product.id)
    with pytest.raises(SkuLockedError):
        await service.update(
            product.id, UpdateProduct(expected_version=2, changes={"sku": "HAD-1000"}), actor=ADMIN
        )


async def test_update_rejects_unknown_fields(uow: FakeUnitOfWork) -> None:
    with pytest.raises(PermissionDeniedError):
        await ProductService(uow).update(
            new_id(), UpdateProduct(expected_version=1, changes={"is_active": False}), actor=ADMIN
        )


async def test_activate_and_deactivate_are_idempotent_and_audited(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)
    product = await service.create(create_command(), actor=ADMIN)

    retired = await service.set_active(
        product.id, active=False, expected_version=1, actor=BACK_OFFICE
    )
    assert retired.is_active is False and retired.version == 2
    again = await service.set_active(product.id, active=False, expected_version=2, actor=ADMIN)
    assert again.version == 2
    revived = await service.set_active(product.id, active=True, expected_version=2, actor=ADMIN)
    assert revived.is_active and revived.version == 3
    assert uow.actions() == ["product.created", "product.deactivated", "product.activated"]
    assert uow.committed_events[1].changes == {"is_active": {"before": True, "after": False}}

    with pytest.raises(ConcurrentModificationError):
        await service.set_active(product.id, active=False, expected_version=1, actor=ADMIN)
    with pytest.raises(PermissionDeniedError):
        await service.set_active(product.id, active=False, expected_version=3, actor=REP)


def import_row(**overrides: object) -> ImportProduct:
    values: dict[str, object] = {
        "sku": "had-1000",
        "name": "Doppler ES-100",
        "brand_code": "hadeco",
        "family_code": "dopplers",
        "kind": ProductKind.EQUIPMENT,
        "list_price": Decimal("1250.50"),
    }
    values.update(overrides)
    return ImportProduct(**values)  # type: ignore[arg-type]


async def test_upsert_creates_updates_and_detects_unchanged(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)

    created = await service.upsert_by_sku(import_row(), actor=ADMIN)
    assert created.outcome is UpsertOutcome.CREATED
    assert created.product.sku == "HAD-1000"

    unchanged = await service.upsert_by_sku(import_row(), actor=ADMIN)
    assert unchanged.outcome is UpsertOutcome.UNCHANGED
    assert unchanged.product.version == 1

    updated = await service.upsert_by_sku(
        import_row(list_price=Decimal("1300"), brand_code=None, brand_name="HADECO"),
        actor=ADMIN,
    )
    assert updated.outcome is UpsertOutcome.UPDATED
    assert updated.product.version == 2 and updated.product.list_price == Decimal("1300.00")
    assert uow.actions() == ["product.created", "product.updated"]
    assert uow.committed_events[1].changes["list_price"] == {
        "before": "1250.50",
        "after": "1300.00",
    }


async def test_upsert_never_changes_sku_and_fails_unknown_masters(uow: FakeUnitOfWork) -> None:
    service = ProductService(uow)
    await service.upsert_by_sku(import_row(), actor=ADMIN)

    with pytest.raises(FamilyNotFoundError):
        await service.upsert_by_sku(import_row(family_code="laser"), actor=ADMIN)
    with pytest.raises(BrandNotFoundError):
        await service.upsert_by_sku(import_row(brand_code="nope"), actor=ADMIN)
    with pytest.raises(BrandNotFoundError):
        await service.upsert_by_sku(import_row(brand_code=None), actor=ADMIN)
    with pytest.raises(PermissionDeniedError):
        await service.upsert_by_sku(import_row(), actor=REP)
    assert len(uow.products.rows) == 1
    assert uow.actions() == ["product.created"]


async def test_family_service_creates_updates_and_audits(uow: FakeUnitOfWork) -> None:
    service = ProductFamilyService(uow)

    family, outcome = await service.create(
        CreateProductFamily(name=" Láser ", division_id=VASCULAR.id), acting_user_id=ADMIN.id
    )
    assert family.code == "laser" and family.sort_order == 20
    assert outcome is CatalogueOutcome.CREATED
    assert uow.actions() == ["product_family.created"]

    # Same name, same division: the existing family is handed back untouched.
    existing, reused = await service.create(
        CreateProductFamily(name="dopplers", division_id=VASCULAR.id),
        acting_user_id=ADMIN.id,
    )
    assert existing.code == "dopplers" and reused is CatalogueOutcome.REUSED
    with pytest.raises(UnknownReferenceError):
        await service.create(
            CreateProductFamily(name="X", division_id=new_id()), acting_user_id=ADMIN.id
        )

    updated = await service.update(
        family.id,
        UpdateProductFamily(expected_version=1, name="Láser quirúrgico", is_active=False),
        acting_user_id=ADMIN.id,
    )
    assert updated.version == 2 and updated.name_es == "Láser quirúrgico"
    assert updated.division_id == VASCULAR.id
    assert uow.actions() == ["product_family.created", "product_family.updated"]
    assert uow.committed_events[1].changes["is_active"] == {"before": True, "after": False}

    with pytest.raises(ConcurrentModificationError):
        await service.update(
            family.id, UpdateProductFamily(expected_version=1, name="x"), acting_user_id=ADMIN.id
        )
    with pytest.raises(NotFoundError):
        await service.update(
            new_id(), UpdateProductFamily(expected_version=1, name="x"), acting_user_id=ADMIN.id
        )


def test_fixture_ids_are_distinct() -> None:
    ids: set[UUID] = {VASCULAR.id, NEUROLOGY.id, HADECO.id, VINNO.id, DOPPLERS.id, EEG.id}
    assert len(ids) == 6
