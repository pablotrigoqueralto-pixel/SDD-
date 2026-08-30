"""Global search API schemas: typed groups, capped server-side."""

from collections.abc import Callable
from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.application.search.queries import (
    AccountHit,
    ContactHit,
    OpportunityHit,
    QuoteHit,
    SearchGroup,
    SearchResults,
)
from app.domain.opportunities.entities import OpportunityStatus
from app.domain.quotes.entities import QuoteStatus
from app.schemas.catalogue import Price


class AccountHitRead(BaseModel):
    id: UUID
    name: str
    city: str | None
    province_code: str
    is_active: bool


class ContactHitRead(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    full_name: str
    email: str | None
    mobile: str | None


class OpportunityHitRead(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    name: str
    stage_name: str
    status: OpportunityStatus
    amount: Price
    is_tender: bool


class QuoteHitRead(BaseModel):
    id: UUID
    opportunity_id: UUID
    account_name: str
    display_number: str
    status: QuoteStatus
    is_expired: bool
    total: Price
    valid_until: date | None


class SearchGroupRead[T](BaseModel):
    items: list[T]
    total: int
    has_more: bool


class SearchResultsRead(BaseModel):
    q: str
    accounts: SearchGroupRead[AccountHitRead]
    contacts: SearchGroupRead[ContactHitRead]
    opportunities: SearchGroupRead[OpportunityHitRead]
    quotes: SearchGroupRead[QuoteHitRead]

    @classmethod
    def build(cls, q: str, results: SearchResults) -> "SearchResultsRead":
        return cls(
            q=q,
            accounts=_group(results.accounts, _account),
            contacts=_group(results.contacts, _contact),
            opportunities=_group(results.opportunities, _opportunity),
            quotes=_group(results.quotes, _quote),
        )


def _group[S, R](source: SearchGroup[S], mapper: Callable[[S], R]) -> SearchGroupRead[R]:
    return SearchGroupRead(
        items=[mapper(item) for item in source.items],
        total=source.total,
        has_more=source.has_more,
    )


def _account(hit: AccountHit) -> AccountHitRead:
    return AccountHitRead(
        id=hit.id,
        name=hit.name,
        city=hit.city,
        province_code=hit.province_code,
        is_active=hit.is_active,
    )


def _contact(hit: ContactHit) -> ContactHitRead:
    return ContactHitRead(
        id=hit.id,
        account_id=hit.account_id,
        account_name=hit.account_name,
        full_name=hit.full_name,
        email=hit.email,
        mobile=hit.mobile,
    )


def _opportunity(hit: OpportunityHit) -> OpportunityHitRead:
    return OpportunityHitRead(
        id=hit.id,
        account_id=hit.account_id,
        account_name=hit.account_name,
        name=hit.name,
        stage_name=hit.stage_name,
        status=hit.status,
        amount=hit.amount,
        is_tender=hit.is_tender,
    )


def _quote(hit: QuoteHit) -> QuoteHitRead:
    return QuoteHitRead(
        id=hit.id,
        opportunity_id=hit.opportunity_id,
        account_name=hit.account_name,
        display_number=hit.display_number,
        status=hit.status,
        is_expired=hit.is_expired,
        total=hit.total,
        valid_until=hit.valid_until,
    )
