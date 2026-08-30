"""Catalogue importer: Sage rows through the change-05 upsert-by-SKU contract."""

from decimal import Decimal, InvalidOperation

from app.application.catalogue.commands import ImportProduct
from app.application.catalogue.service import ProductService, UpsertOutcome
from app.application.imports.report import (
    ImportReport,
    RowOutcome,
    RowReport,
    normalise_text,
    parse_spanish_number,
)
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.catalogue.entities import ProductKind, normalise_price, normalise_sku
from app.domain.reference.entities import Brand, ProductFamily
from app.domain.shared.errors import DomainError, ValidationFailedError
from app.domain.users.entities import User
from app.infrastructure.imports.reader import read_table

PRODUCT_COLUMNS: dict[str, tuple[str, ...]] = {
    "sku": ("sku", "código", "codigo", "referencia", "codigo sage", "código sage"),
    "name": ("name", "nombre", "producto", "denominación", "denominacion"),
    "brand": ("brand", "marca", "brand_name", "fabricante"),
    "family": ("family", "familia", "family_code"),
    "kind": ("kind", "tipo"),
    "list_price": ("list_price", "pvp", "precio", "precio venta"),
    "cost_price": ("cost_price", "coste", "cost", "precio coste"),
    "unit": ("unit", "unidad"),
    "description": ("description", "descripcion", "descripción", "observaciones"),
}
PRODUCT_REQUIRED = frozenset({"sku", "name", "family", "list_price"})

KIND_ALIASES: dict[str, ProductKind] = {
    "equipment": ProductKind.EQUIPMENT,
    "equipo": ProductKind.EQUIPMENT,
    "consumable": ProductKind.CONSUMABLE,
    "consumible": ProductKind.CONSUMABLE,
    "fungible": ProductKind.CONSUMABLE,
    "service": ProductKind.SERVICE,
    "servicio": ProductKind.SERVICE,
}

_OUTCOMES = {
    UpsertOutcome.CREATED: RowOutcome.CREATED,
    UpsertOutcome.UPDATED: RowOutcome.UPDATED,
    UpsertOutcome.UNCHANGED: RowOutcome.UNCHANGED,
}


def _row_error(row_number: int, label: str, message: str) -> RowReport:
    return RowReport(row=row_number, outcome=RowOutcome.ERROR, label=label, message=message)


def _price(raw: str, *, field: str) -> Decimal:
    try:
        return parse_spanish_number(raw)
    except InvalidOperation as exc:
        raise ValidationFailedError(
            [{"field": field, "message": f"Invalid price: {raw}", "code": "price_invalid"}]
        ) from exc


def _kind(raw: str) -> ProductKind:
    key = normalise_text(raw) if raw else "equipment"
    kind = KIND_ALIASES.get(key)
    if kind is None:
        raise ValidationFailedError(
            [{"field": "kind", "message": f"Unknown kind: {raw}", "code": "kind_invalid"}]
        )
    return kind


def _resolve_family(families: list[ProductFamily], raw: str) -> ProductFamily:
    wanted = normalise_text(raw)
    for family in families:
        if family.code == raw.strip().lower() or normalise_text(family.name_es) == wanted:
            return family
    raise ValidationFailedError(
        [{"field": "family", "message": f"Unknown family: {raw}", "code": "family_not_found"}]
    )


def _resolve_brand(brands: list[Brand], raw: str) -> Brand:
    wanted = normalise_text(raw)
    for brand in brands:
        if brand.code == raw.strip().lower() or normalise_text(brand.name) == wanted:
            return brand
    raise ValidationFailedError(
        [{"field": "brand", "message": f"Unknown brand: {raw}", "code": "brand_not_found"}]
    )


class ProductImporter:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._service = ProductService(uow)

    async def run(
        self, filename: str, content: bytes, *, dry_run: bool, actor: User
    ) -> ImportReport:
        table = read_table(filename, content, columns=PRODUCT_COLUMNS, required=PRODUCT_REQUIRED)
        async with self._uow as uow:
            families = await uow.product_families.list_all()
            brands = await uow.brands.list_all()
        rows: list[RowReport] = []
        for index, raw in enumerate(table, start=2):  # row 1 is the header
            label = raw["sku"] or raw["name"] or f"fila {index}"
            try:
                command = self._command(raw, families, brands)
            except (ValidationFailedError, DomainError) as error:
                rows.append(_row_error(index, label, _message(error)))
                continue
            if dry_run:
                outcome = await self._preview(command)
                rows.append(RowReport(row=index, outcome=outcome, label=label))
                continue
            try:
                result = await self._service.upsert_by_sku(command, actor=actor)
            except (ValidationFailedError, DomainError) as error:
                rows.append(_row_error(index, label, _message(error)))
                continue
            rows.append(RowReport(row=index, outcome=_OUTCOMES[result.outcome], label=label))
        report = ImportReport(rows=rows)
        if not dry_run:
            await self._audit(filename, report, actor)
        return report

    def _command(
        self, raw: dict[str, str], families: list[ProductFamily], brands: list[Brand]
    ) -> ImportProduct:
        family = _resolve_family(families, raw["family"])
        brand = _resolve_brand(brands, raw["brand"]) if raw["brand"] else None
        if brand is None:
            raise ValidationFailedError(
                [{"field": "brand", "message": "Brand is required", "code": "brand_required"}]
            )
        return ImportProduct(
            sku=raw["sku"],
            name=raw["name"],
            family_code=family.code,
            kind=_kind(raw["kind"]),
            list_price=_price(raw["list_price"], field="list_price"),
            brand_code=brand.code,
            cost_price=_price(raw["cost_price"], field="cost_price") if raw["cost_price"] else None,
            unit=raw["unit"] or None,
            description=raw["description"] or None,
        )

    async def _preview(self, command: ImportProduct) -> RowOutcome:
        """Would-be outcome without writing: mirror the service's field comparison."""
        async with self._uow as uow:
            existing = await uow.products.get_by_sku(normalise_sku(command.sku))
            if existing is None:
                return RowOutcome.CREATED
            families = await uow.product_families.list_all()
            brands = await uow.brands.list_all()
            family = next(f for f in families if f.code == command.family_code)
            brand = next(b for b in brands if b.code == command.brand_code)
            same = (
                existing.name == command.name.strip()
                and existing.brand_id == brand.id
                and existing.family_id == family.id
                and existing.kind is command.kind
                and existing.list_price == normalise_price(command.list_price, field="list_price")
                and existing.cost_price
                == (
                    normalise_price(command.cost_price, field="cost_price")
                    if command.cost_price is not None
                    else None
                )
                and (existing.unit or None) == (command.unit or None)
                and (existing.description or None) == (command.description or None)
                and existing.is_active is command.is_active
            )
            return RowOutcome.UNCHANGED if same else RowOutcome.UPDATED

    async def _audit(self, filename: str, report: ImportReport, actor: User) -> None:
        async with self._uow as uow:
            uow.audit.record(
                entity_type="import",
                entity_id=None,
                action="import.products_executed",
                changes={
                    "file": {"before": None, "after": filename},
                    "created": {"before": None, "after": str(report.created)},
                    "updated": {"before": None, "after": str(report.updated)},
                    "unchanged": {"before": None, "after": str(report.unchanged)},
                    "errors": {"before": None, "after": str(report.errors)},
                },
                actor_id=actor.id,
            )
            await uow.commit()


def _message(error: Exception) -> str:
    errors = getattr(error, "errors", None)
    if errors:
        return "; ".join(str(item.get("message", "")) for item in errors)
    return getattr(error, "detail", None) or str(error)
