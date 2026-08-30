"""Repository protocols for quotes (implemented in infrastructure)."""

from typing import Protocol
from uuid import UUID

from app.domain.quotes.entities import Quote
from app.domain.quotes.mail import OutboxEntry


class QuoteRepository(Protocol):
    async def allocate_number(self, year: int) -> int:
        """Atomically increments and returns the counter for the year, inside the
        current transaction so a rollback releases the number without gaps."""
        ...

    async def get(self, quote_id: UUID) -> Quote | None:
        """Aggregate with its lines."""
        ...

    async def add(self, quote: Quote) -> None: ...

    async def save(self, quote: Quote, *, expected_version: int) -> None:
        """Persists scalar fields and synchronises the lines."""
        ...

    async def delete(self, quote: Quote) -> None: ...

    async def list_current_for_opportunity(self, opportunity_id: UUID) -> list[Quote]:
        """Current versions (not superseded), newest first."""
        ...

    async def store_pdf(self, quote_id: UUID, content: bytes) -> None: ...

    async def get_pdf(self, quote_id: UUID) -> bytes | None: ...


class MailOutboxRepository(Protocol):
    async def add(self, entry: OutboxEntry) -> None: ...

    async def update_status(self, entry: OutboxEntry) -> None: ...

    async def latest_for_quote(self, quote_id: UUID) -> OutboxEntry | None: ...


class AppSettingsRepository(Protocol):
    async def get(self, key: str) -> dict[str, object] | None: ...

    async def put(self, key: str, value: dict[str, object]) -> None: ...
