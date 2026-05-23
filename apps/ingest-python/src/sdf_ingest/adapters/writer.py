"""TimescaleDB telemetry writer (boundary adapter).

Persists resolved telemetry to the ``machine_telemetry`` hypertable via asyncpg
``COPY`` (the bulk path; ADR-0002). The adapter takes and returns primitives only
— no asyncpg ``Record`` ever leaks past it (ORM-containment spirit, ADR-0019).
"""

from __future__ import annotations

from collections.abc import Sequence

import asyncpg

from sdf_ingest.adapters.resolver import ResolvedTelemetry
from sdf_ingest.domain.record import Metric

# machine_telemetry columns (infra/timescale/init/003_hypertables.sql). A numeric
# metric lands in value_num; the contract's textual `state` metric would land in
# value_text — kept for forward-compat even though the Phase-1 edge emits neither.
_COLUMNS = ("time", "machine_id", "metric", "value_num", "value_text", "sparkplug_seq")


class TelemetryWriter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write_batch(self, rows: Sequence[ResolvedTelemetry]) -> int:
        if not rows:
            return 0
        records = [
            (
                row.observed_at,
                row.machine_id,
                row.metric.value,
                None if row.metric is Metric.STATE else row.value,
                str(row.value) if row.metric is Metric.STATE else None,
                row.sparkplug_seq,
            )
            for row in rows
        ]
        async with self._pool.acquire() as conn:
            await conn.copy_records_to_table(
                "machine_telemetry",
                records=records,
                columns=list(_COLUMNS),
            )
        return len(records)
