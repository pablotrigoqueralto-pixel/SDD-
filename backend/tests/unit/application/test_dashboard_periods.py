"""Period presets: Madrid-calendar bounds and their previous equivalents."""

from datetime import UTC, date, datetime

import pytest

from app.application.dashboard.periods import DashboardPeriod, ResolvedPeriod, resolve_period


def bounds(resolved: ResolvedPeriod) -> tuple[date, date, date, date]:
    return (
        resolved.current_start,
        resolved.current_end,
        resolved.previous_start,
        resolved.previous_end,
    )


class TestMonth:
    def test_mid_month(self) -> None:
        resolved = resolve_period(DashboardPeriod.MONTH, today=date(2026, 8, 31))
        assert bounds(resolved) == (
            date(2026, 8, 1),
            date(2026, 9, 1),
            date(2026, 7, 1),
            date(2026, 8, 1),
        )

    def test_january_compares_to_december(self) -> None:
        resolved = resolve_period(DashboardPeriod.MONTH, today=date(2026, 1, 15))
        assert bounds(resolved) == (
            date(2026, 1, 1),
            date(2026, 2, 1),
            date(2025, 12, 1),
            date(2026, 1, 1),
        )


class TestQuarter:
    def test_third_quarter(self) -> None:
        resolved = resolve_period(DashboardPeriod.QUARTER, today=date(2026, 8, 31))
        assert bounds(resolved) == (
            date(2026, 7, 1),
            date(2026, 10, 1),
            date(2026, 4, 1),
            date(2026, 7, 1),
        )

    def test_first_quarter_compares_to_last_years_fourth(self) -> None:
        resolved = resolve_period(DashboardPeriod.QUARTER, today=date(2026, 2, 10))
        assert bounds(resolved) == (
            date(2026, 1, 1),
            date(2026, 4, 1),
            date(2025, 10, 1),
            date(2026, 1, 1),
        )


class TestYearToDate:
    def test_ytd_compares_same_fraction_of_previous_year(self) -> None:
        resolved = resolve_period(DashboardPeriod.YEAR, today=date(2026, 8, 31))
        assert bounds(resolved) == (
            date(2026, 1, 1),
            date(2026, 9, 1),
            date(2025, 1, 1),
            date(2025, 9, 1),
        )

    def test_ytd_on_leap_day_clamps_previous_year(self) -> None:
        resolved = resolve_period(DashboardPeriod.YEAR, today=date(2028, 2, 29))
        assert resolved.previous_end == date(2027, 3, 1)


class TestUtcConversion:
    def test_madrid_midnight_becomes_utc_offset(self) -> None:
        resolved = resolve_period(DashboardPeriod.MONTH, today=date(2026, 8, 31))
        # August: Madrid is UTC+2, so the month opens at 22:00 UTC the previous day.
        assert resolved.current_start_utc == datetime(2026, 7, 31, 22, 0, tzinfo=UTC)
        assert resolved.current_end_utc == datetime(2026, 8, 31, 22, 0, tzinfo=UTC)

    def test_winter_offset_is_one_hour(self) -> None:
        resolved = resolve_period(DashboardPeriod.MONTH, today=date(2026, 1, 15))
        assert resolved.current_start_utc == datetime(2025, 12, 31, 23, 0, tzinfo=UTC)

    def test_won_just_before_utc_midnight_counts_in_new_month(self) -> None:
        resolved = resolve_period(DashboardPeriod.MONTH, today=date(2026, 1, 15))
        won_at = datetime(2025, 12, 31, 23, 30, tzinfo=UTC)  # 00:30 Jan 1st in Madrid
        assert resolved.current_start_utc <= won_at < resolved.current_end_utc


class TestDefaultToday:
    def test_today_defaults_to_madrid_calendar(self) -> None:
        resolved = resolve_period(DashboardPeriod.MONTH)
        assert resolved.current_start <= resolved.today < resolved.current_end


@pytest.mark.parametrize("period", list(DashboardPeriod))
def test_half_open_and_contiguous(period: DashboardPeriod) -> None:
    resolved = resolve_period(period, today=date(2026, 5, 20))
    assert resolved.previous_start < resolved.previous_end
    assert resolved.current_start < resolved.current_end
    assert resolved.previous_end <= resolved.current_start
    assert resolved.current_start_utc < resolved.current_end_utc
