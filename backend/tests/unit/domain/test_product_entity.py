from decimal import Decimal

import pytest

from app.domain.catalogue.entities import Product, ProductKind, normalise_sku
from app.domain.catalogue.errors import (
    PriceInvalidError,
    ProductFieldInvalidError,
    SkuLockedError,
)
from app.domain.reference.entities import ProductFamily
from app.domain.shared.ids import new_id

BRAND = new_id()
FAMILY = new_id()
ACTOR = new_id()


def make_product(**overrides: object) -> Product:
    values: dict[str, object] = {
        "sku": "had-1000",
        "name": "Ecógrafo Vinno E10",
        "brand_id": BRAND,
        "family_id": FAMILY,
        "kind": ProductKind.EQUIPMENT,
        "list_price": "12500",
        "created_by": ACTOR,
    }
    values.update(overrides)
    return Product.create(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("had-1000", "HAD-1000"),
        ("  had-1000 ", "HAD-1000"),
        ("gel   5l", "GEL 5L"),
        ("ab\t12", "AB 12"),
    ],
)
def test_normalise_sku(raw: str, expected: str) -> None:
    assert normalise_sku(raw) == expected


def test_normalise_sku_rejects_empty_and_too_long() -> None:
    with pytest.raises(ProductFieldInvalidError):
        normalise_sku("   ")
    with pytest.raises(ProductFieldInvalidError):
        normalise_sku("X" * 51)


def test_create_applies_defaults_and_quantises_prices() -> None:
    product = make_product(list_price="1250.5", cost_price=800)

    assert product.sku == "HAD-1000"
    assert product.unit == "ud"
    assert product.description is None
    assert product.is_active and product.version == 1
    assert product.list_price == Decimal("1250.50")
    assert product.cost_price == Decimal("800.00")
    assert product.snapshot()["list_price"] == "1250.50"


def test_create_rejects_negative_prices() -> None:
    with pytest.raises(PriceInvalidError) as list_error:
        make_product(list_price="-1")
    assert list_error.value.errors[0]["field"] == "list_price"
    with pytest.raises(PriceInvalidError) as cost_error:
        make_product(cost_price="-0.01")
    assert cost_error.value.errors[0]["field"] == "cost_price"


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "  "},
        {"name": "x" * 201},
        {"unit": "u" * 21},
        {"description": "d" * 2001},
    ],
)
def test_create_rejects_invalid_text_fields(overrides: dict[str, object]) -> None:
    with pytest.raises(ProductFieldInvalidError):
        make_product(**overrides)


def test_cost_is_optional_and_competitor_brand_is_accepted() -> None:
    product = make_product(cost_price=None)
    assert product.cost_price is None
    product.set_cost_price("10")
    assert product.cost_price == Decimal("10.00")
    product.set_cost_price(None)
    assert product.cost_price is None


def test_change_sku_normalises_and_locks_when_referenced() -> None:
    product = make_product()

    product.change_sku(" had-100o ", referenced=False)
    assert product.sku == "HAD-100O"
    product.change_sku("had-100o", referenced=True)  # same code: no-op even when locked
    with pytest.raises(SkuLockedError):
        product.change_sku("HAD-1000", referenced=True)


def test_update_setters_clean_values() -> None:
    product = make_product()
    other_family = new_id()

    product.rename("  Ecógrafo   Vinno  ")
    product.set_family(other_family)
    product.set_kind(ProductKind.SERVICE)
    product.set_unit("")
    product.set_description("   ")
    product.set_list_price("99.999")

    assert product.name == "Ecógrafo Vinno"
    assert product.family_id == other_family
    assert product.kind is ProductKind.SERVICE
    assert product.unit == "ud"
    assert product.description is None
    assert product.list_price == Decimal("100.00")


def test_activate_and_deactivate_are_idempotent() -> None:
    product = make_product()

    assert product.deactivate() is True
    assert product.deactivate() is False
    assert product.is_active is False
    assert product.activate() is True
    assert product.activate() is False


def test_product_family_create_and_mutations() -> None:
    division = new_id()
    family = ProductFamily.create(name="  Láser  ", division_id=division, sort_order=10)

    assert family.code == "laser"
    assert family.name_es == "Láser"
    assert family.division_id == division
    family.rename(" Láser quirúrgico ")
    family.set_sort_order(20)
    family.deactivate()
    assert (family.name_es, family.sort_order, family.is_active) == ("Láser quirúrgico", 20, False)
    family.activate()
    assert family.is_active
