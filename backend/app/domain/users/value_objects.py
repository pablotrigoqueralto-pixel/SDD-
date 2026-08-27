"""Value objects for the users context."""

import re
from dataclasses import dataclass

from app.domain.users.errors import InvalidEmailError, PasswordTooShortError

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 12


@dataclass(frozen=True)
class Email:
    """Normalised (lower-cased, trimmed) email address."""

    value: str

    def __init__(self, raw: str) -> None:
        normalised = raw.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalised):
            raise InvalidEmailError()
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


def validate_new_password(raw: str, *, field: str = "new_password") -> None:
    """Password policy: minimum length only (long passphrases beat complexity rules)."""
    if len(raw) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError(MIN_PASSWORD_LENGTH, field=field)
