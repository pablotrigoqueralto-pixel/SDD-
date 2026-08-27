"""Audit events: explicit, typed, redacted diffs recorded by application services."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

REDACTED = "[redacted]"
DEFAULT_REDACTED_FIELDS: frozenset[str] = frozenset({"password_hash", "token_hash"})

type JsonValue = str | int | float | bool | list["JsonValue"] | dict[str, "JsonValue"] | None
type FieldChange = dict[str, JsonValue]


@dataclass(frozen=True)
class AuditEvent:
    entity_type: str
    entity_id: UUID | None
    action: str
    changes: dict[str, FieldChange] = field(default_factory=dict)
    actor_id: UUID | None = None
    trace_id: str | None = None
    occurred_at: datetime | None = None


class AuditLogWriter(Protocol):
    async def write(self, events: list[AuditEvent]) -> None: ...


def to_jsonable(value: Any) -> JsonValue:
    """Convert domain values to JSON-serialisable primitives for the audit payload."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, set | frozenset):
        return sorted(to_jsonable(item) for item in value)  # type: ignore[type-var]
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if hasattr(value, "value"):
        return to_jsonable(value.value)
    return str(value)


def diff_fields(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    redact: frozenset[str] = DEFAULT_REDACTED_FIELDS,
) -> dict[str, FieldChange]:
    """Return {field: {before, after}} for fields whose value changed; redacted ones masked."""
    changes: dict[str, FieldChange] = {}
    for key in sorted(set(before) | set(after)):
        old, new = to_jsonable(before.get(key)), to_jsonable(after.get(key))
        if old == new:
            continue
        if key in redact:
            changes[key] = {"before": REDACTED, "after": REDACTED}
        else:
            changes[key] = {"before": old, "after": new}
    return changes
