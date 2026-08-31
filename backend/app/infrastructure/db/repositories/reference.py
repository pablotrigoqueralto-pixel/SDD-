"""SQLAlchemy implementations of the reference data repositories."""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.reference.entities import (
    AccountType,
    ActivityType,
    Brand,
    JobTitle,
    LossReason,
    Pipeline,
    PipelineStage,
    ProductFamily,
    Specialty,
)
from app.domain.reference.errors import (
    BrandNameAlreadyExistsError,
    JobTitleNameAlreadyExistsError,
    LossReasonNameAlreadyExistsError,
    PipelineNameAlreadyExistsError,
    ProductFamilyNameAlreadyExistsError,
)
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import (
    AccountTypeModel,
    ActivityTypeModel,
    BrandDivisionModel,
    BrandModel,
    DivisionModel,
    JobTitleModel,
    LossReasonModel,
    PipelineModel,
    PipelineStageModel,
    ProductFamilyModel,
    SpecialtyModel,
)
from app.infrastructure.db.repositories.results import rowcount_of

BRAND_UNIQUE_MARKERS = ("brands_name_key", "brands_code_key")
LOSS_REASON_UNIQUE_MARKERS = ("loss_reasons_name_es_key", "loss_reasons_code_key")
PIPELINE_UNIQUE_MARKERS = ("pipelines_name_es_key",)
JOB_TITLE_UNIQUE_MARKERS = ("job_titles_name_es_key", "job_titles_code_key")
PRODUCT_FAMILY_UNIQUE_MARKERS = ("uq_product_families_name_division", "product_families_code_key")


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

    async def ensure_division(self, brand_id: UUID, division_id: UUID) -> bool:
        statement = (
            insert(BrandDivisionModel)
            .values(brand_id=brand_id, division_id=division_id)
            .on_conflict_do_nothing()
        )
        result = await self._session.execute(statement)
        return rowcount_of(result) == 1


def product_family_to_entity(row: ProductFamilyModel) -> ProductFamily:
    return ProductFamily(
        id=row.id,
        code=row.code,
        name_es=row.name_es,
        division_id=row.division_id,
        sort_order=row.sort_order,
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyProductFamilyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, family_id: UUID) -> ProductFamily | None:
        row = await self._session.get(ProductFamilyModel, family_id)
        return product_family_to_entity(row) if row else None

    async def get_by_code(self, code: str) -> ProductFamily | None:
        statement = select(ProductFamilyModel).where(ProductFamilyModel.code == code)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return product_family_to_entity(row) if row else None

    async def list_all(self) -> list[ProductFamily]:
        statement = (
            select(ProductFamilyModel)
            .join(DivisionModel, DivisionModel.id == ProductFamilyModel.division_id)
            .order_by(
                DivisionModel.sort_order, ProductFamilyModel.sort_order, ProductFamilyModel.name_es
            )
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [product_family_to_entity(row) for row in rows]

    async def next_sort_order(self, division_id: UUID) -> int:
        current = await self._session.scalar(
            select(func.max(ProductFamilyModel.sort_order)).where(
                ProductFamilyModel.division_id == division_id
            )
        )
        return int(current or 0) + 10

    async def add(self, family: ProductFamily) -> None:
        self._session.add(
            ProductFamilyModel(
                id=family.id,
                code=family.code,
                name_es=family.name_es,
                division_id=family.division_id,
                sort_order=family.sort_order,
                is_active=family.is_active,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            _raise_if_unique(
                exc, PRODUCT_FAMILY_UNIQUE_MARKERS, ProductFamilyNameAlreadyExistsError
            )
            raise

    async def save(self, family: ProductFamily, *, expected_version: int) -> None:
        statement = (
            update(ProductFamilyModel)
            .where(
                ProductFamilyModel.id == family.id,
                ProductFamilyModel.version == expected_version,
            )
            .values(
                name_es=family.name_es,
                is_active=family.is_active,
                sort_order=family.sort_order,
                version=expected_version + 1,
            )
        )
        try:
            result = await self._session.execute(statement)
        except IntegrityError as exc:
            _raise_if_unique(
                exc, PRODUCT_FAMILY_UNIQUE_MARKERS, ProductFamilyNameAlreadyExistsError
            )
            raise
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        family.version = expected_version + 1


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


def job_title_to_entity(row: JobTitleModel) -> JobTitle:
    return JobTitle(
        id=row.id,
        code=row.code,
        name_es=row.name_es,
        sort_order=row.sort_order,
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyJobTitleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, job_title_id: UUID) -> JobTitle | None:
        row = await self._session.get(JobTitleModel, job_title_id)
        return job_title_to_entity(row) if row else None

    async def list_all(self) -> list[JobTitle]:
        statement = select(JobTitleModel).order_by(JobTitleModel.sort_order)
        rows = (await self._session.execute(statement)).scalars().all()
        return [job_title_to_entity(row) for row in rows]

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        wanted = list(set(ids))
        if not wanted:
            return frozenset()
        statement = select(JobTitleModel.id).where(JobTitleModel.id.in_(wanted))
        return frozenset((await self._session.execute(statement)).scalars().all())

    async def next_sort_order(self) -> int:
        current = await self._session.scalar(select(func.max(JobTitleModel.sort_order)))
        return int(current or 0) + 10

    async def add(self, job_title: JobTitle) -> None:
        self._session.add(
            JobTitleModel(
                id=job_title.id,
                code=job_title.code,
                name_es=job_title.name_es,
                sort_order=job_title.sort_order,
                is_active=job_title.is_active,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            _raise_if_unique(exc, JOB_TITLE_UNIQUE_MARKERS, JobTitleNameAlreadyExistsError)
            raise

    async def save(self, job_title: JobTitle, *, expected_version: int) -> None:
        statement = (
            update(JobTitleModel)
            .where(JobTitleModel.id == job_title.id, JobTitleModel.version == expected_version)
            .values(
                name_es=job_title.name_es,
                is_active=job_title.is_active,
                sort_order=job_title.sort_order,
                version=expected_version + 1,
            )
        )
        try:
            result = await self._session.execute(statement)
        except IntegrityError as exc:
            _raise_if_unique(exc, JOB_TITLE_UNIQUE_MARKERS, JobTitleNameAlreadyExistsError)
            raise
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        job_title.version = expected_version + 1


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


def specialty_to_entity(row: SpecialtyModel) -> Specialty:
    return Specialty(
        id=row.id,
        code=row.code,
        name_es=row.name_es,
        sort_order=row.sort_order,
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemySpecialtyRepository:
    """Read-only for now: administrators gain CRUD in change 14."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Specialty]:
        statement = select(SpecialtyModel).order_by(SpecialtyModel.sort_order)
        rows = (await self._session.execute(statement)).scalars().all()
        return [specialty_to_entity(row) for row in rows]

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        wanted = list(set(ids))
        if not wanted:
            return frozenset()
        statement = select(SpecialtyModel.id).where(SpecialtyModel.id.in_(wanted))
        return frozenset((await self._session.execute(statement)).scalars().all())
