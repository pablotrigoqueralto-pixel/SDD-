"""Golden-content test: the rendered PDF must carry the printed business values."""

from datetime import date
from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from app.application.quotes.pdf import PdfLine, QuotePdfDocument
from app.domain.quotes.entities import QuoteConditions, VatBucket
from app.infrastructure.pdf.quotes import ReportLabQuoteRenderer


def document() -> QuotePdfDocument:
    return QuotePdfDocument(
        display_number="P-2026-0007-v2",
        issued_on=date(2026, 9, 1),
        valid_until=date(2026, 10, 1),
        account_name="Clínica Tambre",
        account_province="28",
        contact_name="Dra. Ruiz",
        owner_name="Ana García",
        owner_email="ana@quermed.com",
        conditions=QuoteConditions(
            validez_dias=30,
            plazo_entrega="4-6 semanas",
            forma_pago="Transferencia a 30 días",
            garantia="2 años",
        ),
        lines=[
            PdfLine(
                description="Doppler vascular DP-3000",
                product_code="DP-3000",
                quantity=Decimal("2.00"),
                unit_price=Decimal("13000.00"),
                discount_percent=Decimal("10.00"),
                vat_rate=Decimal("21.00"),
                base=Decimal("23400.00"),
            ),
            PdfLine(
                description="Instalación y formación",
                product_code=None,
                quantity=Decimal("1.00"),
                unit_price=Decimal("500.00"),
                discount_percent=Decimal("0.00"),
                vat_rate=Decimal("10.00"),
                base=Decimal("500.00"),
            ),
        ],
        vat_breakdown=[
            VatBucket(rate=Decimal("21.00"), base=Decimal("23400.00"), vat=Decimal("4914.00")),
            VatBucket(rate=Decimal("10.00"), base=Decimal("500.00"), vat=Decimal("50.00")),
        ],
        total_base=Decimal("23900.00"),
        total_vat=Decimal("4964.00"),
        total=Decimal("28864.00"),
    )


def test_pdf_contains_number_lines_totals_and_conditions() -> None:
    content = ReportLabQuoteRenderer().render(document())

    assert content.startswith(b"%PDF")
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
    for expected in (
        "Presupuesto P-2026-0007-v2",
        "Clínica Tambre",
        "Dra. Ruiz",
        "Doppler vascular DP-3000",
        "DP-3000",
        "Instalación y formación",
        "23.400,00 EUR",
        "Base imponible",
        "23.900,00 EUR",
        "IVA 21 %",
        "4.914,00 EUR",
        "IVA 10 %",
        "50,00 EUR",
        "28.864,00 EUR",
        "Forma de pago:",
        "Transferencia a 30 días",
        "Ana García",
        "01/09/2026",
        "01/10/2026",
    ):
        assert expected in text, f"missing {expected!r} in PDF text"


def test_render_is_deterministic_enough_for_storage() -> None:
    renderer = ReportLabQuoteRenderer()
    first = renderer.render(document())
    second = renderer.render(document())
    # Metadata timestamps may differ; the printed content must not.
    first_text = "".join(p.extract_text() for p in PdfReader(BytesIO(first)).pages)
    second_text = "".join(p.extract_text() for p in PdfReader(BytesIO(second)).pages)
    assert first_text == second_text
