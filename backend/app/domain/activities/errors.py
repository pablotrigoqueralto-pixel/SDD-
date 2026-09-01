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


class OwnerCannotAttendError(ValidationFailedError):
    """The owner is already on the activity: a guest row would double them everywhere."""

    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "attendee_ids",
                    "message": "The owner of the activity cannot also attend it",
                    "code": "owner_cannot_attend",
                }
            ]
        )
        self.code = "owner_cannot_attend"


class AttendeeNotActiveError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "attendee_ids",
                    "message": "Every attendee must be an active user",
                    "code": "attendee_not_active",
                }
            ]
        )
        self.code = "attendee_not_active"


class AttendeeOutOfScopeError(ValidationFailedError):
    """An invitation must never become a way into another territory."""

    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "attendee_ids",
                    "message": "Every attendee must be able to see the activity's account",
                    "code": "attendee_out_of_scope",
                }
            ]
        )
        self.code = "attendee_out_of_scope"


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


class CalendarRangeTooLongError(ValidationFailedError):
    """A quarter is the longest window a list answers; beyond that it is a report."""

    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "to",
                    "message": "The range cannot be longer than 92 days",
                    "code": "range_too_long",
                }
            ]
        )
        self.code = "range_too_long"
