"""Line-state machine for the monitoring bounded context.

This module is a pure functional core: it never reads the system clock, never
generates IDs, and carries no I/O dependencies.  The only inputs are a
:class:`LineStateSnapshot` (the current persisted state, or ``None`` on first
sight of a line) and a :class:`LineStateObserved` event delivered by the shell.

Honest model — no forbidden transitions
-----------------------------------------
Line state is *observed*, not *commanded*.  The telemetry pipeline tells us what
a line is doing; we record it.  We therefore do **not** invent a transition table
that says "RUNNING → IDLE is allowed but RUNNING → CHANGEOVER is not" — that
would be policy we do not have.  The domain has exactly two real invariants,
both rooted in UC-001:

1. **Monotonic since** — an observation whose ``observed_at`` is strictly earlier
   than the snapshot's ``since`` timestamp cannot logically supersede it.
   ``apply_observation`` returns :class:`StaleObservation` in that case; the
   shell decides whether to discard or re-examine the event.

2. **Idempotency** — re-observing the same state that is already recorded
   produces :class:`Unchanged` and emits *no* ``LineStateChanged`` event.
   ``LineStateChanged`` fires at most once per ``(line_id, to_state, since)``
   triple, which lets the shell safely retry without double-counting transitions.

Sum-type outcomes
-----------------
:func:`apply_observation` returns ``ApplyOutcome``, a closed union of three
frozen dataclass cases discriminated by class type (``match`` / ``isinstance``):

- :class:`Transitioned` — state changed (or first observation).  Carries both
  the new snapshot and the domain event value.
- :class:`Unchanged` — same state; snapshot is unchanged.
- :class:`StaleObservation` — observation is older than current state; ignored.

Shell contract
--------------
Passing a ``current`` snapshot whose ``line_id`` differs from ``observed.line_id``
is a shell contract breach (a programming error, not a business outcome) and
raises :class:`ValueError` immediately (ADR-0016).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sdf_api.shared_kernel.ids import LineId
from sdf_api.shared_kernel.timestamp import Timestamp


class LineState(StrEnum):
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    DOWN = "DOWN"
    CHANGEOVER = "CHANGEOVER"


@dataclass(frozen=True, slots=True)
class LineStateSnapshot:
    """The current persisted state of a line as the domain knows it."""

    line_id: LineId
    state: LineState
    since: Timestamp


@dataclass(frozen=True, slots=True)
class LineStateObserved:
    """Input event: the shell observed ``state`` for ``line_id`` at ``observed_at``."""

    line_id: LineId
    state: LineState
    observed_at: Timestamp
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class LineStateChanged:
    """Domain event (a value, not dispatched in Phase 1).

    ``from_state`` is ``None`` on the first-ever observation of a line.
    Carries ``reason`` verbatim from the triggering :class:`LineStateObserved`.
    """

    line_id: LineId
    from_state: LineState | None
    to_state: LineState
    since: Timestamp
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Transitioned:
    """State changed (or first observation).  Both snapshot and event are fresh."""

    snapshot: LineStateSnapshot
    event: LineStateChanged


@dataclass(frozen=True, slots=True)
class Unchanged:
    """Re-observation of the current state — no event emitted."""

    snapshot: LineStateSnapshot


@dataclass(frozen=True, slots=True)
class StaleObservation:
    """Observation is older than the current snapshot — discarded by convention."""

    current: LineStateSnapshot
    observed_at: Timestamp
    reason: str = "observation older than current state"


ApplyOutcome = Transitioned | Unchanged | StaleObservation


def apply_observation(
    current: LineStateSnapshot | None,
    observed: LineStateObserved,
) -> ApplyOutcome:
    """Apply one telemetry observation to the current line state.

    Parameters
    ----------
    current:
        The persisted snapshot for this line, or ``None`` if this is the
        first-ever observation.
    observed:
        The incoming telemetry event from the shell.

    Returns
    -------
    ApplyOutcome
        One of :class:`Transitioned`, :class:`Unchanged`, or
        :class:`StaleObservation`.  Discriminate with ``match`` or
        ``isinstance``.

    Raises
    ------
    ValueError
        If ``current`` is not ``None`` and ``current.line_id != observed.line_id``
        (shell contract breach — ADR-0016).
    """
    if current is not None and current.line_id != observed.line_id:
        raise ValueError(
            f"observation line_id {observed.line_id!r} does not match "
            f"current snapshot line_id {current.line_id!r}"
        )

    if current is None:
        snapshot = LineStateSnapshot(observed.line_id, observed.state, observed.observed_at)
        event = LineStateChanged(
            observed.line_id, None, observed.state, observed.observed_at, observed.reason
        )
        return Transitioned(snapshot, event)

    if observed.observed_at < current.since:
        return StaleObservation(current, observed.observed_at)

    if observed.state == current.state:
        return Unchanged(current)

    snapshot = LineStateSnapshot(observed.line_id, observed.state, observed.observed_at)
    event = LineStateChanged(
        observed.line_id, current.state, observed.state, observed.observed_at, observed.reason
    )
    return Transitioned(snapshot, event)
