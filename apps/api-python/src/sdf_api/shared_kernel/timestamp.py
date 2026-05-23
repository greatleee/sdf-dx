"""Domain timestamp value object.

A point in time as the domain understands it. The single invariant is
*timezone-awareness*: the production clock (ADR-0021 ``SystemClock``) returns
tz-aware UTC and the Pydantic boundary uses ``AwareDatetime``, so a *naive*
datetime reaching the domain is a shell contract breach — it raises (ADR-0016
invariant violation), it is never a domain outcome.

``order=True`` gives natural chronological comparison, relied on by the
line-state machine to reject out-of-order observations (UC-001 invariant:
``since`` is non-decreasing for a given line).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, order=True)
class Timestamp:
    """A timezone-aware instant. Naive datetimes are rejected at construction."""

    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValueError("Timestamp requires a timezone-aware datetime")

    def __str__(self) -> str:
        return self.value.isoformat()
