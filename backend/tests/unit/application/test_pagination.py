from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.application.shared.pagination import (
    Page,
    PageParams,
    SortField,
    page_params_dependency,
    parse_sort,
)
from app.domain.shared.errors import InvalidSortFieldError


def test_parse_sort_returns_default_when_empty() -> None:
    assert parse_sort(None, allowed={"name"}, default="name") == [SortField("name", False)]


def test_parse_sort_handles_descending_and_multiple_fields() -> None:
    result = parse_sort("-updated_at,name", allowed={"updated_at", "name"}, default="name")

    assert result == [SortField("updated_at", True), SortField("name", False)]


def test_parse_sort_rejects_unknown_field() -> None:
    with pytest.raises(InvalidSortFieldError) as exc_info:
        parse_sort("foo", allowed={"name"}, default="name")

    assert exc_info.value.code == "invalid_sort_field"
    assert exc_info.value.status == 422


def test_page_offset_and_limit() -> None:
    params = PageParams(page=3, page_size=20, sort=[SortField("name", False)])

    assert params.offset == 40
    assert params.limit == 20


def test_page_envelope_serialises_expected_shape() -> None:
    page = Page[int](items=[1, 2], total=10, page=1, page_size=2)

    assert page.model_dump() == {"items": [1, 2], "total": 10, "page": 1, "page_size": 2}


async def test_dependency_applies_defaults(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/paged")
    async def paged(
        params: Annotated[PageParams, Depends(page_params_dependency({"name", "email"}, "name"))],
    ) -> dict[str, object]:
        return {"page": params.page, "page_size": params.page_size, "sort": params.sort}

    response = await client.get("/paged")

    assert response.json() == {
        "page": 1,
        "page_size": 50,
        "sort": [{"name": "name", "descending": False}],
    }


async def test_dependency_rejects_page_size_over_limit(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/paged")
    async def paged(
        params: Annotated[PageParams, Depends(page_params_dependency({"name"}, "name"))],
    ) -> dict[str, int]:
        return {"page_size": params.page_size}

    response = await client.get("/paged", params={"page_size": 500})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "page_size"


async def test_dependency_rejects_unknown_sort_field(app: FastAPI, client: AsyncClient) -> None:
    @app.get("/paged")
    async def paged(
        params: Annotated[PageParams, Depends(page_params_dependency({"name"}, "name"))],
    ) -> dict[str, int]:
        return {"page_size": params.page_size}

    response = await client.get("/paged", params={"sort": "foo"})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_sort_field"
