"""Domain tests for the Phase-1 line-activity heuristic (zero mocks — rules §10)."""

from __future__ import annotations

from sdf_ingest.domain.line_activity import (
    LineState,
    derive_machine_state,
    line_state_from_machines,
)


def test_first_sight_is_running() -> None:
    assert derive_machine_state(None, 0) is LineState.RUNNING
    assert derive_machine_state(None, 17) is LineState.RUNNING


def test_advancing_counter_is_running() -> None:
    assert derive_machine_state(10, 11) is LineState.RUNNING


def test_unchanged_counter_is_idle() -> None:
    assert derive_machine_state(10, 10) is LineState.IDLE


def test_counter_reset_is_idle() -> None:
    # A monotonic counter that decreased = machine restart; no progress this window.
    assert derive_machine_state(100, 3) is LineState.IDLE


def test_line_is_running_if_any_machine_runs() -> None:
    assert line_state_from_machines([LineState.IDLE, LineState.RUNNING]) is LineState.RUNNING


def test_line_is_idle_when_all_machines_idle() -> None:
    assert line_state_from_machines([LineState.IDLE, LineState.IDLE]) is LineState.IDLE


def test_line_with_no_machines_is_idle() -> None:
    assert line_state_from_machines([]) is LineState.IDLE
