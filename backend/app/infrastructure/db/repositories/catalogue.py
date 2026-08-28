"""SQLAlchemy implementation of the product repository."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.catalogue.entities import Product, normalise_sku
from app.domain.catalogue.errors import SkuAlreadyExistsError
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import OpportunityLineModel, ProductModel
from app.infrastructure.db.repositories.results import rowcount_of

SKU_UNIQUE_MARKER = "products_sku_key"


def product_to_entity(row: ProductModel) -> Product:
    return Product(
        id=row.id,
        sku=row.sku,
        name=row.name,
        brand_id=row.brand_id,
        family_id=row.family_id,
        kind=row.kind,
        list_price=row.list_price,
        cost_price=row.cost_price,
        unit=row.unit,
        description=row.description,
        is_active=row.is_active,
        created_by=row.created_by,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, product_id: UUID) -> Product | None:
        row = await self._session.get(ProductModel, product_id)
        return product_to_entity(row) if row else None

    async def get_by_sku(self, sku: str) -> Product | None:
        statement = select(ProductModel).where(ProductModel.sku == normalise_sku(sku))
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return product_to_entity(row) if row else None

    async def add(self, product: Product) -> None:
        self._session.add(
            ProductModel(
                id=product.id,
                sku=product.sku,
                name=product.name,
                brand_id=product.brand_id,
                family_id=product.family_id,
                kind=product.kind,
                list_price=product.list_price,
                cost_price=product.cost_price,
                unit=product.unit,
                description=product.description,
                is_active=product.is_active,
                created_by=product.created_by,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            self._raise_if_sku_taken(exc)
            raise

    async def save(self, product: Product, *, expected_version: int) -> None:
        statement = (
            update(ProductModel)
            .where(ProductModel.id == product.id, ProductModel.version == expected_version)
            .values(
                sku=product.sku,
                name=product.name,
                brand_id=product.brand_id,
                family_id=product.family_id,
                kind=product.kind,
                list_price=product.list_price,
                cost_price=product.cost_price,
                unit=product.unit,
                description=product.description,
                is_active=product.is_active,
                version=expected_version + 1,
            )
        )
        try:
            result = await self._session.execute(statement)
        except IntegrityError as exc:
            self._raise_if_sku_taken(exc)
            raise
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        product.version = expected_version + 1

    async def is_referenced(self, product_id: UUID) -> bool:
        statement = select(OpportunityLineModel.id).where(
            OpportunityLineModel.product_id == product_id
        )
        return (await self._session.execute(statement.limit(1))).first() is not None

    @staticmethod
    def _raise_if_sku_taken(exc: IntegrityError) -> None:
        # The service pre-checks the code and reports the conflicting id; this only guards
        # the race between two concurrent inserts.
        if SKU_UNIQUE_MARKER in str(exc.orig):
            raise SkuAlreadyExistsError() from exc
