"""SQLAlchemy implementations of ContactRepository and PersonalDataAccessLog."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.entities import ConsentRecord, Contact
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import ContactModel, PersonalDataAccessLogModel
from app.infrastructure.db.repositories.results import rowcount_of


def contact_to_entity(row: ContactModel) -> Contact:
    return Contact(
        id=row.id,
        account_id=row.account_id,
        first_name=row.first_name,
        last_name=row.last_name,
        job_title_id=row.job_title_id,
        division_id=row.division_id,
        email=row.email,
        mobile=row.mobile,
        landline=row.landline,
        preferred_channel=row.preferred_channel,
        notes=row.notes,
        is_primary=row.is_primary,
        is_active=row.is_active,
        consent=ConsentRecord(
            status=row.consent_status,
            at=row.consent_at,
            source=row.consent_source,
            recorded_by=row.consent_recorded_by,
        ),
        anonymised_at=row.anonymised_at,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _contact_values(contact: Contact) -> dict[str, object]:
    return {
        "account_id": contact.account_id,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "job_title_id": contact.job_title_id,
        "division_id": contact.division_id,
        "email": contact.email,
        "mobile": contact.mobile,
        "landline": contact.landline,
        "preferred_channel": contact.preferred_channel,
        "notes": contact.notes,
        "is_primary": contact.is_primary,
        "is_active": contact.is_active,
        "consent_status": contact.consent.status,
        "consent_at": contact.consent.at,
        "consent_source": contact.consent.source,
        "consent_recorded_by": contact.consent.recorded_by,
        "anonymised_at": contact.anonymised_at,
    }


class SqlAlchemyContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, contact_id: UUID) -> Contact | None:
        row = await self._session.get(ContactModel, contact_id)
        return contact_to_entity(row) if row else None

    async def list_by_account(
        self, account_id: UUID, *, include_inactive: bool = False
    ) -> list[Contact]:
        statement = select(ContactModel).where(ContactModel.account_id == account_id)
        if not include_inactive:
            statement = statement.where(ContactModel.is_active.is_(True))
        statement = statement.order_by(
            ContactModel.is_primary.desc(), ContactModel.last_name, ContactModel.first_name
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [contact_to_entity(row) for row in rows]

    async def find_primary(self, account_id: UUID) -> Contact | None:
        statement = select(ContactModel).where(
            ContactModel.account_id == account_id, ContactModel.is_primary.is_(True)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return contact_to_entity(row) if row else None

    async def add(self, contact: Contact) -> None:
        self._session.add(ContactModel(id=contact.id, **_contact_values(contact)))
        await self._session.flush()

    async def save(self, contact: Contact, *, expected_version: int) -> None:
        result = await self._session.execute(
            update(ContactModel)
            .where(ContactModel.id == contact.id, ContactModel.version == expected_version)
            .values(**_contact_values(contact), version=expected_version + 1)
        )
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        contact.version = expected_version + 1


class SqlAlchemyPersonalDataAccessLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self, *, user_id: UUID, contact_ids: Sequence[UUID], trace_id: str | None
    ) -> None:
        if not contact_ids:
            return
        await self._session.execute(
            insert(PersonalDataAccessLogModel),
            [
                {"user_id": user_id, "contact_id": contact_id, "trace_id": trace_id}
                for contact_id in contact_ids
            ],
        )
