"""Domain tests for the Normalized value object (zero mocks — rules §10)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from sdf_ingest.domain.record import Metric, Normalized


def test_metric_values_match_contract() -> None:
    # The closed vocabulary must match kafka-payloads/machine_telemetry.schema.json.
    assert {m.value for m in Metric} == {
        "cycle_count",
        "good_count",
        "scrap_count",
        "state",
        "cycle_time_ms",
    }


def test_normalized_is_frozen() -> None:
    record = Normalized(
        tenant_id="sdf_default",
        line_id="line-a",
        machine_key="press",
        metric=Metric.CYCLE_COUNT,
        value=42.0,
        observed_at=datetime(2026, 5, 24, 10, 0, tzinfo=UTC),
        sparkplug_seq=5,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.value = 99.0  # type: ignore[misc]
