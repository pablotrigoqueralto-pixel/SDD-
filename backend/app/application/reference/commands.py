"""Input DTOs for reference data use cases."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.application.users.commands import UNSET


@dataclass(frozen=True)
class CreateBrand:
    name: str
    is_own: bool
    division_ids: frozenset[UUID] = field(default_factory=frozenset)


@dataclass(frozen=True)
class UpdateBrand:
    expected_version: int
    name: str | object = UNSET
    is_own: bool | object = UNSET
    is_active: bool | object = UNSET
    division_ids: frozenset[UUID] | object = UNSET


@dataclass(frozen=True)
class CreateLossReason:
    name: str


@dataclass(frozen=True)
class UpdateLossReason:
    expected_version: int
    name: str | object = UNSET
    is_active: bool | object = UNSET


@dataclass(frozen=True)
class UpdateStage:
    expected_version: int
    name: str | object = UNSET
    probability: int | object = UNSET
    is_active: bool | object = UNSET


@dataclass(frozen=True)
class ReorderStages:
    expected_version: int
    stage_ids: Sequence[UUID]


@dataclass(frozen=True)
class CreateJobTitle:
    name: str


@dataclass(frozen=True)
class UpdateJobTitle:
    expected_version: int
    name: str | object = UNSET
    is_active: bool | object = UNSET
