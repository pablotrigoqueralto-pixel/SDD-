"""Repository protocol for activities (implemented in infrastructure)."""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from app.domain.activities.entities import Activity


class ActivityRepository(Protocol):
    async def get(self, activity_id: UUID) -> Activity | None: ...

    async def add(self, activity: Activity) -> None: ...

    async def save(self, activity: Activity, *, expected_version: int) -> None: ...

    async def contacts_belong_to(self, account_id: UUID, contact_ids: Iterable[UUID]) -> bool:
        """True when every id is a contact of the account (empty set is trivially true)."""
        ...
