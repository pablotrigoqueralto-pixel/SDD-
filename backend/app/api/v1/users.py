"""User administration endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AdminUser, ExpectedVersion, SessionDep, StaffUser, UowDep, get_user_service
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.application.users.commands import UNSET, CreateUser, UpdateUser
from app.application.users.queries import (
    USER_DEFAULT_SORT,
    USER_SORT_FIELDS,
    UserFilters,
    UserQueries,
)
from app.application.users.service import UserService
from app.domain.shared.errors import NotFoundError
from app.domain.users.roles import Role
from app.schemas.users import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

UserPage = Annotated[
    PageParams, Depends(page_params_dependency(USER_SORT_FIELDS, USER_DEFAULT_SORT))
]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.get("", response_model=Page[UserRead], summary="List users")
async def list_users(
    _: StaffUser,
    session: SessionDep,
    params: UserPage,
    role: Annotated[Role | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    territory_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[UserRead]:
    result = await UserQueries(session).list_page(
        params, UserFilters(role=role, is_active=is_active, territory_id=territory_id, q=q)
    )
    return Page[UserRead](
        items=[UserRead.from_entity(user) for user in result.items],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post(
    "", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Create user"
)
async def create_user(payload: UserCreate, admin: AdminUser, service: UserServiceDep) -> UserRead:
    user = await service.create(
        CreateUser(
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
            password=payload.password,
            territory_ids=frozenset(payload.territory_ids),
            division_ids=frozenset(payload.division_ids),
        ),
        acting_user_id=admin.id,
    )
    return UserRead.from_entity(user)


@router.get("/{user_id}", response_model=UserRead, summary="Read a user")
async def read_user(user_id: UUID, _: StaffUser, uow: UowDep) -> UserRead:
    user = await uow.users.get(user_id)
    if user is None:
        raise NotFoundError("User not found")
    return UserRead.from_entity(user)


@router.patch("/{user_id}", response_model=UserRead, summary="Update a user")
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    admin: AdminUser,
    expected_version: ExpectedVersion,
    service: UserServiceDep,
) -> UserRead:
    provided = payload.model_fields_set
    command = UpdateUser(
        expected_version=expected_version,
        full_name=payload.full_name if "full_name" in provided and payload.full_name else UNSET,
        role=payload.role if "role" in provided and payload.role else UNSET,
        is_active=payload.is_active
        if "is_active" in provided and payload.is_active is not None
        else UNSET,
        password=payload.password if "password" in provided and payload.password else UNSET,
        territory_ids=frozenset(payload.territory_ids)
        if payload.territory_ids is not None
        else UNSET,
        division_ids=frozenset(payload.division_ids) if payload.division_ids is not None else UNSET,
    )
    user = await service.update(user_id, command, acting_user_id=admin.id)
    return UserRead.from_entity(user)
