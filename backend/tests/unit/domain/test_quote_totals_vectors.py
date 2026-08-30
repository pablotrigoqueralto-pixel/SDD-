"""Shared money vectors: the frontend mirrors this fixture and must match exactly."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.domain.quotes.entities import QuoteLineDraft, _build_line

VECTORS_PATH = Path(__file__).parents[2] / "fixtures" / "quote_totals_vectors.json"


def load_cases() -> list[dict[str, Any]]:
    payload = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = payload["cases"]
    return cases


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: str(case["name"]))
def test_vector(case: dict[str, Any]) -> None:
    lines = [
        _build_line(
            QuoteLineDraft(
                description=f"Line {position}",
                quantity=raw["quantity"],
                unit_price=raw["unit_price"],
                discount_percent=raw["discount_percent"],
                vat_rate=raw["vat_rate"],
            ),
            position,
        )
        for position, raw in enumerate(case["lines"])
    ]

    assert [line.base for line in lines] == [Decimal(value) for value in case["line_bases"]]
    assert [line.vat for line in lines] == [Decimal(value) for value in case["line_vats"]]
    assert sum((line.base for line in lines), Decimal("0")) == Decimal(case["total_base"])
    assert sum((line.vat for line in lines), Decimal("0")) == Decimal(case["total_vat"])
    total = Decimal(case["total_base"]) + Decimal(case["total_vat"])
    assert total == Decimal(case["total"])
