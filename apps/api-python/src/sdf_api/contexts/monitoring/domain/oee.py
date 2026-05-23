"""OEE (Overall Equipment Effectiveness) — pure functional core.

Implements ISO 22400-2:2014 §6 definitions exactly:

    OEE = Availability x Performance x Quality

    Availability = APT / PBT
    Performance  = (ICT x Produced Quantity) / APT   [ISO calls this "Effectiveness"]
    Quality      = Good Quantity / Produced Quantity

Phase-1 simplification (ADR-0012 §D-2): the shell always passes bucket length as
both APT and PBT, so Availability is always 1.0 in practice.  The function stays
general — it does NOT hardcode 1.0.

Performance can exceed 1.0 when the ideal cycle time is loose (i.e., the line ran
faster than the planned rate).  ISO 22400-2 does not clamp it, and neither do we.
OEE is therefore only *nominally* in [0, 1]; it can exceed 1.  This is documented
as a known unknown in docs/KNOWN-UNKNOWNS.md and is the correct ISO behaviour.

Degenerate-but-normal inputs (idle bucket, zero-time window) return a named
``OeeUndefined`` sum-type case.  Corrupt inputs (violated by-construction
preconditions that cannot come from a correct CAGG) raise ``ValueError`` — those
are programmer errors, not domain outcomes (ADR-0016).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class OeeUndefinedReason(StrEnum):
    NO_PRODUCTION = "no_production"  # produced_quantity == 0 (idle bucket)
    ZERO_PLANNED_TIME = "zero_planned_time"  # planned_busy_time_s == 0
    ZERO_PRODUCTION_TIME = "zero_production_time"  # actual_production_time_s == 0


@dataclass(frozen=True, slots=True)
class OeeInputs:
    produced_quantity: int  # ISO Produced Quantity (good + scrap)
    good_quantity: int  # ISO Good Quantity (excludes rework)
    ideal_cycle_time_s: float  # ISO planned run time per item (PRI), seconds
    actual_production_time_s: float  # APT, seconds
    planned_busy_time_s: float  # PBT, seconds


@dataclass(frozen=True, slots=True)
class OeeReading:
    availability: float
    performance: float
    quality: float
    oee: float


@dataclass(frozen=True, slots=True)
class OeeUndefined:
    reason: OeeUndefinedReason


OeeOutcome = OeeReading | OeeUndefined


def compute_oee(inputs: OeeInputs) -> OeeOutcome:
    """Compute OEE from raw bucket counters per ISO 22400-2:2014 §6.

    Returns ``OeeReading`` for a productive bucket, or ``OeeUndefined`` when
    the result is mathematically undefined (idle bucket or zero-time window).
    Raises ``ValueError`` for corrupt inputs (precondition violations).
    """
    _reject_corrupt(inputs)
    if inputs.produced_quantity == 0:
        return OeeUndefined(OeeUndefinedReason.NO_PRODUCTION)
    if inputs.planned_busy_time_s == 0:
        return OeeUndefined(OeeUndefinedReason.ZERO_PLANNED_TIME)
    if inputs.actual_production_time_s == 0:
        return OeeUndefined(OeeUndefinedReason.ZERO_PRODUCTION_TIME)
    availability = inputs.actual_production_time_s / inputs.planned_busy_time_s
    performance = (
        inputs.ideal_cycle_time_s * inputs.produced_quantity
    ) / inputs.actual_production_time_s
    quality = inputs.good_quantity / inputs.produced_quantity
    oee = availability * performance * quality
    return OeeReading(availability=availability, performance=performance, quality=quality, oee=oee)


def _reject_corrupt(inputs: OeeInputs) -> None:
    """Raise ValueError for inputs that violate by-construction preconditions.

    These checks guard against programmer error (e.g., a CAGG bug that emits
    negative counts), not against normal domain variation.  Every branch here
    represents a condition the CAGG layer is contractually required to prevent.
    """
    for value in (
        inputs.ideal_cycle_time_s,
        inputs.actual_production_time_s,
        inputs.planned_busy_time_s,
    ):
        if not math.isfinite(value):
            raise ValueError("times and cycle time must be finite")
    if inputs.produced_quantity < 0 or inputs.good_quantity < 0:
        raise ValueError("quantities must be non-negative")
    if inputs.good_quantity > inputs.produced_quantity:
        raise ValueError("good_quantity cannot exceed produced_quantity")
    if inputs.ideal_cycle_time_s < 0:
        raise ValueError("ideal_cycle_time_s must be non-negative")
    if inputs.actual_production_time_s < 0 or inputs.planned_busy_time_s < 0:
        raise ValueError("times must be non-negative")
    if inputs.actual_production_time_s > inputs.planned_busy_time_s:
        raise ValueError("actual_production_time_s cannot exceed planned_busy_time_s")
