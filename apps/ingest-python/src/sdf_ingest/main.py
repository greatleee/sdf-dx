"""Composition root for the ingest service.

Wires the Kafka source → edge-key resolver → TimescaleDB telemetry writer +
derived line-state writer, then runs the consume loop. System reads (env config)
live here, never in the functional core (backend-code-architecture §4).
"""

from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

from sdf_ingest.adapters.consumer import KafkaTelemetrySource
from sdf_ingest.adapters.line_state_writer import LineStateWriter
from sdf_ingest.adapters.resolver import MachineResolver
from sdf_ingest.adapters.writer import TelemetryWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("sdf_ingest")


async def run() -> None:
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    pg_dsn = os.environ.get("PG_DSN", "postgresql://sdf:sdf@localhost:5432/sdf")

    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=8)
    if pool is None:
        raise RuntimeError("failed to create asyncpg pool")
    resolver = MachineResolver(pool)
    telemetry_writer = TelemetryWriter(pool)
    line_state_writer = LineStateWriter(pool)
    try:
        async with KafkaTelemetrySource(bootstrap) as source:
            async for batch in source.batches():
                resolved = await resolver.resolve_batch(batch)
                written = await telemetry_writer.write_batch(resolved)
                transitions = await line_state_writer.observe(resolved)
                log.info(
                    "batch parsed=%d resolved=%d telemetry_written=%d line_transitions=%d",
                    len(batch),
                    len(resolved),
                    written,
                    transitions,
                )
    finally:
        await pool.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
