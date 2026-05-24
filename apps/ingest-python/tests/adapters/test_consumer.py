"""Boundary-parse tests for the Kafka consumer adapter.

``parse_telemetry`` is the seam where the generated contract DTO validates a raw
payload and converts it to the domain VO. These run without a broker — they
exercise the validate-then-convert logic and the drop-on-invalid contract.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sdf_ingest.adapters.consumer import parse_telemetry
from sdf_ingest.domain.record import Metric, Normalized


def _payload(**overrides: object) -> bytes:
    base: dict[str, object] = {
        "tenantId": "sdf_default",
        "lineId": "line-a",
        "machineKey": "press",
        "metric": "cycle_count",
        "value": 42.0,
        "observedAt": "2026-05-24T10:00:00Z",
        "sparkplugSeq": 5,
    }
    base.update(overrides)
    return json.dumps(base).encode()


def test_parses_valid_record() -> None:
    record = parse_telemetry(_payload())
    assert record == Normalized(
        tenant_id="sdf_default",
        line_id="line-a",
        machine_key="press",
        metric=Metric.CYCLE_COUNT,
        value=42.0,
        observed_at=datetime(2026, 5, 24, 10, 0, tzinfo=UTC),
        sparkplug_seq=5,
    )


def test_rejects_sparkplug_seq_out_of_range() -> None:
    assert parse_telemetry(_payload(sparkplugSeq=300)) is None


def test_rejects_unknown_metric() -> None:
    assert parse_telemetry(_payload(metric="velocity")) is None


def test_rejects_additional_property() -> None:
    # machine_telemetry.schema.json sets additionalProperties: false.
    assert parse_telemetry(_payload(extra="nope")) is None


def test_rejects_naive_timestamp() -> None:
    # observedAt is AwareDatetime — a tz-naive instant must be rejected.
    assert parse_telemetry(_payload(observedAt="2026-05-24T10:00:00")) is None


def test_rejects_non_json() -> None:
    assert parse_telemetry(b"{not json") is None


def test_drops_string_valued_state_metric() -> None:
    # The 'state' metric carries a string value; the Phase-1 numeric pipeline drops it.
    assert parse_telemetry(_payload(metric="state", value="RUNNING")) is None
