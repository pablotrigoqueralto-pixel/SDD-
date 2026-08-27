"""Password hashing (argon2id via pwdlib)."""

from typing import Protocol

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hash = PasswordHash((Argon2Hasher(),))

    def hash(self, password: str) -> str:
        return self._hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._hash.verify(password, password_hash)
