from uuid import UUID

import pytest

from app.application.accounts.commands import (
    AddressInput,
    AssignAccount,
    CreateAccount,
    ReplaceAddresses,
    UpdateAccount,
)
from app.application.accounts.service import AccountService
from app.domain.accounts.entities import PhoneEntry
from app.domain.accounts.errors import (
    AssignmentForbiddenError,
    OwnerNotSalesRepError,
    TaxIdAlreadyExistsError,
)
from app.domain.reference.entities import AccountType, Brand
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
NEUROLOGY = Division(id=new_id(), code="neurology", name_es="Neurología", sort_order=50)
IVF = AccountType(new_id(), "ivf_clinic", "Clínica FIV", 10, False, True)
CENTRO = Territory.create(name="Centro", provinces=frozenset({"28", "45"}))
NORTE = Territory.create(name="Norte", provinces=frozenset({"48"}))


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
    uow.divisions = InMemoryDivisionRepository([VASCULAR, NEUROLOGY])
    uow.reference = InMemoryReferenceReadRepository(account_types=[IVF])
    uow.territories.rows[CENTRO.id] = CENTRO
    uow.territories.rows[NORTE.id] = NORTE
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


def create(name: str = "Tambre", province: str = "28", **details: object) -> CreateAccount:
    return CreateAccount(name=name, account_type_id=IVF.id, province_code=province, details=details)


async def test_rep_creates_minimum_account_with_defaults(uow: FakeUnitOfWork, rep: User) -> None:
    view = await AccountService(uow).create(create(), actor=rep)

    assert view.account.territory_id == CENTRO.id
    assert view.account.owner_id == rep.id
    assert view.territory_mismatch is False
    assert uow.actions() == ["account.created"]
    changes = uow.committed_events[0].changes
    assert changes["owner_id"] == {"before": None, "after": str(rep.id)}


async def test_manager_creation_resolves_single_compatible_rep(
    uow: FakeUnitOfWork, rep: User, manager: User
) -> None:
    other = make_user(Role.SALES_REP, territories={CENTRO.id}, divisions={NEUROLOGY.id})
    uow.users.rows[other.id] = other

    vascular = await AccountService(uow).create(create(division_ids=[VASCULAR.id]), actor=manager)
    ambiguous = await AccountService(uow).create(create(name="Otro"), actor=manager)
    no_territory = await AccountService(uow).create(
        create(name="Canarias", province="35"), actor=manager
    )

    assert vascular.account.owner_id == rep.id
    assert ambiguous.account.owner_id is None
    assert no_territory.account.territory_id is None and no_territory.account.owner_id is None


async def test_create_validates_references_and_tax_id(uow: FakeUnitOfWork, rep: User) -> None:
    service = AccountService(uow)
    with pytest.raises(UnknownReferenceError):
        await service.create(create(division_ids=[new_id()]), actor=rep)
    with pytest.raises(UnknownReferenceError):
        await service.create(create(brand_ids=[new_id()]), actor=rep)
    with pytest.raises(UnknownReferenceError):
        await service.create(
            CreateAccount(name="X", account_type_id=new_id(), province_code="28"), actor=rep
        )
    uow.brands.rows[new_id()] = Brand(id=new_id(), code="hadeco", name="Hadeco", is_own=True)
    first = await service.create(create(tax_id="B12345674"), actor=rep)
    with pytest.raises(TaxIdAlreadyExistsError) as info:
        await service.create(create(name="Dup", tax_id="b-12345674"), actor=rep)
    assert info.value.existing_account_id == first.account.id


async def test_get_and_update_are_scoped(uow: FakeUnitOfWork, rep: User, manager: User) -> None:
    service = AccountService(uow)
    far = await service.create(create(name="Far", province="48"), actor=manager)
    near = await service.create(create(name="Near"), actor=manager)

    with pytest.raises(NotFoundError):
        await service.get(far.account.id, actor=rep)
    with pytest.raises(NotFoundError):
        await service.update(far.account.id, UpdateAccount(1, {"city": "Bilbao"}), actor=rep)

    updated = await service.update(
        near.account.id,
        UpdateAccount(1, {"city": " Madrid ", "province_code": "08", "notes": None}),
        actor=rep,
    )
    assert updated.account.city == "Madrid"
    assert updated.account.version == 2
    assert updated.territory_mismatch is True
    assert uow.actions()[-1] == "account.updated"
    assert set(uow.committed_events[-1].changes) == {"city", "province_code"}

    deactivated = await service.update(
        near.account.id, UpdateAccount(2, {"is_active": False}), actor=manager
    )
    assert deactivated.account.is_active is False
    assert uow.actions()[-1] == "account.deactivated"


async def test_patch_rejects_assignment_fields_and_back_office_limits(
    uow: FakeUnitOfWork, rep: User, manager: User
) -> None:
    service = AccountService(uow)
    account = (await service.create(create(), actor=rep)).account
    back_office = make_user(Role.BACK_OFFICE)

    with pytest.raises(AssignmentForbiddenError):
        await service.update(account.id, UpdateAccount(1, {"owner_id": None}), actor=manager)
    with pytest.raises(PermissionDeniedError):
        await service.update(account.id, UpdateAccount(1, {"notes": "x"}), actor=back_office)
    view = await service.update(
        account.id,
        UpdateAccount(
            1,
            {
                "customer_code": "C-1",
                "phones": [PhoneEntry.create(label="Centralita", number="911234567")],
            },
        ),
        actor=back_office,
    )
    assert view.account.customer_code == "C-1"
    assert [p.number for p in view.account.phones] == ["+34911234567"]


async def test_assignment_rules(uow: FakeUnitOfWork, rep: User, manager: User) -> None:
    service = AccountService(uow)
    account = (await service.create(create(), actor=manager)).account
    other_rep = make_user(Role.SALES_REP, territories={NORTE.id})
    uow.users.rows[other_rep.id] = other_rep

    with pytest.raises(AssignmentForbiddenError):
        await service.assign(account.id, AssignAccount(1, owner_id=rep.id), actor=rep)
    with pytest.raises(OwnerNotSalesRepError):
        await service.assign(account.id, AssignAccount(1, owner_id=manager.id), actor=manager)
    with pytest.raises(UnknownReferenceError):
        await service.assign(account.id, AssignAccount(1, territory_id=new_id()), actor=manager)

    view = await service.assign(
        account.id, AssignAccount(1, owner_id=other_rep.id, territory_id=NORTE.id), actor=manager
    )
    assert view.account.owner_id == other_rep.id
    assert view.account.territory_id == NORTE.id
    assert view.territory_mismatch is True
    assert uow.actions()[-1] == "account.assigned"
    assert uow.committed_events[-1].changes["owner_id"]["after"] == str(other_rep.id)


async def test_replace_addresses_is_audited(uow: FakeUnitOfWork, rep: User) -> None:
    service = AccountService(uow)
    account = (await service.create(create(), actor=rep)).account
    address = AddressInput("Laboratorio", "C/ 1", "28001", "Madrid", "28")

    view = await service.replace_addresses(account.id, ReplaceAddresses(1, [address]), actor=rep)

    assert [a.label for a in view.account.addresses] == ["Laboratorio"]
    assert uow.actions()[-1] == "account.addresses_replaced"
    assert uow.committed_events[-1].changes["addresses"]["before"] == []
    unchanged = await service.replace_addresses(
        account.id, ReplaceAddresses(2, [address]), actor=rep
    )
    assert unchanged.account.version == 3
    assert uow.actions().count("account.addresses_replaced") == 1
