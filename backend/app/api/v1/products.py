"""Product catalogue: global reads for every role, writes for admin and back office."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.deps import CurrentUser, ExpectedVersion, SessionDep, UowDep, require_roles
from app.application.catalogue.commands import CreateProduct, UpdateProduct
from app.application.catalogue.queries import (
    PRODUCT_COST_SORT_FIELD,
    PRODUCT_DEFAULT_PAGE_SIZE,
    PRODUCT_DEFAULT_SORT,
    PRODUCT_MAX_PAGE_SIZE,
    PRODUCT_SORT_FIELDS,
    ProductFilters,
    ProductQueries,
    ProductSummary,
    can_view_cost,
)
from app.application.catalogue.service import ProductService
from app.application.imports.products import ProductImporter
from app.application.shared.pagination import Page, PageParams, parse_sort
from app.domain.catalogue.entities import ProductKind
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.schemas.catalogue import (
    ProductCreate,
    ProductPublicRead,
    ProductRead,
    ProductSummaryPublicRead,
    ProductSummaryRead,
    ProductUpdate,
)
from app.schemas.imports import ImportReportRead

router = APIRouter(prefix="/products", tags=["catalogue"])


def product_page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PRODUCT_MAX_PAGE_SIZE)] = PRODUCT_DEFAULT_PAGE_SIZE,
    sort: Annotated[str | None, Query()] = None,
) -> PageParams:
    return PageParams(
        page=page,
        page_size=page_size,
        sort=parse_sort(
            sort,
            allowed=PRODUCT_SORT_FIELDS | {PRODUCT_COST_SORT_FIELD},
            default=PRODUCT_DEFAULT_SORT,
        ),
    )


ProductPage = Annotated[PageParams, Depends(product_page_params)]
ActiveFilter = Literal["true", "false", "all"]


def get_product_service(uow: UowDep) -> ProductService:
    return ProductService(uow)


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]


def _detail(summary: ProductSummary, user: User) -> ProductRead | ProductPublicRead:
    if can_view_cost(user):
        return ProductRead.from_summary(summary)
    return ProductPublicRead.from_summary(summary)


async def _load(
    session: SessionDep, product_id: UUID, user: User
) -> ProductRead | ProductPublicRead:
    summary = await ProductQueries(session).get(product_id)
    if summary is None:
        raise NotFoundError("Product not found")
    return _detail(summary, user)


def _active_filter(user: User, is_active: ActiveFilter) -> bool | None:
    if is_active != "true" and not can_view_cost(user):
        raise PermissionDeniedError("Only sales managers and admins can list retired products")
    return {"true": True, "false": False, "all": None}[is_active]


@router.get(
    "",
    response_model=Page[ProductSummaryRead] | Page[ProductSummaryPublicRead],
    summary="Search the catalogue (global, no territory scope)",
)
async def list_products(
    user: CurrentUser,
    session: SessionDep,
    params: ProductPage,
    q: Annotated[str | None, Query(max_length=100)] = None,
    division_id: Annotated[UUID | None, Query()] = None,
    family_id: Annotated[UUID | None, Query()] = None,
    brand_id: Annotated[UUID | None, Query()] = None,
    kind: Annotated[ProductKind | None, Query()] = None,
    own: Annotated[bool | None, Query()] = None,
    is_active: Annotated[ActiveFilter, Query()] = "true",
) -> Page[ProductSummaryRead] | Page[ProductSummaryPublicRead]:
    bounded = params
    cost_viewer = can_view_cost(user)
    result = await ProductQueries(session).list_page(
        bounded,
        ProductFilters(
            q=q,
            division_id=division_id,
            family_id=family_id,
            brand_id=brand_id,
            kind=kind,
            own=own,
            is_active=_active_filter(user, is_active),
        ),
        cost_viewer=cost_viewer,
    )
    if cost_viewer:
        return Page[ProductSummaryRead](
            items=[ProductSummaryRead.from_summary(item) for item in result.items],
            total=result.total,
            page=bounded.page,
            page_size=bounded.page_size,
        )
    return Page[ProductSummaryPublicRead](
        items=[ProductSummaryPublicRead.from_summary(item) for item in result.items],
        total=result.total,
        page=bounded.page,
        page_size=bounded.page_size,
    )


@router.get(
    "/{product_id}",
    response_model=ProductRead | ProductPublicRead,
    summary="Product detail (retired products stay readable)",
)
async def read_product(
    product_id: UUID, user: CurrentUser, session: SessionDep
) -> ProductRead | ProductPublicRead:
    return await _load(session, product_id, user)


@router.post(
    "",
    response_model=ProductRead | ProductPublicRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product (admin, back office)",
)
async def create_product(
    payload: ProductCreate, user: CurrentUser, session: SessionDep, service: ProductServiceDep
) -> ProductRead | ProductPublicRead:
    product = await service.create(
        CreateProduct(
            sku=payload.sku,
            name=payload.name,
            brand_id=payload.brand_id,
            family_id=payload.family_id,
            kind=payload.kind,
            list_price=payload.list_price,
            cost_price=payload.cost_price,
            unit=payload.unit,
            description=payload.description,
        ),
        actor=user,
    )
    return await _load(session, product.id, user)


@router.patch(
    "/{product_id}",
    response_model=ProductRead | ProductPublicRead,
    summary="Update a product (admin, back office)",
)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    session: SessionDep,
    service: ProductServiceDep,
) -> ProductRead | ProductPublicRead:
    await service.update(
        product_id,
        UpdateProduct(expected_version=expected_version, changes=payload.changes()),
        actor=user,
    )
    return await _load(session, product_id, user)


@router.post(
    "/{product_id}/deactivate",
    response_model=ProductRead | ProductPublicRead,
    summary="Retire a product (idempotent)",
)
async def deactivate_product(
    product_id: UUID,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    session: SessionDep,
    service: ProductServiceDep,
) -> ProductRead | ProductPublicRead:
    await service.set_active(
        product_id, active=False, expected_version=expected_version, actor=user
    )
    return await _load(session, product_id, user)


@router.post(
    "/{product_id}/activate",
    response_model=ProductRead | ProductPublicRead,
    summary="Reactivate a product (idempotent)",
)
async def activate_product(
    product_id: UUID,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    session: SessionDep,
    service: ProductServiceDep,
) -> ProductRead | ProductPublicRead:
    await service.set_active(product_id, active=True, expected_version=expected_version, actor=user)
    return await _load(session, product_id, user)


ImporterUser = Annotated[User, Depends(require_roles(Role.ADMIN, Role.BACK_OFFICE))]


@router.post(
    "/import",
    response_model=ImportReportRead,
    summary="Import the Sage catalogue export (dry-run preview by default)",
)
async def import_products(
    user: ImporterUser,
    uow: UowDep,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Query()] = True,
) -> ImportReportRead:
    content = await file.read()
    report = await ProductImporter(uow).run(
        file.filename or "productos.csv", content, dry_run=dry_run, actor=user
    )
    return ImportReportRead.build(report, dry_run=dry_run)
