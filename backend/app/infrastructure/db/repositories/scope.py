"""The territory visibility rule as one reusable SQL predicate (design D3)."""

from typing import Any

from sqlalchemy import ColumnElement, Select, exists, or_, select, true

from app.domain.shared.policies import ScopeFilter
from app.infrastructure.db.models import AccountDivisionModel, AccountModel


def account_scope_predicate(scope: ScopeFilter | None) -> ColumnElement[bool]:
    """owner = user OR (territory in scope AND (no divisions OR divisions intersect))."""
    if scope is None:
        return true()
    has_divisions = exists(
        select(1).where(AccountDivisionModel.account_id == AccountModel.id)
    ).correlate(AccountModel)
    matches_division = exists(
        select(1).where(
            AccountDivisionModel.account_id == AccountModel.id,
            AccountDivisionModel.division_id.in_(list(scope.division_ids) or [None]),
        )
    ).correlate(AccountModel)
    in_territory = AccountModel.territory_id.in_(list(scope.territory_ids) or [None])
    return or_(
        AccountModel.owner_id == scope.user_id,
        in_territory & or_(~has_divisions, matches_division),
    )


def scoped_accounts(statement: Select[Any], scope: ScopeFilter | None) -> Select[Any]:
    if scope is None:
        return statement
    return statement.where(account_scope_predicate(scope))
