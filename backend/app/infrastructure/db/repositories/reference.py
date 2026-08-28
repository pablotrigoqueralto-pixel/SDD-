"""SQLAlchemy implementations of the reference data repositories."""

from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.reference.entities import (
    AccountType,
    ActivityType,
    Brand,
    LossReason,
    Pipeline,
    PipelineStage,
)
from app.domain.reference.errors import (
    BrandNameAlreadyExistsError,
    LossReasonNameAlreadyExistsError,
    PipelineNameAlreadyExistsError,
)
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import (
    AccountTypeModel,
    ActivityTypeModel,
    BrandDivisionModel,
    BrandModel,
    LossReasonModel,
    PipelineModel,
    PipelineStageModel,
)
from app.infrastructure.db.repositories.results import rowcount_of

BRAND_UNIQUE_MARKERS = ("brands_name_key", "brands_code_key")
LOSS_REASON_UNIQUE_MARKERS = ("loss_reasons_name_es_key", "loss_reasons_code_key")
PIPELINE_UNIQUE_MARKERS = ("pipelines_name_es_key",)


def brand_to_entity(row: BrandModel) -> Brand:
    return Brand(
        id=row.id,
        code=row.code,
        name=row.name,
        is_own=row.is_own,
        is_active=row.is_active,
        division_ids=frozenset(link.division_id for link in row.division_links),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyBrandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, brand_id: UUID) -> Brand | None:
        statement = (
            select(BrandModel)
            .options(selectinload(BrandModel.division_links))
            .where(BrandModel.id == brand_id)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return brand_to_entity(row) if row else None

    async def list_all(
        self, *, is_own: bool | None = None, is_active: bool | None = None, q: str | None = None
    ) -> list[Brand]:
        statement = select(BrandModel).options(selectinload(BrandModel.division_links))
        if is_own is not None:
            statement = statement.where(BrandModel.is_own.is_(is_own))
        if is_active is not None:
            statement = statement.where(BrandModel.is_active.is_(is_active))
        if q:
            statement = statement.where(BrandModel.name.ilike(f"{q.strip()}%"))
        rows = (await self._session.execute(statement.order_by(BrandModel.name))).scalars().all()
        return [brand_to_entity(row) for row in rows]

    async def add(self, brand: Brand) -> None:
        row = BrandModel(
            id=brand.id,
            code=brand.code,
            name=brand.name,
            is_own=brand.is_own,
            is_active=brand.is_active,
        )
        row.division_links = [
            BrandDivisionModel(brand_id=brand.id, division_id=division_id)
            for division_id in brand.division_ids
        ]
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            _raise_if_unique(exc, BRAND_UNIQUE_MARKERS, BrandNameAlreadyExistsError)
            raise

    async def save(self, brand: Brand, *, expected_version: int) -> None:
        statement = (
            update(BrandModel)
            .where(BrandModel.id == brand.id, BrandModel.version == expected_version)
            .values(
                name=brand.name,
                is_own=brand.is_own,
                is_active=brand.is_active,
                version=expected_version + 1,
            )
        )
        try:
            result = await self._session.execute(statement)
        except IntegrityError as exc:
            _raise_if_unique(exc, BRAND_UNIQUE_MARKERS, BrandNameAlreadyExistsError)
            raise
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        await self._session.execute(
            delete(BrandDivisionModel).where(BrandDivisionModel.brand_id == brand.id)
        )
        if brand.division_ids:
            await self._session.execute(
                insert(BrandDivisionModel),
                [{"brand_id": brand.id, "division_id": d} for d in brand.division_ids],
            )
        brand.version = expected_version + 1


def loss_reason_to_entity(row: LossReasonModel) -> LossReason:
    return LossReason(
        id=row.id,
        code=row.code,
        name_es=row.name_es,
        sort_order=row.sort_order,
        requires_brand=row.requires_brand,
        requires_note=row.requires_note,
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyLossReasonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, reason_id: UUID) -> LossReason | None:
        row = await self._session.get(LossReasonModel, reason_id)
        return loss_reason_to_entity(row) if row else None

    async def list_all(self) -> list[LossReason]:
        statement = select(LossReasonModel).order_by(LossReasonModel.sort_order)
        rows = (await self._session.execute(statement)).scalars().all()
        return [loss_reason_to_entity(row) for row in rows]

    async def next_sort_order(self) -> int:
        current = await self._session.scalar(select(func.max(LossReasonModel.sort_order)))
        return int(current or 0) + 1

    async def add(self, reason: LossReason) -> None:
        self._session.add(
            LossReasonModel(
                id=reason.id,
                code=reason.code,
                name_es=reason.name_es,
                sort_order=reason.sort_order,
                requires_brand=reason.requires_brand,
                requires_note=reason.requires_note,
                is_active=reason.is_active,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            _raise_if_unique(exc, LOSS_REASON_UNIQUE_MARKERS, LossReasonNameAlreadyExistsError)
            raise

    async def save(self, reason: LossReason, *, expected_version: int) -> None:
        statement = (
            update(LossReasonModel)
            .where(LossReasonModel.id == reason.id, LossReasonModel.version == expected_version)
            .values(
                name_es=reason.name_es,
                is_active=reason.is_active,
                sort_order=reason.sort_order,
                version=expected_version + 1,
            )
        )
        try:
            result = await self._session.execute(statement)
        except IntegrityError as exc:
            _raise_if_unique(exc, LOSS_REASON_UNIQUE_MARKERS, LossReasonNameAlreadyExistsError)
            raise
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        reason.version = expected_version + 1


def stage_to_entity(row: PipelineStageModel) -> PipelineStage:
    return PipelineStage(
        id=row.id,
        code=row.code,
        name_es=row.name_es,
        sort_order=row.sort_order,
        probability=row.probability,
        is_won=row.is_won,
        is_lost=row.is_lost,
        is_at_risk=row.is_at_risk,
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def pipeline_to_entity(row: PipelineModel) -> Pipeline:
    return Pipeline(
        id=row.id,
        code=row.code,
        name_es=row.name_es,
        sort_order=row.sort_order,
        division_ids=frozenset(link.division_id for link in row.division_links),
        stages=[stage_to_entity(stage) for stage in row.stages],
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


_PIPELINE_LOAD = (
    selectinload(PipelineModel.division_links),
    selectinload(PipelineModel.stages),
)


class SqlAlchemyPipelineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, pipeline_id: UUID) -> Pipeline | None:
        statement = (
            select(PipelineModel).options(*_PIPELINE_LOAD).where(PipelineModel.id == pipeline_id)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return pipeline_to_entity(row) if row else None

    async def list_all(self) -> list[Pipeline]:
        statement = (
            select(PipelineModel).options(*_PIPELINE_LOAD).order_by(PipelineModel.sort_order)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [pipeline_to_entity(row) for row in rows]

    async def save(self, pipeline: Pipeline, *, expected_version: int) -> None:
        """Persist pipeline-level changes (name, stage order) under the pipeline version."""
        statement = (
            update(PipelineModel)
            .where(PipelineModel.id == pipeline.id, PipelineModel.version == expected_version)
            .values(name_es=pipeline.name_es, version=expected_version + 1)
        )
        try:
            result = await self._session.execute(statement)
        except IntegrityError as exc:
            _raise_if_unique(exc, PIPELINE_UNIQUE_MARKERS, PipelineNameAlreadyExistsError)
            raise
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        for stage in pipeline.stages:
            await self._session.execute(
                update(PipelineStageModel)
                .where(PipelineStageModel.id == stage.id)
                .values(sort_order=stage.sort_order)
            )
        pipeline.version = expected_version + 1

    async def save_stage(
        self, pipeline: Pipeline, stage_id: UUID, *, expected_version: int
    ) -> None:
        stage = pipeline.stage(stage_id)
        result = await self._session.execute(
            update(PipelineStageModel)
            .where(
                PipelineStageModel.id == stage.id,
                PipelineStageModel.pipeline_id == pipeline.id,
                PipelineStageModel.version == expected_version,
            )
            .values(
                name_es=stage.name_es,
                probability=stage.probability,
                is_active=stage.is_active,
                version=expected_version + 1,
            )
        )
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        stage.version = expected_version + 1


class SqlAlchemyReferenceReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def account_types(self) -> list[AccountType]:
        rows = (
            (
                await self._session.execute(
                    select(AccountTypeModel).order_by(AccountTypeModel.sort_order)
                )
            )
            .scalars()
            .all()
        )
        return [
            AccountType(
                id=r.id,
                code=r.code,
                name_es=r.name_es,
                sort_order=r.sort_order,
                buys_via_tender=r.buys_via_tender,
                is_active=r.is_active,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def activity_types(self) -> list[ActivityType]:
        rows = (
            (
                await self._session.execute(
                    select(ActivityTypeModel).order_by(ActivityTypeModel.sort_order)
                )
            )
            .scalars()
            .all()
        )
        return [
            ActivityType(
                id=r.id,
                code=r.code,
                name_es=r.name_es,
                sort_order=r.sort_order,
                icon=r.icon,
                counts_as_contact=r.counts_as_contact,
                is_active=r.is_active,
                updated_at=r.updated_at,
            )
            for r in rows
        ]


def _raise_if_unique(exc: IntegrityError, markers: tuple[str, ...], error: type[Exception]) -> None:
    message = str(exc.orig)
    if any(marker in message for marker in markers):
        raise error() from exc
