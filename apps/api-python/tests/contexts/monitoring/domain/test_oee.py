"""Property-based and example tests for OEE computation (ISO 22400-2:2014 §6).

Covers:
- Structural invariants (availability, quality bounded; performance ≥ 0; OEE formula).
- Phase-1 property: APT == PBT > 0 and produced ≥ 1  ⇒  availability == 1.0 exactly.
- Quality monotonicity in good_quantity.
- All three OeeUndefined variants.
- All corrupt-input ValueError cases.
- Performance > 1 honesty (no clamping).
- Worked Phase-1 example.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sdf_api.contexts.monitoring.domain.oee import (
    OeeInputs,
    OeeReading,
    OeeUndefined,
    OeeUndefinedReason,
    compute_oee,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# A finite, non-NaN float that is strictly positive (used for time values).
_positive_float = st.floats(min_value=1e-9, max_value=1e12, allow_nan=False, allow_infinity=False)

# A finite, non-NaN float that is non-negative (used for ICT which may be 0).
_nonneg_float = st.floats(min_value=0.0, max_value=1e12, allow_nan=False, allow_infinity=False)


@st.composite
def valid_oee_inputs(draw: st.DrawFn) -> OeeInputs:
    """Strategy for inputs guaranteed to produce OeeReading (no undefined cases)."""
    # PBT > 0 so availability is defined; APT in (0, PBT] so APT > 0 too.
    pbt = draw(_positive_float)
    apt = draw(st.floats(min_value=1e-9, max_value=pbt, allow_nan=False, allow_infinity=False))
    # Ensure APT is really > 0 (st.floats with min_value=1e-9 guarantees this).
    produced = draw(st.integers(min_value=1, max_value=10_000))
    good = draw(st.integers(min_value=0, max_value=produced))
    ict = draw(_nonneg_float)
    return OeeInputs(
        produced_quantity=produced,
        good_quantity=good,
        ideal_cycle_time_s=ict,
        actual_production_time_s=apt,
        planned_busy_time_s=pbt,
    )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(inputs=valid_oee_inputs())
@settings(max_examples=500)
def test_oee_reading_structural_invariants(inputs: OeeInputs) -> None:
    """availability ∈ [0,1]; quality ∈ [0,1]; performance ≥ 0; oee ≥ 0; formula holds."""
    result = compute_oee(inputs)
    assert isinstance(result, OeeReading)

    assert 0.0 <= result.availability <= 1.0
    assert 0.0 <= result.quality <= 1.0
    assert result.performance >= 0.0
    assert result.oee >= 0.0

    expected_oee = result.availability * result.performance * result.quality
    assert result.oee == pytest.approx(expected_oee, abs=1e-9)


@given(
    pbt=_positive_float,
    produced=st.integers(min_value=1, max_value=10_000),
    good=st.integers(min_value=0),
    ict=_nonneg_float,
)
def test_availability_is_one_when_apt_equals_pbt(
    pbt: float, produced: int, good: int, ict: float
) -> None:
    """Phase-1 property: APT == PBT and produced ≥ 1  ⇒  availability == 1.0 exactly."""
    good = min(good, produced)
    inputs = OeeInputs(
        produced_quantity=produced,
        good_quantity=good,
        ideal_cycle_time_s=ict,
        actual_production_time_s=pbt,
        planned_busy_time_s=pbt,
    )
    result = compute_oee(inputs)
    assert isinstance(result, OeeReading)
    assert result.availability == 1.0


@given(
    pbt=_positive_float,
    apt=st.floats(min_value=1e-9, max_value=None, allow_nan=False, allow_infinity=False),
    produced=st.integers(min_value=1, max_value=10_000),
    good1=st.integers(min_value=0),
    good2=st.integers(min_value=0),
    ict=_nonneg_float,
)
def test_quality_monotonic_in_good_quantity(
    pbt: float,
    apt: float,
    produced: int,
    good1: int,
    good2: int,
    ict: float,
) -> None:
    """Fixing produced & times: good1 < good2  ⇒  quality1 ≤ quality2."""
    apt = min(apt, pbt) if apt > pbt else apt
    apt = max(apt, 1e-9)
    good1 = min(good1, produced)
    good2 = min(good2, produced)
    if good1 > good2:
        good1, good2 = good2, good1

    inputs1 = OeeInputs(
        produced_quantity=produced,
        good_quantity=good1,
        ideal_cycle_time_s=ict,
        actual_production_time_s=apt,
        planned_busy_time_s=pbt,
    )
    inputs2 = OeeInputs(
        produced_quantity=produced,
        good_quantity=good2,
        ideal_cycle_time_s=ict,
        actual_production_time_s=apt,
        planned_busy_time_s=pbt,
    )
    r1 = compute_oee(inputs1)
    r2 = compute_oee(inputs2)
    assert isinstance(r1, OeeReading)
    assert isinstance(r2, OeeReading)
    # good1 ≤ good2  ⇒  quality1 ≤ quality2
    assert r1.quality <= r2.quality + 1e-12  # tolerance for float rounding


# ---------------------------------------------------------------------------
# Explicit example tests — OeeUndefined variants
# ---------------------------------------------------------------------------


def test_undefined_no_production() -> None:
    """produced == 0  ⇒  OeeUndefined(NO_PRODUCTION)."""
    inputs = OeeInputs(
        produced_quantity=0,
        good_quantity=0,
        ideal_cycle_time_s=1.0,
        actual_production_time_s=300.0,
        planned_busy_time_s=300.0,
    )
    result = compute_oee(inputs)
    assert isinstance(result, OeeUndefined)
    assert result.reason is OeeUndefinedReason.NO_PRODUCTION


def test_undefined_zero_planned_time() -> None:
    """PBT == 0 forces APT == 0 via APT<=PBT precondition => OeeUndefined(ZERO_PLANNED_TIME)."""
    inputs = OeeInputs(
        produced_quantity=10,
        good_quantity=8,
        ideal_cycle_time_s=1.0,
        actual_production_time_s=0.0,
        planned_busy_time_s=0.0,
    )
    result = compute_oee(inputs)
    assert isinstance(result, OeeUndefined)
    assert result.reason is OeeUndefinedReason.ZERO_PLANNED_TIME


def test_undefined_zero_production_time() -> None:
    """produced > 0, APT == 0, PBT > 0  ⇒  OeeUndefined(ZERO_PRODUCTION_TIME)."""
    inputs = OeeInputs(
        produced_quantity=10,
        good_quantity=8,
        ideal_cycle_time_s=1.0,
        actual_production_time_s=0.0,
        planned_busy_time_s=300.0,
    )
    result = compute_oee(inputs)
    assert isinstance(result, OeeUndefined)
    assert result.reason is OeeUndefinedReason.ZERO_PRODUCTION_TIME


# ---------------------------------------------------------------------------
# Explicit example tests — corrupt inputs (ValueError)
# ---------------------------------------------------------------------------


def test_raises_good_exceeds_produced() -> None:
    with pytest.raises(ValueError, match="good_quantity cannot exceed produced_quantity"):
        compute_oee(
            OeeInputs(
                produced_quantity=5,
                good_quantity=6,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=10.0,
                planned_busy_time_s=10.0,
            )
        )


def test_raises_negative_produced() -> None:
    with pytest.raises(ValueError, match="quantities must be non-negative"):
        compute_oee(
            OeeInputs(
                produced_quantity=-1,
                good_quantity=0,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=10.0,
                planned_busy_time_s=10.0,
            )
        )


def test_raises_negative_time() -> None:
    with pytest.raises(ValueError, match="times must be non-negative"):
        compute_oee(
            OeeInputs(
                produced_quantity=10,
                good_quantity=8,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=-1.0,
                planned_busy_time_s=10.0,
            )
        )


def test_raises_apt_exceeds_pbt() -> None:
    with pytest.raises(ValueError, match="actual_production_time_s cannot exceed"):
        compute_oee(
            OeeInputs(
                produced_quantity=10,
                good_quantity=8,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=20.0,
                planned_busy_time_s=10.0,
            )
        )


def test_corrupt_guard_fires_before_zero_pbt_branch() -> None:
    """APT > PBT must raise ValueError, NOT return ZERO_PLANNED_TIME.

    Pins the ordering: _reject_corrupt's APT>PBT check runs before compute_oee
    inspects the zero-PBT branch.  produced>0 and APT>0 ensure we only hit the
    APT>PBT precondition, not any undefined-case path.
    """
    with pytest.raises(ValueError, match="actual_production_time_s cannot exceed"):
        compute_oee(
            OeeInputs(
                produced_quantity=5,
                good_quantity=3,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=10.0,
                planned_busy_time_s=0.0,
            )
        )


def test_raises_nan_in_float_fields() -> None:
    """NaN in any float field must raise ValueError, not produce a poisoned OeeReading."""

    nan = float("nan")
    with pytest.raises(ValueError, match="must be finite"):
        compute_oee(
            OeeInputs(
                produced_quantity=10,
                good_quantity=8,
                ideal_cycle_time_s=nan,
                actual_production_time_s=10.0,
                planned_busy_time_s=10.0,
            )
        )
    with pytest.raises(ValueError, match="must be finite"):
        compute_oee(
            OeeInputs(
                produced_quantity=10,
                good_quantity=8,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=nan,
                planned_busy_time_s=10.0,
            )
        )
    with pytest.raises(ValueError, match="must be finite"):
        compute_oee(
            OeeInputs(
                produced_quantity=10,
                good_quantity=8,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=10.0,
                planned_busy_time_s=nan,
            )
        )


def test_raises_inf_in_float_fields() -> None:
    """Infinity in any float field must raise ValueError."""
    inf = float("inf")
    with pytest.raises(ValueError, match="must be finite"):
        compute_oee(
            OeeInputs(
                produced_quantity=10,
                good_quantity=8,
                ideal_cycle_time_s=inf,
                actual_production_time_s=10.0,
                planned_busy_time_s=10.0,
            )
        )
    with pytest.raises(ValueError, match="must be finite"):
        compute_oee(
            OeeInputs(
                produced_quantity=10,
                good_quantity=8,
                ideal_cycle_time_s=1.0,
                actual_production_time_s=inf,
                planned_busy_time_s=inf,
            )
        )


# ---------------------------------------------------------------------------
# Performance > 1 honesty test
# ---------------------------------------------------------------------------


def test_performance_can_exceed_one() -> None:
    """ISO 22400-2 does not clamp Performance.  OEE > 1 is allowed and expected here."""
    inputs = OeeInputs(
        produced_quantity=10,
        good_quantity=10,
        ideal_cycle_time_s=100.0,
        actual_production_time_s=10.0,
        planned_busy_time_s=10.0,
    )
    result = compute_oee(inputs)
    assert isinstance(result, OeeReading)
    assert result.performance == pytest.approx(100.0)
    assert result.oee == pytest.approx(100.0)
    assert result.performance > 1.0
    assert result.oee > 1.0


# ---------------------------------------------------------------------------
# Worked Phase-1 example
# ---------------------------------------------------------------------------


def test_worked_phase1_example() -> None:
    """produced=100, good=95, ICT=1.0s, APT=PBT=300s (Phase-1 bucket of 5 min)."""
    inputs = OeeInputs(
        produced_quantity=100,
        good_quantity=95,
        ideal_cycle_time_s=1.0,
        actual_production_time_s=300.0,
        planned_busy_time_s=300.0,
    )
    result = compute_oee(inputs)
    assert isinstance(result, OeeReading)

    assert result.availability == 1.0
    assert result.quality == pytest.approx(0.95)
    assert result.performance == pytest.approx(100.0 / 300.0)
    assert result.oee == pytest.approx(0.95 / 3.0)
