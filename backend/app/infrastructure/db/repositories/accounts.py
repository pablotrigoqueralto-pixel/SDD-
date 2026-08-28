"""SQLAlchemy implementation of AccountRepository."""

import re
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.accounts.entities import Account, AdditionalAddress
from app.domain.accounts.errors import AddressLabelDuplicatedError, TaxIdAlreadyExistsError
from app.domain.activities.entities import ActivityStatus
from app.domain.shared.errors import ConcurrentModificationError
from app.domain.shared.policies import ScopeFilter
from app.infrastructure.db.models import (
    AccountAddressModel,
    AccountBrandModel,
    AccountDivisionModel,
    AccountModel,
    ActivityModel,
    ActivityTypeModel,
)
from app.infrastructure.db.repositories.results import rowcount_of
from app.infrastructure.db.repositories.scope import scoped_accounts

TAX_ID_UNIQUE_INDEX = "ux_accounts_tax_id"
ADDRESS_LABEL_UNIQUE = "uq_account_addresses_label"
LABEL_KEY_PATTERN = re.compile(r"\(account_id, label\)=\([^,]+, (.+)\)")

_ACCOUNT_LOAD = (
    selectinload(AccountModel.addresses),
    selectinload(AccountModel.division_links),
    selectinload(AccountModel.brand_links),
)


def account_to_entity(row: AccountModel) -> Account:
    return Account(
        id=row.id,
        name=row.name,
        account_type_id=row.account_type_id,
        province_code=row.province_code,
        street=row.street,
        postal_code=row.postal_code,
        city=row.city,
        tax_id=row.tax_id,
        phone=row.phone,
        email=row.email,
        website=row.website,
        customer_code=row.customer_code,
        notes=row.notes,
        territory_id=row.territory_id,
        owner_id=row.owner_id,
        division_ids=frozenset(link.division_id for link in row.division_links),
        brand_ids=frozenset(link.brand_id for link in row.brand_links),
        addresses=[
            AdditionalAddress(
                label=a.label,
                street=a.street,
                postal_code=a.postal_code,
                city=a.city,
                province_code=a.province_code,
                notes=a.notes,
            )
            for a in row.addresses
        ],
        last_contact_at=row.last_contact_at,
        next_activity_at=row.next_activity_at,
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _account_values(account: Account) -> dict[str, object]:
    return {
        "name": account.name,
        "account_type_id": account.account_type_id,
        "province_code": account.province_code,
        "street": account.street,
        "postal_code": account.postal_code,
        "city": account.city,
        "tax_id": account.tax_id,
        "phone": account.phone,
        "email": account.email,
        "website": account.website,
        "customer_code": account.customer_code,
        "notes": account.notes,
        "territory_id": account.territory_id,
        "owner_id": account.owner_id,
        "is_active": account.is_active,
    }


class SqlAlchemyAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, account_id: UUID, *, scope: ScopeFilter | None = None) -> Account | None:
        statement = scoped_accounts(
            select(AccountModel).options(*_ACCOUNT_LOAD).where(AccountModel.id == account_id),
            scope,
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return account_to_entity(row) if row else None

    async def find_id_by_tax_id(self, tax_id: str) -> UUID | None:
        statement = select(AccountModel.id).where(AccountModel.tax_id == tax_id)
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def add(self, account: Account) -> None:
        row = AccountModel(id=account.id, **_account_values(account))
        row.addresses = [_address_row(account.id, a) for a in account.addresses]
        row.division_links = [
            AccountDivisionModel(account_id=account.id, division_id=d) for d in account.division_ids
        ]
        row.brand_links = [
            AccountBrandModel(account_id=account.id, brand_id=b) for b in account.brand_ids
        ]
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._raise_domain_error(exc, account)

    async def save(self, account: Account, *, expected_version: int) -> None:
        statement = (
            update(AccountModel)
            .where(AccountModel.id == account.id, AccountModel.version == expected_version)
            .values(**_account_values(account), version=expected_version + 1)
        )
        try:
            result = await self._session.execute(statement)
            if rowcount_of(result) != 1:
                raise ConcurrentModificationError()
            await self._sync_children(account)
        except IntegrityError as exc:
            await self._raise_domain_error(exc, account)
        account.version = expected_version + 1

    async def refresh_activity_summary(self, account_id: UUID) -> None:
        """Recomputed from scratch (never incremented) so the columns can never drift."""
        last_contact = (
            select(func.max(ActivityModel.scheduled_at))
            .join(ActivityTypeModel, ActivityTypeModel.id == ActivityModel.activity_type_id)
            .where(
                ActivityModel.account_id == account_id,
                ActivityModel.status == ActivityStatus.DONE,
                ActivityTypeModel.counts_as_contact.is_(True),
            )
            .scalar_subquery()
        )
        next_activity = (
            select(func.min(ActivityModel.scheduled_at))
            .where(
                ActivityModel.account_id == account_id,
                ActivityModel.status == ActivityStatus.PLANNED,
            )
            .scalar_subquery()
        )
        await self._session.execute(
            update(AccountModel)
            .where(AccountModel.id == account_id)
            .values(last_contact_at=last_contact, next_activity_at=next_activity)
        )

    async def _sync_children(self, account: Account) -> None:
        await self._session.execute(
            delete(AccountAddressModel).where(AccountAddressModel.account_id == account.id)
        )
        await self._session.execute(
            delete(AccountDivisionModel).where(AccountDivisionModel.account_id == account.id)
        )
        await self._session.execute(
            delete(AccountBrandModel).where(AccountBrandModel.account_id == account.id)
        )
        if account.addresses:
            self._session.add_all([_address_row(account.id, a) for a in account.addresses])
            await self._session.flush()
        if account.division_ids:
            await self._session.execute(
                insert(AccountDivisionModel),
                [{"account_id": account.id, "division_id": d} for d in account.division_ids],
            )
        if account.brand_ids:
            await self._session.execute(
                insert(AccountBrandModel),
                [{"account_id": account.id, "brand_id": b} for b in account.brand_ids],
            )

    async def _raise_domain_error(self, exc: IntegrityError, account: Account) -> None:
        message = str(exc.orig)
        if TAX_ID_UNIQUE_INDEX in message and account.tax_id is not None:
            # The flush failed inside a savepoint-less session state; a fresh SELECT still
            # works on PostgreSQL only after rollback, so the conflicting id is resolved by
            # the application service through `find_id_by_tax_id` before adding.
            raise TaxIdAlreadyExistsError() from exc
        if ADDRESS_LABEL_UNIQUE in message:
            match = LABEL_KEY_PATTERN.search(message)
            raise AddressLabelDuplicatedError(match.group(1) if match else "?") from exc
        raise exc


def _address_row(account_id: UUID, address: AdditionalAddress) -> AccountAddressModel:
    return AccountAddressModel(
        account_id=account_id,
        label=address.label,
        street=address.street,
        postal_code=address.postal_code,
        city=address.city,
        province_code=address.province_code,
        notes=address.notes,
    )
