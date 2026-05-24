"""Derived line-state writer (boundary adapter + Phase-1 activity tracker).

Phase 1 has no dedicated line-state producer, so ingest derives a coarse state
from telemetry (``domain.line_activity``): a line whose machines' cycle counts
advanced is ``RUNNING``, otherwise ``IDLE``. A row is written to ``line_state``
only on a *change* — mirroring the monitoring line-state machine's idempotency
(one row per transition), so the table is a transition log, not a per-tick dump.

The per-machine cycle-count memory and last-written state are imperative-shell
state held here, never in the functional core (backend-code-architecture §4).
This is an explicit heuristic, not modeled downtime — see docs/KNOWN-UNKNOWNS.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import asyncpg

from sdf_ingest.adapters.resolver import ResolvedTelemetry
from sdf_ingest.domain.line_activity import (
    LineState,
    derive_machine_state,
    line_state_from_machines,
)
from sdf_ingest.domain.record import Metric


class LineStateWriter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._machine_cycles: dict[UUID, int] = {}
        self._line_state: dict[UUID, LineState] = {}

    async def observe(self, rows: Sequence[ResolvedTelemetry]) -> int:
        """Update per-machine cycle memory, derive line states, write transitions.

        Returns the number of ``line_state`` rows written (i.e. state changes).
        """
        line_machine_states: dict[UUID, list[LineState]] = {}
        line_latest_ts: dict[UUID, datetime] = {}
        for row in rows:
            if row.metric is not Metric.CYCLE_COUNT:
                continue
            previous = self._machine_cycles.get(row.machine_id)
            current = int(row.value)
            self._machine_cycles[row.machine_id] = current
            line_machine_states.setdefault(row.line_id, []).append(
                derive_machine_state(previous, current),
            )
            latest = line_latest_ts.get(row.line_id)
            if latest is None or row.observed_at > latest:
                line_latest_ts[row.line_id] = row.observed_at

        transitions: list[tuple[datetime, UUID, str]] = []
        for line_id, machine_states in line_machine_states.items():
            new_state = line_state_from_machines(machine_states)
            if self._line_state.get(line_id) != new_state:
                self._line_state[line_id] = new_state
                transitions.append((line_latest_ts[line_id], line_id, new_state.value))

        if not transitions:
            return 0
        async with self._pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO line_state (time, line_id, state, reason) VALUES ($1, $2, $3, NULL)",
                transitions,
            )
        return len(transitions)
