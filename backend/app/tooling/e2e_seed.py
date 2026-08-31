"""Seed an administrator for end-to-end tests (idempotent).

Usage: python -m app.tooling.e2e_seed
Env:   E2E_ADMIN_EMAIL (default admin@quermed.com), E2E_ADMIN_PASSWORD (required, >= 12 chars)

The production first-admin path is `app.tooling.bootstrap_admin`; this wrapper only
keeps the E2E-specific defaults and reuses the same `ensure_admin` logic.
"""

import asyncio
import os
import sys

from app.tooling.bootstrap_admin import run


def main() -> int:
    email = os.environ.get("E2E_ADMIN_EMAIL", "admin@quermed.com")
    password = os.environ.get("E2E_ADMIN_PASSWORD")
    if not password:
        sys.stderr.write("E2E_ADMIN_PASSWORD is required\n")
        return 2
    outcome = asyncio.run(run(email, password))
    sys.stdout.write(f"admin {email} {outcome}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
