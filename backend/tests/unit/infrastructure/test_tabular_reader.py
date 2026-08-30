from io import BytesIO

import pytest
from openpyxl import Workbook

from app.domain.shared.errors import ValidationFailedError
from app.infrastructure.imports.reader import MAX_ROWS, read_table

COLUMNS = {
    "sku": ("sku", "código", "codigo"),
    "name": ("name", "nombre"),
    "list_price": ("list_price", "pvp"),
}
REQUIRED = frozenset({"sku", "name"})


def read(content: bytes, filename: str = "file.csv") -> list[dict[str, str]]:
    return read_table(filename, content, columns=COLUMNS, required=REQUIRED)


def xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class TestCsv:
    def test_semicolon_delimiter_sniffed(self) -> None:
        rows = read(b"sku;name;pvp\nA-1;Doppler;100\n")
        assert rows == [{"sku": "A-1", "name": "Doppler", "list_price": "100"}]

    def test_comma_delimiter_sniffed(self) -> None:
        rows = read(b"sku,name\nA-1,Doppler\n")
        assert rows == [{"sku": "A-1", "name": "Doppler", "list_price": ""}]

    def test_utf8_bom_and_cp1252_fallback(self) -> None:
        with_bom = "sku;nombre\nA-1;Clínica\n".encode("utf-8-sig")
        assert read(with_bom)[0]["name"] == "Clínica"

        cp1252 = "sku;nombre\nA-1;Clínica\n".encode("cp1252")
        assert read(cp1252)[0]["name"] == "Clínica"

    def test_values_are_trimmed_and_empty_rows_skipped(self) -> None:
        rows = read(b"sku;name\n  A-1  ;  Doppler \n;;\n\nA-2;Otro\n")
        assert rows == [
            {"sku": "A-1", "name": "Doppler", "list_price": ""},
            {"sku": "A-2", "name": "Otro", "list_price": ""},
        ]


class TestHeaders:
    def test_spanish_aliases_case_and_accent_insensitive(self) -> None:
        rows = read("CÓDIGO;Nombre;PVP\nA-1;Doppler;100\n".encode())
        assert rows == [{"sku": "A-1", "name": "Doppler", "list_price": "100"}]

    def test_missing_required_header_fails(self) -> None:
        with pytest.raises(ValidationFailedError) as excinfo:
            read(b"name;pvp\nDoppler;100\n")
        assert "sku" in str(excinfo.value.errors)


class TestXlsx:
    def test_first_worksheet_read(self) -> None:
        content = xlsx([["Código", "Nombre", "PVP"], ["A-1", "Doppler", 100]])
        rows = read(content, "productos.xlsx")
        assert rows == [{"sku": "A-1", "name": "Doppler", "list_price": "100"}]

    def test_unreadable_file_fails(self) -> None:
        with pytest.raises(ValidationFailedError):
            read(b"not really a workbook", "productos.xlsx")


class TestLimits:
    def test_row_cap_enforced(self) -> None:
        body = "sku;name\n" + "".join(f"A-{i};X\n" for i in range(MAX_ROWS + 1))
        with pytest.raises(ValidationFailedError) as excinfo:
            read(body.encode())
        assert str(MAX_ROWS) in str(excinfo.value.errors)

    def test_size_cap_enforced(self) -> None:
        with pytest.raises(ValidationFailedError):
            read(b"x" * (5 * 1024 * 1024 + 1))
