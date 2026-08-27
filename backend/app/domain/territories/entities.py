"""Territory aggregate root and Division reference entity."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.shared.ids import new_id
from app.domain.territories.errors import InvalidProvinceError, TerritoryInUseError
from app.domain.territories.provinces import is_valid_province_code


def validate_province_codes(codes: frozenset[str]) -> None:
    invalid = sorted(code for code in codes if not is_valid_province_code(code))
    if invalid:
        raise InvalidProvinceError(invalid)


@dataclass
class Territory:
    id: UUID
    name: str
    provinces: frozenset[str]
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, *, name: str, provinces: frozenset[str]) -> "Territory":
        validate_province_codes(provinces)
        return cls(id=new_id(), name=name.strip(), provinces=provinces)

    def rename(self, name: str) -> None:
        self.name = name.strip()

    def set_provinces(self, provinces: frozenset[str]) -> None:
        validate_province_codes(provinces)
        self.provinces = provinces

    def deactivate(self, *, active_user_count: int) -> None:
        if active_user_count > 0:
            raise TerritoryInUseError(active_user_count)
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True


@dataclass(frozen=True)
class Division:
    id: UUID
    code: str
    name_es: str
    sort_order: int
