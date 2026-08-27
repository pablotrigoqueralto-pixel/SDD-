"""User management use cases (admin) and self profile."""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from app.application.shared.unit_of_work import UnitOfWork
from app.application.users.commands import UNSET, CreateUser, UpdateUser
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email, validate_new_password
from app.infrastructure.security.passwords import PasswordHasher


def _snapshot(user: User) -> dict[str, object]:
    return {
        "email": user.email.value,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "password_hash": user.password_hash,
        "territory_ids": user.territory_ids,
        "division_ids": user.division_ids,
    }


class UserService:
    def __init__(self, uow: UnitOfWork, *, hasher: PasswordHasher) -> None:
        self._uow = uow
        self._hasher = hasher

    async def create(self, command: CreateUser, *, acting_user_id: UUID) -> User:
        validate_new_password(command.password, field="password")
        async with self._uow as uow:
            await _ensure_references(uow, command.territory_ids, command.division_ids)
            user = User.create(
                email=Email(command.email),
                full_name=command.full_name.strip(),
                role=command.role,
                password_hash=self._hasher.hash(command.password),
                territory_ids=command.territory_ids,
                division_ids=command.division_ids,
            )
            await uow.users.add(user)
            uow.audit.record(
                entity_type="user",
                entity_id=user.id,
                action="user.created",
                changes=diff_fields({}, _snapshot(user)),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return user

    async def update(self, user_id: UUID, command: UpdateUser, *, acting_user_id: UUID) -> User:
        if isinstance(command.password, str):
            validate_new_password(command.password, field="password")
        async with self._uow as uow:
            user = await uow.users.get(user_id)
            if user is None:
                raise NotFoundError("User not found")
            before = _snapshot(user)
            scope_before = (user.territory_ids, user.division_ids)

            if isinstance(command.full_name, str):
                user.rename(command.full_name)
            if isinstance(command.role, Role):
                user.change_role(command.role, acting_user_id=acting_user_id)
            if isinstance(command.is_active, bool):
                if command.is_active:
                    user.activate()
                else:
                    user.deactivate(acting_user_id=acting_user_id)
            territory_ids = (
                command.territory_ids
                if isinstance(command.territory_ids, frozenset)
                else user.territory_ids
            )
            division_ids = (
                command.division_ids
                if isinstance(command.division_ids, frozenset)
                else user.division_ids
            )
            if command.territory_ids is not UNSET or command.division_ids is not UNSET:
                await _ensure_references(uow, territory_ids, division_ids)
                user.assign_scope(territory_ids=territory_ids, division_ids=division_ids)
            password_reset = isinstance(command.password, str)
            if isinstance(command.password, str):
                user.set_password_hash(self._hasher.hash(command.password))

            await uow.users.save(user, expected_version=command.expected_version)
            after = _snapshot(user)

            if before["is_active"] and not after["is_active"]:
                await uow.refresh_tokens.revoke_all_for_user(user.id, now=datetime.now(UTC))
                uow.audit.record(
                    entity_type="user",
                    entity_id=user.id,
                    action="user.deactivated",
                    actor_id=acting_user_id,
                )
            elif not before["is_active"] and after["is_active"]:
                uow.audit.record(
                    entity_type="user",
                    entity_id=user.id,
                    action="user.activated",
                    actor_id=acting_user_id,
                )
            if scope_before != (user.territory_ids, user.division_ids):
                uow.audit.record(
                    entity_type="user",
                    entity_id=user.id,
                    action="user.scope_changed",
                    changes=diff_fields(
                        {"territory_ids": scope_before[0], "division_ids": scope_before[1]},
                        {"territory_ids": user.territory_ids, "division_ids": user.division_ids},
                    ),
                    actor_id=acting_user_id,
                )
            if password_reset:
                await uow.refresh_tokens.revoke_all_for_user(user.id, now=datetime.now(UTC))
                uow.audit.record(
                    entity_type="user",
                    entity_id=user.id,
                    action="user.password_reset",
                    actor_id=acting_user_id,
                )
            general = diff_fields(
                {
                    k: v
                    for k, v in before.items()
                    if k not in {"territory_ids", "division_ids", "password_hash"}
                },
                {
                    k: v
                    for k, v in after.items()
                    if k not in {"territory_ids", "division_ids", "password_hash"}
                },
            )
            if general:
                uow.audit.record(
                    entity_type="user",
                    entity_id=user.id,
                    action="user.updated",
                    changes=general,
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return user

    async def rename_self(self, user_id: UUID, full_name: str, *, expected_version: int) -> User:
        async with self._uow as uow:
            user = await uow.users.get(user_id)
            if user is None:
                raise NotFoundError("User not found")
            before = {"full_name": user.full_name}
            user.rename(full_name)
            await uow.users.save(user, expected_version=expected_version)
            uow.audit.record(
                entity_type="user",
                entity_id=user.id,
                action="user.updated",
                changes=diff_fields(before, {"full_name": user.full_name}),
                actor_id=user_id,
            )
            await uow.commit()
            return user


async def _ensure_references(
    uow: UnitOfWork, territory_ids: Iterable[UUID], division_ids: Iterable[UUID]
) -> None:
    wanted_territories = frozenset(territory_ids)
    wanted_divisions = frozenset(division_ids)
    if wanted_territories:
        missing = wanted_territories - await uow.territories.existing_ids(wanted_territories)
        if missing:
            raise UnknownReferenceError("territory_ids", sorted(str(m) for m in missing))
    if wanted_divisions:
        missing = wanted_divisions - await uow.divisions.existing_ids(wanted_divisions)
        if missing:
            raise UnknownReferenceError("division_ids", sorted(str(m) for m in missing))
