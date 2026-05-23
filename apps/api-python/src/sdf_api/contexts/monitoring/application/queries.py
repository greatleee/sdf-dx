"""Monitoring read use cases: latest line state and OEE for a window.

BC-local application layer: depends only on this BC's ports and domain — never on
adapters (``composition-only-imports-adapters``, ADR-0023 #7). The composition
root injects concrete adapters that satisfy the Port Protocols structurally.
"""

from __future__ import annotations

from dataclasses import dataclass

from sdf_api.contexts.monitoring.domain.line_state import LineStateSnapshot
from sdf_api.contexts.monitoring.domain.read_models import LineOeeSnapshot, OeeWindow
from sdf_api.contexts.monitoring.ports.line_state import LineStateReader
from sdf_api.contexts.monitoring.ports.oee import OeeReader
from sdf_api.shared_kernel.ids import LineId


@dataclass(frozen=True, slots=True)
class GetLineState:
    line_id: LineId


@dataclass(frozen=True, slots=True)
class GetLineOee:
    line_id: LineId
    window: OeeWindow


class LineQueries:
    def __init__(self, states: LineStateReader, oees: OeeReader) -> None:
        self._states = states
        self._oees = oees

    async def line_state(self, query: GetLineState) -> LineStateSnapshot | None:
        return await self._states.latest(query.line_id)

    async def line_oee(self, query: GetLineOee) -> LineOeeSnapshot | None:
        return await self._oees.latest(query.line_id, query.window)
