"""Reference data: bundle and per-master reads for every role, admin writes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.api.deps import AdminUser, CurrentUser, ExpectedVersion, UowDep
from app.application.reference.commands import (
    CreateBrand,
    CreateJobTitle,
    CreateLossReason,
    ReorderStages,
    UpdateBrand,
    UpdateJobTitle,
    UpdateLossReason,
    UpdateStage,
)
from app.application.reference.queries import ReferenceQueries
from app.application.reference.service import (
    BrandService,
    JobTitleService,
    LossReasonService,
    PipelineService,
)
from app.application.users.commands import UNSET
from app.domain.reference.errors import StageFlagImmutableError
from app.domain.shared.errors import NotFoundError
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.schemas.reference import (
    AccountTypeRead,
    ActivityTypeRead,
    BrandCreate,
    BrandRead,
    BrandUpdate,
    JobTitleCreate,
    JobTitleRead,
    JobTitleUpdate,
    LossReasonCreate,
    LossReasonRead,
    LossReasonUpdate,
    PipelineRead,
    PipelineUpdate,
    ReferenceDataRead,
    StageOrder,
    StageUpdate,
)
from app.schemas.territories import DivisionRead

router = APIRouter(tags=["reference-data"])


def get_brand_service(uow: UowDep) -> BrandService:
    return BrandService(uow)


def get_loss_reason_service(uow: UowDep) -> LossReasonService:
    return LossReasonService(uow)


def get_pipeline_service(uow: UowDep) -> PipelineService:
    return PipelineService(uow)


def get_job_title_service(uow: UowDep) -> JobTitleService:
    return JobTitleService(uow)


BrandServiceDep = Annotated[BrandService, Depends(get_brand_service)]
LossReasonServiceDep = Annotated[LossReasonService, Depends(get_loss_reason_service)]
PipelineServiceDep = Annotated[PipelineService, Depends(get_pipeline_service)]
JobTitleServiceDep = Annotated[JobTitleService, Depends(get_job_title_service)]


def _quote(etag: str) -> str:
    return f'"{etag}"'


@router.get(
    "/reference-data",
    response_model=ReferenceDataRead,
    summary="All reference data in one response (cached by the client)",
    responses={304: {"description": "Not modified"}},
)
async def read_reference_data(
    _: CurrentUser,
    uow: UowDep,
    response: Response,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> ReferenceDataRead | Response:
    bundle = await ReferenceQueries(uow).bundle()
    etag = _quote(bundle.etag)
    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return ReferenceDataRead(
        account_types=[AccountTypeRead.from_entity(t) for t in bundle.account_types],
        activity_types=[ActivityTypeRead.from_entity(t) for t in bundle.activity_types],
        divisions=[DivisionRead.from_entity(d) for d in bundle.divisions],
        brands=[BrandRead.from_entity(b) for b in bundle.brands],
        loss_reasons=[LossReasonRead.from_entity(r) for r in bundle.loss_reasons],
        pipelines=[PipelineRead.from_entity(p) for p in bundle.pipelines],
        job_titles=[JobTitleRead.from_entity(j) for j in bundle.job_titles],
    )


@router.get("/account-types", response_model=list[AccountTypeRead], summary="Account types")
async def list_account_types(_: CurrentUser, uow: UowDep) -> list[AccountTypeRead]:
    return [AccountTypeRead.from_entity(t) for t in await uow.reference.account_types()]


@router.get("/activity-types", response_model=list[ActivityTypeRead], summary="Activity types")
async def list_activity_types(_: CurrentUser, uow: UowDep) -> list[ActivityTypeRead]:
    return [ActivityTypeRead.from_entity(t) for t in await uow.reference.activity_types()]


@router.get("/brands", response_model=list[BrandRead], summary="Brands (own and competitors)")
async def list_brands(
    _: CurrentUser,
    uow: UowDep,
    is_own: Annotated[bool | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[BrandRead]:
    brands = await uow.brands.list_all(is_own=is_own, is_active=is_active, q=q)
    return [BrandRead.from_entity(b) for b in brands]


@router.post(
    "/brands", response_model=BrandRead, status_code=status.HTTP_201_CREATED, summary="Create brand"
)
async def create_brand(
    payload: BrandCreate, admin: AdminUser, service: BrandServiceDep
) -> BrandRead:
    brand = await service.create(
        CreateBrand(
            name=payload.name, is_own=payload.is_own, division_ids=frozenset(payload.division_ids)
        ),
        acting_user_id=admin.id,
    )
    return BrandRead.from_entity(brand)


@router.patch("/brands/{brand_id}", response_model=BrandRead, summary="Update brand")
async def update_brand(
    brand_id: UUID,
    payload: BrandUpdate,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: BrandServiceDep,
) -> BrandRead:
    brand = await service.update(
        brand_id,
        UpdateBrand(
            expected_version=expected_version,
            name=payload.name if payload.name is not None else UNSET,
            is_own=payload.is_own if payload.is_own is not None else UNSET,
            is_active=payload.is_active if payload.is_active is not None else UNSET,
            division_ids=(
                frozenset(payload.division_ids) if payload.division_ids is not None else UNSET
            ),
        ),
        acting_user_id=admin.id,
    )
    return BrandRead.from_entity(brand)


@router.get("/loss-reasons", response_model=list[LossReasonRead], summary="Loss reasons")
async def list_loss_reasons(_: CurrentUser, uow: UowDep) -> list[LossReasonRead]:
    return [LossReasonRead.from_entity(r) for r in await uow.loss_reasons.list_all()]


@router.post(
    "/loss-reasons",
    response_model=LossReasonRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create loss reason",
)
async def create_loss_reason(
    payload: LossReasonCreate, admin: AdminUser, service: LossReasonServiceDep
) -> LossReasonRead:
    reason = await service.create(CreateLossReason(name=payload.name), acting_user_id=admin.id)
    return LossReasonRead.from_entity(reason)


@router.patch(
    "/loss-reasons/{reason_id}", response_model=LossReasonRead, summary="Update loss reason"
)
async def update_loss_reason(
    reason_id: UUID,
    payload: LossReasonUpdate,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: LossReasonServiceDep,
) -> LossReasonRead:
    reason = await service.update(
        reason_id,
        UpdateLossReason(
            expected_version=expected_version,
            name=payload.name if payload.name is not None else UNSET,
            is_active=payload.is_active if payload.is_active is not None else UNSET,
        ),
        acting_user_id=admin.id,
    )
    return LossReasonRead.from_entity(reason)


@router.get("/job-titles", response_model=list[JobTitleRead], summary="Job titles (cargos)")
async def list_job_titles(_: CurrentUser, uow: UowDep) -> list[JobTitleRead]:
    return [JobTitleRead.from_entity(j) for j in await uow.job_titles.list_all()]


@router.post(
    "/job-titles",
    response_model=JobTitleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create job title",
)
async def create_job_title(
    payload: JobTitleCreate, admin: AdminUser, service: JobTitleServiceDep
) -> JobTitleRead:
    job_title = await service.create(CreateJobTitle(name=payload.name), acting_user_id=admin.id)
    return JobTitleRead.from_entity(job_title)


@router.patch("/job-titles/{job_title_id}", response_model=JobTitleRead, summary="Update job title")
async def update_job_title(
    job_title_id: UUID,
    payload: JobTitleUpdate,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: JobTitleServiceDep,
) -> JobTitleRead:
    job_title = await service.update(
        job_title_id,
        UpdateJobTitle(
            expected_version=expected_version,
            name=payload.name if payload.name is not None else UNSET,
            is_active=payload.is_active if payload.is_active is not None else UNSET,
        ),
        acting_user_id=admin.id,
    )
    return JobTitleRead.from_entity(job_title)


@router.get("/pipelines", response_model=list[PipelineRead], summary="Pipelines with stages")
async def list_pipelines(_: CurrentUser, uow: UowDep) -> list[PipelineRead]:
    return [PipelineRead.from_entity(p) for p in await uow.pipelines.list_all()]


@router.patch("/pipelines/{pipeline_id}", response_model=PipelineRead, summary="Rename pipeline")
async def rename_pipeline(
    pipeline_id: UUID,
    payload: PipelineUpdate,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: PipelineServiceDep,
) -> PipelineRead:
    pipeline = await service.rename(
        pipeline_id, payload.name, expected_version=expected_version, acting_user_id=admin.id
    )
    return PipelineRead.from_entity(pipeline)


@router.patch(
    "/pipelines/{pipeline_id}/stages/{stage_id}",
    response_model=PipelineRead,
    summary="Edit a stage (name, probability, active)",
)
async def update_stage(
    pipeline_id: UUID,
    stage_id: UUID,
    payload: StageUpdate,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: PipelineServiceDep,
) -> PipelineRead:
    if payload.is_won is not None or payload.is_lost is not None or payload.is_at_risk is not None:
        raise StageFlagImmutableError()
    pipeline, _ = await service.update_stage(
        pipeline_id,
        stage_id,
        UpdateStage(
            expected_version=expected_version,
            name=payload.name if payload.name is not None else UNSET,
            probability=payload.probability if payload.probability is not None else UNSET,
            is_active=payload.is_active if payload.is_active is not None else UNSET,
        ),
        acting_user_id=admin.id,
    )
    return PipelineRead.from_entity(pipeline)


@router.put(
    "/pipelines/{pipeline_id}/stages/order",
    response_model=PipelineRead,
    summary="Reorder the stages of a pipeline",
)
async def reorder_stages(
    pipeline_id: UUID,
    payload: StageOrder,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: PipelineServiceDep,
) -> PipelineRead:
    pipeline = await service.reorder(
        pipeline_id,
        ReorderStages(expected_version=expected_version, stage_ids=payload.stage_ids),
        acting_user_id=admin.id,
    )
    return PipelineRead.from_entity(pipeline)


async def _get_pipeline_or_404(uow: SqlAlchemyUnitOfWork, pipeline_id: UUID) -> PipelineRead:
    pipeline = await uow.pipelines.get(pipeline_id)
    if pipeline is None:
        raise NotFoundError("Pipeline not found")
    return PipelineRead.from_entity(pipeline)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineRead, summary="Read a pipeline")
async def read_pipeline(pipeline_id: UUID, _: CurrentUser, uow: UowDep) -> PipelineRead:
    return await _get_pipeline_or_404(uow, pipeline_id)
