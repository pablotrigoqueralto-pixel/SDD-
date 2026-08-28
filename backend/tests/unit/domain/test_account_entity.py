from uuid import UUID

import pytest

from app.domain.accounts.entities import Account, AdditionalAddress
from app.domain.accounts.errors import (
    AddressLabelDuplicatedError,
    InvalidTaxIdError,
    TooManyAddressesError,
)
from app.domain.accounts.owner_resolver import resolve_owner
from app.domain.shared.ids import new_id
from app.domain.territories.errors import InvalidProvinceError
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email

TYPE_ID = new_id()
CENTRO = new_id()
VASCULAR = new_id()
NEUROLOGY = new_id()


def address(label: str) -> AdditionalAddress:
    return AdditionalAddress.create(
        label=label, street="Calle 1", postal_code="28001", city="Madrid", province_code="28"
    )


def make_user(
    role: Role,
    *,
    territories: set[UUID] | None = None,
    divisions: set[UUID] | None = None,
    is_active: bool = True,
) -> User:
    user = User.create(
        email=Email(f"{new_id()}@quermed.com"),
        full_name="U",
        role=role,
        password_hash="h",
        territory_ids=frozenset(territories or set()),
        division_ids=frozenset(divisions or set()),
    )
    user.is_active = is_active
    return user


def test_minimum_account_has_defaults() -> None:
    account = Account.create(
        name="  Clínica Tambre ",
        account_type_id=TYPE_ID,
        province_code="28",
        territory_id=CENTRO,
        owner_id=None,
    )

    assert account.name == "Clínica Tambre"
    assert account.territory_id == CENTRO
    assert account.owner_id is None
    assert account.tax_id is None
    assert account.division_ids == frozenset()
    assert account.addresses == []
    assert account.is_active is True
    assert account.version == 1


def test_create_with_details_normalises_values() -> None:
    account = Account.create(
        name="Tambre",
        account_type_id=TYPE_ID,
        province_code="28",
        territory_id=CENTRO,
        owner_id=None,
        details={
            "tax_id": "b-12345674",
            "phone": "91 123 45 67",
            "postal_code": " 28001",
            "email": "Info@Tambre.ES",
            "website": "  ",
            "division_ids": [VASCULAR],
            "owner_id": new_id(),  # ignored: assignment goes through assign()
        },
    )

    assert account.tax_id == "B12345674"
    assert account.phone == "+34911234567"
    assert account.postal_code == "28001"
    assert account.email == "info@tambre.es"
    assert account.website is None
    assert account.division_ids == frozenset({VASCULAR})
    assert account.owner_id is None


def test_invalid_province_and_tax_id_are_rejected() -> None:
    with pytest.raises(InvalidProvinceError):
        Account.create(
            name="X", account_type_id=TYPE_ID, province_code="99", territory_id=None, owner_id=None
        )
    account = Account.create(
        name="X", account_type_id=TYPE_ID, province_code="28", territory_id=None, owner_id=None
    )
    with pytest.raises(InvalidTaxIdError):
        account.update_details({"tax_id": "B1234567X"})


def test_addresses_require_unique_labels_and_a_maximum() -> None:
    account = Account.create(
        name="X", account_type_id=TYPE_ID, province_code="28", territory_id=None, owner_id=None
    )
    account.replace_addresses([address("Laboratorio"), address("Almacén")])
    assert [a.label for a in account.addresses] == ["Laboratorio", "Almacén"]

    with pytest.raises(AddressLabelDuplicatedError) as duplicated:
        account.replace_addresses([address("Laboratorio"), address("laboratorio")])
    assert duplicated.value.errors[0]["code"] == "address_label_duplicated"

    with pytest.raises(TooManyAddressesError) as too_many:
        account.replace_addresses([address(f"Sede {i}") for i in range(11)])
    assert too_many.value.errors[0]["code"] == "too_many_addresses"


def test_assignment_and_territory_mismatch() -> None:
    account = Account.create(
        name="X", account_type_id=TYPE_ID, province_code="28", territory_id=CENTRO, owner_id=None
    )
    assert not account.territory_mismatch(CENTRO)

    account.update_details({"province_code": "08"})
    assert account.territory_id == CENTRO
    assert account.territory_mismatch(new_id())

    other_owner = new_id()
    account.assign(owner_id=other_owner, territory_id=None)
    assigned: tuple[object, object] = (account.owner_id, account.territory_id)
    assert assigned == (other_owner, None)
    account.deactivate()
    assert account.snapshot()["is_active"] is False


def test_owner_is_the_creator_when_they_are_a_rep() -> None:
    rep = make_user(Role.SALES_REP, territories={CENTRO}, divisions={VASCULAR})

    assert (
        resolve_owner(
            creator=rep,
            territory_id=new_id(),
            account_division_ids=frozenset({NEUROLOGY}),
            territory_reps=[],
        )
        == rep.id
    )


def test_manager_creation_picks_the_only_compatible_rep() -> None:
    manager = make_user(Role.SALES_MANAGER)
    vascular_rep = make_user(Role.SALES_REP, territories={CENTRO}, divisions={VASCULAR})
    neurology_rep = make_user(Role.SALES_REP, territories={CENTRO}, divisions={NEUROLOGY})
    inactive = make_user(
        Role.SALES_REP, territories={CENTRO}, divisions={VASCULAR}, is_active=False
    )
    reps = [vascular_rep, neurology_rep, inactive, manager]

    assert (
        resolve_owner(
            creator=manager,
            territory_id=CENTRO,
            account_division_ids=frozenset({VASCULAR}),
            territory_reps=reps,
        )
        == vascular_rep.id
    )
    # No divisions declared: both active reps qualify -> ambiguous.
    assert (
        resolve_owner(
            creator=manager,
            territory_id=CENTRO,
            account_division_ids=frozenset(),
            territory_reps=reps,
        )
        is None
    )
    assert (
        resolve_owner(
            creator=manager,
            territory_id=None,
            account_division_ids=frozenset(),
            territory_reps=reps,
        )
        is None
    )
