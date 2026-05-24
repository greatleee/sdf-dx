"""Normalized telemetry value object — the ingest functional core.

A :class:`Normalized` is one machine-metric observation *after* the Kafka boundary
DTO (``sdf_contracts.kafka.machine_telemetry.MachineTelemetry``) has validated the
raw payload. The envelope contract — required fields, enum membership, the
``0..255`` Sparkplug-seq range, a timezone-aware timestamp — is enforced at the
boundary by the generated DTO (contract-first §2 / ADR-0018), so this core type
restates none of it: it is a plain frozen value carrying stdlib types only.

Domain purity (backend-code-architecture §2): no ``pydantic``, no IO, no system
reads. ``line_id`` / ``machine_key`` are edge-native slugs (ADR-0011 D-2), not
topology UUIDs — the adapter layer resolves those downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Metric(StrEnum):
    """Closed metric vocabulary — mirrors ``kafka-payloads/machine_telemetry.schema.json``.

    The Phase-1 simulator emits only the three counters (``cycle_count`` /
    ``good_count`` / ``scrap_count``); ``state`` and ``cycle_time_ms`` are part of
    the contract but not produced by the current edge (docs/KNOWN-UNKNOWNS.md).
    """

    CYCLE_COUNT = "cycle_count"
    GOOD_COUNT = "good_count"
    SCRAP_COUNT = "scrap_count"
    STATE = "state"
    CYCLE_TIME_MS = "cycle_time_ms"


@dataclass(frozen=True, slots=True)
class Normalized:
    """One validated machine-metric observation with edge-native string keys."""

    tenant_id: str
    line_id: str
    machine_key: str
    metric: Metric
    value: float
    observed_at: datetime
    sparkplug_seq: int
