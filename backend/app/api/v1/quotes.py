"""Quotes: drafts from opportunities, send with PDF + mail, accept/reject/revise."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import Select, select

from app.api.deps import CurrentUser, ExpectedVersion, SessionDep, UowDep
from app.application.activities.queries import BUSINESS_TIMEZONE
from app.application.quotes.commands import (
    AcceptQuote,
    CreateQuote,
    QuoteLineInput,
    RejectQuote,
    SendQuote,
    UpdateQuoteDraft,
)
from app.application.quotes.mailer import QuoteMailer
from app.application.quotes.pdf import QuotePdfRenderer
from app.application.quotes.queries import (
    QUOTE_DEFAULT_SORT,
    QUOTE_MAX_PAGE_SIZE,
    QUOTE_SORT_FIELDS,
    QuoteFilters,
    QuoteQueries,
    quote_status_filter,
)
from app.application.quotes.service import (
    QuoteService,
    QuoteSettingsService,
    build_pdf_document,
)
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.application.shared.scope import user_scope_filter
from app.domain.quotes.entities import Quote
from app.domain.quotes.mail import MailRecipient
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.repositories.scope import scoped_accounts
from app.schemas.quotes import (
    QuoteAccept,
    QuoteCreate,
    QuotePublicRead,
    QuoteRead,
    QuoteReject,
    QuoteSend,
    QuoteSettingsRead,
    QuoteSettingsUpdate,
    QuoteSummaryRead,
    QuoteUpdate,
)

router = APIRouter(prefix="/quotes", tags=["quotes"])
opportunity_quotes_router = APIRouter(prefix="/opportunities", tags=["quotes"])
settings_router = APIRouter(prefix="/quote-settings", tags=["quotes"])

COST_ROLES = frozenset({Role.ADMIN, Role.SALES_MANAGER})

QuotePage = Annotated[
    PageParams, Depends(page_params_dependency(QUOTE_SORT_FIELDS, QUOTE_DEFAULT_SORT))
]


def get_pdf_renderer(request: Request) -> QuotePdfRenderer:
    renderer: QuotePdfRenderer = request.app.state.quote_pdf_renderer
    return renderer


def get_quote_service(request: Request, uow: UowDep) -> QuoteService:
    mailer: QuoteMailer = request.app.state.quote_mailer
    return QuoteService(uow, mailer=mailer, pdf_renderer=get_pdf_renderer(request))


QuoteServiceDep = Annotated[QuoteService, Depends(get_quote_service)]


def get_settings_service(uow: UowDep) -> QuoteSettingsService:
    return QuoteSettingsService(uow)


SettingsServiceDep = Annotated[QuoteSettingsService, Depends(get_settings_service)]


async def _account_ids(uow: UowDep, user: User) -> Select[tuple[UUID]] | None:
    scope = await user_scope_filter(uow, user)
    return None if scope is None else scoped_accounts(select(AccountModel.id), scope)


async def _read(
    uow: UowDep, session: SessionDep, user: User, quote: Quote
) -> QuoteRead | QuotePublicRead:
    opportunity = await uow.opportunities.get(quote.opportunity_id)
    account = await uow.accounts.get(opportunity.account_id) if opportunity else None
    owner = await uow.users.get(quote.owner_id)
    queries = QuoteQueries(session)
    email = await queries.latest_email_status(quote.id)
    context: dict[str, object] = {
        "account_id": account.id if account else quote.opportunity_id,
        "account_name": account.name if account else "",
        "opportunity_name": opportunity.name if opportunity else "",
        "owner_name": owner.full_name if owner else "",
        "today": datetime.now(UTC).astimezone(BUSINESS_TIMEZONE).date(),
        "versions": await queries.version_chain(quote.year, quote.number),
        "email_status": email[0] if email else None,
        "email_error": email[1] if email else None,
    }
    if user.role in COST_ROLES:
        return QuoteRead.build(quote, **context)
    return QuotePublicRead.build(quote, **context)


def _line_inputs(payload: QuoteUpdate) -> list[QuoteLineInput] | None:
    if payload.lines is None:
        return None
    return [
        QuoteLineInput(
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            discount_percent=line.discount_percent,
            vat_rate=line.vat_rate,
            product_id=line.product_id,
        )
        for line in payload.lines
    ]


@router.get("", response_model=Page[QuoteSummaryRead], summary="List quotes (current versions)")
async def list_quotes(
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    params: QuotePage,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    owner_id: Annotated[UUID | None, Query()] = None,
    opportunity_id: Annotated[UUID | None, Query()] = None,
    account_id: Annotated[UUID | None, Query()] = None,
    expiring: Annotated[bool, Query()] = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[QuoteSummaryRead]:
    page_size = min(params.page_size, QUOTE_MAX_PAGE_SIZE)
    bounded = PageParams(page=params.page, page_size=page_size, sort=params.sort)
    result = await QuoteQueries(session).list_page(
        bounded,
        QuoteFilters(
            status=quote_status_filter(status_value),
            owner_id=owner_id,
            opportunity_id=opportunity_id,
            account_id=account_id,
            expiring=expiring,
            q=q,
        ),
        await _account_ids(uow, user),
    )
    return Page[QuoteSummaryRead](
        items=[QuoteSummaryRead.from_summary(item) for item in result.items],
        total=result.total,
        page=bounded.page,
        page_size=bounded.page_size,
    )


@opportunity_quotes_router.get(
    "/{opportunity_id}/quotes",
    response_model=list[QuoteSummaryRead],
    summary="Current quote versions of one opportunity",
)
async def list_opportunity_quotes(
    opportunity_id: UUID,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> list[QuoteSummaryRead]:
    # Visibility check piggybacks on the opportunity loader (404 out of scope).
    await service.ensure_opportunity_visible(opportunity_id, actor=user)
    items = await QuoteQueries(session).for_opportunity(opportunity_id)
    return [QuoteSummaryRead.from_summary(item) for item in items]


@router.get("/{quote_id}", response_model=QuoteRead | QuotePublicRead, summary="Quote detail")
async def read_quote(
    quote_id: UUID,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    quote, _, _ = await service.get(quote_id, actor=user)
    return await _read(uow, session, user, quote)


@router.get("/{quote_id}/pdf", summary="Quote PDF (stored when sent, preview for drafts)")
async def read_quote_pdf(
    quote_id: UUID,
    user: CurrentUser,
    uow: UowDep,
    request: Request,
    service: QuoteServiceDep,
) -> Response:
    quote, _, account = await service.get(quote_id, actor=user)
    content = await uow.quotes.get_pdf(quote.id)
    if content is None:
        document = await build_pdf_document(uow, quote, account)
        content = get_pdf_renderer(request).render(document)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{quote.display_number}.pdf"'},
    )


@router.post(
    "",
    response_model=QuoteRead | QuotePublicRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft from an opportunity (copies its lines)",
)
async def create_quote(
    payload: QuoteCreate,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    quote = await service.create(
        CreateQuote(opportunity_id=payload.opportunity_id, contact_id=payload.contact_id),
        actor=user,
    )
    return await _read(uow, session, user, quote)


@router.patch("/{quote_id}", response_model=QuoteRead | QuotePublicRead, summary="Update a draft")
async def update_quote(
    quote_id: UUID,
    payload: QuoteUpdate,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    provided = payload.model_fields_set
    quote = await service.update_draft(
        quote_id,
        UpdateQuoteDraft(
            expected_version=expected_version,
            contact_id=payload.contact_id if "contact_id" in provided else ...,
            conditions=payload.conditions.to_entity() if payload.conditions else None,
            valid_until=payload.valid_until if "valid_until" in provided else ...,
            lines=_line_inputs(payload),
        ),
        actor=user,
    )
    return await _read(uow, session, user, quote)


@router.delete("/{quote_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a draft")
async def delete_quote(quote_id: UUID, user: CurrentUser, service: QuoteServiceDep) -> None:
    await service.delete_draft(quote_id, actor=user)


@router.post(
    "/{quote_id}/send",
    response_model=QuoteRead | QuotePublicRead,
    summary="Freeze the version, store the PDF and email it",
)
async def send_quote(
    quote_id: UUID,
    payload: QuoteSend,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    quote = await service.send(
        quote_id,
        SendQuote(
            expected_version=expected_version,
            recipients=[
                MailRecipient(email=recipient.email, name=recipient.name)
                for recipient in payload.recipients
            ],
            subject=payload.subject,
            body=payload.body,
            valid_until=payload.valid_until,
            skip_email=payload.skip_email,
        ),
        actor=user,
    )
    return await _read(uow, session, user, quote)


@router.post(
    "/{quote_id}/accept",
    response_model=QuoteRead | QuotePublicRead,
    summary="Accept: wins the opportunity and rejects sibling quotes",
)
async def accept_quote(
    quote_id: UUID,
    payload: QuoteAccept,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    quote = await service.accept(
        quote_id,
        AcceptQuote(expected_version=expected_version, occurred_on=payload.occurred_on),
        actor=user,
    )
    return await _read(uow, session, user, quote)


@router.post(
    "/{quote_id}/reject",
    response_model=QuoteRead | QuotePublicRead,
    summary="Reject with an optional note",
)
async def reject_quote(
    quote_id: UUID,
    payload: QuoteReject,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    quote = await service.reject(
        quote_id,
        RejectQuote(expected_version=expected_version, note=payload.note),
        actor=user,
    )
    return await _read(uow, session, user, quote)


@router.post(
    "/{quote_id}/revise",
    response_model=QuoteRead | QuotePublicRead,
    status_code=status.HTTP_201_CREATED,
    summary="New draft version copying the current content",
)
async def revise_quote(
    quote_id: UUID,
    user: CurrentUser,
    expected_version: ExpectedVersion,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    revision = await service.revise(quote_id, expected_version=expected_version, actor=user)
    return await _read(uow, session, user, revision)


@router.post(
    "/{quote_id}/retry-email",
    response_model=QuoteRead | QuotePublicRead,
    summary="Re-send the stored PDF after a failed delivery",
)
async def retry_email(
    quote_id: UUID,
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    service: QuoteServiceDep,
) -> QuoteRead | QuotePublicRead:
    quote = await service.retry_email(quote_id, actor=user)
    return await _read(uow, session, user, quote)


@settings_router.get(
    "", response_model=QuoteSettingsRead, summary="Quote defaults and email template (admin)"
)
async def read_quote_settings(user: CurrentUser, service: SettingsServiceDep) -> QuoteSettingsRead:
    settings = await service.get(actor=user)
    return QuoteSettingsRead(
        conditions_defaults=settings.conditions_defaults, email_template=settings.email_template
    )


@settings_router.put(
    "", response_model=QuoteSettingsRead, summary="Replace quote defaults and template (admin)"
)
async def update_quote_settings(
    payload: QuoteSettingsUpdate, user: CurrentUser, service: SettingsServiceDep
) -> QuoteSettingsRead:
    settings = await service.update(
        conditions_defaults=payload.conditions_defaults.model_dump(),
        email_template=payload.email_template.model_dump(),
        actor=user,
    )
    return QuoteSettingsRead(
        conditions_defaults=settings.conditions_defaults, email_template=settings.email_template
    )
