"""Read side for the catalogue: global (unscoped), paginated, searched on demand."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.pagination import PageParams
from app.domain.catalogue.entities import ProductKind
from app.domain.shared.errors import InvalidSortFieldError
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import BrandModel, ProductFamilyModel, ProductModel

PRODUCT_SORT_FIELDS: set[str] = {"name", "sku", "list_price", "updated_at"}
PRODUCT_COST_SORT_FIELD = "cost_price"
PRODUCT_DEFAULT_SORT = "name"
PRODUCT_MAX_PAGE_SIZE = 100
PRODUCT_DEFAULT_PAGE_SIZE = 25
TRIGRAM_MIN_LENGTH = 3

COST_VIEWER_ROLES: frozenset[Role] = frozenset({Role.SALES_MANAGER, Role.ADMIN})
CATALOGUE_WRITER_ROLES: frozenset[Role] = frozenset({Role.ADMIN, Role.BACK_OFFICE})


def can_view_cost(user: User) -> bool:
    return user.role in COST_VIEWER_ROLES


@dataclass(frozen=True)
class ProductFilters:
    q: str | None = None
    division_id: UUID | None = None
    family_id: UUID | None = None
    brand_id: UUID | None = None
    kind: ProductKind | None = None
    own: bool | None = None
    is_active: bool | None = True


@dataclass(frozen=True)
class BrandRef:
    id: UUID
    name: str
    is_own: bool


@dataclass(frozen=True)
class FamilyRef:
    id: UUID
    name: str
    division_id: UUID


@dataclass(frozen=True)
class ProductSummary:
    id: UUID
    sku: str
    name: str
    brand: BrandRef
    family: FamilyRef
    kind: ProductKind
    list_price: Decimal
    cost_price: Decimal | None
    unit: str
    description: str | None
    is_active: bool
    version: int
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class ProductListResult:
    items: list[ProductSummary]
    total: int


def _base_select() -> Select[Any]:
    return (
        select(ProductModel, BrandModel, ProductFamilyModel)
        .join(BrandModel, BrandModel.id == ProductModel.brand_id)
        .join(ProductFamilyModel, ProductFamilyModel.id == ProductModel.family_id)
    )


def _to_summary(product: ProductModel, brand: BrandModel, family: ProductFamilyModel) -> Any:
    return ProductSummary(
        id=product.id,
        sku=product.sku,
        name=product.name,
        brand=BrandRef(id=brand.id, name=brand.name, is_own=brand.is_own),
        family=FamilyRef(id=family.id, name=family.name_es, division_id=family.division_id),
        kind=product.kind,
        list_price=product.list_price,
        cost_price=product.cost_price,
        unit=product.unit,
        description=product.description,
        is_active=product.is_active,
        version=product.version,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


class ProductQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, product_id: UUID) -> ProductSummary | None:
        statement = _base_select().where(ProductModel.id == product_id)
        row = (await self._session.execute(statement)).first()
        if row is None:
            return None
        summary: ProductSummary = _to_summary(row[0], row[1], row[2])
        return summary

    async def list_page(
        self, params: PageParams, filters: ProductFilters, *, cost_viewer: bool
    ) -> ProductListResult:
        for field in params.sort:
            if field.name == PRODUCT_COST_SORT_FIELD and not cost_viewer:
                raise InvalidSortFieldError(field.name, PRODUCT_SORT_FIELDS)
        base = self._apply_filters(_base_select(), filters)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = (
            base.order_by(*self._order_by(params, filters.q))
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(statement)).all()
        return ProductListResult(
            items=[_to_summary(row[0], row[1], row[2]) for row in rows],
            total=int(total or 0),
        )

    @staticmethod
    def _apply_filters(statement: Select[Any], filters: ProductFilters) -> Select[Any]:
        if filters.division_id is not None:
            statement = statement.where(ProductFamilyModel.division_id == filters.division_id)
        if filters.family_id is not None:
            statement = statement.where(ProductModel.family_id == filters.family_id)
        if filters.brand_id is not None:
            statement = statement.where(ProductModel.brand_id == filters.brand_id)
        if filters.kind is not None:
            statement = statement.where(ProductModel.kind == filters.kind)
        if filters.own is not None:
            statement = statement.where(BrandModel.is_own.is_(filters.own))
        if filters.is_active is not None:
            statement = statement.where(ProductModel.is_active.is_(filters.is_active))
        if filters.q and filters.q.strip():
            statement = statement.where(_text_predicate(filters.q))
        return statement

    @staticmethod
    def _order_by(params: PageParams, q: str | None) -> list[ColumnElement[Any]]:
        columns = {
            "name": ProductModel.name,
            "sku": ProductModel.sku,
            "list_price": ProductModel.list_price,
            "cost_price": ProductModel.cost_price,
            "updated_at": ProductModel.updated_at,
        }
        clauses: list[ColumnElement[Any]] = []
        term = (q or "").strip()
        if term:
            # Sage code prefix matches first ("HAD-10" lists the Hadeco range before names).
            clauses.append(case((ProductModel.sku.ilike(_escape(term) + "%"), 0), else_=1))
        for field in params.sort:
            column = columns[field.name]
            ordered = column.desc() if field.descending else column.asc()
            clauses.append(ordered.nulls_last())
        clauses.append(ProductModel.id.asc())
        return clauses


def _escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _text_predicate(q: str) -> ColumnElement[bool]:
    term = q.strip()
    prefix = _escape(term) + "%"
    clauses: list[ColumnElement[bool]] = [ProductModel.sku.ilike(prefix)]
    if len(term) >= TRIGRAM_MIN_LENGTH:
        contains = f"%{_escape(term)}%"
        clauses.append(ProductModel.name.ilike(contains))
        clauses.append(ProductModel.sku.ilike(contains))
    return or_(*clauses)
