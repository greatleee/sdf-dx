"""Line-activity heuristic — pure functional core.

Phase 1 has no dedicated line-state producer, so the ingest service derives a
*coarse* line state from the only signal the edge emits: the monotonic per-machine
``cycle_count``. A machine whose counter advanced since the previous observation is
producing; a line is ``RUNNING`` when any of its machines is producing, otherwise
``IDLE``.

``DOWN`` and ``CHANGEOVER`` are deliberately **not** derivable here — the Phase-1
simulator emits no downtime or changeover signal, so synthesising those
transitions would be unmodeled fiction (the honest-boundary stance of
docs/KNOWN-UNKNOWNS.md). This module reads no clock and performs no IO; the shell
supplies the previous/current counts (backend-code-architecture §2 / §4).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class LineState(StrEnum):
    """Line states per ``kafka-payloads/line_state.schema.json`` / GLOSSARY ``monitoring``."""

    RUNNING = "RUNNING"
    IDLE = "IDLE"
    DOWN = "DOWN"
    CHANGEOVER = "CHANGEOVER"


def derive_machine_state(previous_cycle_count: int | None, current_cycle_count: int) -> LineState:
    """Map one machine's cycle-count progression to a coarse activity state.

    ``previous_cycle_count is None`` is first sight of the machine: treat it as
    ``RUNNING`` (it was already producing when observation began). Otherwise the
    machine is ``RUNNING`` iff its monotonic counter strictly advanced, else
    ``IDLE``. A non-increase covers both a genuinely idle machine and a counter
    reset (machine restart) — neither is production progress this window.
    """
    if previous_cycle_count is None:
        return LineState.RUNNING
    return LineState.RUNNING if current_cycle_count > previous_cycle_count else LineState.IDLE


def line_state_from_machines(machine_states: Iterable[LineState]) -> LineState:
    """Aggregate machine activity to a line state: ``RUNNING`` if any machine is."""
    return (
        LineState.RUNNING
        if any(state is LineState.RUNNING for state in machine_states)
        else LineState.IDLE
    )
