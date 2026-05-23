"""Read port: the latest persisted line state (ADR-0022 — one Port per file)."""

from __future__ import annotations

from typing import Protocol

from sdf_api.contexts.monitoring.domain.line_state import LineStateSnapshot
from sdf_api.shared_kernel.ids import LineId


class LineStateReader(Protocol):
    """Reads the most recent :class:`LineStateSnapshot` for a line, or ``None``."""

    async def latest(self, line_id: LineId) -> LineStateSnapshot | None: ...
