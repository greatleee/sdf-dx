"""Edge-key → topology-id resolution (boundary adapter).

The ``machine_telemetry`` payload carries edge-native string keys (``lineId``
slug, ``machineKey``); the topology tables key on UUIDs. This adapter resolves
``(tenantId, lineId, machineKey)`` to ``(machine_id, line_id)`` via the UNIQUE
``machine.sparkplug_node_id``, reassembled as the real Sparkplug address
``{tenant}/{lineId}/{machineKey}`` — the join contract settled in
docs/KNOWN-UNKNOWNS.md ("Edge↔topology identifier resolution"). The seed
(``infra/timescale/init/005_seed.sql``) writes node ids in exactly this shape.

Resolution is memoized: the Phase-1 topology is static, so a hit is cached; a
miss is re-queried (the machine may simply not be seeded yet) and the record is
dropped with a warning rather than silently mis-joined.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from sdf_ingest.domain.record import Metric, Normalized

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ResolvedTelemetry:
    """A :class:`~sdf_ingest.domain.record.Normalized` with its topology UUIDs resolved."""

    machine_id: UUID
    line_id: UUID
    metric: Metric
    value: float
    observed_at: datetime
    sparkplug_seq: int


class MachineResolver:
    """Resolves edge keys to topology UUIDs against ``machine.sparkplug_node_id``."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._cache: dict[str, tuple[UUID, UUID]] = {}

    @staticmethod
    def node_id(record: Normalized) -> str:
        """Reassemble the Sparkplug address the seed indexes: ``{group}/{slug}/{key}``."""
        return f"{record.tenant_id}/{record.line_id}/{record.machine_key}"

    async def resolve(self, record: Normalized) -> ResolvedTelemetry | None:
        node_id = self.node_id(record)
        ids = self._cache.get(node_id)
        if ids is None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, line_id FROM machine WHERE sparkplug_node_id = $1",
                    node_id,
                )
            if row is None:
                log.warning("unresolved machine sparkplug_node_id=%s — dropped", node_id)
                return None
            ids = (row["id"], row["line_id"])
            self._cache[node_id] = ids
        machine_id, line_id = ids
        return ResolvedTelemetry(
            machine_id=machine_id,
            line_id=line_id,
            metric=record.metric,
            value=record.value,
            observed_at=record.observed_at,
            sparkplug_seq=record.sparkplug_seq,
        )

    async def resolve_batch(self, records: Sequence[Normalized]) -> list[ResolvedTelemetry]:
        resolved: list[ResolvedTelemetry] = []
        for record in records:
            hit = await self.resolve(record)
            if hit is not None:
                resolved.append(hit)
        return resolved
