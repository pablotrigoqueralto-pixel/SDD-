"""Per-row import outcomes and the run report."""

import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class RowOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    ERROR = "error"


@dataclass(frozen=True)
class RowReport:
    row: int
    outcome: RowOutcome
    label: str
    message: str | None = None


@dataclass(frozen=True)
class ImportReport:
    rows: list[RowReport] = field(default_factory=list)

    def count(self, outcome: RowOutcome) -> int:
        return sum(1 for row in self.rows if row.outcome is outcome)

    @property
    def created(self) -> int:
        return self.count(RowOutcome.CREATED)

    @property
    def updated(self) -> int:
        return self.count(RowOutcome.UPDATED)

    @property
    def unchanged(self) -> int:
        return self.count(RowOutcome.UNCHANGED)

    @property
    def errors(self) -> int:
        return self.count(RowOutcome.ERROR)


def normalise_text(value: str) -> str:
    """Unaccent + casefold + collapse spaces: the Python twin of the SQL matcher."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.casefold().split())


def normalise_tax_id(value: str) -> str:
    return "".join(char for char in value if char.isalnum()).upper()


def parse_spanish_number(raw: str) -> Decimal:
    """ "1.234,56", "1234.56" and "1234" all parse; raises InvalidOperation otherwise."""
    text = "".join(char for char in raw if not char.isspace()).replace("€", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    if not text:
        raise InvalidOperation()
    return Decimal(text)
