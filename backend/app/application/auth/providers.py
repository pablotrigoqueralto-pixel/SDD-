"""Authentication providers. Password today; OIDC (Microsoft Entra ID) can be added later
without touching the login API."""

from dataclasses import dataclass
from typing import Protocol

from app.application.shared.unit_of_work import UnitOfWork
from app.domain.users.entities import User
from app.domain.users.value_objects import Email
from app.infrastructure.security.passwords import PasswordHasher


@dataclass(frozen=True)
class Credentials:
    email: Email
    password: str


@dataclass(frozen=True)
class AuthenticationOutcome:
    user: User | None
    password_matches: bool


class AuthProvider(Protocol):
    async def authenticate(
        self, uow: UnitOfWork, credentials: Credentials
    ) -> AuthenticationOutcome:
        """Return the user matching the credentials and whether the secret matched.

        The user is returned even when the password is wrong so the caller can apply
        lockout rules; it is None when no such user exists.
        """
        ...


class PasswordAuthProvider:
    def __init__(self, hasher: PasswordHasher) -> None:
        self._hasher = hasher

    async def authenticate(
        self, uow: UnitOfWork, credentials: Credentials
    ) -> AuthenticationOutcome:
        user = await uow.users.get_by_email(credentials.email)
        if user is None or user.password_hash is None:
            return AuthenticationOutcome(user=user, password_matches=False)
        matches = self._hasher.verify(credentials.password, user.password_hash)
        return AuthenticationOutcome(user=user, password_matches=matches)
