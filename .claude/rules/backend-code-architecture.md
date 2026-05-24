# Backend Code Architecture — Rules

Fast-scan condensation of `docs/architecture/2026-05-23-code-architecture.md` + ADRs 0004 / 0009 / 0016 / 0017 / 0018 / 0019 / 0020 / 0021 / 0022 / 0023 / 0024. Reference impl: kept locally (see memory `reference-codebase`).

Arch doc carries full rationale; this file is rules-only, do/don't form. On conflict between Phase 1 plan code samples and these rules, these rules win (per plan header forward reference).

---

## §1. Layer placement

DO:
- Pure domain logic → `contexts/<bc>/domain/` (Python) or `<package>.domain` (Kotlin).
- Port Protocols → `contexts/<bc>/ports/<noun>.py` — folder, file-per-feature (ADR-0022).
- Per-BC `UnitOfWork` Protocol → `contexts/<bc>/ports/unit_of_work.py` (ADR-0020).
- Cross-cutting Port Protocols → `shared_kernel/ports/<name>.py` (`ClockPort` per ADR-0021).
- IO / adapters → `contexts/<bc>/adapters/`.
- BC-local use cases → `contexts/<bc>/application/`.
- Cross-BC use cases → top-level `src/sdf_api/use_cases/`.
- Cross-BC reusable values → `shared_kernel/` (IDs, cross-cutting VOs, `DomainEventDispatcher`).
- Composition / DI wiring → `composition.py` at top level.
- Fakes → `tests/contexts/<bc>/fakes.py` per BC (ADR-0024); cross-cutting fakes → `tests/shared_kernel/fakes.py`.
- Arch tests (import contracts + AST checks) → `tests/architecture/`.

DON'T:
- Put cross-BC use cases inside `contexts/<bc>/application/`.
- Put aggregates / domain services / BC-spanning events / per-BC `UnitOfWork` in `shared_kernel/`.
- Use single `contexts/<bc>/ports.py` file. Always `ports/` folder.
- Use a global `UnitOfWork` spanning multiple BCs (ADR-0020 + ADR-0009).
- Subclass an ORM `Base` class for any domain type.

---

## §2. Domain purity — forbidden imports

MUST NOT import inside `contexts/*/domain/` or `shared_kernel/` (except `shared_kernel/ports/` which holds Port Protocols only):
- `pydantic`, `attrs`, `marshmallow`, `returns.*` (Python), `arrow.core.*` (Kotlin)
- `datetime.now`, `datetime.utcnow`, `uuid.uuid4`, `random`, `secrets`, `time.time` — call sites (AST check A1/A2, ADR-0023)
- `Instant.now()`, `UUID.randomUUID()`, `System.currentTimeMillis()` (Kotlin)
- `asyncpg`, `sqlalchemy.*`, `aiokafka`, `httpx`, `fastapi`, `redis`, `pymemcache`
- `jakarta.persistence.*`, `org.jetbrains.exposed.*` (Kotlin, in domain)

Type imports (`from datetime import datetime`, `import java.time.Instant`) ARE allowed — only call-site reads of the system are forbidden.

MUST in domain:
- `@dataclass(frozen=True, slots=True)` (Python) or `data class` with `val` (Kotlin) for data types.
- Receive clock / UUID / randomness as `ClockPort` / `UUIDPort` / `RandomPort` Protocol parameter (ADR-0021).
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
- Add `tag: Literal["..."]` field on sum-type cases — discriminate by class type (`match Case():` / `is Case`), not tag literal (intentional divergence from the reference codebase; see plan §10.3 #3).

---

## §4. Clock / UUID / Random

DO:
- Inject `ClockPort` Protocol from `shared_kernel/ports/clock.py` via constructor (ADR-0021).
- Production: wire `SystemClock` (returns tz-aware UTC) in `composition.py`.
- Tests: pass `FixedClock(frozen=datetime(2026, 5, 23, 12, 0, tzinfo=UTC))` from `tests/shared_kernel/fakes.py`. No mock library.
- Same shape for UUID / randomness: `UUIDPort` / `RandomPort` in `shared_kernel/ports/`.
- Kotlin: `java.time.Clock` (stdlib) constructor-injected; `Clock.systemUTC()` / `Clock.fixed(...)`.

DON'T:
- Call `datetime.now()` / `uuid.uuid4()` / `random.*` / `time.time()` inside `domain/` or `shared_kernel/` (AST check A1/A2).
- Use `Callable[[], datetime]` — retired by ADR-0021. Always `ClockPort` Protocol.
- Mock the system clock — pass a frozen value via `FixedClock`.

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

Note: the reference codebase uses Pydantic-in-domain. ADR-0018 documents our intentional divergence (status quo).

---

## §6. ORM / persistence

DO:
- Python: SQLAlchemy 2.0 ORM **inside adapter under containment** (ADR-0019):
  - Private `class _Base(DeclarativeBase): pass` + `class _Order(_Base): ...` (underscore prefix, file-local).
  - Public adapter (e.g., `PostgresOrdersRepo`) takes `AsyncSession`, returns domain types / primitives only.
  - Mirror DB-side `GENERATED ALWAYS AS (...) STORED` columns with `Computed("expr", persisted=True)`; never write to those columns.
  - SQLAlchemy Core / `asyncpg` raw remain available — pick by adapter need.
- Use case owns commit via UoW (ADR-0020): `async with self._uow_factory() as uow: ... await uow.commit()`.
- Production sessionmaker: `async_sessionmaker(engine, expire_on_commit=False)` — avoids async lazy-load foot-gun.
- Kotlin: Exposed (DSL) or JOOQ (codegen) in adapters.
- Map DB rows → domain via explicit `_to_domain(row)` helper at file boundary.

DON'T:
- Use JPA `@Entity` / `@Id` on domain types (Kotlin).
- Use SQLAlchemy ORM declarative `class Foo(Base)` for domain types (Python).
- Return `_Order` / any `Mapped[...]` / `Row[...]` from adapter public method.
- Adapter call `await self._session.commit()` — UoW owns the boundary.
- `class PostgresOrdersRepo(OrdersRepoPort)` inheritance — structural match only (`adapters-no-upward`, ADR-0023 #6). Composition root acknowledges with `cast(...)`.
- Use case touching `uow.session` directly — escape hatch belongs to `composition.py` only (AST check A3, ADR-0023).
- Global UoW spanning multiple BCs (ADR-0020 + ADR-0009).
- Couple domain field names to DB column names — adapter does the rename.

---

## §7. Cross-BC interaction

DO:
- Expose contracts in `contexts/<bc>/ports/<noun>.py` (Python `Protocol`, one Port per file).
- Cross-BC sync query → write in `src/sdf_api/use_cases/`, importing both BCs' `ports/<noun>.py`.
- Cross-BC state propagation → emit `DomainEvent` as a value from core, shell dispatches via `DomainEventDispatcher` in `shared_kernel/events.py`.
- Register cross-BC handlers in `composition.py`.

DON'T:
- `from sdf_api.contexts.<other_bc> import ...` inside any BC's `domain/` or `application/` (`bc-independence` contract, ADR-0023 #5).
- `from sdf_api.contexts.*.ports import ...` from adapter (`adapters-no-upward` contract, ADR-0023 #6).
- Use Kafka for domain events (Phase 1~4). Kafka is for telemetry pipeline only.
- Add an in-memory event bus library — `DomainEventDispatcher` is hand-rolled in `shared_kernel/`.
- Swallow exceptions inside `DomainEventDispatcher.dispatch()`. Fail-fast; handler exceptions propagate to caller.

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
- Ports: pick by concrete role — `<Noun>Reader` / `<Noun>Writer` / `<Noun>Port` / `<Noun>Repo` / `<Noun>Ledger`.
- Adapter classes: `Postgres<Noun>Repo`, `Memcached<Noun>Adapter`, `<System><Noun>Reader` — role-prefixed (ADR-0019).

ALLOWED suffixes (ADR-0019 — `*Repo` is general persistence vocabulary, not DDD-classical):
- `*Repo`, `*Reader`, `*Writer`, `*Port`, `*Ledger`, `*Adapter`.

DON'T USE as code identifiers or filenames:
- `*Service` suffix (implies DDD Domain Service — dropped).
- `*Repository` (DDD-classical pattern marker — use `*Repo` instead).
- `*Factory`.
- `*EventEvent` (double-noun).

---

## §10. Tests

DO:
- Domain tests under `tests/contexts/*/domain/` — zero mocks, stubs, fakes. Pass concrete values directly.
- Use-case tests — construct `dataset = MonitoringInMemoryDataset(...)`, `uow_factory = lambda: FakeUnitOfWork(dataset)`, drive the use case, assert on `dataset.<table>` state (ADR-0024).
- Cross-cutting fakes (`FixedClock` etc.) from `tests/shared_kernel/fakes.py`.
- Mirror DB-side constraints (`GENERATED` columns, biconditional `CHECK`) inside fakes so they fail the same inputs as the real adapter.
- Assert on observable state — `dataset.<table>`, returned sum-type variant, `uow.committed` flag — never on call patterns.
- Property-based tests (Hypothesis / Kotest) for pure domain functions with large input space.
- Explicit test cases for every sum-type failure variant (`Rejected`, `NotFound`).
- Cross-BC use-case tests: one `InMemoryDataset` per BC (never shared across BCs — mirrors ADR-0020 per-BC UoW).

DON'T:
- Mock the system clock — pass a frozen value via `FixedClock`.
- Use mock library (`unittest.mock`, `MagicMock`) inside `tests/contexts/*/`. Working in-memory fakes only.
- Assert on whether a method was called or with what arguments. Assert on dataset state / returned value.
- Use testcontainers in domain or unit tests — only in integration tests (`tests/.../integration/`).
- Skip a `Rejected` / `NotFound` variant in tests.
- Per-test ad-hoc fakes that re-implement a Port. Use the BC's `fakes.py`.
- Share one `InMemoryDataset` across multiple BCs.

Sanctioned escape: optional `call_log: list[str]` parameter on a fake, for cross-fake call *ordering* assertions (lock-then-read). Never for argument inspection.

---

## §11. DDD terminology — what we say in code

USE (in identifiers and filenames):
- "Value Object" (concept; identifiers as concrete nouns).
- "Domain Event" (concept; identifiers as past-tense verbs — `LineWentDown`).
- "Aggregate" / "Entity" — concepts only. In code, name by concrete role (`LineState`, `Topology`).
- "Repo" suffix on adapter / port classes — general persistence vocabulary, not DDD-classical marker (ADR-0019).

DO NOT USE (as code identifiers or filenames):
- "Aggregate", "Repository", "Domain Service", "Factory" suffixes — DDD-classical names carrying mutable-method / infra-coupled-abstraction implications that conflict with FC/IS.

---

## §12. CI gates (single source: ADR-0023; extended by ADR-0032)

Python `import-linter` contracts (full list in ADR-0023):
1. `domain-no-system-reads`
2. `domain-no-validation-libs`
3. `domain-no-infrastructure`
4. `use-cases-no-domain-or-adapters`
5. `bc-independence` (per BC pair)
6. `adapters-no-upward` (ADR-0019)
7. `composition-only-imports-adapters`

Kotlin Konsist:
- K1 (domain-no-system-reads), K2 (domain-no-persistence), K3 (adapters-no-upward — **active**: `assertArchitecture` layer-direction test in bridge + simulator, ADR-0032).

Custom AST checks (`tests/architecture/`):
- A1 — `datetime.now(` / `datetime.utcnow(` / `time.time(` call-site in domain.
- A2 — `uuid.uuid4(` / `uuid.uuid1(` call-site in domain.
- A3 — `uow.session` access outside `composition.py` (ADR-0020 escape-hatch enforcement).

**Added by ADR-0032 (lint hardening):**
- **Suppression discipline** — ruff `PGH004` (blanket-noqa) + `RUF100` (stale-noqa); mypy `warn_unused_ignores` + `enable_error_code=["ignore-without-code"]`; detekt `ForbiddenSuppress` (architecture rules un-silenceable) + `ForbiddenComment` (TODO/FIXME/STOPSHIP ban); `scripts/check-domain-no-suppress.py` (no inline `# noqa` / `# type: ignore` under `*/src/**/domain/` or `shared_kernel/`).
- **Complexity** (explicit, Py↔Kt aligned) — ruff mccabe `max-complexity=12` + pylint `max-args/branches/returns/statements`; detekt `NestedBlockDepth` / `LongParameterList` / `ThrowsCount`.
- **Private-member leak** — ruff `SLF001` (attribute access; `tests/**` exempt for fakes).
- **Kotlin domain-purity defense-in-depth** — detekt `ForbiddenImport` + `ForbiddenMethodCall`, scoped `includes: ['**/domain/**']` (mirror K1/K2 at lint level). `ForbiddenMethodCall` **requires type resolution** → CI runs `detektMain detektTest`, not plain `detekt`. A new forbidden API must be added in BOTH `detekt.yml` and the Konsist tests.
- **Formatter** — `apps/ot-gateway-kotlin/.editorconfig` (line length 120) aligns ktlint with detekt's `MaxLineLength`.
- **Edit-time hook** (`.claude/hooks/lint-on-edit.sh`, registered in `.claude/settings.json`) — per-folder *self-only* format+lint at authoring time. An accelerator, **NOT** a gate; the authoritative gates remain pre-commit + CI.

mypy strict / detekt / ktlint — no opt-outs.

If your code adds a new domain module: mirror the lint contracts.
DO NOT disable a contract to make code pass. Fix the code.

---

Full rationale: `docs/architecture/2026-05-23-code-architecture.md`. Decision records: `docs/ADR/0004 / 0009 / 0016 / 0017 / 0018 / 0019 / 0020 / 0021 / 0022 / 0023 / 0024 / 0032`. Reference impl: kept locally (memory `reference-codebase`).
