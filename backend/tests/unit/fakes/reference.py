from copy import deepcopy
from uuid import UUID

from app.domain.reference.entities import (
    AccountType,
    ActivityType,
    Brand,
    LossReason,
    Pipeline,
)
from app.domain.reference.errors import (
    BrandNameAlreadyExistsError,
    LossReasonNameAlreadyExistsError,
    PipelineNameAlreadyExistsError,
)
from app.domain.shared.errors import ConcurrentModificationError


class InMemoryBrandRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Brand] = {}

    async def get(self, brand_id: UUID) -> Brand | None:
        row = self.rows.get(brand_id)
        return deepcopy(row) if row else None

    async def list_all(
        self, *, is_own: bool | None = None, is_active: bool | None = None, q: str | None = None
    ) -> list[Brand]:
        rows = [deepcopy(r) for r in self.rows.values()]
        if is_own is not None:
            rows = [r for r in rows if r.is_own == is_own]
        if is_active is not None:
            rows = [r for r in rows if r.is_active == is_active]
        if q:
            rows = [r for r in rows if r.name.lower().startswith(q.lower())]
        return sorted(rows, key=lambda r: r.name.lower())

    async def add(self, brand: Brand) -> None:
        self._check_name(brand)
        self.rows[brand.id] = deepcopy(brand)

    async def save(self, brand: Brand, *, expected_version: int) -> None:
        current = self.rows.get(brand.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        self._check_name(brand)
        brand.version = expected_version + 1
        self.rows[brand.id] = deepcopy(brand)

    def _check_name(self, brand: Brand) -> None:
        for row in self.rows.values():
            if row.id != brand.id and (
                row.name.lower() == brand.name.lower() or row.code == brand.code
            ):
                raise BrandNameAlreadyExistsError()


class InMemoryLossReasonRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, LossReason] = {}

    async def get(self, reason_id: UUID) -> LossReason | None:
        row = self.rows.get(reason_id)
        return deepcopy(row) if row else None

    async def list_all(self) -> list[LossReason]:
        return sorted((deepcopy(r) for r in self.rows.values()), key=lambda r: r.sort_order)

    async def next_sort_order(self) -> int:
        return max((r.sort_order for r in self.rows.values()), default=0) + 1

    async def add(self, reason: LossReason) -> None:
        self._check_name(reason)
        self.rows[reason.id] = deepcopy(reason)

    async def save(self, reason: LossReason, *, expected_version: int) -> None:
        current = self.rows.get(reason.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        self._check_name(reason)
        reason.version = expected_version + 1
        self.rows[reason.id] = deepcopy(reason)

    def _check_name(self, reason: LossReason) -> None:
        for row in self.rows.values():
            if row.id != reason.id and row.name_es.lower() == reason.name_es.lower():
                raise LossReasonNameAlreadyExistsError()


class InMemoryPipelineRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Pipeline] = {}

    async def get(self, pipeline_id: UUID) -> Pipeline | None:
        row = self.rows.get(pipeline_id)
        return deepcopy(row) if row else None

    async def list_all(self) -> list[Pipeline]:
        return sorted((deepcopy(r) for r in self.rows.values()), key=lambda r: r.sort_order)

    async def save(self, pipeline: Pipeline, *, expected_version: int) -> None:
        current = self.rows.get(pipeline.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        for row in self.rows.values():
            if row.id != pipeline.id and row.name_es.lower() == pipeline.name_es.lower():
                raise PipelineNameAlreadyExistsError()
        pipeline.version = expected_version + 1
        self.rows[pipeline.id] = deepcopy(pipeline)

    async def save_stage(
        self, pipeline: Pipeline, stage_id: UUID, *, expected_version: int
    ) -> None:
        current = self.rows.get(pipeline.id)
        if current is None:
            raise ConcurrentModificationError()
        stored = next((s for s in current.stages if s.id == stage_id), None)
        if stored is None or stored.version != expected_version:
            raise ConcurrentModificationError()
        stage = pipeline.stage(stage_id)
        stage.version = expected_version + 1
        current.stages = [deepcopy(stage) if s.id == stage_id else s for s in current.stages]


class InMemoryReferenceReadRepository:
    def __init__(
        self,
        account_types: list[AccountType] | None = None,
        activity_types: list[ActivityType] | None = None,
    ) -> None:
        self._account_types = list(account_types or [])
        self._activity_types = list(activity_types or [])

    async def account_types(self) -> list[AccountType]:
        return sorted(self._account_types, key=lambda t: t.sort_order)

    async def activity_types(self) -> list[ActivityType]:
        return sorted(self._activity_types, key=lambda t: t.sort_order)
