from dataclasses import dataclass, field
from uuid import UUID

import pytest

from app.domain.shared.ids import new_id
from app.domain.shared.policies import Scope, ScopeFilter, VisibilityPolicy, resolve_scope
from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email


@dataclass(frozen=True)
class Record:
    owner_id: UUID | None
    territory_id: UUID | None
    division_ids: frozenset[UUID] = field(default_factory=frozenset)


CENTRO = Territory.create(name="Centro", provinces=frozenset({"28", "45"}))
NORTE = Territory.create(name="Norte", provinces=frozenset({"48", "20"}))
VASCULAR = new_id()
NEUROLOGY = new_id()


def make_user(
    role: Role, territories: set[UUID] | None = None, divisions: set[UUID] | None = None
) -> User:
    return User.create(
        email=Email("rep@quermed.com"),
        full_name="Rep",
        role=role,
        password_hash="h",
        territory_ids=frozenset(territories or set()),
        division_ids=frozenset(divisions or set()),
    )


@pytest.fixture
def rep() -> User:
    return make_user(Role.SALES_REP, {CENTRO.id}, {VASCULAR})


@pytest.fixture
def scope(rep: User) -> Scope:
    return resolve_scope(rep, [CENTRO, NORTE])


def test_resolve_scope_collects_provinces_of_assigned_territories(scope: Scope) -> None:
    assert scope.territory_ids == frozenset({CENTRO.id})
    assert scope.province_codes == frozenset({"28", "45"})
    assert scope.division_ids == frozenset({VASCULAR})
    assert not scope.is_empty


def test_rep_sees_record_in_territory_and_division(rep: User, scope: Scope) -> None:
    record = Record(new_id(), CENTRO.id, frozenset({VASCULAR, NEUROLOGY}))

    assert VisibilityPolicy.can_read(rep, scope, record)
    assert VisibilityPolicy.can_write(rep, scope, record)


def test_rep_excluded_by_division(rep: User, scope: Scope) -> None:
    record = Record(new_id(), CENTRO.id, frozenset({NEUROLOGY}))

    assert not VisibilityPolicy.can_read(rep, scope, record)


def test_rep_excluded_by_territory(rep: User, scope: Scope) -> None:
    record = Record(new_id(), NORTE.id, frozenset({VASCULAR}))

    assert not VisibilityPolicy.can_read(rep, scope, record)


def test_rep_sees_owned_record_outside_scope(rep: User, scope: Scope) -> None:
    record = Record(rep.id, NORTE.id, frozenset({NEUROLOGY}))

    assert VisibilityPolicy.can_read(rep, scope, record)


def test_record_without_divisions_only_needs_territory(rep: User, scope: Scope) -> None:
    record = Record(new_id(), CENTRO.id)

    assert VisibilityPolicy.can_read(rep, scope, record)


def test_unassigned_record_in_territory_is_visible(rep: User, scope: Scope) -> None:
    record = Record(None, CENTRO.id)

    assert VisibilityPolicy.can_read(rep, scope, record)


def test_manager_sees_and_writes_everything() -> None:
    manager = make_user(Role.SALES_MANAGER)
    scope = resolve_scope(manager, [])
    record = Record(new_id(), NORTE.id, frozenset({NEUROLOGY}))

    assert VisibilityPolicy.can_read(manager, scope, record)
    assert VisibilityPolicy.can_write(manager, scope, record)


def test_back_office_reads_everything_but_does_not_write_by_default() -> None:
    back_office = make_user(Role.BACK_OFFICE)
    scope = resolve_scope(back_office, [])
    record = Record(new_id(), NORTE.id, frozenset({NEUROLOGY}))

    assert VisibilityPolicy.can_read(back_office, scope, record)
    assert not VisibilityPolicy.can_write(back_office, scope, record)


def test_rep_without_scope_has_empty_scope() -> None:
    lonely = make_user(Role.SALES_REP)

    assert resolve_scope(lonely, [CENTRO]).is_empty


def test_scope_filter_is_none_for_roles_with_full_visibility() -> None:
    for role in (Role.ADMIN, Role.SALES_MANAGER, Role.BACK_OFFICE):
        user = make_user(role)
        assert ScopeFilter.for_user(user, resolve_scope(user, [])) is None


def test_scope_filter_carries_the_rep_identity_and_scope(rep: User, scope: Scope) -> None:
    scope_filter = ScopeFilter.for_user(rep, scope)

    assert scope_filter == ScopeFilter(
        user_id=rep.id,
        territory_ids=frozenset({CENTRO.id}),
        division_ids=frozenset({VASCULAR}),
    )
