import pytest

from app.domain.users.errors import InvalidEmailError, PasswordTooShortError
from app.domain.users.value_objects import Email, validate_new_password


def test_email_is_normalised_and_compares_case_insensitively() -> None:
    assert Email("  Ana@Quermed.COM ") == Email("ana@quermed.com")
    assert str(Email("Ana@Quermed.com")) == "ana@quermed.com"


def test_email_rejects_invalid_format() -> None:
    with pytest.raises(InvalidEmailError) as exc_info:
        Email("not-an-email")

    assert exc_info.value.errors[0]["code"] == "invalid_email"
    assert exc_info.value.status == 422


def test_password_policy_accepts_twelve_characters() -> None:
    validate_new_password("correct-horse")


def test_password_policy_rejects_short_password() -> None:
    with pytest.raises(PasswordTooShortError) as exc_info:
        validate_new_password("short")

    error = exc_info.value.errors[0]
    assert error["field"] == "new_password"
    assert error["code"] == "password_too_short"
