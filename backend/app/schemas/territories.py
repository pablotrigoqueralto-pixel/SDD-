from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.territories.entities import Division, Territory


class DivisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    sort_order: int

    @classmethod
    def from_entity(cls, division: Division) -> "DivisionRead":
        return cls.model_validate(division)


class TerritoryRead(BaseModel):
    id: UUID
    name: str
    provinces: list[str]
    is_active: bool
    user_count: int
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, territory: Territory, *, user_count: int = 0) -> "TerritoryRead":
        return cls(
            id=territory.id,
            name=territory.name,
            provinces=sorted(territory.provinces),
            is_active=territory.is_active,
            user_count=user_count,
            version=territory.version,
            created_at=territory.created_at,
            updated_at=territory.updated_at,
        )


class TerritoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provinces: list[str] = Field(min_length=1)


class TerritoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    provinces: list[str] | None = Field(default=None, min_length=1)
    is_active: bool | None = None
