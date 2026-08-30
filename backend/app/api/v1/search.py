"""Global search: one scoped request, grouped results across four entities."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import Select, select

from app.api.deps import CurrentUser, SessionDep, UowDep
from app.application.search.queries import SearchQueries, empty_results
from app.application.search.router import parse_query
from app.application.shared.scope import user_scope_filter
from app.domain.users.entities import User
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.repositories.scope import scoped_accounts
from app.schemas.search import SearchResultsRead

router = APIRouter(prefix="/search", tags=["search"])


async def _account_ids(uow: UowDep, user: User) -> Select[tuple[UUID]] | None:
    scope = await user_scope_filter(uow, user)
    return None if scope is None else scoped_accounts(select(AccountModel.id), scope)


@router.get(
    "",
    response_model=SearchResultsRead,
    summary="Global search: accounts, contacts, opportunities and quotes (scoped)",
)
async def search(
    user: CurrentUser,
    uow: UowDep,
    session: SessionDep,
    q: Annotated[str, Query(max_length=100)] = "",
) -> SearchResultsRead:
    parsed = parse_query(q)
    if parsed is None:
        return SearchResultsRead.build(q, empty_results())
    results = await SearchQueries(session).search(parsed, await _account_ids(uow, user))
    return SearchResultsRead.build(q, results)
