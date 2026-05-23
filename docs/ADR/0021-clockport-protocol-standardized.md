# ADR-0021: Clock injection standardized as `ClockPort` Protocol

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

ADR-0017 forbids `datetime.now()` (Python) / `Instant.now()` (Kotlin) inside `domain/` and requires shell-injected clocks. It listed *two acceptable shapes* on the Python side: a function-argument `now: Callable[[], datetime]` for single-purpose injection, or a `Clock` Protocol when multiple methods are needed. The choice was left to author preference.

Two-shape latitude has produced friction in practice:

1. **Same project, two patterns side by side.** Use cases written first reach for `Callable[[], datetime]` (smaller); use cases written later reach for a Protocol (extensible). Composition wiring then has to provide both — once as a lambda, once as an instance. Test fixtures also fork: `lambda: datetime(...)` vs a `FixedClock` class. The codebase pays the cost of two conventions for one concern.
2. **Reference impl is single-shape.** `the reference codebase` uses `ClockPort` Protocol uniformly: `ports/admin_operations.py:ClockPort` declares `now(self) -> datetime`; production `SystemClock` and test `FixedClock` both implement it; every use case constructor takes a `clock: ClockPort` parameter. The pattern is small, consistent, and proven.
3. **`Clock`-the-name conflicts with `java.time.Clock`.** ADR-0017 references `java.time.Clock` as the Kotlin idiom (constructor-injected, `Clock.systemUTC()` / `Clock.fixed(...)`). Calling the Python Protocol just `Clock` reads as a name collision with the Java stdlib type when scanning across languages. `ClockPort` disambiguates and matches the existing Port-suffix convention.

Single-method Protocols carry a small ceremony cost: three lines of Protocol declaration versus one line for `Callable[[], datetime]`. The cost is paid once per project, not per use case, and is dwarfed by the consistency win.

The `Clock` Protocol option in ADR-0017 was technically a permission, not a requirement. This ADR converts it into the *only* acceptable shape; `Callable[[], datetime]` is retired.

## Decision

**Python**: clock injection is always a `ClockPort` Protocol parameter. `Callable[[], datetime]` is no longer an acceptable injection shape.

```python
# shared_kernel/ports/clock.py
from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...
```

The Protocol lives in `shared_kernel/ports/clock.py` — clock is a cross-cutting concern shared by every BC, so a per-BC duplicate definition would invite divergence. (`the reference codebase` co-locates `ClockPort` inside `ports/admin_operations.py` because it is single-BC; for our multi-BC structure, the cross-cutting location is `shared_kernel/`.)

Production binding (composition root):

```python
# adapters/system_clock.py
from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=UTC)
```

Returns tz-aware UTC `datetime`. Naive datetime is never produced by the production clock; use cases that need a different tz convert at the boundary they care about.

Test binding (in `tests/<bc>/fakes.py` per ADR-0024):

```python
class FixedClock:
    def __init__(self, frozen: datetime) -> None:
        self._frozen = frozen

    def now(self) -> datetime:
        return self._frozen
```

Use case shape:

```python
class CreateLineUseCase:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], clock: ClockPort) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, ...) -> Outcome:
        async with self._uow_factory() as uow:
            now = self._clock.now()
            ...
```

**Kotlin** is unchanged: `java.time.Clock` (stdlib) as a constructor argument per ADR-0017. Kotlin already has a single-shape convention; no migration needed.

## Consequences

### Positive
- One way to express "this code needs the wall clock". Composition wiring is uniform; test fixtures are uniform.
- Cross-BC consistency: every use case takes `clock: ClockPort`; reviewers do not need to remember which BC uses which shape.
- Extension path: if a second clock method is ever needed (`monotonic()`, `today_local()`), it adds to the Protocol — no breaking refactor from `Callable` to Protocol.
- Reference alignment: matches `the reference codebase` shape directly.
- Naming disambiguates from Kotlin's `java.time.Clock`.

### Negative / Trade-offs
- Three lines of Protocol declaration where `Callable[[], datetime]` was one. Small, one-time cost.
- Existing call sites (if any predate this ADR) need a mechanical rewrite. In practice there are none yet — this ADR lands before the first Phase 1 use case.

## Migration Path

Forward: each new use case takes `clock: ClockPort`; the composition root wires `SystemClock`; tests pass `FixedClock(frozen=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))`.

Reversal (back to mixed shapes) would mean re-allowing `Callable[[], datetime]` and updating wiring. Mechanical; the loss is consistency.

## Sources

- `adapters/system_clock.py` + `ports/admin_operations.py:ClockPort` — reference impl.
- Python `typing.Protocol` (PEP 544) — https://peps.python.org/pep-0544/
- Internal: `docs/ADR/0017-system-reads-injection.md` (superseded shape latitude), `docs/architecture/2026-05-23-code-architecture.md` §5, `docs/plans/2026-05-23-reference-codebase-alignment-plan.md` §10.
