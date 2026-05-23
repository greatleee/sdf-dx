"""Tests for the monitoring line-state machine.

Zero mocks.  Every test constructs concrete values and asserts on the returned
sum-type variant.  Helpers keep individual tests focused on the case under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from sdf_api.contexts.monitoring.domain.line_state import (
    ApplyOutcome,
    LineState,
    LineStateObserved,
    LineStateSnapshot,
    StaleObservation,
    Transitioned,
    Unchanged,
    apply_observation,
)
from sdf_api.shared_kernel.ids import LineId
from sdf_api.shared_kernel.timestamp import Timestamp

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LINE_A = LineId(UUID(int=1))
_LINE_B = LineId(UUID(int=2))


def _ts(hour: int, minute: int = 0) -> Timestamp:
    """Build a tz-aware UTC Timestamp at the given hour:minute on a fixed date."""
    return Timestamp(datetime(2026, 5, 23, hour, minute, tzinfo=UTC))


def _snapshot(
    line_id: LineId,
    state: LineState,
    hour: int,
    minute: int = 0,
) -> LineStateSnapshot:
    return LineStateSnapshot(line_id, state, _ts(hour, minute))


def _observed(
    line_id: LineId,
    state: LineState,
    hour: int,
    minute: int = 0,
    reason: str | None = None,
) -> LineStateObserved:
    return LineStateObserved(line_id, state, _ts(hour, minute), reason=reason)


def _apply(current: LineStateSnapshot | None, observed: LineStateObserved) -> ApplyOutcome:
    """Thin wrapper so tests can annotate against the full union type."""
    return apply_observation(current, observed)


# ---------------------------------------------------------------------------
# Case 1 — first observation (current=None)
# ---------------------------------------------------------------------------


def test_first_observation_returns_transitioned() -> None:
    obs = _observed(_LINE_A, LineState.RUNNING, hour=10)
    result = apply_observation(None, obs)

    assert isinstance(result, Transitioned)
    assert result.snapshot.line_id == _LINE_A
    assert result.snapshot.state == LineState.RUNNING
    assert result.snapshot.since == _ts(10)
    assert result.event.from_state is None
    assert result.event.to_state == LineState.RUNNING
    assert result.event.since == _ts(10)
    assert result.event.line_id == _LINE_A


# ---------------------------------------------------------------------------
# Case 2 — re-observe same state with a newer timestamp
# ---------------------------------------------------------------------------


def test_same_state_newer_time_returns_unchanged() -> None:
    current = _snapshot(_LINE_A, LineState.RUNNING, hour=10)
    obs = _observed(_LINE_A, LineState.RUNNING, hour=11)

    result = apply_observation(current, obs)

    assert isinstance(result, Unchanged)
    # The snapshot returned is the *original* current, not a new one.
    assert result.snapshot is current


# ---------------------------------------------------------------------------
# Case 2b — re-observe same state with equal timestamp
# ---------------------------------------------------------------------------


def test_same_state_equal_time_returns_unchanged() -> None:
    current = _snapshot(_LINE_A, LineState.IDLE, hour=10)
    obs = _observed(_LINE_A, LineState.IDLE, hour=10)

    result = apply_observation(current, obs)

    assert isinstance(result, Unchanged)
    assert result.snapshot is current


# ---------------------------------------------------------------------------
# Case 3 — different state, newer time → Transitioned
# ---------------------------------------------------------------------------


def test_different_state_newer_time_returns_transitioned() -> None:
    current = _snapshot(_LINE_A, LineState.RUNNING, hour=10)
    obs = _observed(_LINE_A, LineState.DOWN, hour=12)

    result = apply_observation(current, obs)

    assert isinstance(result, Transitioned)
    assert result.event.from_state == LineState.RUNNING
    assert result.event.to_state == LineState.DOWN
    assert result.snapshot.state == LineState.DOWN
    assert result.snapshot.since == _ts(12)
    assert result.event.since == _ts(12)


# ---------------------------------------------------------------------------
# Case 4 — stale observation (observed_at < current.since)
# ---------------------------------------------------------------------------


def test_stale_observation_returns_stale_outcome() -> None:
    current = _snapshot(_LINE_A, LineState.DOWN, hour=12)
    obs = _observed(_LINE_A, LineState.RUNNING, hour=9)  # older

    result = apply_observation(current, obs)

    assert isinstance(result, StaleObservation)
    assert result.current is current
    assert result.observed_at == _ts(9)


# ---------------------------------------------------------------------------
# Case 5 — boundary: observed_at == current.since, different state → Transitioned
# ---------------------------------------------------------------------------


def test_equal_timestamp_different_state_is_transitioned_not_stale() -> None:
    """The stale check uses strict `<`; equality is NOT stale."""
    current = _snapshot(_LINE_A, LineState.RUNNING, hour=10)
    obs = _observed(_LINE_A, LineState.CHANGEOVER, hour=10)  # same timestamp

    result = apply_observation(current, obs)

    assert isinstance(result, Transitioned)
    assert result.event.from_state == LineState.RUNNING
    assert result.event.to_state == LineState.CHANGEOVER


# ---------------------------------------------------------------------------
# Case 6 — boundary: observed_at == current.since, same state → Unchanged
# ---------------------------------------------------------------------------


def test_equal_timestamp_same_state_is_unchanged() -> None:
    current = _snapshot(_LINE_A, LineState.CHANGEOVER, hour=10)
    obs = _observed(_LINE_A, LineState.CHANGEOVER, hour=10)

    result = apply_observation(current, obs)

    assert isinstance(result, Unchanged)
    assert result.snapshot is current


# ---------------------------------------------------------------------------
# Case 7 — line_id mismatch raises ValueError
# ---------------------------------------------------------------------------


def test_line_id_mismatch_raises_value_error() -> None:
    current = _snapshot(_LINE_A, LineState.RUNNING, hour=10)
    obs = _observed(_LINE_B, LineState.IDLE, hour=11)

    with pytest.raises(ValueError, match="line_id"):
        apply_observation(current, obs)


# ---------------------------------------------------------------------------
# Case 8 — reason is carried onto the domain event
# ---------------------------------------------------------------------------


def test_reason_is_propagated_to_event_on_transition() -> None:
    obs = _observed(_LINE_A, LineState.DOWN, hour=10, reason="sensor-timeout")
    result = apply_observation(None, obs)

    assert isinstance(result, Transitioned)
    assert result.event.reason == "sensor-timeout"


def test_reason_propagated_on_state_change() -> None:
    current = _snapshot(_LINE_A, LineState.RUNNING, hour=10)
    obs = _observed(_LINE_A, LineState.IDLE, hour=11, reason="planned-stop")

    result = apply_observation(current, obs)

    assert isinstance(result, Transitioned)
    assert result.event.reason == "planned-stop"


def test_no_reason_defaults_to_none_on_event() -> None:
    obs = _observed(_LINE_A, LineState.RUNNING, hour=10)
    result = apply_observation(None, obs)

    assert isinstance(result, Transitioned)
    assert result.event.reason is None
