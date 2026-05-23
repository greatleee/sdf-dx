# ADR-0024: Fakes — per-BC file + `InMemoryDataset` shared state

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

ADR-0020 introduces the `UnitOfWork` Protocol and a corresponding fake (`FakeUnitOfWork`) for use-case tests. ADR-0019 lets adapters use ORM under containment; the same Port surface is fulfilled by the fake. Open questions: *where* do fakes live, *how* are they organized when a use case exercises multiple repos, and *what guarantees* do they make.

The wrong answer — write per-test ad-hoc fakes — produces three failures over time:

1. **Drift.** Two tests write two slightly different `FakeAuditLogRepo`s. One implements `append` correctly; the other misses a DB-side constraint that the real adapter enforces. Both tests pass; the production code regresses on the missed constraint.
2. **No shared state.** A use case that writes to `lines` and then reads from `audit_logs` needs both fakes to see the same `InMemoryDataset` so the read returns the write. Per-test fakes default to isolated state, forcing tests to plumb the shared mutation in by hand each time.
3. **Mock-shaped fakes.** Without a convention, fakes start as `MagicMock(spec=AuditLogRepo)`. Tests then assert on call patterns ("was `append` called with X") rather than on observable outcomes (the audit log now contains entry X). This is the assertion-on-implementation anti-pattern.

The reference impl (`the reference codebase`) places one `adapters/fakes.py` file with working in-memory implementations. Multiple fakes share a single `InMemoryDataset` instance, mirroring the way real session-bound adapters share an `AsyncSession`. The fake UoW wires them together. Tests inject the dataset, drive the use case, and assert on the dataset state — never on call patterns.

For our project, the only deviation is location: the reference codebase has fakes under `adapters/` because Python single-source layout makes that natural. Our `src/` is production code only; tests live under `backend/tests/`. The fakes belong in `tests/`, organized per BC to mirror the production `contexts/<bc>/` layout.

A secondary design call: should `InMemoryDataset` be per-BC or global? Per-BC mirrors the per-BC UnitOfWork from ADR-0020 — a fake UoW for the monitoring BC composes monitoring-only repos around a `MonitoringInMemoryDataset`. Cross-BC use-case tests instantiate one dataset per BC, matching the production "one UoW per BC, in sequence" pattern. This keeps the contract that no atomic tx spans BCs, even in tests.

## Decision

**Location**: `backend/tests/contexts/<bc>/fakes.py` — one file per BC, alongside the BC's tests:

```
backend/tests/
├─ architecture/                  # ADR-0023 import contracts + AST checks
├─ contexts/
│  ├─ monitoring/
│  │  ├─ fakes.py                 # InMemoryDataset + FakeUnitOfWork + per-Port fakes
│  │  ├─ domain/                  # pure-function tests
│  │  ├─ application/             # use-case tests
│  │  └─ adapters/                # integration tests (testcontainers)
│  └─ configuration/
│     └─ ...
└─ shared_kernel/
   └─ fakes.py                    # FixedClock + any cross-cutting fakes
```

Cross-cutting fakes (e.g., `FixedClock` for `ClockPort` per ADR-0021) live in `tests/shared_kernel/fakes.py`, mirroring the production `shared_kernel/ports/` location.

**Discipline — fakes are working implementations, not mocks**:

- Each fake implements the production Port Protocol structurally.
- State mutates on writes; reads return the mutated state.
- DB-side constraints relevant to behavior (e.g., `GENERATED` columns, biconditional `CHECK` constraints) are mirrored in the fake. The fake `FakeOrdersRepo.insert_order` computes `quantity_remaining = quantity_total - quantity_filled` itself; `FakeOrdersRepo.cancel_with_reason` sets both `status` and `cancelled_reason` together; etc. The rule is: *the fake fails the same kinds of inputs the real adapter fails*.
- No assertion-on-call. Tests assert on observable outcomes (dataset state, returned domain values, sum-type variants), never on whether a method was called or with what arguments.

**`InMemoryDataset` per BC**: a `@dataclass` holding the BC's mutable state:

```python
# tests/contexts/monitoring/fakes.py
from dataclasses import dataclass, field
# ... imports ...

@dataclass
class MonitoringInMemoryDataset:
    line_events: list[LineEvent] = field(default_factory=list)
    line_states: dict[LineId, LineStateProjection] = field(default_factory=dict)
    audit_logs: list[AuditLogEntry] = field(default_factory=list)
```

`FakeUnitOfWork` takes an `InMemoryDataset` argument and constructs each per-feature fake around it, so all repos within one UoW see one source of truth:

```python
class FakeUnitOfWork:
    def __init__(self, dataset: MonitoringInMemoryDataset) -> None:
        self._dataset = dataset
        self.line_events: FakeLineEventWriter = FakeLineEventWriter(dataset)
        self.line_states: FakeLineStateReader = FakeLineStateReader(dataset)
        self.audit_logs: FakeAuditLogRepo = FakeAuditLogRepo(dataset)
        self.committed: bool = False
        self.rolled_back: bool = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
```

`committed` / `rolled_back` are observable flags; tests assert on them instead of on `commit()` call patterns.

**Optional `call_log`**: when a test needs to verify cross-fake call ordering (lock-then-read, write-then-event-emit), individual fakes accept an optional shared `call_log: list[str]` and append a string on each method entry. Default `None` uses an internal list (no observation effect). This is the only place where a call pattern is observed, and only for ordering — never for argument inspection.

**Test usage shape**:

```python
async def test_create_line_appends_audit_log() -> None:
    dataset = MonitoringInMemoryDataset()
    uow_factory = lambda: FakeUnitOfWork(dataset)
    clock = FixedClock(frozen=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))

    use_case = CreateLineUseCase(uow_factory, clock)
    result = await use_case.execute(make_create_request())

    assert isinstance(result, CreateOk)
    assert len(dataset.audit_logs) == 1
    assert dataset.audit_logs[0].action_key == "line.create"
```

Three test assertions: variant type, dataset state, dataset detail. No mock library imported.

**Pytest marker**: fakes-based tests are unit tests (`@pytest.mark.unit` or no marker). Integration tests using testcontainers go in `tests/contexts/<bc>/adapters/` with `@pytest.mark.integration`.

## Consequences

### Positive
- One fake implementation per Port per BC — no per-test divergence.
- Shared `InMemoryDataset` makes the cross-repo state visible at the test boundary; assertions read like business statements, not implementation traces.
- DB-side constraint mirroring catches "the fake says OK but production rejects" bugs in the unit lane, not in integration.
- Working fakes accelerate test writing — once the dataset is constructed, building scenarios is just calling use cases.
- Per-BC dataset reinforces ADR-0020's per-BC UoW: cross-BC tests construct multiple datasets, never one.

### Negative / Trade-offs
- Per-BC `fakes.py` will grow with the BC. The reference impl's `fakes.py` is 1000+ lines in maturity. Split into multiple files (`fakes/line.py`, `fakes/audit.py`) is permitted once the file becomes hard to navigate — keep the package-level `from .fakes import ...` import shape stable when splitting.
- Mirroring DB-side constraints in the fake duplicates schema knowledge across `migrations/`, the ORM declaration, and the fake. A schema change requires updating all three; the cost is paid for behavior-level test reliability.
- `call_log` is an escape hatch. Overuse re-introduces assertion-on-call patterns. Lint cannot enforce this — review must.

## Migration Path

Forward: when the first use-case test lands for a BC, create `backend/tests/contexts/<bc>/fakes.py` with the `InMemoryDataset` + `FakeUnitOfWork` + the per-Port fakes that the use case needs. Subsequent tests add to the same file.

`tests/shared_kernel/fakes.py` starts with `FixedClock` and grows when cross-cutting Ports (e.g., a future `OutboxPort`) need fakes.

Reversal (dropping shared `InMemoryDataset`, going back to per-test fakes) would be a per-test rewrite — mechanical but the loss is behavior-level assertion clarity. The likely failure mode this ADR prevents (silent fake/production drift) would recur.

If the project ever adopts a property-based test framework for use cases (Hypothesis-driven scenarios), fakes accept Hypothesis-built datasets without modification — the same shape works.

## Sources

- `adapters/fakes.py` — reference impl of working fakes + `InMemoryDataset` pattern (first 200 lines verified in plan §10).
- Harry Percival & Bob Gregory, *Architecture Patterns with Python* — Test pyramid chapter (cosmic-python) — fakes are working in-memory implementations of repositories, not mocks. https://www.cosmicpython.com/
- Martin Fowler, "Mocks Aren't Stubs" — the assertion-on-state vs assertion-on-call distinction. https://martinfowler.com/articles/mocksArentStubs.html
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §10 (test pyramid), `docs/ADR/0019-orm-containment-in-adapters.md`, `docs/ADR/0020-unit-of-work.md`, `docs/ADR/0021-clockport-protocol-standardized.md`, `docs/plans/2026-05-23-reference-codebase-alignment-plan.md` §10.
