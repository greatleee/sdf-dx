# Backend Code Architecture — Conventions

| | |
|---|---|
| **Date** | 2026-05-23 |
| **Status** | Draft — initial body. |
| **Layer** | Engineering Conventions (see `docs/SOT-LAYERS.md`) |
| **Scope** | Backend code-level conventions for Python + Kotlin. Frontend has its own conventions (TBD). |
| **Audience** | Self (future me), LLM pair, portfolio reviewer reading code first. |
| **Related** | Strategy `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2, §6, §9. Working notes `docs/plans/2026-05-23-arch-doc-discussion-notes.md`. |

> **Editing rule**: living guide. Edit only when a convention actually evolves. Each substantive change references (or triggers) an ADR. The doc says *how*; the ADR says *why*. See `docs/SOT-LAYERS.md` line *Engineering Conventions* row.

---

## TL;DR (rule cheatsheet)

1. **FC/IS** — domain code is pure, IO at shell. Spec §2.1.
2. **Core returns failures as values** (sealed class / tagged union). Shell may throw at boundary.
3. **Core may not read clock / uuid / random** — these are injected from shell.
4. **DDD tactical**: Value Object ✓ / Aggregate concept ✓ (data + pure functions, no OO methods) / Repository ✗ (use `Reader`/`Writer` ports) / Domain Service term ✗ / Domain Event = pure value returned by core.
5. **shared_kernel**: IDs + cross-cutting VOs only. No aggregates, no services, no cross-BC events.
6. **Cross-BC sync query**: top-level `src/sdf_api/use_cases/`. BCs stay peers (import-linter `independence` contract enforced).
7. **Cross-BC state propagation**: in-process `DomainEventDispatcher`, fail-fast. No Kafka for domain events.
8. **Cross-aggregate (same BC)**: 1 transaction = 1 aggregate. Multi-aggregate orchestration in application/use-case layer.
9. **ORM**: avoid object-relational mappers that pollute domain (JPA, SQLAlchemy ORM). Use Exposed/JOOQ (Kotlin) or SQLAlchemy Core / asyncpg raw (Python).
10. **Pydantic**: shell boundary only (HTTP DTO, JSON parsing, OpenAPI). Domain uses stdlib `@dataclass(frozen=True, slots=True)`.
11. **Test pyramid**: domain tests = 0 mock / 0 stub / 0 fake / sub-second. Spec §7.

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
| `src/sdf_api/contexts/<bc>/application/` | Shell (BC-local use cases) |
| `src/sdf_api/contexts/<bc>/adapters/` | Shell (IO) |
| `src/sdf_api/use_cases/` | Shell (cross-BC use cases — see §3.2) |
| `src/sdf_api/shared_kernel/` | Core (cross-BC pure values only — see §6) |
| `src/sdf_api/composition.py` | Shell (wiring root) |

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
| Repository | Shell only | ✗ | `<Noun>Reader` / `<Noun>Writer` ports (`Protocol` in Python, `interface` in Kotlin). No "domain interface, infra impl" abstraction; just ports + adapters. |
| Domain Service | Split | ✗ | Pure logic → module-level function in `domain/`. Mixed-with-IO → use case in `application/`. The term itself is not used in code or docs. |
| Factory | Core (just a function) | ✗ | Module-level function, often `make_<noun>` or just the constructor. No `Factory` suffix. |
| Entity (with identity) | Core (data + transition functions) | ✓ (limited) | Same shape as Aggregate. ID equality, no method-based self-mutation. |
| Specification | — | ✗ | A predicate function (`fn(x: T) -> bool`). No class. |

### §2.1 Naming consequences

- **No `*Service` suffix** in domain code (it would imply Domain Service, which we've dropped).
- **No `*Repository`** anywhere — `LineStateReader`, `LineStateWriter` instead.
- **No `*Factory`** — `make_topology(...)` or just call the dataclass.
- **Ports**: `<Noun>Reader` (read-only), `<Noun>Writer` (write-only), or `<Noun>Port` if both. Lives in `contexts/<bc>/ports.py` (Python) or `<package>/ports/` (Kotlin).
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
│   │   ├── application/    ← BC-local use cases only
│   │   ├── adapters/
│   │   └── ports.py
│   └── topology/
│       └── ...
├── use_cases/               ← cross-BC ONLY
│   └── get_line_with_meta.py
├── shared_kernel/
└── composition.py
```

#### Rules

- A file in `use_cases/` may import multiple BCs' `ports.py`.
- A file in `use_cases/` may **not** import any BC's `domain/` or `adapters/` directly.
- A file in `contexts/<bc>/application/` may **not** import any other BC at all. (`import-linter` `independence` contract stays in force between BCs.)
- The composition root (`composition.py`) wires concrete adapters into both BC-local and cross-BC use cases.

#### Example

```python
# contexts/monitoring/ports.py
class LineStateReader(Protocol):
    async def latest(self, line_id: LineId) -> LineStateSnapshot | NotFound: ...

# contexts/topology/ports.py
class TopologyReader(Protocol):
    async def line(self, line_id: LineId) -> Line | NotFound: ...

# use_cases/get_line_with_meta.py
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

Function-argument injection (simpler) or a `Clock` Protocol (when multiple methods are needed).

```python
# Pure — value injected
def apply_event(state: State, event: Event, at: datetime) -> ApplyOutcome: ...

# Shell — reads clock, passes value to core
async def handle_telemetry(
    event: TelemetryEvent,
    ...,
    now: Callable[[], datetime],
) -> None:
    outcome = apply_event(state, event, at=now())
    ...

# composition.py
from datetime import datetime, UTC
real_now = lambda: datetime.now(UTC)

# tests
fixed_now = lambda: datetime(2026, 5, 23, 12, 0, tzinfo=UTC)
```

For multiple system reads, group into a Protocol:

```python
class Clock(Protocol):
    def now(self) -> datetime: ...
    def new_id(self) -> UUID: ...
```

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

Detail in §9. Summary:
- Python: `import-linter` blocks importing `datetime.datetime.now` / `uuid.uuid4` / `random` / `time.time` *from inside* `contexts.*.domain`. Type imports (`from datetime import datetime`) are allowed.
- Kotlin: Konsist rule forbids calls to `Instant.now()` / `UUID.randomUUID()` from domain packages.

---

## §6. shared_kernel boundary

### §6.1 Allowed

- **Typed IDs**: UUID newtype wrappers (`FactoryId`, `LineId`, `MachineId`, `TenantId`).
- **Cross-cutting VOs**: `Tenant`, timezone-aware `Timestamp` wrapper, currency-like primitives — values used identically by multiple BCs.
- **`DomainEventDispatcher`** interface and base `DomainEvent` marker (§3.3).
- **Generic protocols / typing utilities** used by multiple BCs.

### §6.2 Forbidden

- Aggregates / domain root types (those belong to a single BC).
- Domain services or use cases.
- BC-spanning events with semantics owned by a specific BC. (E.g., `LineWentDown` lives in `contexts/monitoring/domain/`, *not* `shared_kernel/`, even though `quality` subscribes to it.)
- Anything that depends on a specific BC's domain types.

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
| DI (clock) | constructor inject `java.time.Clock` | function arg `now: Callable[[], datetime]` or `Clock` Protocol |
| Async | `suspend fun` | `async def` |
| Module visibility | `internal` keyword + `-Xexplicit-api=strict` | leading underscore convention + `import-linter` |
| Pure enforcement | Konsist arch tests + `suspend` makes IO partially formal | `import-linter` `forbidden` contracts |
| Validation lib | none in domain | none in domain (Pydantic at boundary only) |
| Test framework | JUnit 5 + Kotest property | pytest + Hypothesis property |
| Coroutine cancellation | structured concurrency (`coroutineScope`) | `asyncio.TaskGroup` |

---

## §8. Persistence — ORM caution + Pydantic boundary

### §8.1 ORM rules

- **Forbidden in core**: any ORM that requires annotations or inheritance on domain types.
  - Kotlin: **no JPA** (`@Entity`, `@Id` on domain types pollutes core; lazy-loading and change-tracking violate purity).
  - Python: **no SQLAlchemy ORM declarative base** on domain types for the same reason.
- **Allowed at adapters**:
  - Kotlin: **Exposed** (DSL — separate from domain types) or **JOOQ** (codegen — generated types stay in adapter package).
  - Python: **SQLAlchemy Core** (Core, not ORM) or **`asyncpg`** raw.

### §8.2 Adapter pattern

Domain types must be constructible without DB knowledge. Adapter maps DB rows → domain factory:

```python
# adapters/postgres_line_state.py
class PgLineStateReader(LineStateReader):
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def latest(self, line_id: LineId) -> LineStateSnapshot | NotFound:
        row = await self._conn.fetchrow(
            "SELECT state, time FROM line_state WHERE line_id = $1 ORDER BY time DESC LIMIT 1",
            line_id.value,
        )
        if row is None:
            return NotFound(reason="no state recorded")
        return LineStateSnapshot(
            line_id=line_id,
            state=row["state"],
            since=row["time"],
        )
```

### §8.3 Pydantic position

**Domain (core)**: `@dataclass(frozen=True, slots=True)` only. Pydantic is forbidden here.

**Shell (boundary)**: Pydantic is the standard tool. Used for:
- FastAPI request/response models (DTOs).
- Kafka payload validation (incoming JSON).
- OpenAPI schema generation.
- Configuration loading (`pydantic-settings`).

The boundary DTO is a *separate type* from the domain type, with explicit `from_domain` / `to_domain` conversion. They are not the same class.

Rationale (decided 2026-05-23):
- Pydantic models are pure data containers + sync validation — they don't break test purity. But:
- Putting Pydantic in domain conflates *input shape validation* (Pydantic's job) with *domain invariant validation* (sum types and functions). The literature (cosmic-python, "Architecture Patterns with Python") explicitly separates the two.
- Serialization knowledge (`.model_dump_json()`) leaks into core if Pydantic lives there. JSON is a boundary concern.
- Pydantic v1→v2 was a breaking API change; coupling domain to Pydantic API decisions is unnecessary risk.
- The current Phase 1 plan already uses stdlib dataclass for domain — this rule is consistent with existing code.

### §8.4 Anti-patterns

- ❌ Returning a Pydantic model from a domain function.
- ❌ Adding `@field_validator` for domain invariants on a Pydantic DTO. (Domain invariants live in core sum types and functions, not boundary types.)
- ❌ Letting a SQLAlchemy ORM `class Order(Base)` be a "domain entity."

---

## §9. Lint / enforcement — delta over spec §6

Spec §6 already has the full per-language drift toolchain matrix. This section adds the *additional* contracts implied by §3, §4, §5, §6, §8 above.

### §9.1 Python — `import-linter` contracts to add

```toml
# 1. Domain may not read system clock / UUID / randomness
[[tool.importlinter.contracts]]
name = "domain may not read system clock / uuid / random"
type = "forbidden"
source_modules = ["sdf_api.contexts.*.domain"]
forbidden_modules = ["random", "secrets"]
# Note: import-linter is module-level. For `datetime.now` / `uuid.uuid4` call-site
# enforcement we add a ruff custom rule or a small AST-walking pytest in
# tests/architecture/ (see §9.3).

# 2. Domain may not import Pydantic or other validation libs
[[tool.importlinter.contracts]]
name = "domain may not import Pydantic or other validation libs"
type = "forbidden"
source_modules = ["sdf_api.contexts.*.domain"]
forbidden_modules = ["pydantic", "marshmallow", "attrs", "returns", "arrow"]
# Note: 'arrow' here means the dateutil-flavored library, not arrow-kt.

# 3. use_cases/ may import ports across BCs, but never domain or adapters
[[tool.importlinter.contracts]]
name = "use_cases/ may import any BC's ports, but not their domain or adapters"
type = "forbidden"
source_modules = ["sdf_api.use_cases"]
forbidden_modules = [
  "sdf_api.contexts.*.domain",
  "sdf_api.contexts.*.adapters",
]

# 4. BC application/ may not import another BC at all (independence stays)
# This is already in Phase 1 plan as 'independence' contract — see plan Task 2.
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

A small `tests/architecture/` directory contains AST-walking tests for call-site enforcement that lint tools can't express at module level. Example: a test that walks every `.py` file under `contexts/*/domain/` and fails if it finds `datetime.now(`, `uuid.uuid4(`, etc. as call expressions.

This runs as part of the unit-test suite (always-on, sub-second).

### §9.4 CI gate behavior

All §9 contracts run in CI (`make ci`) per spec §6.5. Local pre-commit runs the cheap subset (ruff / detekt / ktlint). Full `import-linter` / Konsist / mypy strict / tsc strict / dependency-cruiser / codegen-drift only in CI.

---

## §10. Open questions

To resolve when concrete code lands or in a follow-up ADR:

- **O1.** Should a BC's `application/` be allowed to import the *same BC's* `adapters` for type signatures, or only via `ports`? Tentative: only `ports`; the composition root is the sole importer of `adapters`. Verify when wiring the first cross-BC use case.
- **O2.** When a domain event handler needs to read its own BC's state before reacting (e.g., `quality.on_line_went_down` checks the quality plan), does the handler take a port via DI like a use case? Almost certainly yes — confirm pattern with first concrete subscriber.

(O3 = dispatcher fail-fast → §3.3. O4 = Pydantic at boundary only → §8.3.)

---

**End of body. ADRs to follow: ADR-4 (FC/IS) and ADR-9 (inter-context), plus new ADR for error-as-value + clock-injection if not subsumed.**
