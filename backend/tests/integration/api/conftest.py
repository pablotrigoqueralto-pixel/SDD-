"""API integration fixtures: real app + real PostgreSQL session (rolled back per test)."""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.api.rate_limit import limiter
from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from app.infrastructure.db.repositories.territories import SqlAlchemyTerritoryRepository
from app.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.db.seed import DIVISIONS, seed_divisions
from app.infrastructure.db.session import get_session
from app.infrastructure.settings import Settings
from app.main import create_app
from tests.unit.fakes.security import FakePasswordHasher

pytestmark = pytest.mark.integration

PASSWORD = "correct-horse-battery"
VASCULAR_ID: UUID = next(d.id for d in DIVISIONS if d.code == "vascular")
NEUROLOGY_ID: UUID = next(d.id for d in DIVISIONS if d.code == "neurology")


async def _always_ready() -> bool:
    return True


@pytest.fixture
async def app(settings: Settings, session: AsyncSession, engine: AsyncEngine) -> FastAPI:
    await seed_divisions(engine)  # idempotent, outside the test transaction
    app = create_app(settings, readiness_probe=_always_ready)
    app.state.hasher = FakePasswordHasher()  # argon2 is slow; hashing is covered elsewhere

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    limiter.reset()
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testclient") as http:
        yield http


class Users:
    """Creates users straight in the database and issues access tokens for them."""

    def __init__(self, app: FastAPI, session: AsyncSession) -> None:
        self._app = app
        self._session = session
        self._repo = SqlAlchemyUserRepository(session)

    async def create(
        self,
        role: Role,
        *,
        email: str | None = None,
        full_name: str | None = None,
        is_active: bool = True,
        territory_ids: frozenset[UUID] = frozenset(),
        division_ids: frozenset[UUID] = frozenset(),
        password: str = PASSWORD,
    ) -> User:
        user = User.create(
            email=Email(email or f"{role.value}@quermed.com"),
            full_name=full_name or f"{role.value.replace('_', ' ').title()} Test",
            role=role,
            password_hash=FakePasswordHasher().hash(password),
            territory_ids=territory_ids,
            division_ids=division_ids,
        )
        user.is_active = is_active
        await self._repo.add(user)
        # Release the savepoint so a request-level rollback cannot wipe fixture data.
        await self._session.commit()
        return user

    def headers(self, user: User) -> dict[str, str]:
        token = self._app.state.codec.issue(user_id=user.id, role=user.role)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def users(app: FastAPI, session: AsyncSession) -> Users:
    return Users(app, session)


@pytest.fixture
async def admin(users: Users) -> User:
    return await users.create(Role.ADMIN)


@pytest.fixture
def admin_headers(users: Users, admin: User) -> dict[str, str]:
    return users.headers(admin)


@pytest.fixture
async def centro(session: AsyncSession) -> Territory:
    territory = Territory.create(name="Centro", provinces=frozenset({"28", "45"}))
    await SqlAlchemyTerritoryRepository(session).add(territory)
    await session.commit()
    return territory
