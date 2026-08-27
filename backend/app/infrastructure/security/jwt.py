"""Access token issuing and verification (HS256 JWT)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.domain.shared.errors import UnauthenticatedError
from app.domain.users.roles import Role

ALGORITHM = "HS256"
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: UUID
    role: Role
    token_id: str
    expires_at: datetime


class AccessTokenCodec:
    def __init__(self, secret: str, ttl_seconds: int, *, clock: Clock = utc_now) -> None:
        self._secret = secret
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock

    @property
    def ttl_seconds(self) -> int:
        return int(self._ttl.total_seconds())

    def issue(self, *, user_id: UUID, role: Role) -> str:
        now = self._clock()
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + self._ttl).timestamp()),
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(payload, self._secret, algorithm=ALGORITHM)

    def verify(self, token: str) -> AccessTokenClaims:
        try:
            # Expiry is checked against the injected clock (testable, single time source).
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                options={"require": ["sub", "role", "exp", "iat", "jti"], "verify_exp": False},
            )
            claims = AccessTokenClaims(
                user_id=UUID(payload["sub"]),
                role=Role(payload["role"]),
                token_id=str(payload["jti"]),
                expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
            )
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise UnauthenticatedError("Invalid or expired access token") from exc
        if claims.expires_at <= self._clock():
            raise UnauthenticatedError("Access token expired")
        return claims
