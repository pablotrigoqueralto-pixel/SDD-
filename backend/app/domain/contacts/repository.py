"""Repository protocols for contacts and the personal data access log."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.domain.contacts.entities import Contact


class ContactRepository(Protocol):
    async def get(self, contact_id: UUID) -> Contact | None: ...

    async def list_by_account(
        self, account_id: UUID, *, include_inactive: bool = False
    ) -> list[Contact]: ...

    async def find_primary(self, account_id: UUID) -> Contact | None: ...

    async def add(self, contact: Contact) -> None: ...

    async def save(self, contact: Contact, *, expected_version: int) -> None: ...


class PersonalDataAccessLog(Protocol):
    async def record(
        self, *, user_id: UUID, contact_ids: Sequence[UUID], trace_id: str | None
    ) -> None: ...
