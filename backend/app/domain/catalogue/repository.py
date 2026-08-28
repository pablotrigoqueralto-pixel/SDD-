"""Repository protocol for products."""

from typing import Protocol
from uuid import UUID

from app.domain.catalogue.entities import Product


class ProductRepository(Protocol):
    async def get(self, product_id: UUID) -> Product | None: ...

    async def get_by_sku(self, sku: str) -> Product | None:
        """Lookup by normalised Sage code."""
        ...

    async def add(self, product: Product) -> None: ...

    async def save(self, product: Product, *, expected_version: int) -> None: ...

    async def is_referenced(self, product_id: UUID) -> bool:
        """True once quote lines (change 07) reference the product; always False until then."""
        ...
