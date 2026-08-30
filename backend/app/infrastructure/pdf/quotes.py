"""Fixed ReportLab template for quote PDFs.

The layout is deliberately code (design decision 6): logo header, fiscal data,
account block, line table with discount and VAT, totals by VAT rate, conditions
and the owner's signature footer. Pure Python, identical output on every OS.
"""

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.application.quotes.pdf import QuotePdfDocument

BRAND_COLOR = colors.HexColor("#0f4c81")
LIGHT_ROW = colors.HexColor("#f2f6fa")

COMPANY_LINES = (
    "Quermed S.L. · CIF B-00000000",
    "C/ de la Salud 1, 28001 Madrid · +34 910 000 000 · info@quermed.com",
)

_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=16, textColor=BRAND_COLOR)
_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=12)
_SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=8, textColor=colors.grey)
_HEADING = ParagraphStyle(
    "heading", fontName="Helvetica-Bold", fontSize=10, textColor=BRAND_COLOR, spaceBefore=6
)


def _eur(value: Decimal) -> str:
    whole, _, cents = f"{value:,.2f}".partition(".")
    return f"{whole.replace(',', '.')},{cents} EUR"


def _pct(value: Decimal) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text} %"


class ReportLabQuoteRenderer:
    def render(self, document: QuotePdfDocument) -> bytes:
        buffer = BytesIO()
        pdf = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"Presupuesto {document.display_number}",
            author="Quermed S.L.",
        )
        story: list[object] = [
            Paragraph(f"Presupuesto {document.display_number}", _TITLE),
            Spacer(0, 2 * mm),
        ]
        for line in COMPANY_LINES:
            story.append(Paragraph(line, _SMALL))
        story.append(Spacer(0, 4 * mm))

        issued = document.issued_on.strftime("%d/%m/%Y")
        validity = document.valid_until.strftime("%d/%m/%Y") if document.valid_until else "—"
        header_rows = [
            ["Centro", document.account_name, "Fecha", issued],
            [
                "Atención de",
                document.contact_name or "—",
                "Válido hasta",
                validity,
            ],
        ]
        header = Table(header_rows, colWidths=[24 * mm, 78 * mm, 24 * mm, 40 * mm])
        header.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                    ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                    ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
                    ("TEXTCOLOR", (0, 0), (0, -1), BRAND_COLOR),
                    ("TEXTCOLOR", (2, 0), (2, -1), BRAND_COLOR),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.extend([header, Spacer(0, 5 * mm)])

        line_rows: list[list[object]] = [
            ["Ref.", "Descripción", "Cant.", "Precio", "Dto.", "IVA", "Importe"]
        ]
        for pdf_line in document.lines:
            line_rows.append(
                [
                    pdf_line.product_code or "—",
                    Paragraph(pdf_line.description, _BODY),
                    f"{pdf_line.quantity:.2f}".rstrip("0").rstrip("."),
                    _eur(pdf_line.unit_price),
                    _pct(pdf_line.discount_percent),
                    _pct(pdf_line.vat_rate),
                    _eur(pdf_line.base),
                ]
            )
        lines_table = Table(
            line_rows, colWidths=[18 * mm, 62 * mm, 12 * mm, 26 * mm, 12 * mm, 12 * mm, 28 * mm]
        )
        lines_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                    ("BACKGROUND", (0, 0), (-1, 0), BRAND_COLOR),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_ROW]),
                    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d4e0")),
                ]
            )
        )
        story.extend([lines_table, Spacer(0, 5 * mm)])

        totals_rows: list[list[str]] = [["Base imponible", _eur(document.total_base)]]
        for bucket in document.vat_breakdown:
            totals_rows.append([f"IVA {_pct(bucket.rate)}", _eur(bucket.vat)])
        totals_rows.append(["TOTAL", _eur(document.total)])
        totals = Table(totals_rows, colWidths=[120 * mm, 50 * mm])
        totals.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                    ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 10),
                    ("TEXTCOLOR", (0, -1), (-1, -1), BRAND_COLOR),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.5, BRAND_COLOR),
                ]
            )
        )
        story.extend([totals, Spacer(0, 6 * mm), Paragraph("Condiciones", _HEADING)])

        conditions = document.conditions
        for label, value in (
            ("Validez", f"{conditions.validez_dias} días"),
            ("Plazo de entrega", conditions.plazo_entrega or "—"),
            ("Forma de pago", conditions.forma_pago or "—"),
            ("Garantía", conditions.garantia or "—"),
        ):
            story.append(Paragraph(f"<b>{label}:</b> {value}", _BODY))

        story.extend(
            [
                Spacer(0, 8 * mm),
                Paragraph(document.owner_name, _BODY),
                Paragraph(document.owner_email, _SMALL),
                Paragraph("Quermed S.L.", _SMALL),
            ]
        )
        pdf.build(story)
        return buffer.getvalue()
