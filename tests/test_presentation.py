from datetime import UTC, datetime

import pytest

from skyblock_monitor.models import PeriodReport, Snapshot
from skyblock_monitor.presentation import format_report, parse_custom_period


def test_parses_custom_period_in_moscow_time():
    start, end = parse_custom_period("04.09.2026 18:30 - 04.09.2026 21:45")
    assert start == datetime(2026, 9, 4, 15, 30, tzinfo=UTC)
    assert end == datetime(2026, 9, 4, 18, 45, tzinfo=UTC)


def test_rejects_reversed_period():
    with pytest.raises(ValueError, match="раньше"):
        parse_custom_period("05.09.2026 18:30 - 04.09.2026 21:45")


def test_report_has_no_fuel_and_flags_idle_commissions():
    start = Snapshot(1, datetime(2026, 9, 4, tzinfo=UTC), 100, 29, 60_000, 4, 10, 100, 0, 0, 1_000, 50)
    end = Snapshot(1, datetime(2026, 9, 4, 1, tzinfo=UTC), 20_100, 29, 60_000, 4, 10, 500, 0, 0, 2_000, 50)
    report = PeriodReport(start, end, 20_000, 0, 400, 0, 0, 1_000)

    text = format_report("VenomKillerIRL", "Papaya", report)

    assert "Mining XP: +20 000" in text
    assert "Commissions: +0" in text
    assert "выполнено ни одной комиссии" in text
    assert "топлив" not in text.lower()
