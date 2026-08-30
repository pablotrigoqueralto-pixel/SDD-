"""Repository protocol for accounts (implemented in infrastructure)."""

from typing import Protocol
from uuid import UUID

from app.domain.accounts.entities import Account
from app.domain.shared.policies import ScopeFilter


class AccountRepository(Protocol):
    async def get(self, account_id: UUID, *, scope: ScopeFilter | None = None) -> Account | None:
        """The account when it exists and is inside `scope` (None = unrestricted)."""
        ...

    async def find_id_by_tax_id(self, tax_id: str) -> UUID | None: ...

    async def find_id_by_normalised_name(self, normalised_name: str) -> UUID | None:
        """Exact match after unaccenting, case-folding and collapsing spaces (import matching)."""
        ...

    async def add(self, account: Account) -> None: ...

    async def save(self, account: Account, *, expected_version: int) -> None: ...

    async def refresh_activity_summary(self, account_id: UUID) -> None:
        """Recompute `last_contact_at` / `next_activity_at` from the account's activities."""
        ...
