"""Smart default for the account owner (design D4)."""

from collections.abc import Sequence
from uuid import UUID

from app.domain.users.entities import User
from app.domain.users.roles import Role


def resolve_owner(
    *,
    creator: User,
    territory_id: UUID | None,
    account_division_ids: frozenset[UUID],
    territory_reps: Sequence[User],
) -> UUID | None:
    """The creator when they are a rep; else the only compatible active rep of the territory.

    `territory_reps` are the users assigned to `territory_id` (any role, any state); the
    resolver filters them so callers do not need to know the rule.
    """
    if creator.role == Role.SALES_REP:
        return creator.id
    if territory_id is None:
        return None
    compatible = [
        rep
        for rep in territory_reps
        if rep.role == Role.SALES_REP
        and rep.is_active
        and territory_id in rep.territory_ids
        and (not account_division_ids or rep.division_ids & account_division_ids)
    ]
    if len(compatible) == 1:
        return compatible[0].id
    return None
