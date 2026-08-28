"""ORM models. Import every model module here so Alembic autogenerate sees them."""

from app.infrastructure.db.models.audit import AuditLogModel
from app.infrastructure.db.models.base import Base
from app.infrastructure.db.models.reference import (
    AccountTypeModel,
    ActivityTypeModel,
    BrandDivisionModel,
    BrandModel,
    LossReasonModel,
    PipelineDivisionModel,
    PipelineModel,
    PipelineStageModel,
)
from app.infrastructure.db.models.territories import (
    DivisionModel,
    TerritoryModel,
    TerritoryProvinceModel,
)
from app.infrastructure.db.models.users import (
    RefreshTokenModel,
    UserDivisionModel,
    UserModel,
    UserTerritoryModel,
)

__all__ = [
    "AccountTypeModel",
    "ActivityTypeModel",
    "AuditLogModel",
    "Base",
    "BrandDivisionModel",
    "BrandModel",
    "DivisionModel",
    "LossReasonModel",
    "PipelineDivisionModel",
    "PipelineModel",
    "PipelineStageModel",
    "RefreshTokenModel",
    "TerritoryModel",
    "TerritoryProvinceModel",
    "UserDivisionModel",
    "UserModel",
    "UserTerritoryModel",
]
