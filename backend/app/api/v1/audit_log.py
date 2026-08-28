"""Audit log read endpoint (admin only)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminUser, SessionDep
from app.application.audit.queries import (
    AUDIT_DEFAULT_SORT,
    AUDIT_SORT_FIELDS,
    AuditFilters,
    AuditQueries,
    PersonalDataAccessFilters,
    PersonalDataAccessQueries,
)
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.schemas.audit import AuditLogEntryRead, PersonalDataAccessRead

router = APIRouter(prefix="/audit-log", tags=["audit"])

AuditPage = Annotated[
    PageParams, Depends(page_params_dependency(AUDIT_SORT_FIELDS, AUDIT_DEFAULT_SORT))
]


@router.get("", response_model=Page[AuditLogEntryRead], summary="Read the audit log")
async def list_audit_log(
    _: AdminUser,
    session: SessionDep,
    params: AuditPage,
    entity_type: Annotated[str | None, Query(max_length=50)] = None,
    entity_id: Annotated[UUID | None, Query()] = None,
    actor_id: Annotated[UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    occurred_from: Annotated[datetime | None, Query(alias="from")] = None,
    occurred_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> Page[AuditLogEntryRead]:
    result = await AuditQueries(session).list_page(
        params,
        AuditFilters(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            action=action,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        ),
    )
    return Page[AuditLogEntryRead](
        items=[AuditLogEntryRead.model_validate(entry) for entry in result.items],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/personal-data-access",
    response_model=Page[PersonalDataAccessRead],
    summary="Who read which contact's personal data (GDPR access log)",
)
async def list_personal_data_access(
    _: AdminUser,
    session: SessionDep,
    params: AuditPage,
    contact_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Query()] = None,
    occurred_from: Annotated[datetime | None, Query(alias="from")] = None,
    occurred_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> Page[PersonalDataAccessRead]:
    result = await PersonalDataAccessQueries(session).list_page(
        params,
        PersonalDataAccessFilters(
            contact_id=contact_id,
            user_id=user_id,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        ),
    )
    return Page[PersonalDataAccessRead](
        items=[PersonalDataAccessRead.model_validate(entry) for entry in result.items],
        total=result.total,
        page=params.page,
        page_size=params.page_size,
    )
