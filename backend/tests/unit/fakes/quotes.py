from copy import deepcopy
from uuid import UUID

from app.domain.quotes.entities import Quote
from app.domain.quotes.mail import MailRecipient, OutboxEntry
from app.domain.shared.errors import ConcurrentModificationError


class InMemoryQuoteRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Quote] = {}
        self.counters: dict[int, int] = {}
        self.pdfs: dict[UUID, bytes] = {}

    async def allocate_number(self, year: int) -> int:
        self.counters[year] = self.counters.get(year, 0) + 1
        return self.counters[year]

    async def get(self, quote_id: UUID) -> Quote | None:
        row = self.rows.get(quote_id)
        return deepcopy(row) if row else None

    async def add(self, quote: Quote) -> None:
        self.rows[quote.id] = deepcopy(quote)

    async def save(self, quote: Quote, *, expected_version: int) -> None:
        current = self.rows.get(quote.id)
        if current is None or current.version_lock != expected_version:
            raise ConcurrentModificationError()
        quote.version_lock = expected_version + 1
        self.rows[quote.id] = deepcopy(quote)

    async def delete(self, quote: Quote) -> None:
        self.rows.pop(quote.id, None)
        self.pdfs.pop(quote.id, None)

    async def list_current_for_opportunity(self, opportunity_id: UUID) -> list[Quote]:
        rows = [
            deepcopy(row)
            for row in self.rows.values()
            if row.opportunity_id == opportunity_id and row.superseded_at is None
        ]
        return sorted(rows, key=lambda quote: (quote.number, quote.version), reverse=True)

    async def store_pdf(self, quote_id: UUID, content: bytes) -> None:
        self.pdfs[quote_id] = content

    async def get_pdf(self, quote_id: UUID) -> bytes | None:
        return self.pdfs.get(quote_id)


class InMemoryMailOutboxRepository:
    def __init__(self) -> None:
        self.rows: list[OutboxEntry] = []

    async def add(self, entry: OutboxEntry) -> None:
        self.rows.append(deepcopy(entry))

    async def update_status(self, entry: OutboxEntry) -> None:
        for index, row in enumerate(self.rows):
            if row.id == entry.id:
                self.rows[index] = deepcopy(entry)
                return

    async def latest_for_quote(self, quote_id: UUID) -> OutboxEntry | None:
        rows = [row for row in self.rows if row.quote_id == quote_id]
        return deepcopy(rows[-1]) if rows else None


class InMemoryAppSettingsRepository:
    def __init__(self, values: dict[str, dict[str, object]] | None = None) -> None:
        self.rows: dict[str, dict[str, object]] = values or {}

    async def get(self, key: str) -> dict[str, object] | None:
        row = self.rows.get(key)
        return deepcopy(row) if row is not None else None

    async def put(self, key: str, value: dict[str, object]) -> None:
        self.rows[key] = deepcopy(value)


class FakeDeliveryError(Exception):
    pass


class FakeMailer:
    """Records sends; flip `fail` to simulate a Graph outage."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.fail = False
        self.sent: list[dict[str, object]] = []

    async def send(
        self,
        *,
        sender_email: str,
        recipients: list[MailRecipient],
        subject: str,
        body: str,
        attachment_name: str,
        attachment: bytes,
    ) -> None:
        if self.fail:
            raise FakeDeliveryError("Graph returned 500")
        self.sent.append(
            {
                "sender_email": sender_email,
                "recipients": recipients,
                "subject": subject,
                "attachment_name": attachment_name,
                "attachment": attachment,
            }
        )


class FakePdfRenderer:
    def __init__(self) -> None:
        self.rendered: list[str] = []

    def render(self, document: object) -> bytes:
        display_number = getattr(document, "display_number", "?")
        self.rendered.append(str(display_number))
        return f"%PDF fake {display_number}".encode()
