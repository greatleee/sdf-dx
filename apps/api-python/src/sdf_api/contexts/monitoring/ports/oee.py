"""Read port: the latest OEE reading for a line over a window (ADR-0022)."""

from __future__ import annotations

from typing import Protocol

from sdf_api.contexts.monitoring.domain.read_models import LineOeeSnapshot, OeeWindow
from sdf_api.shared_kernel.ids import LineId


class OeeReader(Protocol):
    """Reads the latest :class:`LineOeeSnapshot` for a line+window, or ``None``."""

    async def latest(self, line_id: LineId, window: OeeWindow) -> LineOeeSnapshot | None: ...
