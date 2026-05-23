"""Clock port (ADR-0021).

The only sanctioned way to read the wall clock. Domain and use-case code depend
on this Protocol; ``composition.py`` wires the production ``SystemClock`` (tz-aware
UTC) and tests pass ``FixedClock`` (``tests/shared_kernel/fakes.py``). The retired
``Callable[[], datetime]`` shape from ADR-0017 is no longer acceptable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...
