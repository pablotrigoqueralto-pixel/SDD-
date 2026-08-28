"""Resolve the acting user's scope once per use case."""

from app.application.shared.unit_of_work import UnitOfWork
from app.domain.shared.policies import Scope, ScopeFilter, resolve_scope
from app.domain.users.entities import User
from app.domain.users.roles import ROLES_WITH_FULL_VISIBILITY


async def user_scope(uow: UnitOfWork, user: User) -> Scope:
    if user.role in ROLES_WITH_FULL_VISIBILITY or not user.territory_ids:
        return resolve_scope(user, [])
    territories = await uow.territories.get_many(user.territory_ids)
    return resolve_scope(user, territories)


async def user_scope_filter(uow: UnitOfWork, user: User) -> ScopeFilter | None:
    return ScopeFilter.for_user(user, await user_scope(uow, user))
