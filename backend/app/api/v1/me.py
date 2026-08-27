"""Self profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, ExpectedVersion, UowDep, get_user_service
from app.application.users.service import UserService
from app.domain.users.entities import User
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.schemas.users import MeRead, MeUpdate

router = APIRouter(prefix="/me", tags=["me"])


async def build_me(user: User, uow: SqlAlchemyUnitOfWork) -> MeRead:
    territories = await uow.territories.get_many(user.territory_ids)
    divisions = [
        division for division in await uow.divisions.list_all() if division.id in user.division_ids
    ]
    return MeRead.from_scope(user, sorted(territories, key=lambda t: t.name), divisions)


@router.get("", response_model=MeRead, summary="Read the own profile and scope")
async def read_me(user: CurrentUser, uow: UowDep) -> MeRead:
    return await build_me(user, uow)


@router.patch("", response_model=MeRead, summary="Rename the own profile")
async def update_me(
    payload: MeUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    service: Annotated[UserService, Depends(get_user_service)],
    uow: UowDep,
) -> MeRead:
    updated = await service.rename_self(
        user.id, payload.full_name, expected_version=expected_version
    )
    return await build_me(updated, uow)
