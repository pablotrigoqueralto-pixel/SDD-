"""Product use cases: create, update, activate/deactivate and import upserts."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.application.catalogue.commands import CreateProduct, ImportProduct, UpdateProduct
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.catalogue.entities import Product, ProductKind
from app.domain.catalogue.errors import (
    BrandNotFoundError,
    FamilyNotFoundError,
    SkuAlreadyExistsError,
)
from app.domain.reference.entities import Brand, ProductFamily
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.users.entities import User
from app.domain.users.roles import Role

CATALOGUE_WRITER_ROLES: frozenset[Role] = frozenset({Role.ADMIN, Role.BACK_OFFICE})
UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "sku",
        "name",
        "brand_id",
        "family_id",
        "kind",
        "list_price",
        "cost_price",
        "unit",
        "description",
    }
)


class UpsertOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class UpsertResult:
    product: Product
    outcome: UpsertOutcome


def ensure_catalogue_writer(actor: User) -> None:
    if actor.role not in CATALOGUE_WRITER_ROLES:
        raise PermissionDeniedError("Your role cannot modify the catalogue")


async def _load_product(uow: UnitOfWork, product_id: UUID) -> Product:
    product = await uow.products.get(product_id)
    if product is None:
        raise NotFoundError("Product not found")
    return product


async def _brand_by_id(uow: UnitOfWork, brand_id: UUID) -> Brand:
    brand = await uow.brands.get(brand_id)
    if brand is None:
        raise BrandNotFoundError(str(brand_id))
    return brand


async def _family_by_id(uow: UnitOfWork, family_id: UUID) -> ProductFamily:
    family = await uow.product_families.get(family_id)
    if family is None:
        raise FamilyNotFoundError(str(family_id))
    return family


async def _ensure_sku_free(uow: UnitOfWork, sku: str, product_id: UUID | None) -> None:
    existing = await uow.products.get_by_sku(sku)
    if existing is not None and existing.id != product_id:
        raise SkuAlreadyExistsError(existing.id)


class ProductService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(self, command: CreateProduct, *, actor: User) -> Product:
        ensure_catalogue_writer(actor)
        async with self._uow as uow:
            await _brand_by_id(uow, command.brand_id)
            family = await _family_by_id(uow, command.family_id)
            product = Product.create(
                sku=command.sku,
                name=command.name,
                brand_id=command.brand_id,
                family_id=command.family_id,
                kind=command.kind,
                list_price=command.list_price,
                cost_price=command.cost_price,
                unit=command.unit,
                description=command.description,
                created_by=actor.id,
            )
            await _ensure_sku_free(uow, product.sku, None)
            await uow.products.add(product)
            await uow.brands.ensure_division(product.brand_id, family.division_id)
            uow.audit.record(
                entity_type="product",
                entity_id=product.id,
                action="product.created",
                changes=diff_fields({}, product.snapshot()),
                actor_id=actor.id,
            )
            await uow.commit()
            return product

    async def update(self, product_id: UUID, command: UpdateProduct, *, actor: User) -> Product:
        ensure_catalogue_writer(actor)
        unknown = set(command.changes) - UPDATABLE_FIELDS
        if unknown:
            raise PermissionDeniedError(
                f"Fields cannot be changed here: {', '.join(sorted(unknown))}"
            )
        async with self._uow as uow:
            product = await _load_product(uow, product_id)
            before = product.snapshot()
            await self._apply_changes(uow, product, dict(command.changes))
            await uow.products.save(product, expected_version=command.expected_version)
            changes = diff_fields(before, product.snapshot())
            if changes:
                uow.audit.record(
                    entity_type="product",
                    entity_id=product.id,
                    action="product.updated",
                    changes=changes,
                    actor_id=actor.id,
                )
            await uow.commit()
            return product

    async def set_active(
        self, product_id: UUID, *, active: bool, expected_version: int, actor: User
    ) -> Product:
        ensure_catalogue_writer(actor)
        async with self._uow as uow:
            product = await _load_product(uow, product_id)
            if product.version != expected_version:
                await uow.products.save(product, expected_version=expected_version)  # raises 409
            changed = product.activate() if active else product.deactivate()
            if changed:
                await uow.products.save(product, expected_version=expected_version)
                uow.audit.record(
                    entity_type="product",
                    entity_id=product.id,
                    action="product.activated" if active else "product.deactivated",
                    changes=diff_fields({"is_active": not active}, {"is_active": active}),
                    actor_id=actor.id,
                )
            await uow.commit()
            return product

    async def upsert_by_sku(self, row: ImportProduct, *, actor: User) -> UpsertResult:
        """Import contract (change 08): create or update by Sage code, never touching the code."""
        ensure_catalogue_writer(actor)
        async with self._uow as uow:
            brand = await self._brand_from_row(uow, row)
            family = await uow.product_families.get_by_code(row.family_code)
            if family is None:
                raise FamilyNotFoundError(row.family_code)
            existing = await uow.products.get_by_sku(row.sku)
            if existing is None:
                product = Product.create(
                    sku=row.sku,
                    name=row.name,
                    brand_id=brand.id,
                    family_id=family.id,
                    kind=row.kind,
                    list_price=row.list_price,
                    cost_price=row.cost_price,
                    unit=row.unit,
                    description=row.description,
                    is_active=row.is_active,
                    created_by=actor.id,
                )
                await uow.products.add(product)
                await uow.brands.ensure_division(product.brand_id, family.division_id)
                uow.audit.record(
                    entity_type="product",
                    entity_id=product.id,
                    action="product.created",
                    changes=diff_fields({}, product.snapshot()),
                    actor_id=actor.id,
                )
                await uow.commit()
                return UpsertResult(product, UpsertOutcome.CREATED)

            before = existing.snapshot()
            existing.rename(row.name)
            existing.set_brand(brand.id)
            existing.set_family(family.id)
            existing.set_kind(row.kind)
            existing.set_list_price(row.list_price)
            existing.set_cost_price(row.cost_price)
            existing.set_unit(row.unit)
            existing.set_description(row.description)
            if row.is_active:
                existing.activate()
            else:
                existing.deactivate()
            changes = diff_fields(before, existing.snapshot())
            if not changes:
                return UpsertResult(existing, UpsertOutcome.UNCHANGED)
            await uow.products.save(existing, expected_version=existing.version)
            await uow.brands.ensure_division(existing.brand_id, family.division_id)
            uow.audit.record(
                entity_type="product",
                entity_id=existing.id,
                action="product.updated",
                changes=changes,
                actor_id=actor.id,
            )
            await uow.commit()
            return UpsertResult(existing, UpsertOutcome.UPDATED)

    @staticmethod
    async def _brand_from_row(uow: UnitOfWork, row: ImportProduct) -> Brand:
        reference = row.brand_code or row.brand_name
        if not reference:
            raise BrandNotFoundError("(missing)")
        for brand in await uow.brands.list_all():
            if row.brand_code and brand.code == row.brand_code.strip().lower():
                return brand
            if row.brand_name and brand.name.lower() == row.brand_name.strip().lower():
                return brand
        raise BrandNotFoundError(reference)

    @staticmethod
    async def _apply_changes(uow: UnitOfWork, product: Product, changes: dict[str, Any]) -> None:
        if "sku" in changes:
            referenced = await uow.products.is_referenced(product.id)
            product.change_sku(str(changes["sku"]), referenced=referenced)
            await _ensure_sku_free(uow, product.sku, product.id)
        if "name" in changes:
            product.rename(str(changes["name"]))
        if "brand_id" in changes:
            await _brand_by_id(uow, changes["brand_id"])
            product.set_brand(changes["brand_id"])
        if "family_id" in changes:
            await _family_by_id(uow, changes["family_id"])
            product.set_family(changes["family_id"])
        if "kind" in changes:
            product.set_kind(ProductKind(changes["kind"]))
        if "list_price" in changes:
            product.set_list_price(changes["list_price"])
        if "cost_price" in changes:
            product.set_cost_price(changes["cost_price"])
        if "unit" in changes:
            product.set_unit(changes["unit"])
        if "description" in changes:
            product.set_description(changes["description"])
        if "brand_id" in changes or "family_id" in changes:
            family = await _family_by_id(uow, product.family_id)
            await uow.brands.ensure_division(product.brand_id, family.division_id)
