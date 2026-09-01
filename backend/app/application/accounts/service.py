"""Account use cases: scoped reads, creation with smart defaults, updates, assignment."""

from dataclasses import dataclass
from uuid import UUID

from app.application.accounts.commands import (
    AssignAccount,
    CreateAccount,
    ReplaceAddresses,
    UpdateAccount,
)
from app.application.shared.scope import user_scope
from app.application.shared.unit_of_work import UnitOfWork
from app.application.users.commands import UNSET
from app.domain.accounts.entities import (
    ADMINISTRATIVE_FIELDS,
    Account,
    AdditionalAddress,
)
from app.domain.accounts.errors import (
    AssignmentForbiddenError,
    OwnerNotSalesRepError,
    TaxIdAlreadyExistsError,
)
from app.domain.accounts.owner_resolver import resolve_owner
from app.domain.accounts.value_objects import TaxId
from app.domain.notifications.entities import NotificationKind
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.shared.policies import Scope, ScopeFilter, VisibilityPolicy
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role

ASSIGNMENT_FIELDS: frozenset[str] = frozenset({"owner_id", "territory_id"})


@dataclass(frozen=True)
class AccountView:
    account: Account
    territory_mismatch: bool
    territory_name: str | None = None
    owner_name: str | None = None


async def load_visible_account(uow: UnitOfWork, account_id: UUID, actor: User) -> Account:
    """404 for missing *and* out-of-scope accounts (no existence leak)."""
    scope = await user_scope(uow, actor)
    account = await uow.accounts.get(account_id, scope=ScopeFilter.for_user(actor, scope))
    if account is None:
        raise NotFoundError("Account not found")
    return account


async def ensure_account_writer(uow: UnitOfWork, actor: User, account: Account) -> Scope:
    scope = await user_scope(uow, actor)
    if actor.role == Role.BACK_OFFICE or not VisibilityPolicy.can_write(actor, scope, account):
        raise PermissionDeniedError("Your role cannot modify this account")
    return scope


class AccountService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def get(self, account_id: UUID, *, actor: User) -> AccountView:
        async with self._uow as uow:
            account = await load_visible_account(uow, account_id, actor)
            return await self._view(uow, account)

    async def create(self, command: CreateAccount, *, actor: User) -> AccountView:
        async with self._uow as uow:
            details = dict(command.details)
            await self._validate_references(uow, command.account_type_id, details)
            await self._ensure_tax_id_free(uow, details.get("tax_id"), None)
            territory = await uow.territories.find_by_province(command.province_code)
            territory_id = territory.id if territory and territory.is_active else None
            division_ids = _ids(details, "division_ids")
            reps = await uow.users.list_in_territory(territory_id) if territory_id else []
            owner_id = resolve_owner(
                creator=actor,
                territory_id=territory_id,
                account_division_ids=division_ids,
                territory_reps=reps,
            )
            account = Account.create(
                name=command.name,
                account_type_id=command.account_type_id,
                province_code=command.province_code,
                territory_id=territory_id,
                owner_id=owner_id,
                details=details,
            )
            await uow.accounts.add(account)
            uow.audit.record(
                entity_type="account",
                entity_id=account.id,
                action="account.created",
                changes=diff_fields(
                    {},
                    {
                        **account.snapshot(),
                        "territory_id": account.territory_id,
                        "owner_id": account.owner_id,
                    },
                ),
                actor_id=actor.id,
            )
            await uow.commit()
            return await self._view(uow, account)

    async def update(self, account_id: UUID, command: UpdateAccount, *, actor: User) -> AccountView:
        changes = dict(command.changes)
        if ASSIGNMENT_FIELDS & changes.keys():
            raise AssignmentForbiddenError()
        async with self._uow as uow:
            account = await load_visible_account(uow, account_id, actor)
            self._ensure_can_update(actor, changes)
            if actor.role != Role.BACK_OFFICE:
                await ensure_account_writer(uow, actor, account)
            await self._validate_references(
                uow, changes.get("account_type_id", account.account_type_id), changes
            )
            if "tax_id" in changes and changes["tax_id"] is not None:
                await self._ensure_tax_id_free(uow, changes["tax_id"], account.id)
            before = account.snapshot()
            account.update_details(changes)
            if isinstance(changes.get("is_active"), bool):
                if changes["is_active"]:
                    account.activate()
                else:
                    account.deactivate()
            await uow.accounts.save(account, expected_version=command.expected_version)
            after = account.snapshot()
            general = diff_fields(
                {k: v for k, v in before.items() if k != "is_active"},
                {k: v for k, v in after.items() if k != "is_active"},
            )
            if general:
                uow.audit.record(
                    entity_type="account",
                    entity_id=account.id,
                    action="account.updated",
                    changes=general,
                    actor_id=actor.id,
                )
            if before["is_active"] != after["is_active"]:
                uow.audit.record(
                    entity_type="account",
                    entity_id=account.id,
                    action="account.activated" if account.is_active else "account.deactivated",
                    actor_id=actor.id,
                )
            await uow.commit()
            return await self._view(uow, account)

    async def assign(self, account_id: UUID, command: AssignAccount, *, actor: User) -> AccountView:
        if actor.role not in {Role.ADMIN, Role.SALES_MANAGER}:
            raise AssignmentForbiddenError()
        async with self._uow as uow:
            account = await load_visible_account(uow, account_id, actor)
            owner_id = account.owner_id
            territory_id = account.territory_id
            if command.owner_id is not UNSET:
                owner_id = await self._checked_owner(uow, command.owner_id)  # type: ignore[arg-type]
            if command.territory_id is not UNSET:
                territory_id = await self._checked_territory(uow, command.territory_id)  # type: ignore[arg-type]
            before = {"owner_id": account.owner_id, "territory_id": account.territory_id}
            account.assign(owner_id=owner_id, territory_id=territory_id)
            await uow.accounts.save(account, expected_version=command.expected_version)
            changes = diff_fields(before, {"owner_id": owner_id, "territory_id": territory_id})
            if owner_id is not None and owner_id != before["owner_id"]:
                uow.notifications.notify(
                    user_id=owner_id,
                    kind=NotificationKind.ACCOUNT_ASSIGNED,
                    entity_type="account",
                    entity_id=account.id,
                    actor_id=actor.id,
                    payload={"account_name": account.name},
                )
            if changes:
                uow.audit.record(
                    entity_type="account",
                    entity_id=account.id,
                    action="account.assigned",
                    changes=changes,
                    actor_id=actor.id,
                )
            await uow.commit()
            return await self._view(uow, account)

    async def replace_addresses(
        self, account_id: UUID, command: ReplaceAddresses, *, actor: User
    ) -> AccountView:
        async with self._uow as uow:
            account = await load_visible_account(uow, account_id, actor)
            if actor.role != Role.BACK_OFFICE:
                await ensure_account_writer(uow, actor, account)
            before = [a.as_dict() for a in account.addresses]
            account.replace_addresses(
                [
                    AdditionalAddress.create(
                        label=a.label,
                        street=a.street,
                        postal_code=a.postal_code,
                        city=a.city,
                        province_code=a.province_code,
                        notes=a.notes,
                    )
                    for a in command.addresses
                ]
            )
            await uow.accounts.save(account, expected_version=command.expected_version)
            after = [a.as_dict() for a in account.addresses]
            if before != after:
                uow.audit.record(
                    entity_type="account",
                    entity_id=account.id,
                    action="account.addresses_replaced",
                    changes={"addresses": {"before": before, "after": after}},  # type: ignore[dict-item]
                    actor_id=actor.id,
                )
            await uow.commit()
            return await self._view(uow, account)

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _ensure_can_update(actor: User, changes: dict[str, object]) -> None:
        if actor.role == Role.BACK_OFFICE and not set(changes) <= ADMINISTRATIVE_FIELDS:
            raise PermissionDeniedError("Back office can only edit administrative fields")

    @staticmethod
    async def _validate_references(
        uow: UnitOfWork, account_type_id: UUID, details: dict[str, object]
    ) -> None:
        account_types = {t.id for t in await uow.reference.account_types()}
        if account_type_id not in account_types:
            raise UnknownReferenceError("account_type_id", [str(account_type_id)])
        division_ids = _ids(details, "division_ids")
        if division_ids:
            missing = division_ids - await uow.divisions.existing_ids(division_ids)
            if missing:
                raise UnknownReferenceError("division_ids", sorted(str(m) for m in missing))
        brand_ids = _ids(details, "brand_ids")
        if brand_ids:
            known = {b.id for b in await uow.brands.list_all()}
            missing = brand_ids - known
            if missing:
                raise UnknownReferenceError("brand_ids", sorted(str(m) for m in missing))

    @staticmethod
    async def _ensure_tax_id_free(
        uow: UnitOfWork, raw_tax_id: object, account_id: UUID | None
    ) -> None:
        if raw_tax_id is None:
            return
        existing = await uow.accounts.find_id_by_tax_id(TaxId(str(raw_tax_id)).value)
        if existing is not None and existing != account_id:
            raise TaxIdAlreadyExistsError(existing)

    @staticmethod
    async def _checked_owner(uow: UnitOfWork, owner_id: UUID | None) -> UUID | None:
        if owner_id is None:
            return None
        owner = await uow.users.get(owner_id)
        if owner is None or owner.role != Role.SALES_REP or not owner.is_active:
            raise OwnerNotSalesRepError()
        return owner.id

    @staticmethod
    async def _checked_territory(uow: UnitOfWork, territory_id: UUID | None) -> UUID | None:
        if territory_id is None:
            return None
        territory = await uow.territories.get(territory_id)
        if territory is None or not territory.is_active:
            raise UnknownReferenceError("territory_id", [str(territory_id)])
        return territory.id

    @staticmethod
    async def _view(uow: UnitOfWork, account: Account) -> AccountView:
        province_territory = await uow.territories.find_by_province(account.province_code)
        territory = (
            await uow.territories.get(account.territory_id) if account.territory_id else None
        )
        owner = await uow.users.get(account.owner_id) if account.owner_id else None
        return AccountView(
            account=account,
            territory_mismatch=account.territory_mismatch(
                province_territory.id if province_territory else None
            ),
            territory_name=territory.name if territory else None,
            owner_name=owner.full_name if owner else None,
        )


def _ids(details: dict[str, object], key: str) -> frozenset[UUID]:
    raw = details.get(key)
    if raw is None:
        return frozenset()
    if not isinstance(raw, list | set | frozenset | tuple):
        raise UnknownReferenceError(key, [str(raw)])
    return frozenset(UUID(str(item)) for item in raw)
