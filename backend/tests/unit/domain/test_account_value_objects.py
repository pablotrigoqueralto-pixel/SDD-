import pytest

from app.domain.accounts.errors import (
    InvalidPhoneError,
    InvalidPostalCodeError,
    InvalidTaxIdError,
)
from app.domain.accounts.value_objects import PhoneNumber, PostalCode, TaxId


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12345678Z", "12345678Z"),  # NIF
        ("12345678-z", "12345678Z"),
        (" 00000000t ", "00000000T"),
        ("X1234567L", "X1234567L"),  # NIE
        ("Y1234567X", "Y1234567X"),
        ("B12345674", "B12345674"),  # CIF (letter ending on digit)
        ("b-12345674", "B12345674"),
        ("A58818501", "A58818501"),
        ("N0000000J", "N0000000J"),  # CIF with control letter
        ("P2800000H", "P2800000H"),
    ],
)
def test_tax_id_accepts_valid_identifiers_and_normalises(raw: str, expected: str) -> None:
    assert TaxId(raw).value == expected


@pytest.mark.parametrize("raw", ["12345678A", "B1234567X", "B12345670", "X1234567A", "", "ABC"])
def test_tax_id_rejects_invalid_identifiers(raw: str) -> None:
    with pytest.raises(InvalidTaxIdError) as info:
        TaxId(raw)

    assert info.value.errors[0]["code"] == "tax_id_invalid"
    assert info.value.errors[0]["field"] == "tax_id"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("612 345 678", "+34612345678"),
        ("+34 91 123 45 67", "+34911234567"),
        ("0034911234567", "+34911234567"),
        ("(+351) 912 345 678", "+351912345678"),
        ("91-123-45-67", "+34911234567"),
    ],
)
def test_phone_number_normalises_to_e164(raw: str, expected: str) -> None:
    assert PhoneNumber(raw).value == expected


@pytest.mark.parametrize("raw", ["abc", "12", "+34 1", "+123456789012345678", ""])
def test_phone_number_rejects_invalid(raw: str) -> None:
    with pytest.raises(InvalidPhoneError) as info:
        PhoneNumber(raw, field="mobile")

    assert info.value.errors[0] == {
        "field": "mobile",
        "message": "Invalid phone number",
        "code": "phone_invalid",
    }


def test_postal_code_requires_five_digits() -> None:
    assert PostalCode(" 28001 ").value == "28001"
    with pytest.raises(InvalidPostalCodeError):
        PostalCode("2800")
    with pytest.raises(InvalidPostalCodeError):
        PostalCode("28A01")
