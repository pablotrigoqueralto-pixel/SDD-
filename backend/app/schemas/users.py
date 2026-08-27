from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.territories.entities import Division, Territory
from app.domain.users.entities import User
from app.domain.users.roles import IdentityProvider, Role
from app.schemas.territories import DivisionRead, TerritoryRead


class UserRead(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    identity_provider: IdentityProvider
    territory_ids: list[UUID]
    division_ids: list[UUID]
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, user: User) -> "UserRead":
        return cls(
            id=user.id,
            email=user.email.value,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            identity_provider=user.identity_provider,
            territory_ids=sorted(user.territory_ids, key=str),
            division_ids=sorted(user.division_ids, key=str),
            version=user.version,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class MeRead(UserRead):
    territories: list[TerritoryRead]
    divisions: list[DivisionRead]

    @classmethod
    def from_scope(
        cls, user: User, territories: list[Territory], divisions: list[Division]
    ) -> "MeRead":
        base = UserRead.from_entity(user).model_dump()
        return cls(
            **base,
            territories=[TerritoryRead.from_entity(t) for t in territories],
            divisions=[DivisionRead.from_entity(d) for d in divisions],
        )


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    password: str = Field(min_length=1, max_length=256)
    territory_ids: list[UUID] = Field(default_factory=list)
    division_ids: list[UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=1, max_length=256)
    territory_ids: list[UUID] | None = None
    division_ids: list[UUID] | None = None


class MeUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
