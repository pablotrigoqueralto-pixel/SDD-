"""Reference data entities: account/activity types (read-only), brands, loss reasons,
job titles, pipelines with their stages (aggregate)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.reference.codes import slugify_code
from app.domain.reference.errors import (
    LastActiveStageError,
    StageOrderInvalidError,
    StageProbabilityInvalidError,
)
from app.domain.shared.errors import NotFoundError
from app.domain.shared.ids import new_id


@dataclass(frozen=True)
class AccountType:
    id: UUID
    code: str
    name_es: str
    sort_order: int
    buys_via_tender: bool
    is_active: bool
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ActivityType:
    id: UUID
    code: str
    name_es: str
    sort_order: int
    icon: str
    counts_as_contact: bool
    is_active: bool
    updated_at: datetime | None = None


@dataclass
class Brand:
    id: UUID
    code: str
    name: str
    is_own: bool
    is_active: bool = True
    division_ids: frozenset[UUID] = field(default_factory=frozenset)
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, *, name: str, is_own: bool, division_ids: frozenset[UUID]) -> "Brand":
        clean = name.strip()
        return cls(
            id=new_id(),
            code=slugify_code(clean),
            name=clean,
            is_own=is_own,
            division_ids=division_ids,
        )

    def rename(self, name: str) -> None:
        self.name = name.strip()

    def set_own(self, is_own: bool) -> None:
        self.is_own = is_own

    def set_divisions(self, division_ids: frozenset[UUID]) -> None:
        self.division_ids = division_ids

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False


@dataclass
class LossReason:
    id: UUID
    code: str
    name_es: str
    sort_order: int
    requires_brand: bool = False
    requires_note: bool = False
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, *, name: str, sort_order: int) -> "LossReason":
        clean = name.strip()
        return cls(id=new_id(), code=slugify_code(clean), name_es=clean, sort_order=sort_order)

    def rename(self, name: str) -> None:
        self.name_es = name.strip()

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False


@dataclass
class JobTitle:
    id: UUID
    code: str
    name_es: str
    sort_order: int
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(cls, *, name: str, sort_order: int) -> "JobTitle":
        clean = name.strip()
        return cls(id=new_id(), code=slugify_code(clean), name_es=clean, sort_order=sort_order)

    def rename(self, name: str) -> None:
        self.name_es = name.strip()

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False


@dataclass
class PipelineStage:
    id: UUID
    code: str
    name_es: str
    sort_order: int
    probability: int
    is_won: bool = False
    is_lost: bool = False
    is_at_risk: bool = False
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return not self.is_won and not self.is_lost


def validate_probability(probability: int) -> None:
    if not 0 <= probability <= 100:
        raise StageProbabilityInvalidError()


@dataclass
class Pipeline:
    """Aggregate root: stages are only changed through the pipeline."""

    id: UUID
    code: str
    name_es: str
    sort_order: int
    division_ids: frozenset[UUID] = field(default_factory=frozenset)
    stages: list[PipelineStage] = field(default_factory=list)
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def rename(self, name: str) -> None:
        self.name_es = name.strip()

    def stage(self, stage_id: UUID) -> PipelineStage:
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        raise NotFoundError("Stage not found")

    def ordered_stages(self) -> list[PipelineStage]:
        return sorted(self.stages, key=lambda stage: stage.sort_order)

    def update_stage(
        self,
        stage_id: UUID,
        *,
        name: str | None = None,
        probability: int | None = None,
        is_active: bool | None = None,
    ) -> PipelineStage:
        stage = self.stage(stage_id)
        if name is not None:
            stage.name_es = name.strip()
        if probability is not None:
            validate_probability(probability)
            stage.probability = probability
        if is_active is not None:
            if not is_active and stage.is_active and stage.is_open:
                other_open = [
                    s for s in self.stages if s.id != stage.id and s.is_active and s.is_open
                ]
                if not other_open:
                    raise LastActiveStageError()
            stage.is_active = is_active
        return stage

    def reorder(self, stage_ids: Sequence[UUID]) -> None:
        wanted = list(stage_ids)
        existing = {stage.id for stage in self.stages}
        if len(set(wanted)) != len(wanted):
            raise StageOrderInvalidError("Stage ids must not repeat")
        unknown = [str(sid) for sid in wanted if sid not in existing]
        if unknown:
            raise StageOrderInvalidError(f"Unknown stages: {', '.join(unknown)}")
        missing = existing - set(wanted)
        if missing:
            raise StageOrderInvalidError("Every stage of the pipeline must be listed")
        by_id = {stage.id: stage for stage in self.stages}
        for position, sid in enumerate(wanted, start=1):
            by_id[sid].sort_order = position
        self.stages = [by_id[sid] for sid in wanted]
