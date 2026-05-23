"""Cross-cutting test fakes (ADR-0024).

``FixedClock`` is the sanctioned ``ClockPort`` test binding: domain and use-case
tests pass a frozen instant instead of mocking the system clock (rules §4, §10).
BC-specific fakes live in ``tests/contexts/<bc>/fakes.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FixedClock:
    """A ``ClockPort`` that always returns the same instant."""

    frozen: datetime

    def now(self) -> datetime:
        return self.frozen
