from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.accounts.queries import AccountFilters, AccountQueries
from app.application.shared.pagination import PageParams, SortField
from app.domain.accounts.entities import AdditionalAddress
from app.domain.accounts.errors import TaxIdAlreadyExistsError
from app.domain.contacts.entities import Contact
from app.domain.shared.errors import ConcurrentModificationError
from app.domain.shared.policies import ScopeFilter, VisibilityPolicy, resolve_scope
from app.domain.users.entities import User
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.contacts import SqlAlchemyContactRepository
from app.infrastructure.db.seed import reference_id
from tests.integration.repositories.conftest import (
    HOSPITAL_ID,
    NEUROLOGY_ID,
    VASCULAR_ID,
    World,
    make_account,
)

pytestmark = pytest.mark.integration


def page(**overrides: object) -> PageParams:
    values: dict[str, object] = {"page": 1, "page_size": 50, "sort": [SortField("name", False)]}
    values.update(overrides)
    return PageParams(**values)  # type: ignore[arg-type]


async def test_add_get_and_save_round_trip(
    accounts: SqlAlchemyAccountRepository, world: World
) -> None:
    account = make_account(
        "Clínica Tambre",
        territory_id=world.centro.id,
        owner_id=world.rep.id,
        divisions=frozenset({VASCULAR_ID}),
        tax_id="B12345674",
        phone="911234567",
        brand_ids=[reference_id("brands", "hadeco")],
    )
    account.replace_addresses(
        [
            AdditionalAddress.create(
                label="Laboratorio",
                street="C/ 1",
                postal_code="28001",
                city="Madrid",
                province_code="28",
            )
        ]
    )
    await accounts.add(account)

    loaded = await accounts.get(account.id)
    assert loaded is not None
    assert loaded.tax_id == "B12345674"
    assert loaded.division_ids == frozenset({VASCULAR_ID})
    assert loaded.brand_ids == frozenset({reference_id("brands", "hadeco")})
    assert [a.label for a in loaded.addresses] == ["Laboratorio"]
    assert loaded.version == 1

    loaded.update_details({"city": "Madrid", "division_ids": [NEUROLOGY_ID], "brand_ids": []})
    loaded.replace_addresses([])
    await accounts.save(loaded, expected_version=1)
    reloaded = await accounts.get(account.id)
    assert reloaded is not None
    assert reloaded.version == 2
    assert reloaded.city == "Madrid"
    assert reloaded.division_ids == frozenset({NEUROLOGY_ID})
    assert reloaded.brand_ids == frozenset()
    assert reloaded.addresses == []

    with pytest.raises(ConcurrentModificationError):
        await accounts.save(reloaded, expected_version=1)


async def test_duplicate_tax_id_is_rejected(
    accounts: SqlAlchemyAccountRepository, world: World, session: AsyncSession
) -> None:
    first = make_account("A", territory_id=None, owner_id=None, tax_id="B12345674")
    await accounts.add(first)
    await session.commit()

    assert await accounts.find_id_by_tax_id("B12345674") == first.id
    second = make_account("B", territory_id=None, owner_id=None, tax_id="b-12345674")
    with pytest.raises(TaxIdAlreadyExistsError):
        await accounts.add(second)


async def test_get_respects_scope(accounts: SqlAlchemyAccountRepository, world: World) -> None:
    in_scope = make_account(
        "In", territory_id=world.centro.id, owner_id=None, divisions=frozenset({VASCULAR_ID})
    )
    out_of_scope = make_account(
        "Out", territory_id=world.centro.id, owner_id=None, divisions=frozenset({NEUROLOGY_ID})
    )
    await accounts.add(in_scope)
    await accounts.add(out_of_scope)
    scope = ScopeFilter.for_user(world.rep, resolve_scope(world.rep, [world.centro, world.norte]))

    assert await accounts.get(in_scope.id, scope=scope) is not None
    assert await accounts.get(out_of_scope.id, scope=scope) is None
    assert await accounts.get(out_of_scope.id, scope=None) is not None


async def _matrix(accounts: SqlAlchemyAccountRepository, world: World) -> dict[str, UUID]:
    rows = {
        "owned_far": make_account(
            "Owned far",
            province="48",
            territory_id=world.norte.id,
            owner_id=world.rep.id,
            divisions=frozenset({NEUROLOGY_ID}),
        ),
        "territory_division": make_account(
            "Territory division",
            territory_id=world.centro.id,
            owner_id=world.other_rep.id,
            divisions=frozenset({VASCULAR_ID, NEUROLOGY_ID}),
        ),
        "territory_other_division": make_account(
            "Territory other division",
            territory_id=world.centro.id,
            owner_id=None,
            divisions=frozenset({NEUROLOGY_ID}),
        ),
        "territory_no_division": make_account(
            "Territory no division", territory_id=world.centro.id, owner_id=None
        ),
        "other_territory": make_account(
            "Other territory",
            province="48",
            territory_id=world.norte.id,
            owner_id=None,
            divisions=frozenset({VASCULAR_ID}),
        ),
        "no_territory": make_account(
            "No territory", province="35", territory_id=None, owner_id=None
        ),
    }
    for account in rows.values():
        await accounts.add(account)
    return {key: account.id for key, account in rows.items()}


async def test_policy_and_sql_predicate_agree(
    accounts: SqlAlchemyAccountRepository, world: World, session: AsyncSession
) -> None:
    ids = await _matrix(accounts, world)
    territories = [world.centro, world.norte]
    queries = AccountQueries(session)

    async def visible_by_sql(user: User) -> set[UUID]:
        scope = ScopeFilter.for_user(user, resolve_scope(user, territories))
        result = await queries.list_page(page(), AccountFilters(is_active=None), scope)
        return {item.id for item in result.items}

    async def visible_by_policy(user: User) -> set[UUID]:
        scope = resolve_scope(user, territories)
        visible: set[UUID] = set()
        for account_id in ids.values():
            account = await accounts.get(account_id)
            assert account is not None
            if VisibilityPolicy.can_read(user, scope, account):
                visible.add(account_id)
        return visible

    for user in (world.rep, world.other_rep, world.manager, world.back_office):
        assert await visible_by_sql(user) == await visible_by_policy(user), user.full_name

    rep_visible = await visible_by_sql(world.rep)
    assert rep_visible == {
        ids["owned_far"],
        ids["territory_division"],
        ids["territory_no_division"],
    }
    assert await visible_by_sql(world.manager) == set(ids.values())


async def test_list_filters_sorting_and_summary_columns(
    accounts: SqlAlchemyAccountRepository, world: World, session: AsyncSession
) -> None:
    tambre = make_account(
        "Clínica Tambre",
        territory_id=world.centro.id,
        owner_id=world.rep.id,
        city="Madrid",
        tax_id="B12345674",
        divisions=frozenset({VASCULAR_ID}),
    )
    hospital = make_account(
        "Hospital La Paz",
        province="08",
        territory_id=world.centro.id,
        owner_id=None,
        city="Barcelona",
    )
    hospital.account_type_id = HOSPITAL_ID
    inactive = make_account("Zeta inactiva", territory_id=world.centro.id, owner_id=world.rep.id)
    inactive.deactivate()
    for account in (tambre, hospital, inactive):
        await accounts.add(account)
    contacts = SqlAlchemyContactRepository(session)
    await contacts.add(
        Contact.create(account_id=tambre.id, first_name="Ana", last_name="Pérez", is_primary=True)
    )
    queries = AccountQueries(session)

    default = await queries.list_page(page(), AccountFilters(), None)
    assert [i.name for i in default.items] == ["Clínica Tambre", "Hospital La Paz"]
    assert default.total == 2
    tambre_row = default.items[0]
    assert tambre_row.primary_contact_name == "Ana Pérez"
    assert tambre_row.territory_mismatch is False
    assert default.items[1].territory_mismatch is True  # province 08 is not in Centro

    with_inactive = await queries.list_page(page(), AccountFilters(is_active=None), None)
    assert with_inactive.total == 3

    by_q = await queries.list_page(page(), AccountFilters(q="tam"), None)
    assert [i.name for i in by_q.items] == ["Clínica Tambre"]
    by_city = await queries.list_page(page(), AccountFilters(q="barce"), None)
    assert [i.name for i in by_city.items] == ["Hospital La Paz"]
    by_tax = await queries.list_page(page(), AccountFilters(q="b-12345674"), None)
    assert [i.name for i in by_tax.items] == ["Clínica Tambre"]
    by_type = await queries.list_page(page(), AccountFilters(account_type_id=HOSPITAL_ID), None)
    assert by_type.total == 1
    by_division = await queries.list_page(page(), AccountFilters(division_id=VASCULAR_ID), None)
    assert [i.id for i in by_division.items] == [tambre.id]
    unassigned = await queries.list_page(page(), AccountFilters(unassigned=True), None)
    assert [i.id for i in unassigned.items] == [hospital.id]
    by_owner = await queries.list_page(page(), AccountFilters(owner_id=world.rep.id), None)
    assert [i.id for i in by_owner.items] == [tambre.id]

    desc = await queries.list_page(page(sort=[SortField("city", True)]), AccountFilters(), None)
    assert [i.city for i in desc.items] == ["Madrid", "Barcelona"]
    paged = await queries.list_page(page(page=2, page_size=1), AccountFilters(), None)
    assert [i.name for i in paged.items] == ["Hospital La Paz"]
    assert paged.total == 2
