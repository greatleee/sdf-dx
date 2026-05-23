"""In-memory fakes for the monitoring BC (ADR-0024 — per-BC, dataset-backed).

The fakes structurally satisfy the read Port Protocols and read from a shared
``MonitoringInMemoryDataset`` — the same shape a real session-bound adapter has,
so use-case tests assert on dataset state / returned values, never on calls
(rules §10). Working in-memory implementations only; no mock library.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sdf_api.contexts.monitoring.domain.line_state import LineStateSnapshot
from sdf_api.contexts.monitoring.domain.read_models import LineOeeSnapshot, OeeWindow
from sdf_api.shared_kernel.ids import LineId


@dataclass
class MonitoringInMemoryDataset:
    line_states: dict[LineId, LineStateSnapshot] = field(default_factory=dict)
    oee_readings: dict[tuple[LineId, OeeWindow], LineOeeSnapshot] = field(default_factory=dict)


class FakeLineStateReader:
    def __init__(self, dataset: MonitoringInMemoryDataset) -> None:
        self._dataset = dataset

    async def latest(self, line_id: LineId) -> LineStateSnapshot | None:
        return self._dataset.line_states.get(line_id)


class FakeOeeReader:
    def __init__(self, dataset: MonitoringInMemoryDataset) -> None:
        self._dataset = dataset

    async def latest(self, line_id: LineId, window: OeeWindow) -> LineOeeSnapshot | None:
        return self._dataset.oee_readings.get((line_id, window))
