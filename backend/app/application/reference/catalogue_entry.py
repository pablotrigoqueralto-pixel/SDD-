"""One rule shared by every administrator-editable catalogue: adding an option that is
already there reuses it instead of creating a second spelling of the same thing.

A row matches when the requested name resolves to its `code` OR equals its `name_es`
unaccented and case-folded (see `catalogue_match` in the repositories). Both halves are
needed: seeded rows carry hand-written English codes their Spanish names never derive
("management" for "Gerencia"), and a row renamed after creation no longer matches its
own code either.
"""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Protocol


class CatalogueOutcome(StrEnum):
    """What happened to the entry the administrator asked for."""

    CREATED = "created"
    REUSED = "reused"
    REACTIVATED = "reactivated"


class ActivatableEntry(Protocol):
    """The shape every catalogue entry shares (job title, specialty, loss reason, …)."""

    is_active: bool

    def activate(self) -> None: ...


async def reuse_or_reactivate[T: ActivatableEntry](
    existing: T | None,
    *,
    reactivate: Callable[[T], Awaitable[None]],
) -> tuple[T, CatalogueOutcome] | None:
    """Decide what an existing row means for a creation request.

    `None` means "nothing matched, go ahead and create". Otherwise the caller gets the
    row to return and what to tell the administrator; `reactivate` is only awaited when
    the row was inactive, and is where the caller saves it and records the audit event.
    """
    if existing is None:
        return None
    if existing.is_active:
        return existing, CatalogueOutcome.REUSED
    existing.activate()
    await reactivate(existing)
    return existing, CatalogueOutcome.REACTIVATED
