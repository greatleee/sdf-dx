"""Use-case tests for monitoring read queries (dataset-backed fakes — rules §10)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from sdf_api.contexts.monitoring.application.queries import (
    GetLineOee,
    GetLineState,
    LineQueries,
)
from sdf_api.contexts.monitoring.domain.line_state import LineState, LineStateSnapshot
from sdf_api.contexts.monitoring.domain.oee import OeeReading
from sdf_api.contexts.monitoring.domain.read_models import LineOeeSnapshot, OeeWindow
from sdf_api.shared_kernel.ids import LineId
from sdf_api.shared_kernel.timestamp import Timestamp
from tests.contexts.monitoring.fakes import (
    FakeLineStateReader,
    FakeOeeReader,
    MonitoringInMemoryDataset,
)


def _queries(dataset: MonitoringInMemoryDataset) -> LineQueries:
    return LineQueries(FakeLineStateReader(dataset), FakeOeeReader(dataset))


def _timestamp() -> Timestamp:
    return Timestamp(datetime(2026, 5, 24, 12, 0, tzinfo=UTC))


async def test_line_state_returns_recorded_snapshot() -> None:
    line_id = LineId(uuid4())
    dataset = MonitoringInMemoryDataset()
    dataset.line_states[line_id] = LineStateSnapshot(line_id, LineState.RUNNING, _timestamp())

    snapshot = await _queries(dataset).line_state(GetLineState(line_id=line_id))

    assert snapshot is not None
    assert snapshot.state is LineState.RUNNING


async def test_line_state_returns_none_when_absent() -> None:
    snapshot = await _queries(MonitoringInMemoryDataset()).line_state(
        GetLineState(line_id=LineId(uuid4())),
    )
    assert snapshot is None


async def test_line_oee_returns_reading() -> None:
    line_id = LineId(uuid4())
    dataset = MonitoringInMemoryDataset()
    dataset.oee_readings[(line_id, OeeWindow.FIVE_MINUTES)] = LineOeeSnapshot(
        line_id=line_id,
        window=OeeWindow.FIVE_MINUTES,
        reading=OeeReading(availability=1.0, performance=0.95, quality=0.99, oee=0.9405),
        observed_at=_timestamp(),
    )

    snapshot = await _queries(dataset).line_oee(
        GetLineOee(line_id=line_id, window=OeeWindow.FIVE_MINUTES),
    )

    assert snapshot is not None
    assert snapshot.reading.oee == pytest.approx(0.9405)


async def test_line_oee_returns_none_for_unmaterialized_window() -> None:
    snapshot = await _queries(MonitoringInMemoryDataset()).line_oee(
        GetLineOee(line_id=LineId(uuid4()), window=OeeWindow.ONE_HOUR),
    )
    assert snapshot is None
