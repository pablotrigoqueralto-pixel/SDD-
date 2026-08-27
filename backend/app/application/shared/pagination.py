"""Pagination and sorting primitives shared by every list endpoint."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

from app.domain.shared.errors import InvalidSortFieldError

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class SortField:
    name: str
    descending: bool


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int
    sort: list[SortField]

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


def parse_sort(raw: str | None, *, allowed: set[str], default: str) -> list[SortField]:
    if not raw:
        return [_to_sort_field(default)]
    fields: list[SortField] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        field = _to_sort_field(token)
        if field.name not in allowed:
            raise InvalidSortFieldError(field.name, allowed)
        fields.append(field)
    return fields or [_to_sort_field(default)]


def _to_sort_field(token: str) -> SortField:
    if token.startswith("-"):
        return SortField(token[1:], True)
    return SortField(token, False)


def page_params_dependency(allowed_sort: set[str], default_sort: str) -> Callable[..., PageParams]:
    """Build a FastAPI dependency bound to the sort fields an endpoint declares."""

    def dependency(
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
        sort: Annotated[str | None, Query()] = None,
    ) -> PageParams:
        return PageParams(
            page=page,
            page_size=page_size,
            sort=parse_sort(sort, allowed=allowed_sort, default=default_sort),
        )

    return dependency
