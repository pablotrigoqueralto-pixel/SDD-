from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain.quotes.entities import (
    Quote,
    QuoteConditions,
    QuoteLineDraft,
    QuoteStatus,
    round_half_up,
)
from app.domain.quotes.errors import (
    InvalidVatRateError,
    QuoteNotEditableError,
    QuoteSupersededError,
)
from app.domain.shared.errors import ValidationFailedError
from app.domain.shared.ids import new_id

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
OPPORTUNITY = new_id()
ACTOR = new_id()
PRODUCT = new_id()


def status_of(quote: Quote) -> QuoteStatus:
    """Erase mypy's literal narrowing: mutations happen inside aggregate methods."""
    return quote.status


def doppler_line(**overrides: object) -> QuoteLineDraft:
    values: dict[str, object] = {
        "description": "Doppler vascular DP-3000",
        "quantity": "2",
        "unit_price": "13000",
        "product_id": PRODUCT,
        "product_code": "DP-3000",
        "unit_cost": "9000",
    }
    values.update(overrides)
    return QuoteLineDraft(**values)  # type: ignore[arg-type]


def create(**overrides: object) -> Quote:
    values: dict[str, object] = {
        "opportunity_id": OPPORTUNITY,
        "owner_id": ACTOR,
        "created_by": ACTOR,
        "year": 2026,
        "number": 7,
        "conditions": QuoteConditions(validez_dias=30),
        "lines": [doppler_line()],
        "now": NOW,
    }
    values.update(overrides)
    return Quote.create(**values)  # type: ignore[arg-type]


def sent(**overrides: object) -> Quote:
    quote = create(**overrides)
    quote.send(now=NOW)
    return quote


class TestCreation:
    def test_copies_lines_with_defaults(self) -> None:
        quote = create()

        assert quote.status is QuoteStatus.DRAFT
        assert quote.version == 1
        assert quote.quote_number == "P-2026-0007"
        assert quote.display_number == "P-2026-0007"
        line = quote.lines[0]
        assert line.description == "Doppler vascular DP-3000"
        assert line.discount_percent == Decimal("0.00")
        assert line.vat_rate == Decimal("21.00")
        assert line.unit_cost == Decimal("9000.00")
        assert quote.total_base == Decimal("26000.00")
        assert quote.total_vat == Decimal("5460.00")
        assert quote.total == Decimal("31460.00")

    def test_free_text_line_without_product(self) -> None:
        quote = create(
            lines=[
                QuoteLineDraft(description="Instalación y formación", quantity=1, unit_price="500")
            ]
        )

        line = quote.lines[0]
        assert line.product_id is None
        assert line.unit_cost is None
        assert quote.total == Decimal("605.00")

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValidationFailedError):
            create(lines=[doppler_line(description="   ")])


class TestLineMath:
    def test_rounds_half_up_per_line(self) -> None:
        quote = create(
            lines=[
                doppler_line(
                    quantity="3", unit_price="33.33", discount_percent="10", unit_cost=None
                )
            ]
        )

        line = quote.lines[0]
        # 3 x 33.33 x 0.9 = 89.991 -> 89.99; VAT 21% of 89.99 = 18.8979 -> 18.90
        assert line.base == Decimal("89.99")
        assert line.vat == Decimal("18.90")
        assert quote.total_base == Decimal("89.99")
        assert quote.total_vat == Decimal("18.90")
        assert quote.total == Decimal("108.89")

    def test_totals_equal_sum_of_printed_lines(self) -> None:
        quote = create(
            lines=[
                doppler_line(quantity="1", unit_price="10.01", discount_percent="5"),
                doppler_line(
                    description="Gel conductor",
                    product_id=None,
                    product_code=None,
                    unit_cost=None,
                    quantity="7",
                    unit_price="3.17",
                    vat_rate="10",
                ),
            ]
        )

        bases = [line.base for line in quote.lines]
        vats = [line.vat for line in quote.lines]
        assert quote.total_base == sum(bases)
        assert quote.total_vat == sum(vats)
        assert quote.total == quote.total_base + quote.total_vat

    def test_vat_breakdown_groups_by_rate(self) -> None:
        quote = create(
            lines=[
                doppler_line(),
                doppler_line(description="Sonda", vat_rate="10", quantity="1", unit_price="100"),
                doppler_line(description="Kit", vat_rate="10", quantity="2", unit_price="50"),
            ]
        )

        breakdown = quote.vat_breakdown()
        assert [entry.rate for entry in breakdown] == [Decimal("21.00"), Decimal("10.00")]
        ten = breakdown[1]
        assert ten.base == Decimal("200.00")
        assert ten.vat == Decimal("20.00")

    def test_invalid_vat_rate_rejected(self) -> None:
        with pytest.raises(InvalidVatRateError):
            create(lines=[doppler_line(vat_rate="15")])

    def test_discount_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationFailedError):
            create(lines=[doppler_line(discount_percent="120")])
        with pytest.raises(ValidationFailedError):
            create(lines=[doppler_line(discount_percent="-1")])

    def test_quantity_must_be_positive(self) -> None:
        with pytest.raises(ValidationFailedError):
            create(lines=[doppler_line(quantity="0")])

    def test_margin_from_cost_snapshots(self) -> None:
        quote = create()

        # base 26 000 - cost 2 x 9 000 = 8 000
        assert quote.total_margin() == Decimal("8000.00")

        quote.replace_lines([doppler_line(unit_cost=None)])
        assert quote.total_margin() is None


class TestStatusMachine:
    def test_send_stamps_and_defaults_validity_from_conditions(self) -> None:
        quote = create(conditions=QuoteConditions(validez_dias=15))
        quote.send(now=datetime(2026, 9, 1, 9, 0, tzinfo=UTC))

        assert status_of(quote) is QuoteStatus.SENT
        assert quote.sent_at == datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
        assert quote.valid_until == date(2026, 9, 16)

    def test_send_keeps_explicit_validity(self) -> None:
        quote = create()
        quote.send(now=NOW, valid_until=date(2026, 10, 15))

        assert quote.valid_until == date(2026, 10, 15)

    def test_sent_quote_is_frozen(self) -> None:
        quote = sent()

        with pytest.raises(QuoteNotEditableError):
            quote.replace_lines([doppler_line()])
        with pytest.raises(QuoteNotEditableError):
            quote.update_draft(conditions=QuoteConditions(validez_dias=10))
        with pytest.raises(QuoteNotEditableError):
            quote.send(now=NOW)
        with pytest.raises(QuoteNotEditableError):
            quote.ensure_deletable()

    def test_draft_is_deletable_but_not_closable(self) -> None:
        quote = create()
        quote.ensure_deletable()

        with pytest.raises(QuoteNotEditableError):
            quote.accept(now=NOW)
        with pytest.raises(QuoteNotEditableError):
            quote.reject(now=NOW)

    def test_accept_and_reject_stamp(self) -> None:
        accepted = sent()
        accepted.accept(now=NOW)
        assert status_of(accepted) is QuoteStatus.ACCEPTED
        assert accepted.accepted_at == NOW

        rejected = sent()
        rejected.reject(now=NOW, note="  Precio alto  ")
        assert status_of(rejected) is QuoteStatus.REJECTED
        assert rejected.rejected_at == NOW
        assert rejected.rejection_note == "Precio alto"

    def test_expiry_is_derived_and_visual_only(self) -> None:
        quote = sent()
        assert quote.valid_until is not None

        assert quote.is_expired(today=quote.valid_until) is False
        later = date(2026, 12, 1)
        assert quote.is_expired(today=later) is True
        assert status_of(quote) is QuoteStatus.SENT

        draft = create()
        assert draft.is_expired(today=later) is False


class TestVersions:
    def test_revise_copies_content_and_supersedes(self) -> None:
        original = sent(conditions=QuoteConditions(validez_dias=15, forma_pago="60 días"))
        revision = original.revise(created_by=ACTOR, now=NOW)

        assert original.superseded_at == NOW
        assert revision.version == 2
        assert revision.status is QuoteStatus.DRAFT
        assert revision.quote_number == original.quote_number
        assert revision.display_number == "P-2026-0007-v2"
        assert revision.conditions.forma_pago == "60 días"
        assert [line.description for line in revision.lines] == [
            line.description for line in original.lines
        ]
        assert revision.lines[0].id != original.lines[0].id
        assert revision.total == original.total
        assert revision.sent_at is None
        assert revision.valid_until is None

    def test_rejected_quote_can_be_revised(self) -> None:
        original = sent()
        original.reject(now=NOW)

        revision = original.revise(created_by=ACTOR, now=NOW)
        assert revision.version == 2

    def test_superseded_version_cannot_be_revised(self) -> None:
        original = sent()
        original.revise(created_by=ACTOR, now=NOW)

        with pytest.raises(QuoteSupersededError):
            original.revise(created_by=ACTOR, now=NOW)

    def test_draft_and_accepted_cannot_be_revised(self) -> None:
        draft = create()
        with pytest.raises(QuoteNotEditableError):
            draft.revise(created_by=ACTOR, now=NOW)

        accepted = sent()
        accepted.accept(now=NOW)
        with pytest.raises(QuoteNotEditableError):
            accepted.revise(created_by=ACTOR, now=NOW)


class TestRounding:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2.675", "2.68"),
            ("2.665", "2.67"),
            ("89.991", "89.99"),
            ("0.005", "0.01"),
            ("-1.005", "-1.01"),
        ],
    )
    def test_round_half_up(self, raw: str, expected: str) -> None:
        assert round_half_up(Decimal(raw)) == Decimal(expected)
