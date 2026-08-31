"""Period presets on the Madrid calendar with previous-period equivalents (design D3).

All ranges are half-open [start, end). Timestamp columns are filtered with the UTC
conversion of the Madrid-local midnight bounds; date columns use the local dates.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum

from app.application.activities.queries import BUSINESS_TIMEZONE


class DashboardPeriod(StrEnum):
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


@dataclass(frozen=True)
class ResolvedPeriod:
    period: DashboardPeriod
    today: date
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date

    @property
    def current_start_utc(self) -> datetime:
        return _to_utc(self.current_start)

    @property
    def current_end_utc(self) -> datetime:
        return _to_utc(self.current_end)

    @property
    def previous_start_utc(self) -> datetime:
        return _to_utc(self.previous_start)

    @property
    def previous_end_utc(self) -> datetime:
        return _to_utc(self.previous_end)


def resolve_period(period: DashboardPeriod, today: date | None = None) -> ResolvedPeriod:
    if today is None:
        today = datetime.now(tz=BUSINESS_TIMEZONE).date()
    if period is DashboardPeriod.MONTH:
        current_start = today.replace(day=1)
        current_end = _add_months(current_start, 1)
        previous_start = _add_months(current_start, -1)
        previous_end = current_start
    elif period is DashboardPeriod.QUARTER:
        quarter_month = 3 * ((today.month - 1) // 3) + 1
        current_start = date(today.year, quarter_month, 1)
        current_end = _add_months(current_start, 3)
        previous_start = _add_months(current_start, -3)
        previous_end = current_start
    else:
        current_start = date(today.year, 1, 1)
        current_end = today + timedelta(days=1)
        previous_start = date(today.year - 1, 1, 1)
        previous_end = _shift_year(current_end)
    return ResolvedPeriod(
        period=period,
        today=today,
        current_start=current_start,
        current_end=current_end,
        previous_start=previous_start,
        previous_end=previous_end,
    )


def _add_months(anchor: date, months: int) -> date:
    total = anchor.year * 12 + (anchor.month - 1) + months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def _shift_year(day: date) -> date:
    """Same calendar date one year earlier, clamped to the month's length."""
    last_day = monthrange(day.year - 1, day.month)[1]
    return date(day.year - 1, day.month, min(day.day, last_day))


def _to_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=BUSINESS_TIMEZONE).astimezone(UTC)
