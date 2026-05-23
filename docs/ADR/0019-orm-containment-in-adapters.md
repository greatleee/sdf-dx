# ADR-0019: ORM containment in adapters

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

ADR-0004 forbids `sqlalchemy.*` and `jakarta.persistence.*` from `domain/` and `shared_kernel/`. That rule is uncontested — ORM-flavored domain types (declarative `Base` subclasses, JPA `@Entity`) drag persistence semantics (lazy loading, identity map, session affinity) into pure code and conflate "data shape" with "DB row".

The follow-up question — *what does the adapter use?* — was over-constrained on first pass to "SQLAlchemy Core (DSL only) or `asyncpg` raw". That reading rules out a working pattern used in the Python reference impl this project is calibrated against (`the reference codebase`, see Sources): SQLAlchemy 2.0 ORM is used *inside* the adapter file, with the declarative classes kept private and the public adapter surface returning domain types or primitives. Domain never sees an ORM object; the adapter pays the small cost of mapping rows in/out at the file boundary.

Three forces pushed the rule open:

1. **Reference alignment.** `adapters/postgres_orders.py` demonstrates the containment pattern: `_Base(DeclarativeBase)` and `_Order(_Base)` are module-private; `PostgresOrdersRepo(session)` is the public class and returns `int` / `int | None`. The ORM declarative class never leaks past the file. Independent of any architectural label, this is the pattern that ships in the reference codebase.
2. **ORM ergonomics with discipline.** SQLAlchemy 2.0's `Mapped[...]` + `mapped_column(...)` gives type-checked schema definitions, integrates with Alembic for migrations, and expresses DB-side `Computed(..., persisted=True)` for `GENERATED` columns. Reproducing that with raw `asyncpg` requires hand-rolled type adapters per column. The cost-benefit shifted once SQLAlchemy 2.0 stabilized the typed API.
3. **`*Repo` is general vocabulary, not DDD-classical.** The "no `*Repository`" line in early naming notes was inherited from a DDD-purity stance. In practice "repo" is used in non-DDD codebases as a generic persistence-class name (it was used long before DDD took it on). Banning it forfeits a widely understood term for no benefit once the leakage concerns are addressed by containment.

ADR-0018 (Pydantic boundary-only) is *not* relaxed by this ADR — domain types remain stdlib `@dataclass(frozen=True, slots=True)`. Containment governs *ORM*, not validation libraries. The two libraries play different roles and the rule for each is independent.

## Decision

**Adapter layer (`contexts/*/adapters/`)** may use SQLAlchemy 2.0 ORM under the following containment rules:

1. **Private ORM declarations.** `DeclarativeBase` subclass and every `Mapped`/`mapped_column` class carries an underscore prefix and is defined inside the adapter file: `class _Base(DeclarativeBase): pass`, `class _Order(_Base): ...`. No other module imports these.
2. **Adapter public surface returns domain types or primitives only.** Public methods return `int`, `int | None`, `list[<DomainType>]`, sum-type instances, `None` — never an `_Order` instance, never a `Row[...]`, never a `Mapped[...]` value. Adapter-internal `_to_domain(row) -> <DomainType>` helpers do the projection at the file boundary.
3. **Adapter constructor takes `AsyncSession`, does not own the engine, does not commit.** Engine ownership lives in `composition.py` (the composition root). Transaction commit/rollback belongs to the use case via Unit of Work (ADR-0020). Adapter mutates the session and lets the UoW close the boundary.
4. **No class-level Port inheritance.** Adapters do not write `class PostgresOrdersRepo(OrdersRepoPort): ...`. Port satisfaction is structural (`Protocol` duck-typing). The composition root acknowledges the structural match with an explicit `cast(OrdersRepoPort, PostgresOrdersRepo(session))`. The reason is the `adapters-no-upward` import-linter contract (ADR-0023): adapter files do not import from `ports/`.
5. **DB-side generated columns mirrored at the ORM level.** Columns declared `GENERATED ALWAYS AS (...) STORED` in DDL use `Computed("expr", persisted=True)` in the `Mapped` declaration, and adapter `INSERT`/`UPDATE` calls do not pass those columns (Postgres rejects writes to generated columns).
6. **`*Repo` suffix is allowed** on adapter classes (`PostgresOrdersRepo`) and on Port classes (`AdminLineRepo`). It is treated as general persistence vocabulary, not a DDD-classical "Repository pattern" marker. Other suffixes (`*Reader`, `*Writer`, `*Port`, `*Ledger`, `*Adapter`) remain available — pick the one that best describes the concrete role.

**Domain layer (`contexts/*/domain/`, `shared_kernel/`)** remains ORM-free. The ADR-0004 import contracts continue to forbid `sqlalchemy.*` and `jakarta.persistence.*` from domain modules.

`async_sessionmaker(engine, expire_on_commit=False)` is the standard async sessionmaker configuration (post-commit lazy-load implicitly awaits, which is a common async foot-gun — see ADR-0020 Sources).

## Consequences

### Positive
- Adapter ergonomics: typed `Mapped[...]` columns, Alembic-compatible migrations, `Computed(...)` for generated columns, query DSL with explicit `select` / `update` constructs.
- Reference alignment: `adapters/postgres_orders.py` is a 1:1 template.
- Domain purity preserved: ORM never crosses the adapter file boundary; the import contracts in ADR-0004 keep enforcing that mechanically.
- `*Repo` suffix availability removes a recurring naming-rule friction without compromising the architecture.

### Negative / Trade-offs
- Adapter author has to remember not to leak `_Order` outside the file. This is reviewer-visible (a public method whose return type is `_Order` is an obvious flag) and is the cost of containment.
- DB-side generated columns require ORM-side mirroring with `Computed(...)`, plus a comment that writes to those columns are forbidden — one extra line per such column.
- SQLAlchemy 2.0 typed API still has rough edges around dialect-specific types (`postgresql.UUID(as_uuid=True)`, `PgEnum(...)`). Adapter authors will hit them; the cost is local to the adapter file.

## Migration Path

Each adapter is a single file. If a future decision drops ORM (e.g., for a hot-path adapter where `asyncpg` raw is measurably faster), that one adapter is rewritten in isolation — the Port surface stays the same and use cases are untouched.

Full reversal (revert to "Core only") would mechanically delete the `_Base` / `_X` ORM classes per adapter and rewrite the mutation helpers with `insert()` / `update()` Core constructs. Loss is mostly ergonomics and migration-tooling integration.

## Sources

- `adapters/postgres_orders.py` — reference impl of containment pattern (path local, see project memory).
- SQLAlchemy 2.0 ORM with typed `Mapped[...]` — https://docs.sqlalchemy.org/en/20/orm/quickstart.html
- SQLAlchemy `Computed` for generated columns — https://docs.sqlalchemy.org/en/20/core/defaults.html#server-invoked-ddl-explicit-default-expressions
- Harry Percival & Bob Gregory, *Architecture Patterns with Python* — Repository chapter (cosmic-python). https://www.cosmicpython.com/
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §8, `docs/ADR/0004-functional-core-imperative-shell.md`, `docs/ADR/0020-unit-of-work.md`, `docs/ADR/0023-importlinter-contract-set.md`, `docs/plans/2026-05-23-reference-codebase-alignment-plan.md` §10.
