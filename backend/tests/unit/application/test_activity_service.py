from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.application.accounts.commands import CreateAccount
from app.application.accounts.service import AccountService
from app.application.activities.commands import (
    CancelActivity,
    CompleteActivity,
    CreateActivity,
    RescheduleActivity,
    UpdateActivity,
)
from app.application.activities.service import ActivityService
from app.domain.accounts.errors import AssignmentForbiddenError
from app.domain.activities.entities import ActivityOutcome, ActivityStatus, NextAction
from app.domain.activities.errors import (
    ActivityLockedError,
    ContactNotInAccountError,
    InvalidActivityTransitionError,
    NoteCannotBePlannedError,
)
from app.domain.reference.entities import AccountType, ActivityType
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.shared.ids import new_id
from app.domain.territories.entities import Division, Territory
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.reference import InMemoryReferenceReadRepository
from tests.unit.fakes.repositories import InMemoryDivisionRepository

VASCULAR = Division(id=new_id(), code="vascular", name_es="Vascular", sort_order=40)
IVF = AccountType(new_id(), "ivf_clinic", "Clínica FIV", 10, False, True)
CENTRO = Territory.create(name="Centro", provinces=frozenset({"28"}))
VISIT = ActivityType(new_id(), "visit", "Visita", 10, "map-pin", True, True)
CALL = ActivityType(new_id(), "call", "Llamada", 20, "phone", True, True)
NOTE = ActivityType(new_id(), "note", "Nota", 60, "sticky-note", False, True)


class FrozenClock(datetime):
    frozen = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):  # type: ignore[no-untyped-def]
        return cls.frozen.astimezone(tz) if tz else cls.frozen


NOW = FrozenClock.frozen


def make_user(role: Role, *, territories: set[UUID] = set(), divisions: set[UUID] = set()) -> User:  # noqa: B006
    return User.create(
        email=Email(f"{new_id()}@quermed.com"),
        full_name=role.value,
        role=role,
        password_hash="h",
        territory_ids=frozenset(territories),
        division_ids=frozenset(divisions),
    )


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.divisions = InMemoryDivisionRepository([VASCULAR])
    uow.reference = InMemoryReferenceReadRepository(
        account_types=[IVF], activity_types=[VISIT, CALL, NOTE]
    )
    uow.territories.rows[CENTRO.id] = CENTRO
    uow.accounts.contact_type_ids = {VISIT.id, CALL.id}
    return uow


@pytest.fixture
def rep(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.SALES_REP, territories={CENTRO.id}, divisions={VASCULAR.id})
    uow.users.rows[user.id] = user
    return user


@pytest.fixture
def manager(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.SALES_MANAGER)
    uow.users.rows[user.id] = user
    return user


@pytest.fixture
async def account_id(uow: FakeUnitOfWork, rep: User) -> UUID:
    view = await AccountService(uow).create(
        CreateAccount(name="Tambre", account_type_id=IVF.id, province_code="28"), actor=rep
    )
    uow.committed_events.clear()
    return view.account.id


@pytest.fixture
def service(uow: FakeUnitOfWork) -> ActivityService:
    return ActivityService(uow, clock=FrozenClock)


async def test_three_field_visit_is_done_now_and_refreshes_the_summary(
    uow: FakeUnitOfWork, rep: User, account_id: UUID, service: ActivityService
) -> None:
    result = await service.create(
        CreateActivity(account_id=account_id, activity_type_id=VISIT.id), actor=rep
    )

    activity = result.activity
    assert activity.status is ActivityStatus.DONE and activity.done_at == NOW
    assert activity.owner_id == rep.id and activity.created_by == rep.id
    assert result.next_activity is None
    assert uow.actions() == ["activity.created"]
    account = await uow.accounts.get(account_id)
    assert account is not None and account.last_contact_at == NOW


async def test_create_with_next_action_plans_the_follow_up(
    uow: FakeUnitOfWork, rep: User, account_id: UUID, service: ActivityService
) -> None:
    contact = new_id()
    uow.activities.contact_accounts[contact] = account_id
    later = NOW + timedelta(days=3)

    result = await service.create(
        CreateActivity(
            account_id=account_id,
            activity_type_id=VISIT.id,
            details={"contact_ids": [contact], "outcome": "positive"},
            next_action=NextAction(
                activity_type_id=CALL.id, scheduled_at=later, subject="Seguimiento"
            ),
        ),
        actor=rep,
    )

    assert result.next_activity is not None
    assert result.next_activity.status is ActivityStatus.PLANNED
    assert result.next_activity.contact_ids == frozenset({contact})
    assert result.next_activity.subject == "Seguimiento"
    assert uow.actions() == ["activity.created", "activity.created"]
    account = await uow.accounts.get(account_id)
    assert account is not None and account.next_activity_at == later


async def test_create_validations(
    uow: FakeUnitOfWork, rep: User, manager: User, account_id: UUID, service: ActivityService
) -> None:
    with pytest.raises(UnknownReferenceError):
        await service.create(
            CreateActivity(account_id=account_id, activity_type_id=new_id()), actor=rep
        )
    with pytest.raises(NoteCannotBePlannedError):
        await service.create(
            CreateActivity(
                account_id=account_id, activity_type_id=NOTE.id, status=ActivityStatus.PLANNED
            ),
            actor=rep,
        )
    with pytest.raises(ContactNotInAccountError):
        await service.create(
            CreateActivity(
                account_id=account_id,
                activity_type_id=VISIT.id,
                details={"contact_ids": [new_id()]},
            ),
            actor=rep,
        )
    with pytest.raises(AssignmentForbiddenError):
        await service.create(
            CreateActivity(account_id=account_id, activity_type_id=VISIT.id, owner_id=manager.id),
            actor=rep,
        )
    with pytest.raises(PermissionDeniedError):
        await service.create(
            CreateActivity(account_id=account_id, activity_type_id=VISIT.id),
            actor=make_user(Role.BACK_OFFICE),
        )
    with pytest.raises(NotFoundError):
        await service.create(
            CreateActivity(account_id=new_id(), activity_type_id=VISIT.id), actor=rep
        )

    delegated = await service.create(
        CreateActivity(account_id=account_id, activity_type_id=VISIT.id, owner_id=rep.id),
        actor=manager,
    )
    assert delegated.activity.owner_id == rep.id and delegated.activity.created_by == manager.id


async def test_lifecycle_commands_with_audit_and_summary(
    uow: FakeUnitOfWork, rep: User, account_id: UUID, service: ActivityService
) -> None:
    planned = (
        await service.create(
            CreateActivity(
                account_id=account_id,
                activity_type_id=VISIT.id,
                status=ActivityStatus.PLANNED,
                scheduled_at=NOW + timedelta(days=1),
            ),
            actor=rep,
        )
    ).activity
    uow.committed_events.clear()

    moved = await service.reschedule(
        planned.id, RescheduleActivity(1, NOW + timedelta(days=2)), actor=rep
    )
    assert moved.scheduled_at == NOW + timedelta(days=2) and moved.version == 2
    assert uow.committed_events[-1].action == "activity.rescheduled"
    assert (
        uow.committed_events[-1].changes["scheduled_at"]["before"]
        == (NOW + timedelta(days=1)).isoformat()
    )

    done = await service.complete(
        planned.id,
        CompleteActivity(
            2,
            outcome=ActivityOutcome.POSITIVE,
            next_action=NextAction(activity_type_id=CALL.id, scheduled_at=NOW + timedelta(days=7)),
        ),
        actor=rep,
    )
    assert done.activity.status is ActivityStatus.DONE and done.activity.done_at == NOW
    assert done.next_activity is not None
    assert [e.action for e in uow.committed_events[-2:]] == [
        "activity.completed",
        "activity.created",
    ]
    account = await uow.accounts.get(account_id)
    assert account is not None
    assert account.last_contact_at == NOW + timedelta(days=2)  # the visit's scheduled time
    assert account.next_activity_at == NOW + timedelta(days=7)

    with pytest.raises(InvalidActivityTransitionError):
        await service.cancel(planned.id, CancelActivity(3, "x"), actor=rep)

    follow_up = done.next_activity
    cancelled = await service.cancel(follow_up.id, CancelActivity(1, "Cliente cerrado"), actor=rep)
    assert cancelled.status is ActivityStatus.CANCELLED
    assert uow.committed_events[-1].action == "activity.cancelled"
    account = await uow.accounts.get(account_id)
    assert account is not None and account.next_activity_at is None


async def test_update_respects_the_edit_window(
    uow: FakeUnitOfWork, rep: User, manager: User, account_id: UUID
) -> None:
    service = ActivityService(uow, clock=FrozenClock)
    visit = (
        await service.create(
            CreateActivity(account_id=account_id, activity_type_id=VISIT.id), actor=rep
        )
    ).activity

    updated = await service.update(
        visit.id, UpdateActivity(1, {"subject": "Primera visita", "status": "planned"}), actor=rep
    )
    assert updated.subject == "Primera visita" and updated.status is ActivityStatus.DONE
    assert uow.committed_events[-1].action == "activity.updated"
    assert set(uow.committed_events[-1].changes) == {"subject"}

    class LaterClock(FrozenClock):
        frozen = NOW + timedelta(days=10)

    later = ActivityService(uow, clock=LaterClock)
    with pytest.raises(ActivityLockedError):
        await later.update(visit.id, UpdateActivity(2, {"notes": "x"}), actor=rep)
    edited = await later.update(visit.id, UpdateActivity(2, {"notes": "x"}), actor=manager)
    assert edited.notes == "x"

    stranger = make_user(Role.SALES_REP)
    with pytest.raises(NotFoundError):
        await service.get(visit.id, actor=stranger)
