"""Contact domain errors."""

from app.domain.shared.errors import DomainError, ValidationFailedError


class ConsentIncompleteError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "consent",
                    "message": "Consent date and source are required when the status is known",
                    "code": "consent_incomplete",
                }
            ]
        )
        self.code = "consent_incomplete"


class PreferredChannelMissingValueError(ValidationFailedError):
    def __init__(self, channel: str) -> None:
        super().__init__(
            [
                {
                    "field": "preferred_channel",
                    "message": f"The preferred channel '{channel}' has no value",
                    "code": "preferred_channel_missing_value",
                }
            ]
        )
        self.code = "preferred_channel_missing_value"


class ContactAnonymisedError(DomainError):
    code = "contact_anonymised"
    status = 409
    title = "Contact anonymised"

    def __init__(self) -> None:
        super().__init__("An anonymised contact cannot be modified")
