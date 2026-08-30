"""Quote domain errors."""

from app.domain.shared.errors import DomainError, PermissionDeniedError, ValidationFailedError


class QuoteNotEditableError(DomainError):
    code = "quote_not_editable"
    status = 409
    title = "Quote is not editable"

    def __init__(self, detail: str = "Only drafts can be edited; sent versions are frozen") -> None:
        super().__init__(detail)


class QuoteSupersededError(DomainError):
    code = "quote_superseded"
    status = 409
    title = "Quote version is superseded"

    def __init__(self) -> None:
        super().__init__("A newer version exists; act on the current one")


class InvalidVatRateError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "vat_rate",
                    "message": "VAT rate must be 21, 10, 4 or 0",
                    "code": "invalid_vat_rate",
                }
            ]
        )
        self.code = "invalid_vat_rate"


class QuoteActionForbiddenError(PermissionDeniedError):
    def __init__(self) -> None:
        super().__init__("Back office prepares drafts; sending and closing belong to the owner")
        self.code = "quote_action_forbidden"


class QuoteRecipientsRequiredError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "recipients",
                    "message": "At least one recipient is required to send by email",
                    "code": "quote_recipients_required",
                }
            ]
        )
        self.code = "quote_recipients_required"


class EmailRetryNotAvailableError(DomainError):
    code = "email_retry_not_available"
    status = 409
    title = "No failed email to retry"

    def __init__(self) -> None:
        super().__init__("Retry is only available after a failed email delivery")


class OpportunityAlreadyClosedError(DomainError):
    code = "opportunity_already_closed"
    status = 409
    title = "Opportunity is already closed"

    def __init__(self) -> None:
        super().__init__("The opportunity was already won or lost; reopen it first")
