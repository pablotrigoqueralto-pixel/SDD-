from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.application.accounts.commands import CreateAccount
from app.application.accounts.service import AccountService
from app.application.contacts.commands import ConsentInput, CreateContact, UpdateContact
from app.application.contacts.service import ContactService
from app.application.reference.commands import CreateJobTitle, UpdateJobTitle
from app.application.reference.service import JobTitleService
from app.domain.accounts.entities import PhoneEntry
from app.domain.contacts.entities import ConsentSource, ConsentStatus
from app.domain.contacts.errors import ContactAnonymisedError
from app.domain.reference.entities import AccountType
from app.domain.reference.errors import JobTitleNameAlreadyExistsError
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
NOW = datetime(2026, 8, 28, tzinfo=UTC)


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
    uow.reference = InMemoryReferenceReadRepository(account_types=[IVF])
    uow.territories.rows[CENTRO.id] = CENTRO
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


async def test_create_primary_contact_with_consent(
    uow: FakeUnitOfWork, rep: User, account_id: UUID
) -> None:
    service = ContactService(uow)
    first = await service.create(
        CreateContact(account_id, "Ana", "Pérez", is_primary=True), actor=rep
    )
    second = await service.create(
        CreateContact(
            account_id,
            "Bea",
            "Ruiz",
            details={"email": "bea@x.es", "preferred_channel": "email"},
            is_primary=True,
            consent=ConsentInput(ConsentStatus.GRANTED, NOW, ConsentSource.VERBAL),
        ),
        actor=rep,
    )

    assert second.consent.recorded_by == rep.id
    assert (await uow.contacts.get(first.id)).is_primary is False  # type: ignore[union-attr]
    assert second.is_primary is True
    assert uow.actions() == [
        "contact.created",
        "contact.primary_changed",
        "contact.created",
        "contact.consent_changed",
    ]
    assert uow.committed_events[1].changes["primary_contact_id"]["after"] == str(second.id)


async def test_create_validates_references_and_permissions(
    uow: FakeUnitOfWork, rep: User, account_id: UUID
) -> None:
    service = ContactService(uow)
    with pytest.raises(UnknownReferenceError):
        await service.create(
            CreateContact(account_id, "A", "B", details={"job_title_id": new_id()}), actor=rep
        )
    with pytest.raises(PermissionDeniedError):
        await service.create(CreateContact(account_id, "A", "B"), actor=make_user(Role.BACK_OFFICE))
    with pytest.raises(NotFoundError):
        await service.create(CreateContact(new_id(), "A", "B"), actor=rep)


async def test_reads_log_access_only_for_non_owner_readers(
    uow: FakeUnitOfWork, rep: User, manager: User, account_id: UUID
) -> None:
    service = ContactService(uow)
    contact = await service.create(CreateContact(account_id, "Ana", "Pérez"), actor=rep)
    back_office = make_user(Role.BACK_OFFICE)

    await service.get(contact.id, actor=rep)
    await service.list_for_account(account_id, actor=manager)
    assert uow.personal_data_access.entries == []

    await service.get(contact.id, actor=back_office)
    listed = await service.list_for_account(account_id, actor=back_office)
    assert [c.id for c in listed] == [contact.id]
    assert [(e.user_id, e.contact_id) for e in uow.personal_data_access.entries] == [
        (back_office.id, contact.id),
        (back_office.id, contact.id),
    ]

    stranger = make_user(Role.SALES_REP)
    with pytest.raises(NotFoundError):
        await service.get(contact.id, actor=stranger)


async def test_update_consent_primary_and_anonymise(
    uow: FakeUnitOfWork, rep: User, manager: User, account_id: UUID
) -> None:
    service = ContactService(uow)
    ana = await service.create(
        CreateContact(account_id, "Ana", "Pérez", is_primary=True), actor=rep
    )
    bea = await service.create(CreateContact(account_id, "Bea", "Ruiz"), actor=rep)
    uow.committed_events.clear()

    updated = await service.update(
        bea.id,
        UpdateContact(
            expected_version=1,
            changes={
                "phones": [PhoneEntry.create(label="Móvil", number="612345678")],
                "preferred_channel": "phone",
            },
            is_primary=True,
            consent=ConsentInput(ConsentStatus.DENIED, NOW, ConsentSource.EMAIL),
        ),
        actor=rep,
    )
    assert updated.is_primary and updated.version == 2
    assert updated.consent.status is ConsentStatus.DENIED
    assert (await uow.contacts.get(ana.id)).is_primary is False  # type: ignore[union-attr]
    assert uow.actions() == [
        "contact.primary_changed",
        "contact.updated",
        "contact.consent_changed",
    ]

    with pytest.raises(PermissionDeniedError):
        await service.anonymise(ana.id, expected_version=2, actor=rep)
    anonymised = await service.anonymise(ana.id, expected_version=2, actor=manager)
    assert anonymised.first_name == "Contacto" and anonymised.is_active is False
    event = uow.committed_events[-1]
    assert event.action == "contact.anonymised"
    assert event.changes == {
        "fields": {"cleared": ["first_name", "last_name", "email", "phones", "notes"]}
    }
    assert "Ana" not in str(event.changes)
    with pytest.raises(ContactAnonymisedError):
        await service.update(ana.id, UpdateContact(3, {"notes": "x"}), actor=manager)


async def test_job_title_service(uow: FakeUnitOfWork) -> None:
    service = JobTitleService(uow)
    created = await service.create(CreateJobTitle("Farmacia hospitalaria"), acting_user_id=new_id())
    assert created.code == "farmacia_hospitalaria" and created.sort_order == 10
    with pytest.raises(JobTitleNameAlreadyExistsError):
        await service.create(CreateJobTitle("farmacia hospitalaria"), acting_user_id=new_id())
    updated = await service.update(
        created.id, UpdateJobTitle(1, name="Farmacia", is_active=False), acting_user_id=new_id()
    )
    assert (updated.name_es, updated.is_active, updated.version) == ("Farmacia", False, 2)
    assert uow.actions() == ["job_title.created", "job_title.updated"]
    with pytest.raises(NotFoundError):
        await service.update(new_id(), UpdateJobTitle(1, name="X"), acting_user_id=new_id())
