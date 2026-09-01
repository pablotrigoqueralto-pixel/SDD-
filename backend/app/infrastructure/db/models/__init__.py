"""ORM models. Import every model module here so Alembic autogenerate sees them."""

from app.infrastructure.db.models.accounts import (
    AccountAddressModel,
    AccountBrandModel,
    AccountDivisionModel,
    AccountModel,
    AccountPhoneModel,
    JobTitleModel,
    SpecialtyModel,
)
from app.infrastructure.db.models.activities import (
    ActivityAttendeeModel,
    ActivityContactModel,
    ActivityModel,
)
from app.infrastructure.db.models.audit import AuditLogModel
from app.infrastructure.db.models.base import Base
from app.infrastructure.db.models.catalogue import ProductFamilyModel, ProductModel
from app.infrastructure.db.models.contacts import (
    ContactModel,
    ContactPhoneModel,
    PersonalDataAccessLogModel,
)
from app.infrastructure.db.models.notifications import NotificationModel
from app.infrastructure.db.models.opportunities import (
    OpportunityLineModel,
    OpportunityModel,
    OpportunityStageHistoryModel,
)
from app.infrastructure.db.models.quotes import (
    AppSettingModel,
    MailOutboxModel,
    QuoteCounterModel,
    QuoteLineModel,
    QuoteModel,
    QuotePdfModel,
)
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
    "AccountAddressModel",
    "AccountBrandModel",
    "AccountDivisionModel",
    "AccountModel",
    "AccountPhoneModel",
    "AccountTypeModel",
    "ActivityAttendeeModel",
    "ActivityContactModel",
    "ActivityModel",
    "ActivityTypeModel",
    "AppSettingModel",
    "AuditLogModel",
    "Base",
    "BrandDivisionModel",
    "BrandModel",
    "ContactModel",
    "ContactPhoneModel",
    "DivisionModel",
    "JobTitleModel",
    "LossReasonModel",
    "MailOutboxModel",
    "NotificationModel",
    "OpportunityLineModel",
    "OpportunityModel",
    "OpportunityStageHistoryModel",
    "PersonalDataAccessLogModel",
    "PipelineDivisionModel",
    "PipelineModel",
    "PipelineStageModel",
    "ProductFamilyModel",
    "ProductModel",
    "QuoteCounterModel",
    "QuoteLineModel",
    "QuoteModel",
    "QuotePdfModel",
    "RefreshTokenModel",
    "SpecialtyModel",
    "TerritoryModel",
    "TerritoryProvinceModel",
    "UserDivisionModel",
    "UserModel",
    "UserTerritoryModel",
]
