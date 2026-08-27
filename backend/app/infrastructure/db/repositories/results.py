"""Typed helpers over SQLAlchemy results."""

from typing import Any, cast

from sqlalchemy import CursorResult, Result


def rowcount_of(result: Result[Any]) -> int:
    """Rows affected by an UPDATE/DELETE executed through the session."""
    return int(cast(CursorResult[Any], result).rowcount)
