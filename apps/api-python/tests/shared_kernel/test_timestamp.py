from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from sdf_api.shared_kernel.timestamp import Timestamp


def test_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Timestamp(datetime(2026, 5, 23, 12, 0))


def test_accepts_aware_datetime() -> None:
    ts = Timestamp(datetime(2026, 5, 23, 12, 0, tzinfo=UTC))
    assert ts.value.tzinfo is not None


def test_orders_chronologically() -> None:
    earlier = Timestamp(datetime(2026, 5, 23, 12, 0, tzinfo=UTC))
    later = Timestamp(datetime(2026, 5, 23, 12, 5, tzinfo=UTC))
    assert earlier < later
    assert later > earlier
    assert earlier != later


def test_equal_instants_compare_equal_regardless_of_zone() -> None:
    # Same instant expressed in two zones compares equal (aware datetime semantics).
    utc = Timestamp(datetime(2026, 5, 23, 12, 0, tzinfo=UTC))
    plus_one = Timestamp(datetime(2026, 5, 23, 13, 0, tzinfo=timezone(timedelta(hours=1))))
    assert utc == plus_one
    assert not utc < plus_one
