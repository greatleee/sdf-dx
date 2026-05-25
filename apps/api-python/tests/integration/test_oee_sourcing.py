"""OEE quantity-sourcing regression test (testcontainers; opt-in via --integration).

Guards the bottleneck-vs-sum fix in ``PgOeeReader``. The production line is serial
(press→weld→paint→inspect→pack); each station emits its own cumulative
``cycle_count`` / ``good_count`` counter. The line's throughput is its *bottleneck*
(slowest, smallest-delta) station, NOT the sum across stations — summing overcounts
≈Nx and pushed Performance above 1, which violated the ``OeeDTO`` ``maximum: 1``
bound and returned HTTP 500 at a real ``docker compose up``.

This test seeds two machines on one line with *different* counter deltas
(A: Δ240, B: Δ120) so ``sum`` (360) ≠ ``min`` (120). The assertions below
(``performance``/``quality``/``oee`` ≤ 1, produced == bottleneck delta) FAIL on the
old ``sum(...)`` query (produced 360 → performance 1.2 > 1) and PASS on the
bottleneck fix — that is the regression guarantee.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest
from testcontainers.postgres import PostgresContainer

from sdf_api.contexts.monitoring.adapters.db import (
    _IDEAL_CYCLE_TIME_S,
    _WINDOW_SECONDS,
    PgOeeReader,
)
from sdf_api.contexts.monitoring.domain.oee import OeeReading
from sdf_api.contexts.monitoring.domain.read_models import LineOeeSnapshot, OeeWindow
from sdf_api.shared_kernel.ids import LineId

# Repo root: tests/integration/<file> → tests → api-python → apps → repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_INIT_DIR = _REPO_ROOT / "infra" / "timescale" / "init"
# The OEE query reads only extensions + base tables + hypertables; the continuous
# aggregate (004) and seed (005) are irrelevant to this query path and 004's
# background policy needs the running job scheduler, so we apply 001-003 only.
_SCHEMA_FILES = ("001_extensions.sql", "002_schema.sql", "003_hypertables.sql")

# Bottleneck (machine B) delta — the value the line throughput must reflect.
_BOTTLENECK_PRODUCED = 120
# Sum across both stations — what the old (buggy) query produced; never expected.
_SUMMED_PRODUCED = 360


async def _apply_schema(conn: asyncpg.Connection) -> None:
    for name in _SCHEMA_FILES:
        await conn.execute((_INIT_DIR / name).read_text())


async def _seed_line_with_two_machines(conn: asyncpg.Connection) -> uuid.UUID:
    """Seed a factory + line + two machines with different counter deltas.

    Machine A: cycle_count 100→340 (Δ240), good_count 100→328 (Δ228).
    Machine B: cycle_count 100→220 (Δ120), good_count 100→214 (Δ114) — bottleneck.
    All telemetry timestamps fall inside the trailing window.
    """
    factory_id = await conn.fetchval(
        "INSERT INTO factory (name, region, timezone) VALUES ($1, $2, $3) RETURNING id",
        "Test Factory",
        "KR",
        "Asia/Seoul",
    )
    line_id = await conn.fetchval(
        "INSERT INTO production_line (factory_id, name, isa95_role) "
        "VALUES ($1, $2, 'PRODUCTION_LINE') RETURNING id",
        factory_id,
        "Line A",
    )
    machine_a = await conn.fetchval(
        "INSERT INTO machine (line_id, type, sparkplug_node_id) VALUES ($1, $2, $3) RETURNING id",
        line_id,
        "press",
        "sdf_default/line-a/press",
    )
    machine_b = await conn.fetchval(
        "INSERT INTO machine (line_id, type, sparkplug_node_id) VALUES ($1, $2, $3) RETURNING id",
        line_id,
        "weld",
        "sdf_default/line-a/weld",
    )

    now = datetime.now(UTC)
    start = now - timedelta(minutes=2)  # both samples inside the trailing 5 min
    rows: list[tuple[datetime, uuid.UUID, str, float, int]] = [
        # machine A: Δcycle 240, Δgood 228
        (start, machine_a, "cycle_count", 100.0, 1),
        (now, machine_a, "cycle_count", 340.0, 2),
        (start, machine_a, "good_count", 100.0, 1),
        (now, machine_a, "good_count", 328.0, 2),
        # machine B (bottleneck): Δcycle 120, Δgood 114
        (start, machine_b, "cycle_count", 100.0, 1),
        (now, machine_b, "cycle_count", 220.0, 2),
        (start, machine_b, "good_count", 100.0, 1),
        (now, machine_b, "good_count", 214.0, 2),
    ]
    await conn.executemany(
        "INSERT INTO machine_telemetry (time, machine_id, metric, value_num, sparkplug_seq) "
        "VALUES ($1, $2, $3, $4, $5)",
        rows,
    )
    return line_id


@pytest.mark.integration
async def test_oee_sources_produced_from_bottleneck_not_sum() -> None:
    with PostgresContainer("timescale/timescaledb:2.15.3-pg16") as pg:
        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        pool = await asyncpg.create_pool(dsn)
        assert pool is not None
        try:
            async with pool.acquire() as conn:
                await _apply_schema(conn)
                line_id = await _seed_line_with_two_machines(conn)

            snapshot = await PgOeeReader(pool).latest(LineId(line_id), OeeWindow.FIVE_MINUTES)
        finally:
            await pool.close()

    assert isinstance(snapshot, LineOeeSnapshot)
    reading: OeeReading = snapshot.reading

    # Performance = ideal_cycle_time_s * produced / APT. Inverting it recovers the
    # produced quantity the adapter sourced. The bottleneck fix yields 120 (machine
    # B's Δ); the old sum(...) query would yield 360 — fails the bound below.
    sourced_produced = round(reading.performance * _WINDOW_SECONDS / _IDEAL_CYCLE_TIME_S)
    assert sourced_produced == _BOTTLENECK_PRODUCED
    assert sourced_produced != _SUMMED_PRODUCED

    # Belt-and-suspenders: pin the exact value without relying solely on the
    # float inversion above. bottleneck 120 * ideal 1.0 / window 300 = 0.4.
    assert reading.performance == pytest.approx(0.4)

    # The original 500 cannot recur: every factor stays within the OpenAPI
    # OeeDTO ``maximum: 1`` bound. (The summed query gave performance 1.2 > 1.)
    assert reading.performance <= 1.0
    assert reading.quality <= 1.0
    assert reading.oee <= 1.0


@pytest.mark.integration
async def test_oee_idle_line_returns_none() -> None:
    """A line with no telemetry yields no window end → 404-equivalent None."""
    with PostgresContainer("timescale/timescaledb:2.15.3-pg16") as pg:
        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        pool = await asyncpg.create_pool(dsn)
        assert pool is not None
        try:
            async with pool.acquire() as conn:
                await _apply_schema(conn)

            snapshot = await PgOeeReader(pool).latest(LineId(uuid.uuid4()), OeeWindow.FIVE_MINUTES)
        finally:
            await pool.close()

    assert snapshot is None
