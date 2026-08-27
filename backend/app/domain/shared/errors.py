"""Domain error hierarchy. Mapped to RFC 7807 responses by the API layer."""

from typing import TypedDict


class FieldError(TypedDict):
    field: str
    message: str
    code: str


class DomainError(Exception):
    """Base class for every error raised by domain or application code."""

    code: str = "domain_error"
    status: int = 400
    title: str = "Domain rule violated"

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        errors: list[FieldError] | None = None,
    ) -> None:
        self.detail = detail or self.title
        if code is not None:
            self.code = code
        self.errors = errors or []
        super().__init__(self.detail)


class NotFoundError(DomainError):
    code = "not_found"
    status = 404
    title = "Not found"


class UnauthenticatedError(DomainError):
    code = "unauthenticated"
    status = 401
    title = "Authentication required"


class PermissionDeniedError(DomainError):
    code = "forbidden"
    status = 403
    title = "Forbidden"


class ConcurrentModificationError(DomainError):
    code = "conflict"
    status = 409
    title = "Conflict"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or "The resource was modified by another user")


class PreconditionRequiredError(DomainError):
    code = "precondition_required"
    status = 428
    title = "Precondition required"

    def __init__(self) -> None:
        super().__init__("The If-Match header with the current version is required")


class ValidationFailedError(DomainError):
    code = "validation_error"
    status = 422
    title = "Validation error"

    def __init__(self, errors: list[FieldError], detail: str | None = None) -> None:
        super().__init__(detail or "One or more fields are invalid.", errors=errors)


class InvalidSortFieldError(DomainError):
    code = "invalid_sort_field"
    status = 422
    title = "Invalid sort field"

    def __init__(self, field: str, allowed: set[str]) -> None:
        allowed_list = ", ".join(sorted(allowed))
        super().__init__(f"Cannot sort by '{field}'. Allowed fields: {allowed_list}")


class RateLimitedError(DomainError):
    code = "rate_limited"
    status = 429
    title = "Too many requests"
