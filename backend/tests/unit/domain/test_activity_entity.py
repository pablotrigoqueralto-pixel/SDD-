from datetime import UTC, datetime, timedelta

import pytest

from app.domain.activities.entities import (
    Activity,
    ActivityKind,
    ActivityOutcome,
    ActivityStatus,
    NextAction,
)
from app.domain.activities.errors import (
    ActivityLockedError,
    CancelReasonRequiredError,
    InvalidActivityTransitionError,
    NextActionInPastError,
    NoteCannotBePlannedError,
)
from app.domain.shared.errors import ValidationFailedError
from app.domain.shared.ids import new_id
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
ACCOUNT = new_id()
VISIT = ActivityKind(id=new_id(), is_note=False, counts_as_contact=True)
NOTE = ActivityKind(id=new_id(), is_note=True, counts_as_contact=False)
CALL_ID = new_id()


def make_user(role: Role) -> User:
    return User.create(
        email=Email(f"{new_id()}@q.com"), full_name="U", role=role, password_hash="h"
    )


REP = make_user(Role.SALES_REP)
MANAGER = make_user(Role.SALES_MANAGER)


def done_visit(**details: object) -> Activity:
    return Activity.record_done(
        account_id=ACCOUNT, kind=VISIT, owner_id=REP.id, created_by=REP.id, now=NOW, details=details
    )


def planned_visit(when: datetime = NOW + timedelta(days=1)) -> Activity:
    return Activity.plan(
        account_id=ACCOUNT, kind=VISIT, owner_id=REP.id, created_by=REP.id, scheduled_at=when
    )


def test_minimum_activity_is_done_now() -> None:
    activity = done_visit()

    assert activity.status is ActivityStatus.DONE
    assert activity.scheduled_at == NOW and activity.done_at == NOW
    assert activity.owner_id == REP.id and activity.contact_ids == frozenset()
    assert activity.outcome is None and activity.version == 1
    assert activity.occurred_at == NOW


def test_done_in_the_past_keeps_the_given_time_and_normalises_details() -> None:
    contact = new_id()
    earlier = NOW - timedelta(hours=3)
    activity = Activity.record_done(
        account_id=ACCOUNT,
        kind=VISIT,
        owner_id=REP.id,
        created_by=REP.id,
        now=NOW,
        scheduled_at=earlier,
        details={
            "contact_ids": [contact],
            "subject": "  Demo  ",
            "notes": " ",
            "outcome": "positive",
            "duration_minutes": 45,
        },
    )

    assert activity.scheduled_at == earlier and activity.done_at == earlier
    assert activity.contact_ids == frozenset({contact})
    assert activity.subject == "Demo" and activity.notes is None
    assert activity.outcome is ActivityOutcome.POSITIVE and activity.duration_minutes == 45
    with pytest.raises(ValidationFailedError):
        done_visit(duration_minutes=0)


def test_planned_activity_and_note_rule() -> None:
    activity = planned_visit()
    assert activity.status is ActivityStatus.PLANNED and activity.done_at is None
    with pytest.raises(NoteCannotBePlannedError):
        Activity.plan(
            account_id=ACCOUNT, kind=NOTE, owner_id=REP.id, created_by=REP.id, scheduled_at=NOW
        )


def test_lifecycle_transitions() -> None:
    activity = planned_visit()
    activity.reschedule(NOW + timedelta(days=2))
    assert activity.scheduled_at == NOW + timedelta(days=2)

    activity.complete(now=NOW, outcome=ActivityOutcome.NEGATIVE, notes="No interest")
    assert activity.status is ActivityStatus.DONE
    assert activity.done_at == NOW and activity.outcome is ActivityOutcome.NEGATIVE
    assert activity.occurred_at == NOW

    with pytest.raises(InvalidActivityTransitionError):
        activity.reschedule(NOW)
    with pytest.raises(InvalidActivityTransitionError):
        activity.complete(now=NOW)
    with pytest.raises(InvalidActivityTransitionError):
        activity.cancel("late")

    other = planned_visit()
    with pytest.raises(CancelReasonRequiredError):
        other.cancel("  ")
    other.cancel(" Centro cerrado ")
    assert other.status is ActivityStatus.CANCELLED and other.cancel_reason == "Centro cerrado"


def test_edit_window() -> None:
    activity = done_visit()
    activity.ensure_editable(REP, now=NOW + timedelta(days=3))
    with pytest.raises(ActivityLockedError):
        activity.ensure_editable(REP, now=NOW + timedelta(days=8))
    activity.ensure_editable(MANAGER, now=NOW + timedelta(days=30))
    with pytest.raises(ActivityLockedError):
        activity.ensure_editable(make_user(Role.SALES_REP), now=NOW)
    with pytest.raises(ActivityLockedError):
        activity.ensure_editable(make_user(Role.BACK_OFFICE), now=NOW)

    planned = planned_visit()
    planned.ensure_editable(REP, now=NOW + timedelta(days=90))
    planned.cancel("x")
    with pytest.raises(ActivityLockedError):
        planned.ensure_editable(REP, now=NOW)

    activity.update_details({"subject": "Visita", "status": "planned", "outcome": None})
    assert activity.subject == "Visita" and activity.status is ActivityStatus.DONE
    assert activity.outcome is None


def test_follow_up_creates_a_planned_activity() -> None:
    contact = new_id()
    activity = done_visit(contact_ids=[contact])
    next_action = NextAction(activity_type_id=CALL_ID, scheduled_at=NOW + timedelta(days=3))

    follow_up = activity.follow_up(next_action, now=NOW, is_note=False)

    assert follow_up.status is ActivityStatus.PLANNED
    assert follow_up.account_id == ACCOUNT and follow_up.owner_id == REP.id
    assert follow_up.activity_type_id == CALL_ID
    assert follow_up.contact_ids == frozenset({contact})
    assert follow_up.scheduled_at == NOW + timedelta(days=3)

    with pytest.raises(NextActionInPastError):
        activity.follow_up(
            NextAction(activity_type_id=CALL_ID, scheduled_at=NOW - timedelta(minutes=1)),
            now=NOW,
            is_note=False,
        )
    with pytest.raises(NoteCannotBePlannedError):
        activity.follow_up(next_action, now=NOW, is_note=True)
