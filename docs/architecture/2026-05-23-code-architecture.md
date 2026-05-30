# Backend Code Architecture — Conventions

| | |
|---|---|
| **Date** | 2026-05-23 (aligned with `the reference codebase` reference per ADR-0019~0024 same day) |
| **Status** | Draft — initial body + reference alignment. |
| **Layer** | Engineering Conventions (see `docs/SOT-LAYERS.md`) |
| **Scope** | Backend code-level conventions for Python + Kotlin. Frontend conventions: `docs/architecture/2026-05-24-frontend-architecture.md` (+ `.claude/rules/frontend-code-architecture.md`; ADR-0028 / 0029). |
| **Audience** | Self (future me), LLM pair, portfolio reviewer reading code first. |
| **Related** | Strategy `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2, §6, §9. Working notes `docs/plans/2026-05-23-arch-doc-discussion-notes.md`. |

> **Editing rule**: living guide. Edit only when a convention actually evolves. Each substantive change references (or triggers) an ADR. The doc says *how*; the ADR says *why*. See `docs/SOT-LAYERS.md` line *Engineering Conventions* row.

---

## TL;DR (rule cheatsheet)

1. **FC/IS** — domain code is pure, IO at shell. Spec §2.1.
2. **Core returns failures as values** (sealed class / tagged union). Shell may throw at boundary.
3. **Core may not read clock / uuid / random** — these are injected from shell.
4. **DDD tactical**: Value Object ✓ / Aggregate concept ✓ (data + pure functions, no OO methods) / DDD-classical Repository ✗ (no domain-interface-with-infra-impl); `*Repo` *suffix* is allowed as general persistence vocabulary on adapter classes (ADR-0019) / Domain Service term ✗ / Domain Event = pure value returned by core.
5. **shared_kernel**: IDs + cross-cutting VOs only. Plus the cross-cutting Ports `ClockPort` (ADR-0021) and `DomainEventDispatcher`. No aggregates, no services, no cross-BC events.
6. **Cross-BC sync query**: top-level `src/sdf_api/use_cases/`. BCs stay peers (import-linter `bc-independence` contract enforced; ADR-0023).
7. **Cross-BC state propagation**: in-process `DomainEventDispatcher`, fail-fast. No Kafka for domain events.
8. **Cross-aggregate (same BC)**: 1 transaction = 1 aggregate. Multi-aggregate orchestration in application/use-case layer.
9. **Persistence** (Python): SQLAlchemy 2.0 ORM is allowed under containment rules — private `_Base`/`_X` ORM classes, public adapter (`*Repo`) returns domain types or primitives, adapter does not commit (UoW does). Domain never imports `sqlalchemy.*`. ADR-0019 + ADR-0020. Kotlin: Exposed (DSL) or JOOQ (codegen); JPA is forbidden in domain.
10. **Pydantic**: shell boundary only (HTTP DTO, JSON parsing, OpenAPI). Domain uses stdlib `@dataclass(frozen=True, slots=True)`. ADR-0018 (status quo — intentional divergence from `the reference codebase` reference; see ADR for reasoning).
11. **Clock injection**: always `ClockPort` Protocol (Python) / `java.time.Clock` (Kotlin). `Callable[[], datetime]` is retired. ADR-0021.
12. **Unit of Work**: use cases own the transaction boundary via `async with self._uow_factory() as uow:` + `await uow.commit()`. Per-BC `UnitOfWork` Protocol; no cross-BC atomic tx. ADR-0020.
13. **Ports**: `contexts/<bc>/ports/` is a folder, file-per-feature (Port noun in snake_case, no suffix). Cross-cutting Ports in `shared_kernel/ports/`. ADR-0022.
14. **Fakes**: `tests/contexts/<bc>/fakes.py` per BC. Working in-memory implementations of Ports + `InMemoryDataset` shared mutable state. Not mocks. ADR-0024.
15. **Test pyramid**: domain tests = 0 mock / 0 stub / 0 fake / sub-second. Spec §7.

---

## §1. Principles

FC/IS principle statement lives in spec §2.1 (Bernhardt). This section specifies *how* FC/IS lands in this codebase.

### §1.1 The load-bearing rule

**Domain modules contain zero IO imports and zero validation-library imports.**

Test purity, drift toolchain, BC isolation, and reviewer-readability all derive from this single rule. Everything else in this doc is downstream.

### §1.2 What counts as "domain"

| Path | Layer |
|---|---|
| `src/sdf_api/contexts/<bc>/domain/` (Python) | Core |
| `apps/*/src/main/kotlin/**/domain/` (Kotlin) | Core |
| `src/sdf_api/contexts/<bc>/ports/` *(folder, file-per-feature; ADR-0022)* | Core (Port Protocols only — no IO) |
| `src/sdf_api/contexts/<bc>/application/` | Shell (BC-local use cases) |
| `src/sdf_api/contexts/<bc>/adapters/` | Shell (IO) |
| `src/sdf_api/use_cases/` | Shell (cross-BC use cases — see §3.2) |
| `src/sdf_api/shared_kernel/` | Core (cross-BC pure values + cross-cutting Ports — see §6) |
| `src/sdf_api/shared_kernel/ports/` | Core (cross-cutting Port Protocols: `ClockPort` per ADR-0021, etc.) |
| `src/sdf_api/composition.py` | Shell (wiring root) |
| `backend/tests/contexts/<bc>/fakes.py` | Test (in-memory Port implementations + `InMemoryDataset`; ADR-0024) |
| `backend/tests/shared_kernel/fakes.py` | Test (cross-cutting fakes: `FixedClock`, etc.) |
| `backend/tests/architecture/` | Test (import-linter contracts + AST checks; ADR-0023) |

### §1.3 What core may not do

| Operation | Core | Shell |
|---|---|---|
| Read DB / Kafka / HTTP / filesystem | ❌ | ✅ |
| Read clock / UUID / randomness | ❌ | ✅ — inject value into core (§5) |
| Throw exceptions | ❌ — return as value (§4) | ✅ at HTTP boundary |
| Validate input shape (JSON, dict) | ❌ — Pydantic forbidden here (§8) | ✅ |
| Validate domain invariant | ✅ via sum types / functions | — |
| Log / emit metric | ❌ | ✅ |
| Construct domain events | ✅ as return values | — |
| Dispatch domain events | ❌ | ✅ via `DomainEventDispatcher` (§3.3) |

Enforcement: §9.

---

## §2. DDD Tactical Mapping

Each DDD tactical pattern maps to one of: core / shell / dropped. Where the term is used, it follows DDD definition; where dropped, this doc names the local convention.

| Pattern | Placement | Term used? | Local convention |
|---|---|---|---|
| Value Object | Core | ✓ | `@dataclass(frozen=True, slots=True)` (Python) / `data class` with `val` (Kotlin). |
| Aggregate | Core (data + pure functions) | ✗ | "Domain module root data type". No OO methods, no self-mutation. Behavior in module-level functions, not on the type. |
| Domain Event | Core returns as value | ✓ | Past-tense verb, no `Event` suffix: `LineWentDown`, `OrderPlaced`. Part of sum-type return from core; dispatched in shell. |
| Repository (DDD-classical "domain interface + infra impl") | Shell only | ✗ | Just Ports + Adapters; no "domain interface declared in core, implementation in infra" extra layer. *Suffix* `*Repo` is allowed on adapter and port classes (general persistence vocabulary, not DDD-classical marker) per ADR-0019. `<Noun>Reader` / `<Noun>Writer` / `<Noun>Port` / `<Noun>Repo` all available; pick by concrete role. |
| Domain Service | Split | ✗ | Pure logic → module-level function in `domain/`. Mixed-with-IO → use case in `application/`. The term itself is not used in code or docs. |
| Factory | Core (just a function) | ✗ | Module-level function, often `make_<noun>` or just the constructor. No `Factory` suffix. |
| Entity (with identity) | Core (data + transition functions) | ✓ (limited) | Same shape as Aggregate. ID equality, no method-based self-mutation. |
| Specification | — | ✗ | A predicate function (`fn(x: T) -> bool`). No class. |

### §2.1 Naming consequences

- **No `*Service` suffix** in domain code (it would imply Domain Service, which we've dropped).
- **No `*Repository`** anywhere (DDD-classical "Repository pattern" abstraction is the rejected concept). `*Repo` *suffix* IS allowed on adapter and port classes per ADR-0019 — it is general persistence vocabulary, not a DDD marker. Examples: `PostgresOrdersRepo`, `AdminLineRepo`.
- **No `*Factory`** — `make_topology(...)` or just call the dataclass.
- **Ports**: `<Noun>Reader` (read-only), `<Noun>Writer` (write-only), `<Noun>Port`, `<Noun>Repo`, `<Noun>Ledger` — pick by concrete role. Lives in `contexts/<bc>/ports/<noun>.py` (Python folder, file-per-feature; ADR-0022) or `<package>/ports/` (Kotlin). Cross-cutting Ports in `shared_kernel/ports/`.
- **State transitions**: `apply_<event>(state, event) -> <Outcome>`. Pure function on the domain root, never a method.

---

## §3. Bounded Context boundaries + cross-BC + cross-aggregate calls

Spec §2.2 covers BC evolution policy. This section specifies the call mechanics.

### §3.1 BC-internal — cross-aggregate

- **One transaction = one aggregate write.** A use case that touches multiple aggregates orchestrates them sequentially in the application layer, each in its own consistency boundary.
- If two aggregates must be consistent atomically, that's a signal they should be one aggregate.
- Cross-aggregate orchestration always lives in `contexts/<bc>/application/`, never in `contexts/<bc>/domain/`.

### §3.2 Cross-BC — synchronous queries (joins)

Queries that need data from multiple BCs (e.g., "line state + machine metadata") live in **`src/sdf_api/use_cases/`** — top-level, outside any BC.

```
src/sdf_api/
├── contexts/
│   ├── monitoring/
│   │   ├── domain/
│   │   ├── application/         ← BC-local use cases only
│   │   ├── adapters/
│   │   └── ports/               ← folder, file-per-feature (ADR-0022)
│   │       ├── __init__.py
│   │       ├── line_state.py
│   │       ├── line_event.py
│   │       └── unit_of_work.py  ← per-BC UoW Protocol (ADR-0020)
│   └── topology/
│       └── ...
├── use_cases/                   ← cross-BC ONLY
│   └── get_line_with_meta.py
├── shared_kernel/
│   ├── ports/                   ← cross-cutting Ports (ADR-0021/0022)
│   │   └── clock.py             ← ClockPort
│   └── events.py                ← DomainEventDispatcher
└── composition.py
```

#### Rules

- A file in `use_cases/` may import multiple BCs' `ports/` files.
- A file in `use_cases/` may **not** import any BC's `domain/` or `adapters/` directly. (`use-cases-no-domain-or-adapters` contract — ADR-0023 #4.)
- A file in `contexts/<bc>/application/` may **not** import any other BC at all. (`bc-independence` contract — ADR-0023 #5.)
- A file in `contexts/<bc>/adapters/` may **not** import `ports/`, `application/`, or `use_cases/` upward. Port satisfaction is structural; composition root acknowledges with `cast(...)`. (`adapters-no-upward` contract — ADR-0023 #6.)
- The composition root (`composition.py`) wires concrete adapters into both BC-local and cross-BC use cases.

#### Example

```python
# contexts/monitoring/ports/line_state.py
class LineStateReader(Protocol):
    async def latest(self, line_id: LineId) -> LineStateSnapshot | NotFound: ...

# contexts/topology/ports/line.py
class TopologyReader(Protocol):
    async def line(self, line_id: LineId) -> Line | NotFound: ...

# use_cases/get_line_with_meta.py
from sdf_api.contexts.monitoring.ports.line_state import LineStateReader
from sdf_api.contexts.topology.ports.line import TopologyReader

async def get_line_with_meta(
    line_id: LineId,
    monitoring: LineStateReader,
    topology: TopologyReader,
) -> LineWithMeta | NotFound:
    state = await monitoring.latest(line_id)
    line = await topology.line(line_id)
    if isinstance(state, NotFound) or isinstance(line, NotFound):
        return NotFound(reason=...)
    return LineWithMeta(state=state, line=line)
```

### §3.3 Cross-BC — state propagation (domain events)

In-process `DomainEventDispatcher`, defined in `shared_kernel/events.py`. **Kafka is not used for domain events.** Rationale in §3.4.

#### Interface

```python
# shared_kernel/events.py
from collections.abc import Awaitable, Callable

class DomainEventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable[..., Awaitable[None]]]] = {}

    def register[E](
        self,
        event_type: type[E],
        handler: Callable[[E], Awaitable[None]],
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def dispatch(self, event: object) -> None:
        # Fail-fast: handler exceptions propagate to caller.
        for handler in self._handlers.get(type(event), []):
            await handler(event)
```

#### Producer side (BC that emits)

```python
# contexts/monitoring/domain/line_state.py — pure
@dataclass(frozen=True)
class StateChange:
    new_state: State
    events: tuple[DomainEvent, ...]

@dataclass(frozen=True)
class Rejected:
    reason: str

ApplyOutcome = StateChange | Rejected

def apply_event(state: State, event: TelemetryEvent, at: datetime) -> ApplyOutcome:
    if not _is_allowed(state, event):
        return Rejected(reason=f"event {event.kind} not allowed in {state.value}")
    new_state = _transition(state, event, at)
    domain_events = _emit_for(state, new_state, at)
    return StateChange(new_state=new_state, events=tuple(domain_events))

# contexts/monitoring/application/handle_telemetry.py — shell
async def handle_telemetry(
    event: TelemetryEvent,
    state_reader: LineStateReader,
    state_writer: LineStateWriter,
    dispatcher: DomainEventDispatcher,
    now: Callable[[], datetime],
) -> None:
    state = await state_reader.latest(event.line_id)
    outcome = apply_event(state, event, at=now())
    match outcome:
        case StateChange():
            await state_writer.save(outcome.new_state)
            for e in outcome.events:
                await dispatcher.dispatch(e)
        case Rejected():
            logger.warning("rejected", reason=outcome.reason)
```

#### Consumer side (another BC subscribes)

```python
# contexts/quality/application/on_line_went_down.py
async def on_line_went_down(event: LineWentDown) -> None:
    # quality BC reacts to monitoring's event without knowing monitoring exists
    ...
```

#### Composition (root)

```python
# composition.py
dispatcher = DomainEventDispatcher()
dispatcher.register(LineWentDown, quality.on_line_went_down)
dispatcher.register(LineWentDown, alarm.on_line_went_down)
```

#### Failure policy: fail-fast

A handler exception propagates out of `dispatch()` and aborts the dispatch loop. The caller (use case) decides whether to roll back the transaction.

Rationale: in Phase 1~4, every cross-BC event is part of domain consistency. Silent handler failure (try/except inside the dispatcher) would create implicit "best-effort" behavior that diverges from the apparent control flow. A genuinely best-effort handler wraps its own logic in `try/except`; the dispatcher itself stays strict.

Tests must cover handler-throws scenarios explicitly (use case test with a deliberately-failing handler).

#### Migration path

When BCs are extracted to separate services, `DomainEventDispatcher`'s producer implementation becomes a Kafka publisher; the consumer side becomes a Kafka consumer that calls the same handler functions. The public interface (`register`, `dispatch`) is unchanged at the source level.

### §3.4 Why not Kafka for domain events (Phase 1~4)

Kafka in this project is reserved for the **telemetry pipeline** (OPC UA → MQTT → Sparkplug bridge → Kafka → ingest). Domain events are a different abstraction layer:

- Telemetry messages are *integration* (external system ↔ this system).
- Domain events are *intra-application* (BC ↔ BC inside this app).

Bundling them onto the same broker requires topic/payload-namespace discipline plus an extra integration-test surface (testcontainers per Kafka domain event). The cost is real even though the infrastructure is "already there."

Phase 1~4 BCs all live in one Python process (`api-python`). In-process dispatch is cheaper, easier to debug, and allows same-transaction handler execution.

---

## §4. Error Representation — core returns values

### §4.1 Rule

Core (`domain/`) does not raise on expected failures. Failure shapes are part of the return type, expressed as a sum type. Shell may translate to exceptions at the HTTP/Kafka boundary.

"Expected failure" = anything the call site might reasonably handle differently. "Unexpected failure" (assertion violation, programmer error) may still raise — those are bugs, not domain outcomes.

### §4.2 Python idiom

`@dataclass(frozen=True)` cases + `Union` (`|`). Discriminate with `match` or `isinstance`.

```python
@dataclass(frozen=True)
class StateChange:
    new_state: State
    events: tuple[DomainEvent, ...]

@dataclass(frozen=True)
class Rejected:
    reason: str

ApplyOutcome = StateChange | Rejected

def apply_event(state: State, event: Event) -> ApplyOutcome:
    if not _is_allowed(state, event):
        return Rejected(reason="...")
    return StateChange(new_state=..., events=(LineWentDown(...),))

# Call site — match
match apply_event(state, event):
    case StateChange(new_state, events):
        ...
    case Rejected(reason):
        ...
```

### §4.3 Kotlin idiom

`sealed interface` + `data class` cases.

```kotlin
sealed interface ApplyOutcome
data class StateChange(val newState: State, val events: List<DomainEvent>) : ApplyOutcome
data class Rejected(val reason: String) : ApplyOutcome

fun applyEvent(state: State, event: Event): ApplyOutcome =
    if (!isAllowed(state, event)) Rejected(reason = "...")
    else StateChange(newState = ..., events = listOf(LineWentDown(...)))

// Call site — when with exhaustiveness check
when (val outcome = applyEvent(state, event)) {
    is StateChange -> { ... }
    is Rejected    -> { ... }
}
```

### §4.4 Boundary translation

At the HTTP boundary, sum cases become HTTP status codes:

```python
@router.get("/lines/{line_id}/state")
async def get_state(line_id: UUID, uc: GetLineState = Depends(...)) -> LineStateDTO:
    match await uc(LineId(line_id)):
        case Found(snapshot):
            return LineStateDTO.from_domain(snapshot)
        case NotFound(reason):
            raise HTTPException(status_code=404, detail=reason)
```

Pydantic DTOs live at the boundary, not in core (§8.2).

### §4.5 Anti-patterns

- ❌ `return None` for "not found" — always use a named case (`NotFound`).
- ❌ `Optional<T>` for domain failures — only acceptable for genuinely optional values where absence has no reason.
- ❌ `Result<T, str>` with stringly-typed errors — case names are part of the API.
- ❌ Throwing in core — bypasses exhaustiveness, makes purity tests harder to write.
- ❌ `raise InvalidTransition(...)` inside `apply_event` — return `Rejected(reason=...)` instead.

### §4.6 No external lib

- Kotlin: stdlib `Result<T>` conflates failure types and discards type info on the error side. `arrow-kt` `Either` adds a substantial dependency for a pattern that sealed interfaces express natively. We use sealed interfaces.
- Python: `returns.result.Result` mimics Kotlin's `Result`. Python typing's `Union` + `match` is native and clearer.
- Forbidden in domain (§9): `arrow.core.*`, `returns.*`.

---

## §5. Clock / UUID / Random injection

### §5.1 Rule

Core may not read the system clock, generate UUIDs, or sample randomness. These are *system reads* — they make functions impure and tests non-deterministic.

Shell injects the value or a callable at the use-case boundary.

### §5.2 Python idiom

Always a `ClockPort` Protocol — `Callable[[], datetime]` is retired (ADR-0021). The Protocol lives in `shared_kernel/ports/clock.py` because clock is a cross-cutting concern shared by every BC.

```python
# shared_kernel/ports/clock.py
from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...


# Pure — value injected as parameter
def apply_event(state: State, event: Event, at: datetime) -> ApplyOutcome: ...


# Shell — use case takes ClockPort, passes value to core
class HandleTelemetryUseCase:
    def __init__(self, ..., clock: ClockPort) -> None:
        self._clock = clock

    async def execute(self, event: TelemetryEvent) -> None:
        outcome = apply_event(state, event, at=self._clock.now())
        ...


# adapters/system_clock.py — production binding
from datetime import UTC, datetime

class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=UTC)


# tests/shared_kernel/fakes.py — test binding (ADR-0024)
class FixedClock:
    def __init__(self, frozen: datetime) -> None:
        self._frozen = frozen

    def now(self) -> datetime:
        return self._frozen
```

If a second method ever lands (e.g., `monotonic()`), it extends the same `ClockPort` Protocol — no breaking refactor.

UUID / randomness use the same shape: a `UUIDPort` / `RandomPort` Protocol in `shared_kernel/ports/`, real `SystemUUID` / `SystemRandom` adapters, `FixedUUID` / `SeededRandom` fakes.

### §5.3 Kotlin idiom

`java.time.Clock` is stdlib and the standard injection point.

```kotlin
// Pure
fun applyEvent(state: State, event: Event, at: Instant): ApplyOutcome { ... }

// Shell
class HandleTelemetry(private val clock: Clock, ...) {
    suspend operator fun invoke(event: TelemetryEvent) {
        val outcome = applyEvent(state, event, at = clock.instant())
        ...
    }
}

// composition
val realClock: Clock = Clock.systemUTC()

// tests
val fixedClock = Clock.fixed(Instant.parse("2026-05-23T12:00:00Z"), ZoneOffset.UTC)
```

### §5.4 Test corollary

Domain tests pass explicit timestamps (`at=datetime(2026, 5, 23, ...)`); never `datetime.now()`. Application tests inject a frozen clock. Integration tests use the real clock.

### §5.5 Enforcement

Detail in §9 + ADR-0023. Summary:
- Python `import-linter`: `domain-no-system-reads` contract blocks module-level `random` / `secrets` imports from `contexts.*.domain` and `shared_kernel/` (ADR-0023 #1).
- Python AST checks (`tests/architecture/test_call_sites.py`): blocks call expressions `datetime.now(` / `datetime.utcnow(` / `time.time(` / `uuid.uuid4(` inside the same scope (ADR-0023 A1, A2). Lint-tool granularity cannot see call sites, only imports.
- Kotlin Konsist: K1 forbids `Instant.now()` / `UUID.randomUUID()` / `System.currentTimeMillis()` calls inside `..domain..` packages.
- Type imports (`from datetime import datetime`; `import java.time.Instant`) remain allowed — the rule is *no system reads*, not *no time types*.

---

## §6. shared_kernel boundary

### §6.1 Allowed

- **Typed IDs**: UUID newtype wrappers (`FactoryId`, `LineId`, `MachineId`, `TenantId`).
- **Cross-cutting VOs**: `Tenant`, timezone-aware `Timestamp` wrapper, currency-like primitives — values used identically by multiple BCs.
- **`DomainEventDispatcher`** interface and base `DomainEvent` marker (§3.3).
- **Cross-cutting Ports** in `shared_kernel/ports/<name>.py`: `ClockPort` (ADR-0021), and any future cross-cutting Port (e.g., `UUIDPort`, `RandomPort`, an outbox port if introduced).
- **Generic protocols / typing utilities** used by multiple BCs.

### §6.2 Forbidden

- Aggregates / domain root types (those belong to a single BC).
- Domain services or use cases.
- BC-spanning events with semantics owned by a specific BC. (E.g., `LineWentDown` lives in `contexts/monitoring/domain/`, *not* `shared_kernel/`, even though `quality` subscribes to it.)
- Anything that depends on a specific BC's domain types.
- **`UnitOfWork` Protocol is per-BC, not in `shared_kernel/`** (ADR-0020). Each BC's UoW exposes only that BC's repo attributes, reinforcing ADR-0009 (no cross-BC atomic tx). A global UoW with all BCs' repos was deliberately rejected.

### §6.3 Rationale

`shared_kernel` is intentionally small. The DDD literature treats Shared Kernel as the most coupling-heavy strategic pattern; bloating it defeats BC isolation. When in doubt, put it in a BC and expose via ports.

---

## §7. Per-language idiom matrix

The architectural rule is the same in both languages; only the syntax differs. This matrix is the source of truth for "how do I write X."

| Concept | Kotlin | Python |
|---|---|---|
| Immutable data | `data class Foo(val x: Int)` | `@dataclass(frozen=True, slots=True)` |
| Sum type | `sealed interface Outcome` + `data class` cases | tagged union with `\|` and `@dataclass(frozen=True)` cases |
| Pattern match | `when (x) { is A -> ...; is B -> ... }` (exhaustive) | `match x: case A(): ...; case B(): ...` |
| New-type ID | `@JvmInline value class LineId(val v: UUID)` | `@dataclass(frozen=True, slots=True) class LineId: value: UUID` |
| DI (clock) | constructor inject `java.time.Clock` | constructor inject `ClockPort` Protocol from `shared_kernel/ports/clock.py` (ADR-0021) |
| Async | `suspend fun` | `async def` |
| Module visibility | `internal` keyword + `-Xexplicit-api=strict` | leading underscore convention + `import-linter` |
| Pure enforcement | Konsist arch tests + `suspend` makes IO partially formal | `import-linter` `forbidden` contracts |
| Validation lib | none in domain | none in domain (Pydantic at boundary only) |
| Test framework | JUnit 5 + Kotest property | pytest + Hypothesis property |
| Coroutine cancellation | structured concurrency (`coroutineScope`) | `asyncio.TaskGroup` |

---

## §8. Persistence — ORM containment + UoW + Pydantic boundary

This section integrates ADR-0019 (ORM containment), ADR-0020 (Unit of Work), and ADR-0018 (Pydantic at boundary only). The persistence layer has three rules, not one.

### §8.1 ORM rules

- **Forbidden in core** (uncontested): any ORM declaration on domain types.
  - Python: **no SQLAlchemy ORM declarative base** on domain types. `class Order(Base)` is rejected if `Order` is a domain type.
  - Kotlin: **no JPA `@Entity`/`@Id` on domain types.** (Adapter-internal use is a separate question — see Kotlin row below.)
- **Allowed at adapters with containment** (Python, ADR-0019):
  - **SQLAlchemy 2.0 ORM is allowed inside the adapter file** under five containment rules:
    1. ORM declarative class is *private* (underscore prefix: `class _Base(DeclarativeBase): pass`, `class _Order(_Base): ...`).
    2. Adapter public methods return domain types or primitives only — never an `_Order` instance or a `Row[...]`.
    3. Adapter constructor takes `AsyncSession`, does not own engine, does not commit (UoW does — §8.5).
    4. No class-level Port inheritance. Port satisfaction is structural; composition root acknowledges with `cast(Port, AdapterImpl(session))` (`adapters-no-upward` contract, ADR-0023 #6).
    5. DB-side `GENERATED` columns mirrored via `Computed("expr", persisted=True)`; adapter does not pass those columns in INSERT/UPDATE.
  - SQLAlchemy Core / `asyncpg` raw also remain available — pick by adapter need.
- **Kotlin adapter persistence — decision deferred to Phase 2 W1~W2** (frozen as ADR when the first Kotlin BC with relational persistence lands). Candidates under consideration: **JPA under containment** (adapter-internal `_*Entity`, `@Transactional`-only-in-adapters, Konsist `_*Entity` non-leak rule — symmetric to Python's `_Order` pattern above), **Exposed** (DSL, table objects separate from domain), **JOOQ** (codegen, generated types adapter-local). JPA is the current working preference — industry-standard on JVM, target-viewer familiarity, symmetric containment story. The earlier "no JPA — pollutes core / lazy-loading violates purity" framing in this section conflated *domain-type leak* (still forbidden — see above) with *adapter-internal use* (allowable under containment) and is **retracted**. Phase 1 Kotlin (`ot-gateway-kotlin/{gateway,bridge,simulator}`) has no relational persistence — pure MQTT/Kafka — so no code is affected by the deferral.

### §8.2 Adapter pattern (Python, ORM containment example)

Domain types remain constructible without DB knowledge. Adapter maps `_Order` ORM rows in/out at the file boundary:

```python
# adapters/postgres_orders.py
from sqlalchemy import BigInteger, Computed, Integer, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class _Base(DeclarativeBase):
    pass


class _Order(_Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    line_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity_filled: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    quantity_remaining: Mapped[int] = mapped_column(
        BigInteger,
        Computed("quantity_total - quantity_filled", persisted=True),
        nullable=False,
    )
    # ... other columns


class PostgresOrdersRepo:
    """Public surface. Returns domain types / primitives only.

    Satisfies ports.orders.OrdersRepoPort structurally — no class-level
    inheritance (ADR-0019 rule 4 + ADR-0023 adapters-no-upward).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def insert_order(
        self, *, line_id: int, quantity_total: int,
    ) -> int:
        # Never pass quantity_remaining — Postgres computes it (rule 5).
        row = _Order(
            line_id=line_id,
            quantity_total=quantity_total,
            quantity_filled=0,
        )
        self._s.add(row)
        await self._s.flush()  # no commit — UoW owns the boundary
        return int(row.id)
```

For `asyncpg` raw or SQLAlchemy Core adapters (still valid), the shape is the same: adapter takes session/connection, returns domain types or primitives, does not commit.

### §8.3 Pydantic position

**Domain (core)**: `@dataclass(frozen=True, slots=True)` only. Pydantic is forbidden here.

**Shell (boundary)**: Pydantic is the standard tool. Used for:
- FastAPI request/response models (DTOs).
- Kafka payload validation (incoming JSON).
- OpenAPI schema generation.
- Configuration loading (`pydantic-settings`).

The boundary DTO is a *separate type* from the domain type, with explicit `from_domain` / `to_domain` conversion. They are not the same class.

Rationale (decided 2026-05-23, full version in ADR-0018):
- Pydantic models are pure data containers + sync validation — they don't break test purity. But:
- Putting Pydantic in domain conflates *input shape validation* (Pydantic's job) with *domain invariant validation* (sum types and functions). The literature (cosmic-python, "Architecture Patterns with Python") explicitly separates the two.
- Serialization knowledge (`.model_dump_json()`) leaks into core if Pydantic lives there. JSON is a boundary concern.
- Pydantic v1→v2 was a breaking API change; coupling domain to Pydantic API decisions is unnecessary risk.
- The current Phase 1 plan already uses stdlib dataclass for domain — this rule is consistent with existing code.

**Intentional divergence from `the reference codebase` reference**: the reference impl uses `Pydantic BaseModel` with `ConfigDict(frozen=True, extra="forbid")` throughout `domain/`. We deliberately stay with `@dataclass(frozen=True, slots=True)` to keep the boundary-validation / domain-invariant separation visible by file location. ADR-0018 documents the call; this is not an oversight, it is a chosen line. The other reference patterns (ORM containment, UoW, ClockPort, fakes layout, importlinter) *are* adopted — see ADR-0019 through 0024.

### §8.4 Anti-patterns

- ❌ Returning a Pydantic model from a domain function.
- ❌ Adding `@field_validator` for domain invariants on a Pydantic DTO. (Domain invariants live in core sum types and functions, not boundary types.)
- ❌ Letting a SQLAlchemy ORM `class Order(Base)` be a "domain entity." (ORM declarations stay inside the adapter file with underscore prefix — §8.1 / ADR-0019.)
- ❌ ORM declarative class without underscore prefix at module level. The privacy marker is the load-bearing signal that the class is adapter-internal.
- ❌ Returning `_Order` (or any ORM `Mapped[...]` instance) from an adapter public method. ORM rows convert to domain types or primitives *at the file boundary*.
- ❌ Adapter calling `await self._session.commit()`. The use case owns the commit boundary via UoW (§8.5 / ADR-0020).
- ❌ Adapter class with `class PostgresOrdersRepo(OrdersRepoPort)` inheritance. Port satisfaction is structural; composition root acknowledges with `cast(...)` (`adapters-no-upward` contract — ADR-0023 #6).
- ❌ Use case touching `uow.session` directly. The session escape hatch belongs to `composition.py` only (AST check A3 — ADR-0023).
- ❌ Global UoW spanning multiple BCs. UoW is per-BC; cross-BC operations open multiple UoWs in sequence (ADR-0020, ADR-0009).

### §8.5 Unit of Work — transaction boundary owned by use cases

Per ADR-0020. The adapter never commits (§8.1 rule 3); the use case opens a UoW, performs writes through the bound repos, calls `commit()` on success, and lets `__aexit__` roll back on exception.

**Protocol location**: `contexts/<bc>/ports/unit_of_work.py` — *per BC, not in `shared_kernel/`*. A global UoW with all BCs' repos was deliberately rejected (ADR-0020 §Decision) because it would invite cross-BC atomic writes, contradicting ADR-0009.

```python
# contexts/monitoring/ports/unit_of_work.py
from types import TracebackType
from typing import Protocol

from sdf_api.contexts.monitoring.ports.line_event import LineEventWriter
from sdf_api.contexts.monitoring.ports.line_state import LineStateReader
from sdf_api.contexts.monitoring.ports.audit_log import AuditLogRepo


class UnitOfWork(Protocol):
    """Per-BC async transaction boundary. Use cases program against this."""

    # Per-feature repo attributes — each Port the BC uses.
    line_events: LineEventWriter
    line_states: LineStateReader
    audit_logs: AuditLogRepo

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

```python
# contexts/monitoring/adapters/sqlalchemy_uow.py
class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        """Composition-root-only escape hatch. Use cases never touch this.

        AST check A3 (ADR-0023) restricts access to composition.py.
        """
        assert self._session is not None
        return self._session

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        # Bind per-feature repos to the fresh session.
        self.line_events = PostgresLineEventWriter(self._session)
        self.line_states = PostgresLineStateReader(self._session)
        self.audit_logs = PostgresAuditLogRepo(self._session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        assert self._session is not None
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
```

```python
# contexts/monitoring/application/record_line_event.py
class RecordLineEventUseCase:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        clock: ClockPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, event: TelemetryEvent) -> RecordOutcome:
        async with self._uow_factory() as uow:
            current = await uow.line_states.latest(event.line_id)
            if isinstance(current, NotFound):
                return Rejected(reason="line_not_found")
            outcome = apply_event(current.state, event, at=self._clock.now())
            match outcome:
                case Rejected():
                    return outcome
                case StateChange(new_state, events):
                    for ev in events:
                        await uow.line_events.append(ev)
                    await uow.audit_logs.append(...)
                    await uow.commit()
                    return Ok(state=new_state)
```

**Session-bound adapters that are not part of the published UoW Protocol** (e.g., cross-system readers, use-case-scoped adapters) take the session from `uow.session` *at the composition root* and are injected into the use case as a separate factory parameter. The use case still never reads `uow.session`.

**`async_sessionmaker` config**: production uses `async_sessionmaker(engine, expire_on_commit=False)` — async post-commit lazy-load implicitly awaits, a documented async foot-gun.

**Fakes**: `FakeUnitOfWork(dataset: InMemoryDataset)` implements the same Protocol with in-memory backing — see §8.6 and ADR-0024.

### §8.6 Test fakes — `InMemoryDataset` + per-BC working implementations

Per ADR-0024. Fakes live at `backend/tests/contexts/<bc>/fakes.py` and `backend/tests/shared_kernel/fakes.py` (cross-cutting fakes like `FixedClock`).

Three discipline points:

1. **Fakes are working implementations, not mocks.** Each fake satisfies the production Port Protocol structurally. State mutates on writes; reads return the mutated state. DB-side constraints relevant to behavior (`GENERATED` columns, biconditional `CHECK`s) are mirrored. The rule: *the fake fails the same kinds of inputs the real adapter fails*.

2. **`InMemoryDataset` per BC** holds the BC's shared mutable state. A `FakeUnitOfWork` instance wraps one dataset and constructs each per-feature fake around it, so all repos within one UoW see one source of truth — mirroring the real session-bound adapter pattern.

   ```python
   # tests/contexts/monitoring/fakes.py
   @dataclass
   class MonitoringInMemoryDataset:
       line_events: list[LineEvent] = field(default_factory=list)
       line_states: dict[LineId, LineStateProjection] = field(default_factory=dict)
       audit_logs: list[AuditLogEntry] = field(default_factory=list)


   class FakeUnitOfWork:
       def __init__(self, dataset: MonitoringInMemoryDataset) -> None:
           self._dataset = dataset
           self.line_events = FakeLineEventWriter(dataset)
           self.line_states = FakeLineStateReader(dataset)
           self.audit_logs = FakeAuditLogRepo(dataset)
           self.committed = False
           self.rolled_back = False

       async def __aenter__(self): return self
       async def __aexit__(self, exc_type, exc_val, exc_tb):
           if exc_type is not None:
               await self.rollback()
       async def commit(self): self.committed = True
       async def rollback(self): self.rolled_back = True
   ```

3. **No assertion-on-call.** Tests assert on observable outcomes (dataset state, returned domain values, sum-type variants), never on whether a method was called or with what arguments. `committed` / `rolled_back` flags on `FakeUnitOfWork` are state, not call traces.

   ```python
   async def test_record_line_event_persists_and_commits() -> None:
       dataset = MonitoringInMemoryDataset(
           line_states={line_id: LineStateProjection(state="UP", since=...)},
       )
       uow_factory = lambda: FakeUnitOfWork(dataset)
       clock = FixedClock(frozen=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))

       use_case = RecordLineEventUseCase(uow_factory, clock)
       result = await use_case.execute(make_telemetry_event(...))

       assert isinstance(result, Ok)
       assert len(dataset.line_events) == 1
       assert dataset.audit_logs[0].action_key == "line.state_change"
   ```

Cross-BC use-case tests instantiate *one dataset per BC* — never one shared dataset across BCs. This mirrors ADR-0020's per-BC UoW: no cross-BC atomic boundary, even in tests.

Optional `call_log: list[str]` parameter on fakes is the only sanctioned escape from the no-call-assertion rule, and only for cross-fake call *ordering* (lock-then-read), never for argument inspection.

---

## §9. Lint / enforcement — delta over spec §6

Spec §6 already has the full per-language drift toolchain matrix. This section provides the TOML / Kotlin code samples for the contract set; **the contract list itself is owned by ADR-0023** (single source of truth — changes land in the ADR first, code samples here mirror).

### §9.1 Python — `import-linter` contracts (full list)

ADR-0023 names seven Python contracts (#1–#7). TOML for each (`backend/pyproject.toml`):

```toml
# 1. domain-no-system-reads — ADR-0017
[[tool.importlinter.contracts]]
name = "domain-no-system-reads"
type = "forbidden"
source_modules = ["sdf_api.contexts.*.domain", "sdf_api.shared_kernel"]
forbidden_modules = ["random", "secrets"]
# Note: call-site checks for datetime.now / uuid.uuid4 live in tests/architecture/
# (§9.3, ADR-0023 A1/A2) — import-linter operates at module level only.

# 2. domain-no-validation-libs — ADR-0004 / ADR-0018
[[tool.importlinter.contracts]]
name = "domain-no-validation-libs"
type = "forbidden"
source_modules = ["sdf_api.contexts.*.domain", "sdf_api.shared_kernel"]
forbidden_modules = ["pydantic", "marshmallow", "attrs", "returns", "arrow"]
# 'arrow' = dateutil-flavored Python library, not arrow-kt.

# 3. domain-no-infrastructure — ADR-0004
[[tool.importlinter.contracts]]
name = "domain-no-infrastructure"
type = "forbidden"
source_modules = ["sdf_api.contexts.*.domain", "sdf_api.shared_kernel"]
forbidden_modules = [
  "sqlalchemy", "asyncpg", "aiokafka", "httpx", "fastapi", "redis", "pymemcache",
]

# 4. use-cases-no-domain-or-adapters — arch doc §3.2
[[tool.importlinter.contracts]]
name = "use-cases-no-domain-or-adapters"
type = "forbidden"
source_modules = ["sdf_api.use_cases"]
forbidden_modules = [
  "sdf_api.contexts.*.domain",
  "sdf_api.contexts.*.adapters",
]

# 5. bc-independence — Phase 1 plan Task 2, arch doc §3
# (Per BC; one contract per pair. Generated by a small Python helper that
# enumerates BCs and emits one contract per pair to avoid hand-edit drift.)

# 6. adapters-no-upward — ADR-0019 (new)
[[tool.importlinter.contracts]]
name = "adapters-no-upward"
type = "forbidden"
source_modules = ["sdf_api.contexts.*.adapters"]
forbidden_modules = [
  "sdf_api.contexts.*.ports",
  "sdf_api.contexts.*.application",
  "sdf_api.use_cases",
]

# 7. composition-only-imports-adapters — arch doc §1.2, open question O1
[[tool.importlinter.contracts]]
name = "composition-only-imports-adapters"
type = "forbidden"
source_modules = [
  "sdf_api.contexts.*.application",
  "sdf_api.use_cases",
]
forbidden_modules = ["sdf_api.contexts.*.adapters"]
# composition.py is the sole importer of adapters/.
```

### §9.2 Kotlin — Konsist equivalents

```kotlin
@Test
fun `domain must not read system clock or uuid`() {
    Konsist.scopeFromProduction()
        .functions(includeNested = true)
        .filter { it.resideInPackage("..domain..") }
        .assertFalse { fn ->
            fn.text.contains("Instant.now()") ||
            fn.text.contains("UUID.randomUUID()") ||
            fn.text.contains("System.currentTimeMillis()")
        }
}

@Test
fun `domain may not depend on persistence frameworks`() {
    Konsist.scopeFromProduction()
        .classes()
        .filter { it.resideInPackage("..domain..") }
        .assertFalse { cls ->
            cls.hasImports("jakarta.persistence..", "org.jetbrains.exposed..")
        }
}
```

### §9.3 Custom checks (where lint-tool granularity is insufficient)

A small `tests/architecture/` directory contains AST-walking tests for call-site enforcement that lint tools can't express at module level. Per ADR-0023:

- **A1 — `domain-no-datetime-now`**: walks every `.py` file under `contexts/*/domain/` and `shared_kernel/`, fails if it finds call expressions `datetime.now(` / `datetime.utcnow(` / `time.time(`.
- **A2 — `domain-no-uuid-call`**: same scope, fails on `uuid.uuid4(` / `uuid.uuid1(`.
- **A3 — `uow-session-only-from-composition`**: the attribute access `uow.session` (or `<any>.session` where `<any>` is annotated as `UnitOfWork`) may appear only in `composition.py`. Use cases never read `uow.session`; the escape hatch belongs to the wiring layer (ADR-0020).

These run as part of the unit-test suite (always-on, sub-second).

### §9.4 CI gate behavior

All §9 contracts run in CI (`make ci`) per spec §6.5. Local pre-commit runs the cheap subset (ruff / detekt / ktlint). Full `import-linter` / Konsist / mypy strict / tsc strict / dependency-cruiser / codegen-drift only in CI.

---

## §10. Open questions

To resolve when concrete code lands or in a follow-up ADR:

- **O1.** Should a BC's `application/` be allowed to import the *same BC's* `adapters` for type signatures, or only via `ports`? Tentative: only `ports`; the composition root is the sole importer of `adapters`. Verify when wiring the first cross-BC use case.
- **O2.** When a domain event handler needs to read its own BC's state before reacting (e.g., `quality.on_line_went_down` checks the quality plan), does the handler take a port via DI like a use case? Almost certainly yes — confirm pattern with first concrete subscriber.

(O3 = dispatcher fail-fast → §3.3. O4 = Pydantic at boundary only → §8.3.)

---

**End of body. Active ADRs: 0004 (FC/IS), 0009 (inter-context), 0016 (error as value), 0017 (system-reads injection), 0018 (Pydantic at boundary only), 0019 (ORM containment), 0020 (Unit of Work), 0021 (ClockPort standardized), 0022 (Ports as folder), 0023 (importlinter contract set), 0024 (fakes with InMemoryDataset).**
