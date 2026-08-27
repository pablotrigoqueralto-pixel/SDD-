"""Role and identity provider enumerations (persisted as PostgreSQL enums)."""

from enum import StrEnum


class Role(StrEnum):
    SALES_REP = "sales_rep"
    SALES_MANAGER = "sales_manager"
    BACK_OFFICE = "back_office"
    ADMIN = "admin"


class IdentityProvider(StrEnum):
    PASSWORD = "password"  # noqa: S105 - provider name, not a secret
    ENTRA_ID = "entra_id"


ROLES_WITH_FULL_VISIBILITY: frozenset[Role] = frozenset(
    {Role.ADMIN, Role.SALES_MANAGER, Role.BACK_OFFICE}
)
