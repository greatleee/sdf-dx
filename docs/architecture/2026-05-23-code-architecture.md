# Backend Code Architecture — Conventions

| | |
|---|---|
| **Date** | 2026-05-23 |
| **Status** | Draft — skeleton. Body to be filled in subsequent commits. |
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
7. **Cross-BC state propagation**: in-process `DomainEventDispatcher`. No Kafka for domain events.
8. **Cross-aggregate (same BC)**: 1 transaction = 1 aggregate. Multi-aggregate orchestration in application/use-case layer.
9. **ORM**: avoid object-relational mappers that pollute domain (JPA, SQLAlchemy ORM). Use Exposed/JOOQ (Kotlin) or SQLAlchemy Core / asyncpg raw (Python).
10. **Test pyramid**: domain tests = 0 mock / 0 stub / 0 fake / sub-second. Spec §7.

---

## §1. Principles

> **Status**: link-only. FC/IS principle statement lives in spec §2.1 (Bernhardt). This doc only specifies *how* FC/IS is applied in this codebase.

Body TBD:
- Mapping FC/IS terms to this codebase's folder layout (already in spec §9.1, §9.2).
- The single load-bearing claim: **domain modules contain zero IO imports**. Everything else follows.
- Enforcement: see §9.

---

## §2. DDD Tactical Mapping

> **Status**: skeleton.

Body TBD:
- Matrix: Value Object / Aggregate / Domain Event / Repository / Domain Service / Factory / Entity → FC/IS placement + whether we use the term.
- Naming conventions: `<Noun>Reader` / `<Noun>Writer` ports (no Repository). `apply_<event>` for state transitions. No `*Service` suffix for domain code.

---

## §3. Bounded Context boundaries + cross-BC + cross-aggregate calls

> **Status**: skeleton. Reflects decision **B3 = Option B (top-level `use_cases/`)** and **state-propagation = in-process dispatcher**.

Body TBD:

### §3.1 BC-internal calls
- One transaction = one aggregate. Multi-aggregate orchestration lives in `<bc>/application/` use-case (shell), not in domain.

### §3.2 Cross-BC sync queries (joins across BCs)
- Live in `src/sdf_api/use_cases/` (top-level, outside any BC).
- Each BC exposes a `ports.py` (Protocol). Cross-BC use case imports both BCs' ports, never their domain.
- `composition.py` (root) wires concrete adapters into the use case.
- `import-linter` `independence` contract between BCs stays in force.

### §3.3 Cross-BC state propagation (events)
- Core returns domain events as values (part of the sum-type outcome).
- Application (shell) dispatches via in-process `DomainEventDispatcher` (defined in `shared_kernel/events.py`).
- `composition.py` registers handlers. BCs never know about each other directly.
- **Migration path**: when BCs split into separate services, swap the dispatcher's publish implementation with a Kafka producer. Public interface (`dispatch(event)`) stays the same.

### §3.4 Why not Kafka for domain events (in Phase 1~4)
- Kafka in this project is for **telemetry pipeline only** (OPC UA → ingest). Domain events are a different abstraction layer; bundling them onto Kafka is conflation.
- In-process dispatcher: zero infra, synchronous-by-default (easier to reason about, same transaction possible), trivial migration to Kafka when warranted.

---

## §4. Error Representation — "분리안"

> **Status**: skeleton. Reflects decision **B6 = self-defined sealed class / tagged union, no external lib**.

Body TBD:
- Rule: **core returns failures as values**, never raises. Shell may translate to exceptions at the FastAPI/HTTP boundary.
- Kotlin idiom: `sealed class <Operation>Outcome { data class Applied(...); data class Rejected(...) }`.
- Python idiom: `@dataclass(frozen=True)` types + `Union` with a `Literal` discriminator (or `kind` field).
- No `arrow-kt`, no `returns` lib — keep dependency surface minimal.
- Anti-pattern: returning `None` for "not found" (use explicit `NotFound` variant).
- Test rule: every Rejected/NotFound variant has its own test case.

---

## §5. Clock / UUID / Random injection

> **Status**: skeleton.

Body TBD:
- Rule: **core may not import `datetime.now`, `uuid.uuid4`, `random.*`, `time.time()` and equivalents.** These are *system reads*, not domain logic.
- Inject from shell:
  - Python: function-argument injection (`now: Callable[[], datetime]`) or a `Clock` Protocol.
  - Kotlin: `java.time.Clock` (stdlib) — already a standard idiom.
- Enforcement: extend `import-linter` `forbidden` contract on domain modules to include `datetime` / `uuid` / `random` standalone imports (allow `datetime` as a type, but not `datetime.now`). Konsist rule mirror.
- Test corollary: domain tests never depend on wall-clock time; they pass explicit timestamps.

---

## §6. shared_kernel boundary

> **Status**: skeleton. Reflects gap **B4**.

Body TBD:
- **Allowed in `shared_kernel/`**: typed IDs (UUID newtype wrappers), cross-cutting VOs (TenantId, timezone-aware Timestamp wrapper).
- **Forbidden**: aggregates, domain services, BC-spanning events, BC-spanning use cases.
- Reason: shared_kernel is intentionally small to keep BC coupling minimal. Anything beyond pure cross-cutting values goes through ports + events.

---

## §7. Per-language callout matrix

> **Status**: skeleton.

Body TBD (matrix of idioms per concept):

| Concept | Kotlin idiom | Python idiom |
|---|---|---|
| Immutability | `data class` + `val` + `.copy()` | `@dataclass(frozen=True, slots=True)` |
| Sum type | `sealed class` / `sealed interface` | tagged union with `Literal` discriminator |
| DI (clock/uuid) | constructor injection, `java.time.Clock` | function arg or `Protocol` |
| Async | `suspend` (IO boundary visible) | `async def` |
| Module boundary | `internal`, `-Xexplicit-api=strict`, Konsist | `import-linter` contracts |
| Pure enforcement | `suspend` makes IO partially formal | 100% convention + `import-linter` |

The matrix is the source of truth for "how do I write X in Python vs Kotlin." Original principle is the same in both languages.

---

## §8. Persistence — ORM caution

> **Status**: skeleton.

Body TBD:
- Forbidden: any ORM that requires annotations/inheritance on domain classes (JPA in Kotlin, SQLAlchemy ORM declarative base in Python). They pollute the pure core.
- Allowed (Kotlin): Exposed (DSL) or JOOQ (codegen). Domain stays pure; adapters use DSL to map.
- Allowed (Python): SQLAlchemy **Core** (not ORM) or `asyncpg` raw. Domain stays pure; adapters do the row→domain mapping by hand.
- Domain types must be constructible without DB knowledge. Adapter maps DB rows → domain factory function.

---

## §9. Lint / enforcement — delta over spec §6

> **Status**: skeleton. Spec §6 already has the toolchain matrix. This section only lists *additional* contracts implied by §4, §5, §6.

Body TBD (additional `import-linter` / Konsist contracts):

1. **domain ↛ time/random/uuid sources**:
   ```toml
   [[tool.importlinter.contracts]]
   name = "domain may not read system clock / uuid / random"
   type = "forbidden"
   source_modules = ["sdf_api.contexts.*.domain"]
   forbidden_modules = ["datetime.datetime.now", "uuid.uuid4", "random", "time.time"]
   ```
   (Note: `import-linter` works at module level; for `datetime.now` we may need a custom check or a lint plugin. Investigate during body writing.)
2. **`contexts/*/application` may not import other contexts' `domain`** — only `ports`. (Currently spec has full `independence`; this section relaxes it to "ports cross-import allowed only within a `use_cases/` module".)
3. **`use_cases/` may import any BC's `ports`** but not any BC's `domain` directly.
4. Konsist equivalents for Kotlin (multi-module gradle scope).

---

## §10. Open questions

To resolve during body writing or in a future ADR:

- O1. Should `application/` inside each BC be allowed to import the *same BC's* `adapters` for type signatures? (Probably no — only the composition root wires them. Confirm with code.)
- O2. Domain events naming: `<NounPastVerb>` (e.g., `LineWentDown`)? Or `<Noun><PastVerb>Event` suffix?
- O3. `DomainEventDispatcher` failure policy: handler exception kills the whole dispatch? Or swallow + log? (Probably configurable per handler; default = kill.)
- O4. For Python validation libraries (Pydantic) — used in domain or only at shell boundary? Spec §3.1 implies Pydantic is for "ISA-95 data model" which sounds domain-y. But Pydantic v2 is fast enough that it can be a domain modeling tool. Decide.

---

**End of skeleton. Body to be written in §1..§9 order in subsequent commits.**
