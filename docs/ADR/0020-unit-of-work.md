# ADR-0020: Unit of Work — async transaction boundary owned by use cases

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

ADR-0019 frees adapters to use SQLAlchemy 2.0 ORM under containment rules and explicitly forbids adapters from committing. That leaves an open question: *where does `commit()` go?* If not in the adapter, then either the use case manages a session directly (couples the use case to SQLAlchemy) or there is a dedicated transaction-boundary object.

The reference impl (`the reference codebase`) uses the Unit of Work pattern from cosmic-python. A `UnitOfWork` Protocol exposes per-feature repo attributes (`uow.lines`, `uow.audit_logs`, …). A concrete `SqlAlchemyUnitOfWork` opens a fresh `AsyncSession` on `__aenter__`, binds those repos to that session, and closes the session on `__aexit__`. The use case writes `async with self._uow_factory() as uow:`, performs its mutations through the bound repos, calls `await uow.commit()` on success, and lets `__aexit__` roll back if an exception escapes. The session never leaks across use-case invocations and the transaction boundary is visible at the call site.

This pattern complements ORM containment cleanly: the adapter holds the `AsyncSession`, mutates it via the ORM, and never commits; the UoW owns the lifecycle and the commit; the use case orchestrates the calls and decides when the unit is done.

A secondary design question: **scope of a single UoW.** Per the multi-BC structure (`contexts/<bc>/`) and ADR-0009 (inter-context communication — sync reads or async events, no cross-BC atomic writes), a UoW is bounded to one BC. The Protocol exposes only that BC's repo attributes, and cross-BC operations open multiple per-BC UoWs in sequence. A global UoW with all BCs' repos was rejected: it would invite cross-BC atomic writes by reflex, contradicting ADR-0009. Tx-spanning is not the missing feature — independence is.

A simpler alternative — "use case gets a session directly, owns the commit, no UoW abstraction" — was rejected because it couples every use case to SQLAlchemy (breaks ADR-0023's adapters-and-infra-only constraint on SQLAlchemy imports) and forces every test to construct or stub a real `AsyncSession`. The UoW Protocol gives the use case a substitutable boundary; the fake UoW (ADR-0024) is a working in-memory implementation with the same attribute shape.

## Decision

Introduce a `UnitOfWork` Protocol at **`contexts/<bc>/ports/unit_of_work.py`** (per-BC, not global). The Protocol:

- Declares per-feature repo attributes that the BC's use cases need (`audit_logs: AuditLogRepo`, `lines: LineRepo`, …).
- Is an async context manager: `__aenter__` / `__aexit__` return / accept the standard async context types.
- Exposes `commit()` and `rollback()` coroutines.

Concrete adapter **`contexts/<bc>/adapters/sqlalchemy_uow.py`** (`SqlAlchemyUnitOfWork`):

- Constructor takes a `session_factory: async_sessionmaker[AsyncSession]`. Engine ownership stays in `composition.py`.
- `__aenter__` opens a fresh session via `session_factory()`, binds per-feature repo instances (e.g., `self.audit_logs = PostgresAuditLogRepo(self._session)`), returns `self`.
- `__aexit__` rolls back if an exception is propagating, then closes the session unconditionally.
- `commit()` / `rollback()` call through to the session.
- Production sessionmaker is built with `async_sessionmaker(engine, expire_on_commit=False)` — async post-commit lazy-load implicitly awaits, a documented async foot-gun.

Use cases receive a **factory**: `uow_factory: Callable[[], UnitOfWork]`. They do not receive a long-lived UoW. Each call constructs a fresh UoW (and therefore a fresh session) per `async with` block. This matches the the reference codebase pattern and keeps the session lifecycle bounded by the use case invocation, not by the request or by process lifetime.

```python
async def execute(self, request: Request) -> Outcome:
    async with self._uow_factory() as uow:
        result = await uow.lines.insert_draft(...)
        await uow.audit_logs.append(AuditLogEntry(...))
        await uow.commit()
        return Ok(result)
```

Adapters that need a session but are not part of the per-BC UoW Protocol's published attributes (e.g., cross-system readers like a separate read-only legacy DB adapter, or composition-root-bound adapters that vary by use case) get the session via `uow.session` — a property exposed on the concrete `SqlAlchemyUnitOfWork` but *not* on the `UnitOfWork` Protocol. The composition root reads `uow.session` to construct those adapters per-call. Use cases do not touch `uow.session`.

Cross-BC use cases (`src/sdf_api/use_cases/`) open one UoW per BC they operate on, in sequence. There is no cross-BC atomic transaction. State propagation across BCs goes through `DomainEvent` dispatch per ADR-0009, not through a shared tx.

Fakes (ADR-0024) implement the same `UnitOfWork` Protocol. The fake UoW backs its repo attributes with a shared `InMemoryDataset` so multiple repos within one UoW see one source of truth — mirroring the real per-session adapter pattern.

## Consequences

### Positive
- Transaction boundary is visible at the use-case call site (`async with self._uow_factory() as uow: ... await uow.commit()`). No magic.
- Adapter cannot commit. The discipline survives review pressure mechanically.
- Per-BC UoW reinforces ADR-0009 inter-context independence: there is no syntactic way to write a cross-BC atomic tx.
- Fake UoW with `InMemoryDataset` gives use-case tests a working substitute — no mocking the session, no testcontainers in the unit lane.
- Session lifecycle bounded by use-case invocation: no leak across requests, no leak across `async with` blocks.

### Negative / Trade-offs
- Every use case carries an extra constructor argument (`uow_factory`). One more line in the composition wiring.
- Per-BC UoW means cross-BC use cases get *no* atomic boundary across BCs. This is by design (ADR-0009) but reviewers expecting traditional service-layer atomicity will need to read the rationale.
- `uow.session` is an escape hatch — discipline (only composition.py touches it; use cases never) is enforced by review, not by lint. A custom AST check could enforce it later if the escape is abused.
- The factory pattern (zero-arg callable returning a fresh UoW) is one indirection more than passing a UoW class. Tests must remember `lambda: FakeUnitOfWork(dataset)` rather than `FakeUnitOfWork(dataset)`.

## Migration Path

Removing UoW is mostly mechanical: each adapter would absorb its own session/commit responsibility, and each use case would either inline the session lifecycle or accept a session directly. The discipline that adapters cannot commit would be lost; reviewers would need to catch it manually.

Promoting per-BC UoW to a global UoW (if ADR-0009 is ever superseded) means consolidating the Protocol into `shared_kernel/ports/unit_of_work.py` and routing per-BC repos through one big object. Mechanical change; no domain-code rewrite needed.

## Sources

- Harry Percival & Bob Gregory, *Architecture Patterns with Python* — chapter 6 "Unit of Work" (cosmic-python). https://www.cosmicpython.com/book/chapter_06_uow.html
- SQLAlchemy 2.0 async — `async_sessionmaker`, `expire_on_commit=False` rationale. https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession
- `adapters/sqlalchemy_uow.py` + `ports/unit_of_work.py` — reference impl.
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §8 + new UoW section, `docs/ADR/0009-inter-context-communication.md`, `docs/ADR/0019-orm-containment-in-adapters.md`, `docs/ADR/0024-fakes-with-in-memory-dataset.md`, `docs/plans/2026-05-23-reference-codebase-alignment-plan.md` §10.
