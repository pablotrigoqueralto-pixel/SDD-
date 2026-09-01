from copy import deepcopy
from uuid import UUID

from app.domain.catalogue.entities import Product, normalise_sku
from app.domain.catalogue.errors import SkuAlreadyExistsError
from app.domain.reference.entities import ProductFamily
from app.domain.reference.errors import ProductFamilyNameAlreadyExistsError
from app.domain.shared.errors import ConcurrentModificationError
from tests.unit.fakes.accounts import unaccented


class InMemoryProductFamilyRepository:
    def __init__(self, rows: list[ProductFamily] | None = None) -> None:
        self.rows: dict[UUID, ProductFamily] = {row.id: deepcopy(row) for row in rows or []}

    async def get(self, family_id: UUID) -> ProductFamily | None:
        row = self.rows.get(family_id)
        return deepcopy(row) if row else None

    async def matching(self, *, division_id: UUID, code: str, name: str) -> ProductFamily | None:
        wanted = unaccented(name)
        for row in self.rows.values():
            if row.division_id != division_id:
                continue
            if row.code == code or unaccented(row.name_es) == wanted:
                return deepcopy(row)
        return None

    async def get_by_code(self, code: str) -> ProductFamily | None:
        return next((deepcopy(r) for r in self.rows.values() if r.code == code), None)

    async def list_all(self) -> list[ProductFamily]:
        return sorted(
            (deepcopy(r) for r in self.rows.values()),
            key=lambda r: (str(r.division_id), r.sort_order, r.name_es),
        )

    async def next_sort_order(self, division_id: UUID) -> int:
        same = [r.sort_order for r in self.rows.values() if r.division_id == division_id]
        return max(same, default=0) + 10

    async def add(self, family: ProductFamily) -> None:
        self._check_name(family)
        self.rows[family.id] = deepcopy(family)

    async def save(self, family: ProductFamily, *, expected_version: int) -> None:
        current = self.rows.get(family.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        self._check_name(family)
        family.version = expected_version + 1
        self.rows[family.id] = deepcopy(family)

    def _check_name(self, family: ProductFamily) -> None:
        for row in self.rows.values():
            if row.id == family.id:
                continue
            same_division = row.division_id == family.division_id
            if row.code == family.code or (
                same_division and row.name_es.lower() == family.name_es.lower()
            ):
                raise ProductFamilyNameAlreadyExistsError()


class InMemoryProductRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Product] = {}
        self.referenced: set[UUID] = set()

    async def get(self, product_id: UUID) -> Product | None:
        row = self.rows.get(product_id)
        return deepcopy(row) if row else None

    async def get_by_sku(self, sku: str) -> Product | None:
        wanted = normalise_sku(sku)
        return next((deepcopy(r) for r in self.rows.values() if r.sku == wanted), None)

    async def add(self, product: Product) -> None:
        self._check_sku(product)
        self.rows[product.id] = deepcopy(product)

    async def save(self, product: Product, *, expected_version: int) -> None:
        current = self.rows.get(product.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        self._check_sku(product)
        product.version = expected_version + 1
        self.rows[product.id] = deepcopy(product)

    async def is_referenced(self, product_id: UUID) -> bool:
        return product_id in self.referenced

    def _check_sku(self, product: Product) -> None:
        for row in self.rows.values():
            if row.id != product.id and row.sku == product.sku:
                raise SkuAlreadyExistsError(row.id)
