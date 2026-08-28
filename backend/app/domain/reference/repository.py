"""Repository protocols for reference data."""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from app.domain.reference.entities import (
    AccountType,
    ActivityType,
    Brand,
    JobTitle,
    LossReason,
    Pipeline,
)


class BrandRepository(Protocol):
    async def get(self, brand_id: UUID) -> Brand | None: ...

    async def list_all(
        self, *, is_own: bool | None = None, is_active: bool | None = None, q: str | None = None
    ) -> list[Brand]: ...

    async def add(self, brand: Brand) -> None: ...

    async def save(self, brand: Brand, *, expected_version: int) -> None: ...


class LossReasonRepository(Protocol):
    async def get(self, reason_id: UUID) -> LossReason | None: ...

    async def list_all(self) -> list[LossReason]: ...

    async def next_sort_order(self) -> int: ...

    async def add(self, reason: LossReason) -> None: ...

    async def save(self, reason: LossReason, *, expected_version: int) -> None: ...


class JobTitleRepository(Protocol):
    async def get(self, job_title_id: UUID) -> JobTitle | None: ...

    async def list_all(self) -> list[JobTitle]: ...

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]: ...

    async def next_sort_order(self) -> int: ...

    async def add(self, job_title: JobTitle) -> None: ...

    async def save(self, job_title: JobTitle, *, expected_version: int) -> None: ...


class PipelineRepository(Protocol):
    async def get(self, pipeline_id: UUID) -> Pipeline | None: ...

    async def list_all(self) -> list[Pipeline]: ...

    async def save(self, pipeline: Pipeline, *, expected_version: int) -> None: ...

    async def save_stage(
        self, pipeline: Pipeline, stage_id: UUID, *, expected_version: int
    ) -> None: ...


class ReferenceReadRepository(Protocol):
    async def account_types(self) -> list[AccountType]: ...

    async def activity_types(self) -> list[ActivityType]: ...
