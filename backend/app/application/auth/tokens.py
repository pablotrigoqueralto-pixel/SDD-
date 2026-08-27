"""Opaque refresh tokens: random secret handed to the client, SHA-256 hash stored."""

import base64
import hashlib
import secrets

REFRESH_TOKEN_BYTES = 32


def generate_refresh_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(REFRESH_TOKEN_BYTES)).decode().rstrip("=")


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
