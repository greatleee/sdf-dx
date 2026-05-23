"""TimescaleDB read adapters for the monitoring bounded context.

Each adapter takes an asyncpg pool, reads one model, and returns a domain type —
no asyncpg ``Record`` leaks past the boundary (ORM-containment spirit, ADR-0019).
The adapters satisfy the ``LineStateReader`` / ``OeeReader`` Port Protocols
*structurally*; they do not import ``ports/`` (``adapters-no-upward``, ADR-0023
#6). The composition root binds them to the Protocol type.

OEE quantity sourcing (Phase 1)
-------------------------------
``cycle_count`` / ``good_count`` are *cumulative monotonic counters*, so the
per-bucket produced/good quantities are counter **deltas**, computed here as
``max(value_num) - min(value_num)`` per machine over a trailing window, summed to
the line. We query ``machine_telemetry`` directly rather than the ``line_oee_5m``
continuous aggregate, because that CAGG does ``SUM(value_num)`` over the absolute
counters (it treats them as gauges) and so cannot yield a correct produced
quantity — see docs/KNOWN-UNKNOWNS.md. The A·P·Q math itself is the Section D
domain core (``compute_oee``); this adapter only sources its inputs.
"""

from __future__ import annotations

import asyncpg

from sdf_api.contexts.monitoring.domain.line_state import LineState, LineStateSnapshot
from sdf_api.contexts.monitoring.domain.oee import OeeInputs, OeeReading, compute_oee
from sdf_api.contexts.monitoring.domain.read_models import LineOeeSnapshot, OeeWindow
from sdf_api.shared_kernel.ids import LineId
from sdf_api.shared_kernel.timestamp import Timestamp

# Phase-1 OEE simplification (ADR-0012 §D-2 / oee.py docstring): the window length
# is taken as both APT and PBT (→ Availability 1.0), and the ideal cycle time is
# the simulator's calibrated 1 s (the edge emits no cycle_time_ms metric).
_WINDOW_SECONDS = 5 * 60.0
_IDEAL_CYCLE_TIME_S = 1.0

# Produced/good are per-machine counter deltas over the trailing window, summed to
# the line; observed_at is the window's latest telemetry instant.
_OEE_QUERY = """
WITH line_machines AS (
    SELECT id FROM machine WHERE line_id = $1
),
window_end AS (
    SELECT max(time) AS end_time
    FROM machine_telemetry
    WHERE machine_id IN (SELECT id FROM line_machines)
),
per_machine AS (
    SELECT
        max(t.value_num) FILTER (WHERE t.metric = 'cycle_count')
            - min(t.value_num) FILTER (WHERE t.metric = 'cycle_count') AS produced,
        max(t.value_num) FILTER (WHERE t.metric = 'good_count')
            - min(t.value_num) FILTER (WHERE t.metric = 'good_count') AS good
    FROM machine_telemetry t, window_end w
    WHERE t.machine_id IN (SELECT id FROM line_machines)
      AND t.time > w.end_time - make_interval(secs => $2)
      AND t.time <= w.end_time
    GROUP BY t.machine_id
)
SELECT
    (SELECT end_time FROM window_end) AS observed_at,
    coalesce(sum(produced), 0) AS produced_qty,
    coalesce(sum(good), 0) AS good_qty
FROM per_machine;
"""


class PgLineStateReader:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def latest(self, line_id: LineId) -> LineStateSnapshot | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state, time FROM line_state WHERE line_id = $1 ORDER BY time DESC LIMIT 1",
                line_id.value,
            )
        if row is None:
            return None
        return LineStateSnapshot(
            line_id=line_id,
            state=LineState(row["state"]),
            since=Timestamp(row["time"]),
        )


class PgOeeReader:
    """Sources OEE inputs from raw telemetry and runs the Section D OEE core.

    Only the ``5m`` window is supported in Phase 1; ``1h`` / ``shift`` return
    ``None`` (Phase 3). An idle window (no production → ``OeeUndefined``) also
    returns ``None``.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def latest(self, line_id: LineId, window: OeeWindow) -> LineOeeSnapshot | None:
        if window is not OeeWindow.FIVE_MINUTES:
            return None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_OEE_QUERY, line_id.value, _WINDOW_SECONDS)
        if row is None or row["observed_at"] is None:
            return None
        outcome = compute_oee(
            OeeInputs(
                produced_quantity=int(row["produced_qty"]),
                good_quantity=int(row["good_qty"]),
                ideal_cycle_time_s=_IDEAL_CYCLE_TIME_S,
                actual_production_time_s=_WINDOW_SECONDS,
                planned_busy_time_s=_WINDOW_SECONDS,
            ),
        )
        if not isinstance(outcome, OeeReading):
            return None  # OeeUndefined (e.g. idle window) — nothing to report.
        return LineOeeSnapshot(
            line_id=line_id,
            window=window,
            reading=outcome,
            observed_at=Timestamp(row["observed_at"]),
        )
