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
)
from app.application.shared.pagination import Page, PageParams, page_params_dependency
from app.schemas.audit import AuditLogEntryRead

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
