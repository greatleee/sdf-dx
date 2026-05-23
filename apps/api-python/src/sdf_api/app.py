"""Composition root for the SDF API service.

This is the imperative shell's top layer: it reads config, creates the asyncpg
pool, binds the Postgres adapters to their Port Protocols, wires the monitoring
read use cases, and exposes them over HTTP + WebSocket. Driving HTTP/WS routing
lives *here*, not in ``contexts/*/adapters/`` — adapters may not import upward to
``application``/``ports`` (``adapters-no-upward``, ADR-0023 #6), but composition
may import anything.

REST responses are the generated OpenAPI DTOs (``sdf_contracts.openapi``), mapped
from domain types at this boundary — the schema is the source of truth, never a
hand-written model (contract-first §2 / ADR-0018).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from uuid import UUID

import asyncpg
from fastapi import APIRouter, FastAPI, HTTPException
from sdf_contracts.openapi.sdf_openapi_models import LineStateSnapshot as LineStateDTO
from sdf_contracts.openapi.sdf_openapi_models import OeeReading as OeeDTO
from sdf_contracts.openapi.sdf_openapi_models import State as StateDTO
from sdf_contracts.openapi.sdf_openapi_models import Window as WindowDTO

from sdf_api.config import Settings
from sdf_api.contexts.monitoring.adapters.db import PgLineStateReader, PgOeeReader
from sdf_api.contexts.monitoring.adapters.ws import LineStateBroadcaster, register_ws
from sdf_api.contexts.monitoring.application.queries import (
    GetLineOee,
    GetLineState,
    LineQueries,
)
from sdf_api.contexts.monitoring.domain.read_models import OeeWindow
from sdf_api.contexts.monitoring.ports.line_state import LineStateReader
from sdf_api.contexts.monitoring.ports.oee import OeeReader
from sdf_api.shared_kernel.ids import LineId

log = logging.getLogger("sdf_api")

_POLL_INTERVAL_S = 1.0
_PROBE_TIMEOUT_S = 2.0


def _make_router(queries: LineQueries) -> APIRouter:
    """Build the read API router, mapping domain results to generated DTOs."""
    router = APIRouter(prefix="/api/v1")

    @router.get("/lines/{line_id}/state", response_model=LineStateDTO)
    async def get_line_state(line_id: UUID) -> LineStateDTO:
        snapshot = await queries.line_state(GetLineState(line_id=LineId(line_id)))
        if snapshot is None:
            raise HTTPException(status_code=404, detail="no line state recorded")
        return LineStateDTO(
            lineId=snapshot.line_id.value,
            state=StateDTO(snapshot.state.value),
            since=snapshot.since.value,
        )

    @router.get("/lines/{line_id}/oee", response_model=OeeDTO)
    async def get_line_oee(line_id: UUID, window: WindowDTO = WindowDTO.field_5m) -> OeeDTO:
        snapshot = await queries.line_oee(
            GetLineOee(line_id=LineId(line_id), window=OeeWindow(window.value)),
        )
        if snapshot is None:
            raise HTTPException(status_code=404, detail="no oee available for window")
        reading = snapshot.reading
        return OeeDTO(
            lineId=snapshot.line_id.value,
            window=window,
            oee=reading.oee,
            availability=reading.availability,
            performance=reading.performance,
            quality=reading.quality,
            observedAt=snapshot.observed_at.value,
        )

    return router


async def _kafka_reachable(bootstrap: str) -> bool:
    """Liveness-grade TCP reachability of the Kafka bootstrap (spec §8.1: DB+Kafka).

    The API is read-only over the DB; the Kafka probe exists for ops parity with
    the pipeline, so a cheap socket connect is sufficient.
    """
    for broker in (b.strip() for b in bootstrap.split(",") if b.strip()):
        host, _, port = broker.partition(":")
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port or "9092")),
                _PROBE_TIMEOUT_S,
            )
        except (OSError, asyncio.TimeoutError, ValueError):
            continue
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        return True
    return False


async def _poll_line_state(
    pool: asyncpg.Pool,
    broadcaster: LineStateBroadcaster,
) -> None:
    """Publish each line's latest state to WS subscribers, on change, every ~1s.

    Phase-1 glue: a dedicated change-feed (LISTEN/NOTIFY or a tail of the
    transition log) would replace this poll in a later phase.
    """
    last_seen: dict[str, str] = {}
    while True:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT DISTINCT ON (line_id) line_id, state, time "
                    "FROM line_state ORDER BY line_id, time DESC",
                )
            for row in rows:
                key = str(row["line_id"])
                since = row["time"].isoformat()
                signature = f"{row['state']}@{since}"
                if last_seen.get(key) != signature:
                    last_seen[key] = signature
                    await broadcaster.publish(
                        {"lineId": key, "state": row["state"], "since": since},
                    )
        except Exception:
            log.exception("line-state poll iteration failed")
        await asyncio.sleep(_POLL_INTERVAL_S)


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    pool = await asyncpg.create_pool(settings.pg_dsn, min_size=1, max_size=8)
    if pool is None:
        raise RuntimeError("failed to create asyncpg pool")
    # Bind concrete adapters to their Port Protocols (mypy verifies the structural
    # match here, at the composition boundary).
    states: LineStateReader = PgLineStateReader(pool)
    oees: OeeReader = PgOeeReader(pool)
    queries = LineQueries(states, oees)
    app.include_router(_make_router(queries))

    broadcaster = LineStateBroadcaster()
    register_ws(app, broadcaster)
    poller = asyncio.create_task(_poll_line_state(pool, broadcaster))

    app.state.pool = pool
    app.state.kafka_bootstrap = settings.kafka_bootstrap
    try:
        yield
    finally:
        poller.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poller
        await pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="SDF Manufacturing DX API", version="0.1.0", lifespan=_lifespan)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        pool: asyncpg.Pool | None = getattr(app.state, "pool", None)
        if pool is None:
            raise HTTPException(status_code=503, detail="starting")
        try:
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, OSError) as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        if not await _kafka_reachable(app.state.kafka_bootstrap):
            raise HTTPException(status_code=503, detail="kafka unavailable")
        return {"status": "ready"}

    return app


app = create_app()
