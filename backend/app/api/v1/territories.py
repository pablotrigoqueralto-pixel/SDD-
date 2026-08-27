"""Territory administration and division reference endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    AdminUser,
    CurrentUser,
    ExpectedVersion,
    SessionDep,
    StaffUser,
    UowDep,
    get_territory_service,
)
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.application.territories.queries import (
    TERRITORY_DEFAULT_SORT,
    TERRITORY_SORT_FIELDS,
    TerritoryFilters,
    TerritoryQueries,
)
from app.application.territories.service import (
    CreateTerritory,
    TerritoryService,
    UpdateTerritory,
)
from app.application.users.commands import UNSET
from app.domain.shared.errors import NotFoundError
from app.schemas.territories import DivisionRead, TerritoryCreate, TerritoryRead, TerritoryUpdate

router = APIRouter(tags=["territories"])

TerritoryPage = Annotated[
    PageParams, Depends(page_params_dependency(TERRITORY_SORT_FIELDS, TERRITORY_DEFAULT_SORT))
]
TerritoryServiceDep = Annotated[TerritoryService, Depends(get_territory_service)]


@router.get("/territories", response_model=Page[TerritoryRead], summary="List territories")
async def list_territories(
    _: StaffUser,
    session: SessionDep,
    params: TerritoryPage,
    is_active: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[TerritoryRead]:
    result = await TerritoryQueries(session).list_page(
        params, TerritoryFilters(is_active=is_active, q=q)
    )
    return Page[TerritoryRead](
        items=[
            TerritoryRead.from_entity(item.territory, user_count=item.user_count)
            for item in result.items
        ],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "/territories",
    response_model=TerritoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create territory",
)
async def create_territory(
    payload: TerritoryCreate, admin: AdminUser, service: TerritoryServiceDep
) -> TerritoryRead:
    territory = await service.create(
        CreateTerritory(name=payload.name, provinces=frozenset(payload.provinces)),
        acting_user_id=admin.id,
    )
    return TerritoryRead.from_entity(territory)


@router.get("/territories/{territory_id}", response_model=TerritoryRead, summary="Read territory")
async def read_territory(territory_id: UUID, _: StaffUser, session: SessionDep) -> TerritoryRead:
    item = await TerritoryQueries(session).get(territory_id)
    if item is None:
        raise NotFoundError("Territory not found")
    return TerritoryRead.from_entity(item.territory, user_count=item.user_count)


@router.patch(
    "/territories/{territory_id}", response_model=TerritoryRead, summary="Update territory"
)
async def update_territory(
    territory_id: UUID,
    payload: TerritoryUpdate,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: TerritoryServiceDep,
    session: SessionDep,
) -> TerritoryRead:
    command = UpdateTerritory(
        expected_version=expected_version,
        name=payload.name if payload.name is not None else UNSET,
        provinces=frozenset(payload.provinces) if payload.provinces is not None else UNSET,
        is_active=payload.is_active if payload.is_active is not None else UNSET,
    )
    territory = await service.update(territory_id, command, acting_user_id=admin.id)
    item = await TerritoryQueries(session).get(territory.id)
    return TerritoryRead.from_entity(territory, user_count=item.user_count if item else 0)


@router.get("/divisions", response_model=list[DivisionRead], summary="List divisions")
async def list_divisions(_: CurrentUser, uow: UowDep) -> list[DivisionRead]:
    return [DivisionRead.from_entity(division) for division in await uow.divisions.list_all()]
