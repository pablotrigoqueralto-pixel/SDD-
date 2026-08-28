"""Fixtures shared by repository integration tests: seeded masters, territories, users."""

from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.accounts.entities import Account
from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.territories import SqlAlchemyTerritoryRepository
from app.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.db.seed import DIVISIONS, reference_id, run_seed

pytestmark = pytest.mark.integration

VASCULAR_ID: UUID = next(d.id for d in DIVISIONS if d.code == "vascular")
NEUROLOGY_ID: UUID = next(d.id for d in DIVISIONS if d.code == "neurology")
IVF_CLINIC_ID: UUID = reference_id("account_types", "ivf_clinic")
HOSPITAL_ID: UUID = reference_id("account_types", "public_hospital")


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


@dataclass
class World:
    """Two territories and the users the visibility matrix needs."""

    centro: Territory
    norte: Territory
    rep: User  # Centro, vascular
    other_rep: User  # Norte, neurology
    manager: User
    back_office: User


@pytest.fixture
async def world(session: AsyncSession) -> World:
    territories = SqlAlchemyTerritoryRepository(session)
    users = SqlAlchemyUserRepository(session)
    centro = Territory.create(name="Centro", provinces=frozenset({"28", "45"}))
    norte = Territory.create(name="Norte", provinces=frozenset({"48", "20"}))
    await territories.add(centro)
    await territories.add(norte)

    def make(role: Role, name: str, territory: Territory | None, division: UUID | None) -> User:
        return User.create(
            email=Email(f"{name}@quermed.com"),
            full_name=name,
            role=role,
            password_hash="h",
            territory_ids=frozenset({territory.id}) if territory else frozenset(),
            division_ids=frozenset({division}) if division else frozenset(),
        )

    rep = make(Role.SALES_REP, "rep", centro, VASCULAR_ID)
    other_rep = make(Role.SALES_REP, "other", norte, NEUROLOGY_ID)
    manager = make(Role.SALES_MANAGER, "manager", None, None)
    back_office = make(Role.BACK_OFFICE, "backoffice", None, None)
    for user in (rep, other_rep, manager, back_office):
        await users.add(user)
    await session.commit()
    return World(centro, norte, rep, other_rep, manager, back_office)


def make_account(
    name: str,
    *,
    province: str = "28",
    territory_id: UUID | None,
    owner_id: UUID | None,
    divisions: frozenset[UUID] = frozenset(),
    **details: object,
) -> Account:
    account = Account.create(
        name=name,
        account_type_id=IVF_CLINIC_ID,
        province_code=province,
        territory_id=territory_id,
        owner_id=owner_id,
        details={"division_ids": divisions, **details},
    )
    return account


@pytest.fixture
def accounts(session: AsyncSession) -> SqlAlchemyAccountRepository:
    return SqlAlchemyAccountRepository(session)
