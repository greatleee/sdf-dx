"""Query read-models for the monitoring bounded context.

These are the projection types the read-side ports return: pure, frozen value
objects assembled by the DB adapters from query rows and consumed by the
application / composition layers. They live in ``domain/`` because that is the one
layer that ports, adapters, and application may all import without breaching the
``adapters-no-upward`` / ``composition-only-imports-adapters`` contracts
(ADR-0023 #6 / #7).

``LineStateSnapshot`` (live state) and ``OeeReading`` (the A·P·Q result) are the
existing Section D domain types; this module adds only the *read envelope* the OEE
query needs — the window enum plus a line+window+timestamp wrapper around an
``OeeReading``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sdf_api.contexts.monitoring.domain.oee import OeeReading
from sdf_api.shared_kernel.ids import LineId
from sdf_api.shared_kernel.timestamp import Timestamp


class OeeWindow(StrEnum):
    """OEE aggregation windows per the OpenAPI contract (``openapi/sdf-api.yaml``)."""

    FIVE_MINUTES = "5m"
    ONE_HOUR = "1h"
    SHIFT = "shift"


@dataclass(frozen=True, slots=True)
class LineOeeSnapshot:
    """An OEE reading for a line over a window, tagged with the window's end time."""

    line_id: LineId
    window: OeeWindow
    reading: OeeReading
    observed_at: Timestamp
