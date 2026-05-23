"""Kafka telemetry source — boundary adapter.

Consumes the normalized-telemetry topic (``sdf.<tenant>.machine.telemetry``,
produced by the Sparkplug→Kafka bridge, ADR-0011 D-5) and validates each record
against the generated boundary DTO ``MachineTelemetry`` — the schema is the source
of truth, never a hand-written model (contract-first §2 / ADR-0018). Validation
failures are logged and dropped; the dead-letter topic is deferred
(docs/KNOWN-UNKNOWNS.md), and at-least-once + idempotent write is the Phase-1
delivery stance (ADR-0005). Offsets commit only *after* a batch is yielded and
persisted, so a crash mid-write re-delivers rather than loses.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord, TopicPartition
from pydantic import ValidationError
from sdf_contracts.kafka.machine_telemetry import MachineTelemetry

from sdf_ingest.domain.record import Metric, Normalized

log = logging.getLogger(__name__)

# aiokafka subscribe(pattern=...) takes a Java regex; matches the bridge's
# `sdf.<tenant>.machine.telemetry` topic family across tenants.
_TOPIC_PATTERN = r"sdf\..*\.machine\.telemetry"
_GROUP_ID = "sdf-ingest"


def _to_domain(dto: MachineTelemetry) -> Normalized | None:
    """Convert a validated boundary DTO to the domain value object.

    Returns ``None`` for a non-numeric ``value`` — only the contract's ``state``
    metric carries a string, and the Phase-1 edge never emits it; the numeric
    telemetry pipeline has no use for it (docs/KNOWN-UNKNOWNS.md).
    """
    if isinstance(dto.value, str):
        return None
    return Normalized(
        tenant_id=dto.tenantId,
        line_id=dto.lineId,
        machine_key=dto.machineKey,
        metric=Metric(dto.metric.value),
        value=float(dto.value),
        observed_at=dto.observedAt,
        sparkplug_seq=int(dto.sparkplugSeq),
    )


def parse_telemetry(raw: bytes) -> Normalized | None:
    """Validate one raw Kafka value against the contract DTO and convert to domain.

    Returns ``None`` when the payload violates the schema (missing/extra fields,
    unknown metric, seq out of ``0..255``, naive timestamp) or carries a
    non-numeric value. The caller logs and drops — invalid input is never fatal.
    """
    try:
        dto = MachineTelemetry.model_validate_json(raw)
    except ValidationError:
        return None
    return _to_domain(dto)


class KafkaTelemetrySource:
    def __init__(
        self,
        bootstrap: str,
        *,
        topic_pattern: str = _TOPIC_PATTERN,
        topics: Sequence[str] | None = None,
        group_id: str = _GROUP_ID,
        auto_offset_reset: str = "latest",
    ) -> None:
        self._consumer: AIOKafkaConsumer = AIOKafkaConsumer(
            bootstrap_servers=bootstrap,
            group_id=group_id,
            enable_auto_commit=False,
            auto_offset_reset=auto_offset_reset,
        )
        self._pattern = topic_pattern
        self._topics = topics

    async def __aenter__(self) -> KafkaTelemetrySource:
        await self._consumer.start()
        # Explicit topics (used by tests for deterministic assignment) take
        # precedence; production discovers the topic family by regex pattern.
        if self._topics is not None:
            self._consumer.subscribe(topics=list(self._topics))
        else:
            self._consumer.subscribe(pattern=self._pattern)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._consumer.stop()

    async def batches(
        self,
        *,
        max_batch: int = 500,
        max_wait_s: float = 0.5,
    ) -> AsyncIterator[list[Normalized]]:
        """Yield batches of valid records; commit offsets after each is consumed."""
        while True:
            fetched: dict[TopicPartition, list[ConsumerRecord]] = await self._consumer.getmany(
                timeout_ms=int(max_wait_s * 1000),
                max_records=max_batch,
            )
            batch: list[Normalized] = []
            offsets: dict[TopicPartition, int] = {}
            for topic_partition, messages in fetched.items():
                for message in messages:
                    record = self._parse(topic_partition, message)
                    if record is not None:
                        batch.append(record)
                    offsets[topic_partition] = message.offset + 1
            if batch:
                yield batch
                await self._consumer.commit(offsets)
            else:
                await asyncio.sleep(0)

    def _parse(
        self,
        topic_partition: TopicPartition,
        message: ConsumerRecord,
    ) -> Normalized | None:
        raw = message.value
        if raw is None:
            return None
        record = parse_telemetry(raw)
        if record is None:
            log.warning(
                "dropped invalid record topic=%s offset=%s",
                topic_partition.topic,
                message.offset,
            )
        return record
