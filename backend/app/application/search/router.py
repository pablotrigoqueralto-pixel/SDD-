"""Query routing: inspect the raw term once and decide which lookups apply.

Identifier matches run *alongside* the name matching, never instead of it —
the groups simply stay empty when nothing matches their route.
"""

import re
from dataclasses import dataclass

MIN_QUERY_LENGTH = 2

_QUOTE_NUMBER = re.compile(r"^p-?(\d{4})(?:-(\d{1,4}))?(?:-v\d+)?$", re.IGNORECASE)
_CIF = re.compile(r"^[A-Z]\d{7,8}[A-Z0-9]?$")
_NIF = re.compile(r"^\d{8}[A-Z]$")
_PHONE_SEPARATORS = re.compile(r"[\s.\-+()/]")
_MIN_PHONE_DIGITS = 7


@dataclass(frozen=True)
class ParsedQuery:
    """The cleaned term plus every identifier route it activates."""

    text: str
    quote_number: tuple[int, int | None] | None = None
    email: str | None = None
    tax_id: str | None = None
    phone_digits: str | None = None


def parse_query(raw: str) -> ParsedQuery | None:
    text = " ".join(raw.split())
    if len(text) < MIN_QUERY_LENGTH:
        return None

    quote_number: tuple[int, int | None] | None = None
    quote_match = _QUOTE_NUMBER.match(text)
    if quote_match:
        year = int(quote_match.group(1))
        number = int(quote_match.group(2)) if quote_match.group(2) else None
        quote_number = (year, number)

    email = text.lower() if "@" in text else None

    compact = _PHONE_SEPARATORS.sub("", text).upper()
    tax_id = compact if (_CIF.match(compact) or _NIF.match(compact)) else None

    stripped = _PHONE_SEPARATORS.sub("", text)
    phone_digits = stripped if stripped.isdigit() and len(stripped) >= _MIN_PHONE_DIGITS else None

    return ParsedQuery(
        text=text,
        quote_number=quote_number,
        email=email,
        tax_id=tax_id,
        phone_digits=phone_digits,
    )
