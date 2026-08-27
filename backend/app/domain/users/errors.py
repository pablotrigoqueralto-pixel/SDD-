"""User and authentication domain errors."""

from app.domain.shared.errors import DomainError, ValidationFailedError


class InvalidEmailError(ValidationFailedError):
    def __init__(self, field: str = "email") -> None:
        super().__init__(
            [{"field": field, "message": "Invalid email address", "code": "invalid_email"}]
        )


class PasswordTooShortError(ValidationFailedError):
    def __init__(self, minimum_length: int, field: str = "new_password") -> None:
        super().__init__(
            [
                {
                    "field": field,
                    "message": f"Password must have at least {minimum_length} characters",
                    "code": "password_too_short",
                }
            ]
        )


class EmailAlreadyExistsError(DomainError):
    code = "email_already_exists"
    status = 409
    title = "Email already exists"

    def __init__(self) -> None:
        super().__init__("A user with this email already exists")


class UnknownReferenceError(ValidationFailedError):
    def __init__(self, field: str, unknown_ids: list[str]) -> None:
        super().__init__(
            [
                {
                    "field": field,
                    "message": f"Unknown references: {', '.join(unknown_ids)}",
                    "code": "unknown_reference",
                }
            ]
        )


class CannotDemoteSelfError(DomainError):
    code = "cannot_demote_self"
    status = 400
    title = "Cannot demote yourself"

    def __init__(self) -> None:
        super().__init__("An administrator cannot deactivate or demote their own account")


class InvalidCredentialsError(DomainError):
    code = "invalid_credentials"
    status = 401
    title = "Invalid credentials"

    def __init__(self) -> None:
        super().__init__("Email or password is incorrect")


class AccountLockedError(DomainError):
    code = "account_locked"
    status = 401
    title = "Account locked"

    def __init__(self) -> None:
        super().__init__("The account is temporarily locked after too many failed attempts")


class InvalidCurrentPasswordError(DomainError):
    code = "invalid_current_password"
    status = 400
    title = "Invalid current password"

    def __init__(self) -> None:
        super().__init__("The current password is incorrect")
