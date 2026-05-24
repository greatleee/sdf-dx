"""End-to-end ingest pipeline test (testcontainers; opt-in via --integration).

Produces a telemetry record to Kafka, drives the real consumer → resolver →
TimescaleDB writers, and asserts both the raw `machine_telemetry` row landed and
the derived `line_state` transition was written. The seeded `sparkplug_node_id`
uses the edge slug `line-a` (the join contract settled in KNOWN-UNKNOWNS), exactly
as `infra/timescale/init/005_seed.sql` writes it.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest
from aiokafka import AIOKafkaProducer
from testcontainers.kafka import KafkaContainer
from testcontainers.postgres import PostgresContainer

from sdf_ingest.adapters.consumer import KafkaTelemetrySource
from sdf_ingest.adapters.line_state_writer import LineStateWriter
from sdf_ingest.adapters.resolver import MachineResolver
from sdf_ingest.adapters.writer import TelemetryWriter

_TOPIC = "sdf.sdf_default.machine.telemetry"
_NODE_ID = "sdf_default/line-a/press"


async def _create_schema(conn: asyncpg.Connection) -> uuid.UUID:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    await conn.execute(
        """
        CREATE TABLE machine (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            line_id uuid NOT NULL,
            sparkplug_node_id text UNIQUE NOT NULL
        );
        CREATE TABLE machine_telemetry (
            time timestamptz NOT NULL,
            machine_id uuid NOT NULL,
            metric text NOT NULL,
            value_num double precision,
            value_text text,
            sparkplug_seq smallint NOT NULL
        );
        SELECT create_hypertable('machine_telemetry', 'time');
        CREATE TABLE line_state (
            time timestamptz NOT NULL,
            line_id uuid NOT NULL,
            state text NOT NULL,
            reason text
        );
        """,
    )
    line_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO machine (line_id, sparkplug_node_id) VALUES ($1, $2)",
        line_id,
        _NODE_ID,
    )
    return line_id


@pytest.mark.integration
async def test_ingest_writes_telemetry_and_derived_line_state() -> None:
    with (
        PostgresContainer("timescale/timescaledb:2.15.3-pg16") as pg,
        KafkaContainer("confluentinc/cp-kafka:7.6.0") as kafka,
    ):
        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        bootstrap = kafka.get_bootstrap_server()

        pool = await asyncpg.create_pool(dsn)
        assert pool is not None
        try:
            async with pool.acquire() as conn:
                line_id = await _create_schema(conn)

            producer = AIOKafkaProducer(bootstrap_servers=bootstrap)
            await producer.start()
            try:
                payload = json.dumps(
                    {
                        "tenantId": "sdf_default",
                        "lineId": "line-a",
                        "machineKey": "press",
                        "metric": "cycle_count",
                        "value": 1.0,
                        "observedAt": datetime.now(UTC).isoformat(),
                        "sparkplugSeq": 1,
                    },
                ).encode()
                await producer.send_and_wait(_TOPIC, payload)
            finally:
                await producer.stop()

            resolver = MachineResolver(pool)
            telemetry_writer = TelemetryWriter(pool)
            line_state_writer = LineStateWriter(pool)
            async with KafkaTelemetrySource(
                bootstrap,
                topics=[_TOPIC],
                group_id=f"test-{uuid.uuid4()}",
                auto_offset_reset="earliest",
            ) as source:
                batch = await asyncio.wait_for(
                    source.batches(max_batch=10, max_wait_s=2.0).__anext__(),
                    timeout=30.0,
                )
                resolved = await resolver.resolve_batch(batch)
                written = await telemetry_writer.write_batch(resolved)
                transitions = await line_state_writer.observe(resolved)

            assert written == 1
            assert transitions == 1
            async with pool.acquire() as conn:
                telemetry_count = await conn.fetchval("SELECT count(*) FROM machine_telemetry")
                state_row = await conn.fetchrow(
                    "SELECT line_id, state FROM line_state ORDER BY time DESC LIMIT 1",
                )
            assert telemetry_count == 1
            assert state_row is not None
            assert state_row["line_id"] == line_id
            assert state_row["state"] == "RUNNING"
        finally:
            await pool.close()
