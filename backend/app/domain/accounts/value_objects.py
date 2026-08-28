"""Value objects for accounts and contacts: Spanish tax ids, phones, postal codes."""

import re
from dataclasses import dataclass

from app.domain.accounts.errors import InvalidPhoneError, InvalidPostalCodeError, InvalidTaxIdError

NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
CIF_CONTROL_LETTERS = "JABCDEFGHI"
CIF_LETTER_CONTROL = frozenset("KPQRSNW")  # entities whose control is always a letter
CIF_DIGIT_CONTROL = frozenset("ABEH")  # entities whose control is always a digit
NIE_PREFIX = {"X": "0", "Y": "1", "Z": "2"}

NIF_PATTERN = re.compile(r"^\d{8}[A-Z]$")
NIE_PATTERN = re.compile(r"^[XYZ]\d{7}[A-Z]$")
CIF_PATTERN = re.compile(r"^[ABCDEFGHJKLMNPQRSUVW]\d{7}[0-9A-J]$")

DEFAULT_COUNTRY_PREFIX = "+34"
E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
POSTAL_CODE_PATTERN = re.compile(r"^\d{5}$")


def _nif_letter(digits: str) -> str:
    return NIF_LETTERS[int(digits) % 23]


def _cif_control(body: str) -> tuple[str, str]:
    """Return (digit control, letter control) for the seven-digit CIF body."""
    even_sum = sum(int(d) for d in body[1::2])
    odd_sum = 0
    for d in body[0::2]:
        doubled = int(d) * 2
        odd_sum += doubled // 10 + doubled % 10
    control = (10 - (even_sum + odd_sum) % 10) % 10
    return str(control), CIF_CONTROL_LETTERS[control]


def is_valid_tax_id(value: str) -> bool:
    if NIF_PATTERN.match(value):
        return value[-1] == _nif_letter(value[:-1])
    if NIE_PATTERN.match(value):
        return value[-1] == _nif_letter(NIE_PREFIX[value[0]] + value[1:-1])
    if CIF_PATTERN.match(value):
        digit, letter = _cif_control(value[1:8])
        kind, control = value[0], value[8]
        if kind in CIF_LETTER_CONTROL:
            return control == letter
        if kind in CIF_DIGIT_CONTROL:
            return control == digit
        return control in {digit, letter}
    return False


@dataclass(frozen=True)
class TaxId:
    """Spanish NIF / NIE / CIF, upper-cased without separators and checksum-validated."""

    value: str

    def __init__(self, raw: str) -> None:
        normalised = re.sub(r"[\s\-.]", "", raw).upper()
        if not is_valid_tax_id(normalised):
            raise InvalidTaxIdError()
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PhoneNumber:
    """E.164 phone; numbers without a country prefix default to Spain."""

    value: str

    def __init__(self, raw: str, *, field: str = "phone") -> None:
        cleaned = re.sub(r"[\s\-.()/]", "", raw.strip())
        if cleaned.startswith("00"):
            cleaned = "+" + cleaned[2:]
        if not cleaned.startswith("+"):
            cleaned = DEFAULT_COUNTRY_PREFIX + cleaned
        if not E164_PATTERN.match(cleaned):
            raise InvalidPhoneError(field)
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PostalCode:
    value: str

    def __init__(self, raw: str, *, field: str = "postal_code") -> None:
        cleaned = raw.strip()
        if not POSTAL_CODE_PATTERN.match(cleaned):
            raise InvalidPostalCodeError(field)
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value
