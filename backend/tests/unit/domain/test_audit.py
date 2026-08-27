from datetime import UTC, datetime
from uuid import UUID

from app.domain.shared.audit import REDACTED, AuditEvent, diff_fields, to_jsonable
from app.domain.users.roles import Role


def test_diff_omits_unchanged_fields() -> None:
    changes = diff_fields({"a": 1, "b": "x"}, {"a": 1, "b": "y"})

    assert changes == {"b": {"before": "x", "after": "y"}}


def test_diff_redacts_sensitive_fields_only_when_changed() -> None:
    unchanged = diff_fields({"password_hash": "h1"}, {"password_hash": "h1"})
    changed = diff_fields({"password_hash": "h1"}, {"password_hash": "h2"})

    assert unchanged == {}
    assert changed == {"password_hash": {"before": REDACTED, "after": REDACTED}}


def test_diff_serialises_uuids_enums_sets_and_datetimes() -> None:
    first = UUID("00000000-0000-7000-8000-000000000001")
    second = UUID("00000000-0000-7000-8000-000000000002")
    when = datetime(2026, 8, 27, tzinfo=UTC)

    changes = diff_fields(
        {"role": Role.SALES_REP, "territory_ids": frozenset({first}), "at": None},
        {"role": Role.ADMIN, "territory_ids": frozenset({second, first}), "at": when},
    )

    assert changes["role"] == {"before": "sales_rep", "after": "admin"}
    assert changes["territory_ids"] == {"before": [str(first)], "after": [str(first), str(second)]}
    assert changes["at"] == {"before": None, "after": "2026-08-27T00:00:00+00:00"}


def test_diff_handles_added_and_removed_keys() -> None:
    changes = diff_fields({"gone": 1}, {"new": 2})

    assert changes == {"gone": {"before": 1, "after": None}, "new": {"before": None, "after": 2}}


def test_to_jsonable_falls_back_to_str() -> None:
    class Weird:
        def __str__(self) -> str:
            return "weird"

    assert to_jsonable(Weird()) == "weird"


def test_audit_event_defaults() -> None:
    event = AuditEvent(entity_type="user", entity_id=None, action="auth.login_failed")

    assert event.changes == {}
    assert event.actor_id is None
