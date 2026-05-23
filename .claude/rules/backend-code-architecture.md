# Backend Code Architecture — Rules

Fast-scan condensation of `docs/architecture/2026-05-23-code-architecture.md` + ADRs 0004/0009/0016/0017/0018. The arch doc carries full rationale; this file is rules-only, do/don't form.

On conflict between Phase 1 plan code samples and these rules, these rules win (per plan header forward reference).

---

## §1. Layer placement

DO:
- Pure domain logic → `contexts/<bc>/domain/` (Python) or `<package>.domain` (Kotlin).
- IO / adapters → `contexts/<bc>/adapters/`.
- BC-local use cases → `contexts/<bc>/application/`.
- Cross-BC use cases → top-level `src/sdf_api/use_cases/`.
- Cross-BC reusable values → `shared_kernel/` (IDs, cross-cutting VOs).
- Composition / DI wiring → `composition.py` at top level.

DON'T:
- Put cross-BC use cases inside `contexts/<bc>/application/`.
- Put aggregates / domain services / BC-spanning events in `shared_kernel/`.
- Subclass an ORM `Base` class for any domain type.

---

## §2. Domain purity — forbidden imports

MUST NOT import inside `contexts/*/domain/` or `shared_kernel/`:
- `pydantic`, `attrs`, `marshmallow`, `returns.*` (Python), `arrow.core.*` (Kotlin)
- `datetime.now`, `datetime.utcnow`, `uuid.uuid4`, `random`, `secrets`, `time.time`
- `Instant.now()`, `UUID.randomUUID()`, `System.currentTimeMillis()` (Kotlin)
- `asyncpg`, `sqlalchemy.*`, `aiokafka`, `httpx`, `fastapi`, `redis`
- `jakarta.persistence.*`, `org.jetbrains.exposed.*` (Kotlin, in domain)

Type imports (`from datetime import datetime`, `import java.time.Instant`) ARE allowed — only call-site reads of the system are forbidden.

MUST in domain:
- `@dataclass(frozen=True, slots=True)` (Python) or `data class` with `val` (Kotlin) for data types.
- Receive clock / UUID / randomness as function parameters.
- Return failures as sum-type values.

---

## §3. Error handling

DO:
- Return sum types from core: `@dataclass(frozen=True)` cases + `Union` (Python) or `sealed interface` + `data class` cases (Kotlin).
- Name failure cases meaningfully (`NotFound(reason=...)`, `Rejected(reason=...)`).
- Discriminate at call site with `match` (Python) or `when` (Kotlin).
- Translate sum-cases to `HTTPException` at the HTTP boundary in adapters.

DON'T:
- `raise InvalidTransition(...)` from a core function — return `Rejected(reason=...)` instead.
- Return `None` for "not found" — use a named `NotFound` case.
- Use `arrow-kt` `Either`, `returns.Result`, or any external error-monad library.
- Wrap domain failures in stringly-typed `Result<T, str>`.

---

## §4. Clock / UUID / Random

DO:
- Add `now: Callable[[], datetime]` (Python) or `clock: Clock` (Kotlin) as a parameter to any core function that needs current time.
- Use `java.time.Clock` (Kotlin stdlib); inject via constructor.
- Production: wire `Clock.systemUTC()` / `lambda: datetime.now(UTC)` in `composition.py`.
- Tests: pass frozen values directly — e.g., `at=datetime(2026, 5, 23, 12, 0, tzinfo=UTC)`.

DON'T:
- Call `datetime.now()` / `uuid.uuid4()` / `random.*` inside `domain/`.
- Mock the system clock — pass a frozen value, no mock library.

---

## §5. Pydantic placement

DO:
- Pydantic for HTTP DTOs in `adapters/http/`.
- Pydantic for Kafka payload validation in `adapters/kafka/`.
- Pydantic for OpenAPI schema (FastAPI native at adapter level).
- `pydantic-settings` for config loading.
- Explicit `from_domain(d) -> DTO` / `to_domain() -> Domain` conversion methods.

DON'T:
- Import `pydantic` anywhere under `contexts/*/domain/` or `shared_kernel/`.
- Return a Pydantic `BaseModel` from a domain function.
- Put `@field_validator` for *domain invariants* on a Pydantic DTO — invariants belong in core sum types.

---

## §6. ORM / persistence

DO:
- Kotlin: Exposed (DSL) or JOOQ (codegen) in adapters.
- Python: SQLAlchemy **Core** (not ORM) or `asyncpg` raw in adapters.
- Map DB rows → domain via explicit functions in adapter code.

DON'T:
- Use JPA `@Entity` / `@Id` on domain types (Kotlin).
- Use SQLAlchemy ORM declarative `class Foo(Base)` for domain types (Python).
- Couple domain field names to DB column names — adapter does the rename.

---

## §7. Cross-BC interaction

DO:
- Expose `contexts/<bc>/ports.py` (Python `Protocol`) for read/write contracts.
- Name ports `<Noun>Reader` / `<Noun>Writer` / `<Noun>Port`.
- Cross-BC sync query → write in `src/sdf_api/use_cases/`, importing both BCs' `ports.py`.
- Cross-BC state propagation → emit `DomainEvent` as a value from core, shell dispatches via `DomainEventDispatcher` (in `shared_kernel/events.py`).
- Register cross-BC handlers in `composition.py`.

DON'T:
- `from sdf_api.contexts.<other_bc> import ...` inside any BC's `domain/` or `application/`. (Independence contract is in force.)
- Use Kafka for domain events (Phase 1~4). Kafka is for telemetry pipeline only.
- Add an in-memory event bus library — `DomainEventDispatcher` is hand-rolled in `shared_kernel/`.
- Swallow exceptions inside `DomainEventDispatcher.dispatch()`. It is fail-fast; handler exceptions propagate to the caller, which decides on rollback.

---

## §8. Cross-aggregate (same BC)

MUST:
- One transaction = one aggregate write.
- Multi-aggregate orchestration lives in `application/`, not `domain/`.

MUST NOT:
- Atomically write multiple aggregates in one transaction. If they require atomic consistency, they are one aggregate.

---

## §9. Naming

DO:
- Domain events: past-tense verb, no `Event` suffix — `LineWentDown`, `OrderPlaced`.
- State transitions: `apply_<event>(state, event) -> <Outcome>` (Python) / `applyEvent` (Kotlin).
- Ports: `<Noun>Reader` / `<Noun>Writer` / `<Noun>Port`.

DON'T USE as code identifiers or filenames:
- `*Service` suffix.
- `*Repository`.
- `*Factory`.
- `*EventEvent` (double-noun).

---

## §10. Tests

DO:
- Domain tests under `tests/contexts/*/domain/` — zero mocks, stubs, fakes. Pass concrete values directly.
- Application tests — in-memory fakes implementing the BC's `Protocol`/interface (e.g., `FakeStateReader`).
- Property-based tests (Hypothesis / Kotest) for pure domain functions with large input space.
- Frozen clock / fixed values for all time-sensitive tests.
- Explicit test cases for every sum-type failure variant (`Rejected`, `NotFound`).

DON'T:
- Mock the system clock — pass a frozen value via the clock parameter.
- Use testcontainers in domain tests — only in integration tests (`tests/.../integration/`).
- Skip a `Rejected` / `NotFound` variant in tests.

---

## §11. DDD terminology — what we say in code

USE (in identifiers and filenames):
- "Value Object" (concept; identifiers as concrete nouns).
- "Domain Event" (concept; identifiers as past-tense verbs — `LineWentDown`).
- "Aggregate" / "Entity" — concepts only. In code, name by concrete role (`LineState`, `Topology`, etc.).

DO NOT USE (as code identifiers or filenames):
- "Aggregate", "Repository", "Domain Service", "Factory" suffixes.
- These DDD-classical names carry mutable-method / infra-coupled-abstraction implications that conflict with FC/IS.

---

## §12. CI gates that enforce these rules

These run in CI; if your change touches domain code, expect them to fire:
- `import-linter` forbidden contracts (Python) — domain ↛ infrastructure / Pydantic / system reads.
- Konsist architecture tests (Kotlin) — domain ↛ adapters / JPA / Exposed.
- Custom AST checks in `tests/architecture/` for call-site rules (e.g., `datetime.now()` usage inside `domain/`).
- mypy strict / detekt / ktlint — no opt-outs.

If your code adds a new domain module:
- Mirror the lint contracts to cover the new module.
- DO NOT disable a contract to make code pass. Fix the code.

---

Full rationale: `docs/architecture/2026-05-23-code-architecture.md`. Decision records: `docs/ADR/0004` / `0009` / `0016` / `0017` / `0018`.
