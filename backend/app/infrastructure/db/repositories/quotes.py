"""SQLAlchemy implementation of the quote repositories."""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.quotes.entities import Quote, QuoteConditions, QuoteLine
from app.domain.quotes.mail import MailRecipient, OutboxEntry, OutboxStatus
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.models import (
    AppSettingModel,
    MailOutboxModel,
    QuoteCounterModel,
    QuoteLineModel,
    QuoteModel,
    QuotePdfModel,
)
from app.infrastructure.db.repositories.results import rowcount_of


def conditions_to_entity(raw: dict[str, Any]) -> QuoteConditions:
    return QuoteConditions(
        validez_dias=int(raw.get("validez_dias") or 30),
        plazo_entrega=raw.get("plazo_entrega"),
        forma_pago=raw.get("forma_pago"),
        garantia=raw.get("garantia"),
    )


def line_to_entity(row: QuoteLineModel) -> QuoteLine:
    return QuoteLine(
        id=row.id,
        description=row.description,
        quantity=row.quantity,
        unit_price=row.unit_price,
        discount_percent=row.discount_percent,
        vat_rate=row.vat_rate,
        position=row.position,
        product_id=row.product_id,
        product_code=row.product_code,
        unit_cost=row.unit_cost,
    )


def quote_to_entity(row: QuoteModel) -> Quote:
    return Quote(
        id=row.id,
        opportunity_id=row.opportunity_id,
        owner_id=row.owner_id,
        created_by=row.created_by,
        year=row.year,
        number=row.number,
        version=row.version,
        status=row.status,
        conditions=conditions_to_entity(row.conditions),
        total_base=row.total_base,
        total_vat=row.total_vat,
        total=row.total,
        contact_id=row.contact_id,
        valid_until=row.valid_until,
        sent_at=row.sent_at,
        accepted_at=row.accepted_at,
        rejected_at=row.rejected_at,
        rejection_note=row.rejection_note,
        superseded_at=row.superseded_at,
        lines=[line_to_entity(line) for line in row.lines],
        version_lock=row.version_lock,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _scalar_values(quote: Quote) -> dict[str, object]:
    return {
        "owner_id": quote.owner_id,
        "contact_id": quote.contact_id,
        "status": quote.status,
        "conditions": quote.conditions.as_dict(),
        "total_base": quote.total_base,
        "total_vat": quote.total_vat,
        "total": quote.total,
        "valid_until": quote.valid_until,
        "sent_at": quote.sent_at,
        "accepted_at": quote.accepted_at,
        "rejected_at": quote.rejected_at,
        "rejection_note": quote.rejection_note,
        "superseded_at": quote.superseded_at,
    }


def _line_values(line: QuoteLine) -> dict[str, object]:
    return {
        "product_id": line.product_id,
        "description": line.description,
        "product_code": line.product_code,
        "quantity": line.quantity,
        "unit_price": line.unit_price,
        "discount_percent": line.discount_percent,
        "vat_rate": line.vat_rate,
        "unit_cost": line.unit_cost,
        "position": line.position,
    }


class SqlAlchemyQuoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allocate_number(self, year: int) -> int:
        statement = (
            pg_insert(QuoteCounterModel)
            .values(year=year, last_number=1)
            .on_conflict_do_update(
                index_elements=[QuoteCounterModel.year],
                set_={"last_number": QuoteCounterModel.last_number + 1},
            )
            .returning(QuoteCounterModel.last_number)
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def get(self, quote_id: UUID) -> Quote | None:
        statement = (
            select(QuoteModel)
            .options(selectinload(QuoteModel.lines))
            .where(QuoteModel.id == quote_id)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return quote_to_entity(row) if row else None

    async def add(self, quote: Quote) -> None:
        self._session.add(
            QuoteModel(
                id=quote.id,
                opportunity_id=quote.opportunity_id,
                created_by=quote.created_by,
                year=quote.year,
                number=quote.number,
                version=quote.version,
                version_lock=quote.version_lock,
                **_scalar_values(quote),
            )
        )
        for line in quote.lines:
            self._session.add(QuoteLineModel(id=line.id, quote_id=quote.id, **_line_values(line)))
        await self._session.flush()

    async def save(self, quote: Quote, *, expected_version: int) -> None:
        statement = (
            update(QuoteModel)
            .where(QuoteModel.id == quote.id, QuoteModel.version_lock == expected_version)
            .values(version_lock=expected_version + 1, **_scalar_values(quote))
        )
        result = await self._session.execute(statement)
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        await self._sync_lines(quote)
        quote.version_lock = expected_version + 1

    async def delete(self, quote: Quote) -> None:
        await self._session.execute(delete(QuoteModel).where(QuoteModel.id == quote.id))
        await self._session.flush()

    async def list_current_for_opportunity(self, opportunity_id: UUID) -> list[Quote]:
        statement = (
            select(QuoteModel)
            .options(selectinload(QuoteModel.lines))
            .where(
                QuoteModel.opportunity_id == opportunity_id,
                QuoteModel.superseded_at.is_(None),
            )
            .order_by(QuoteModel.created_at.desc())
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [quote_to_entity(row) for row in rows]

    async def store_pdf(self, quote_id: UUID, content: bytes) -> None:
        statement = (
            pg_insert(QuotePdfModel)
            .values(quote_id=quote_id, content=content)
            .on_conflict_do_update(
                index_elements=[QuotePdfModel.quote_id], set_={"content": content}
            )
        )
        await self._session.execute(statement)

    async def get_pdf(self, quote_id: UUID) -> bytes | None:
        statement = select(QuotePdfModel.content).where(QuotePdfModel.quote_id == quote_id)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return bytes(row) if row is not None else None

    async def _sync_lines(self, quote: Quote) -> None:
        kept = {line.id for line in quote.lines}
        removal = delete(QuoteLineModel).where(QuoteLineModel.quote_id == quote.id)
        if kept:
            removal = removal.where(QuoteLineModel.id.not_in(kept))
        await self._session.execute(removal)
        existing = set(
            (
                await self._session.execute(
                    select(QuoteLineModel.id).where(QuoteLineModel.quote_id == quote.id)
                )
            )
            .scalars()
            .all()
        )
        for line in quote.lines:
            if line.id in existing:
                await self._session.execute(
                    update(QuoteLineModel)
                    .where(QuoteLineModel.id == line.id)
                    .values(**_line_values(line))
                )
            else:
                self._session.add(
                    QuoteLineModel(id=line.id, quote_id=quote.id, **_line_values(line))
                )
        await self._session.flush()


class SqlAlchemyMailOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: OutboxEntry) -> None:
        self._session.add(
            MailOutboxModel(
                id=entry.id,
                quote_id=entry.quote_id,
                recipients=[
                    {"email": recipient.email, "name": recipient.name}
                    for recipient in entry.recipients
                ],
                subject=entry.subject,
                body=entry.body,
                status=entry.status.value,
                error=entry.error,
                sent_at=entry.sent_at,
            )
        )
        await self._session.flush()

    async def update_status(self, entry: OutboxEntry) -> None:
        await self._session.execute(
            update(MailOutboxModel)
            .where(MailOutboxModel.id == entry.id)
            .values(status=entry.status.value, error=entry.error, sent_at=entry.sent_at)
        )

    async def latest_for_quote(self, quote_id: UUID) -> OutboxEntry | None:
        statement = (
            select(MailOutboxModel)
            .where(MailOutboxModel.quote_id == quote_id)
            .order_by(MailOutboxModel.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        if row is None:
            return None
        return OutboxEntry(
            id=row.id,
            quote_id=row.quote_id,
            recipients=[
                MailRecipient(email=str(item["email"]), name=item.get("name"))
                for item in row.recipients
            ],
            subject=row.subject,
            body=row.body,
            status=OutboxStatus(row.status),
            error=row.error,
            sent_at=row.sent_at,
            created_at=row.created_at,
        )


class SqlAlchemyAppSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> dict[str, object] | None:
        statement = select(AppSettingModel.value).where(AppSettingModel.key == key)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return dict(row) if row is not None else None

    async def put(self, key: str, value: dict[str, object]) -> None:
        statement = (
            pg_insert(AppSettingModel)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=[AppSettingModel.key], set_={"value": value})
        )
        await self._session.execute(statement)
