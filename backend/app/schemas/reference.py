import unicodedata
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.application.reference.catalogue_entry import CatalogueOutcome
from app.domain.reference.entities import (
    AccountType,
    ActivityType,
    Brand,
    JobTitle,
    LossReason,
    Pipeline,
    PipelineStage,
    ProductFamily,
    Specialty,
)
from app.schemas.territories import DivisionRead


def catalogue_name(value: str) -> str:
    """A catalogue name must yield a code: whitespace or punctuation alone cannot.

    Without this the request reaches `slugify_code`, which raises ValueError and turns an
    administrator's stray spaces into a 500. Applied to every catalogue creation payload.
    """
    clean = value.strip()
    if not any(char.isalnum() for char in unicodedata.normalize("NFKD", clean)):
        msg = "The name must contain at least one letter or digit"
        raise ValueError(msg)
    return clean


CatalogueName = Annotated[str, Field(min_length=1, max_length=100), AfterValidator(catalogue_name)]


class AccountTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    sort_order: int
    buys_via_tender: bool
    is_active: bool

    @classmethod
    def from_entity(cls, entity: AccountType) -> "AccountTypeRead":
        return cls.model_validate(entity)


class ActivityTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    sort_order: int
    icon: str
    counts_as_contact: bool
    is_active: bool

    @classmethod
    def from_entity(cls, entity: ActivityType) -> "ActivityTypeRead":
        return cls.model_validate(entity)


class BrandRead(BaseModel):
    id: UUID
    code: str
    name: str
    is_own: bool
    is_active: bool
    division_ids: list[UUID]
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, brand: Brand) -> "BrandRead":
        return cls(
            id=brand.id,
            code=brand.code,
            name=brand.name,
            is_own=brand.is_own,
            is_active=brand.is_active,
            division_ids=sorted(brand.division_ids, key=str),
            version=brand.version,
            created_at=brand.created_at,
            updated_at=brand.updated_at,
        )


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_own: bool
    division_ids: list[UUID] = Field(default_factory=list)


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_own: bool | None = None
    is_active: bool | None = None
    division_ids: list[UUID] | None = None


class LossReasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    sort_order: int
    requires_brand: bool
    requires_note: bool
    is_active: bool
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, reason: LossReason) -> "LossReasonRead":
        return cls.model_validate(reason)


class LossReasonCreated(LossReasonRead):
    """Creation also says whether the entry was new, reused or brought back."""

    outcome: CatalogueOutcome

    @classmethod
    def of(cls, reason: LossReason, outcome: CatalogueOutcome) -> "LossReasonCreated":
        return cls(**LossReasonRead.from_entity(reason).model_dump(), outcome=outcome)


class LossReasonCreate(BaseModel):
    name: CatalogueName


class LossReasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class JobTitleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    sort_order: int
    is_active: bool
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, job_title: JobTitle) -> "JobTitleRead":
        return cls.model_validate(job_title)


class SpecialtyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    sort_order: int
    is_active: bool
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, specialty: Specialty) -> "SpecialtyRead":
        return cls.model_validate(specialty)


class AccountTypeCreate(BaseModel):
    name: CatalogueName
    # Asked for, never guessed: this flag decides whether an opportunity of a centre of
    # this type offers the tender fields.
    buys_via_tender: bool = False


class AccountTypeCreated(AccountTypeRead):
    """Creation also says whether the entry was new, reused or brought back."""

    outcome: CatalogueOutcome

    @classmethod
    def of(cls, account_type: AccountType, outcome: CatalogueOutcome) -> "AccountTypeCreated":
        return cls(**AccountTypeRead.from_entity(account_type).model_dump(), outcome=outcome)


class SpecialtyCreate(BaseModel):
    name: CatalogueName


class SpecialtyCreated(SpecialtyRead):
    """Creation also says whether the entry was new, reused or brought back."""

    outcome: CatalogueOutcome

    @classmethod
    def of(cls, specialty: Specialty, outcome: CatalogueOutcome) -> "SpecialtyCreated":
        return cls(**SpecialtyRead.from_entity(specialty).model_dump(), outcome=outcome)


class JobTitleCreate(BaseModel):
    name: CatalogueName


class JobTitleCreated(JobTitleRead):
    """Creation also says whether the entry was new, reused or brought back."""

    outcome: CatalogueOutcome

    @classmethod
    def of(cls, job_title: JobTitle, outcome: CatalogueOutcome) -> "JobTitleCreated":
        return cls(**JobTitleRead.from_entity(job_title).model_dump(), outcome=outcome)


class JobTitleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class ProductFamilyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    division_id: UUID
    sort_order: int
    is_active: bool
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, family: ProductFamily) -> "ProductFamilyRead":
        return cls.model_validate(family)


class ProductFamilyCreated(ProductFamilyRead):
    """Creation also says whether the family was new, reused or brought back."""

    outcome: CatalogueOutcome

    @classmethod
    def of(cls, family: ProductFamily, outcome: CatalogueOutcome) -> "ProductFamilyCreated":
        return cls(**ProductFamilyRead.from_entity(family).model_dump(), outcome=outcome)


class ProductFamilyCreate(BaseModel):
    name: CatalogueName
    division_id: UUID


class ProductFamilyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # division_id and code are immutable

    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class PipelineStageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_es: str
    sort_order: int
    probability: int
    is_won: bool
    is_lost: bool
    is_at_risk: bool
    is_active: bool
    version: int

    @classmethod
    def from_entity(cls, stage: PipelineStage) -> "PipelineStageRead":
        return cls.model_validate(stage)


class PipelineRead(BaseModel):
    id: UUID
    code: str
    name_es: str
    sort_order: int
    division_ids: list[UUID]
    stages: list[PipelineStageRead]
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, pipeline: Pipeline) -> "PipelineRead":
        return cls(
            id=pipeline.id,
            code=pipeline.code,
            name_es=pipeline.name_es,
            sort_order=pipeline.sort_order,
            division_ids=sorted(pipeline.division_ids, key=str),
            stages=[PipelineStageRead.from_entity(s) for s in pipeline.ordered_stages()],
            version=pipeline.version,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )


class PipelineUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class StageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    probability: int | None = None
    is_active: bool | None = None
    # Present only to reject attempts explicitly (stage_flag_immutable).
    is_won: bool | None = None
    is_lost: bool | None = None
    is_at_risk: bool | None = None


class StageOrder(BaseModel):
    stage_ids: list[UUID] = Field(min_length=1)


class ReferenceDataRead(BaseModel):
    account_types: list[AccountTypeRead]
    activity_types: list[ActivityTypeRead]
    divisions: list[DivisionRead]
    brands: list[BrandRead]
    loss_reasons: list[LossReasonRead]
    pipelines: list[PipelineRead]
    job_titles: list[JobTitleRead]
    specialties: list[SpecialtyRead]
    product_families: list[ProductFamilyRead]
