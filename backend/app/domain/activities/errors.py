"""Activity domain errors."""

from app.domain.shared.errors import DomainError, ValidationFailedError


class InvalidActivityTransitionError(DomainError):
    code = "invalid_activity_transition"
    status = 409
    title = "Invalid activity transition"

    def __init__(self, current: str, action: str) -> None:
        super().__init__(f"Cannot {action} an activity with status '{current}'")


class ActivityLockedError(DomainError):
    code = "activity_locked"
    status = 409
    title = "Activity locked"

    def __init__(self) -> None:
        super().__init__("Only sales managers can edit an activity closed more than 7 days ago")


class ContactNotInAccountError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "contact_ids",
                    "message": "Every contact must belong to the activity's account",
                    "code": "contact_not_in_account",
                }
            ]
        )
        self.code = "contact_not_in_account"


class NoteCannotBePlannedError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "activity_type_id",
                    "message": "Notes are recorded, never planned",
                    "code": "note_cannot_be_planned",
                }
            ]
        )
        self.code = "note_cannot_be_planned"


class CancelReasonRequiredError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "reason",
                    "message": "A short reason is required to cancel",
                    "code": "cancel_reason_required",
                }
            ]
        )
        self.code = "cancel_reason_required"


class NextActionInPastError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "next_action.scheduled_at",
                    "message": "The next action must be in the future",
                    "code": "next_action_in_past",
                }
            ]
        )
        self.code = "next_action_in_past"
