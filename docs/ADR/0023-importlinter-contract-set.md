# ADR-0023: Import contract set — `import-linter` (Python) + Konsist (Kotlin)

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

Architectural rules — "domain may not import infrastructure", "use cases may import ports across BCs but not their domain or adapters", "BCs are independent" — survive code review pressure only when a tool enforces them mechanically. Manual review catches the obvious case; the subtle ones (a single `import pydantic` deep inside a domain module, an `adapters/` file that reaches into a sibling BC) slip through.

Three forces converged here:

1. **Contracts were drafted in arch doc §9.1 (Python) and §9.2 (Kotlin) but never elevated to an ADR.** A reviewer reading the ADR set would not see the enforcement layer as a *decision* — they would see it only as documentation hidden inside the body of the architecture doc. The lint set is load-bearing; it deserves an ADR with the same status as the rules it enforces.
2. **ADR-0019 (ORM containment) introduces a new contract**: adapters must not import from `ports/`. Adapter classes satisfy Port Protocols structurally (duck-typed via `typing.Protocol`), and the composition root acknowledges the match with `cast(Port, ConcreteAdapter(...))`. The reason for the contract is that allowing `adapters/` to import `ports/` opens the door to cyclic-import workarounds and to adapter classes growing inheritance dependencies that they do not need. The reference impl (`the reference codebase`) uses exactly this pattern with a contract literally named `adapters-no-upward`.
3. **The lint set must be the single source.** Today the same intent appears in three places: arch doc §9, rules file §12 ("CI gates that enforce these rules"), and ADRs 0004 / 0017 / 0018 each mentioning their own contract. Drift between these is a real risk. This ADR consolidates the *list of contracts* as the source; arch doc §9 retains the TOML/Kotlin code samples, the rules file retains the do/don't surface, and individual ADRs reference this one for the enforcement layer.

The custom AST-walking pytest layer (arch doc §9.3) is left as-is — it covers call-site rules (`datetime.now(`, `uuid.uuid4(`, etc.) that `import-linter` cannot express at module level. This ADR enumerates the AST checks alongside the import contracts so the enforcement surface is fully visible.

## Decision

The following contract set is the source of truth for architectural enforcement. Changes land here first; arch doc §9 and the rules file follow.

**Python — `import-linter` contracts** (file: `backend/pyproject.toml` or `backend/.importlinter`):

| # | Name | Type | Source | Forbidden / Constraint | Origin |
|---|---|---|---|---|---|
| 1 | `domain-no-system-reads` | forbidden | `sdf_api.contexts.*.domain`, `sdf_api.shared_kernel` | `random`, `secrets` | ADR-0017 |
| 2 | `domain-no-validation-libs` | forbidden | `sdf_api.contexts.*.domain`, `sdf_api.shared_kernel` | `pydantic`, `marshmallow`, `attrs`, `returns`, `arrow` | ADR-0004, ADR-0018 |
| 3 | `domain-no-infrastructure` | forbidden | `sdf_api.contexts.*.domain`, `sdf_api.shared_kernel` | `sqlalchemy`, `asyncpg`, `aiokafka`, `httpx`, `fastapi`, `redis`, `pymemcache` | ADR-0004 |
| 4 | `use-cases-no-domain-or-adapters` | forbidden | `sdf_api.use_cases` | `sdf_api.contexts.*.domain`, `sdf_api.contexts.*.adapters` | arch doc §3.2 |
| 5 | `bc-independence` | forbidden | `sdf_api.contexts.<bc>` (per BC) | `sdf_api.contexts.<other-bc>` (every other BC) | Phase 1 plan Task 2, arch doc §3 |
| 6 | `adapters-no-upward` | forbidden | `sdf_api.contexts.*.adapters` | `sdf_api.contexts.*.ports`, `sdf_api.contexts.*.application`, `sdf_api.use_cases` | ADR-0019 (new) |
| 7 | `composition-only-imports-adapters` | forbidden | `sdf_api.contexts.*.application`, `sdf_api.use_cases` | `sdf_api.contexts.*.adapters` | arch doc §1.2, open question O1 |

Contracts 1–4 are codification of contracts already present in arch doc §9.1. Contract 5 is the per-BC independence contract drafted in the Phase 1 plan and now formalized. Contracts 6 and 7 are new in this ADR.

`shared_kernel` is treated as domain-grade for contracts 1–3 (same forbidden imports). It may export the `UnitOfWork` Protocol type for cross-BC use cases per ADR-0020, and `ClockPort` per ADR-0021.

**Kotlin — Konsist architecture tests** (file: `apps/*/src/test/kotlin/.../architecture/ArchitectureTest.kt`):

| # | Test name | Rule | Origin |
|---|---|---|---|
| K1 | `domain must not read system clock or uuid` | No call-site `Instant.now()` / `UUID.randomUUID()` / `System.currentTimeMillis()` inside `..domain..` packages | ADR-0017 |
| K2 | `domain may not depend on persistence frameworks` | No imports of `jakarta.persistence..`, `org.jetbrains.exposed..`, `arrow.core..`, `kotlinx.serialization..` (if used at boundary only) inside `..domain..` | ADR-0004 |
| K3 | `adapters may not import upward` | No imports of `..ports..` / `..application..` from `..adapters..` packages | ADR-0019 (Kotlin parallel — TBD at Phase 1 Task 4) |

K3 is listed for parity but will only be enabled when Kotlin code lands at Phase 1 Task 4. At that point a Kotlin-specific ADR (out of this plan's scope per §10.3) confirms the Kotlin contract set.

**Custom AST checks** (file: `backend/tests/architecture/test_call_sites.py`):

| # | Check | Rule | Origin |
|---|---|---|---|
| A1 | `domain-no-datetime-now` | No call expressions `datetime.now(` / `datetime.utcnow(` / `time.time(` inside `contexts/*/domain/` or `shared_kernel/` | ADR-0017 |
| A2 | `domain-no-uuid-call` | No call expressions `uuid.uuid4(` / `uuid.uuid1(` inside same scope | ADR-0017 |
| A3 | `uow-session-only-from-composition` | The attribute access `uow.session` may appear only in `composition.py` (whitelist by file path) | ADR-0020 |

A1 and A2 mirror existing arch doc §9.3 intent. A3 is new and enforces the ADR-0020 escape-hatch discipline.

**CI gate behavior** (unchanged from arch doc §9.4): all contracts run in CI (`make ci`). Local pre-commit runs the cheap subset (ruff, detekt, ktlint). `import-linter`, Konsist, mypy strict, tsc strict, dependency-cruiser, and the AST checks run in CI only.

A future addition (deferred): a `make lint-architecture` target that runs the import-linter + AST checks in isolation, for fast local feedback when intentionally refactoring import structure.

## Consequences

### Positive
- Single source of truth for the lint set. Cross-references from ADR-0004, 0017, 0018, 0019, 0020, 0021, 0022 land here.
- Contracts 6 and 7 close the two structural-purity gaps that the previous contract set left open (adapter-to-port import, adapter-from-non-composition import).
- AST check A3 enforces the `uow.session` escape-hatch discipline from ADR-0020 mechanically instead of by review.
- Kotlin parity contracts (K1–K3) are stated explicitly even though they activate only at Phase 1 Task 4 — the gap is visible.

### Negative / Trade-offs
- Seven Python contracts is a non-trivial enforcement surface. Maintenance cost when new modules land — each new top-level package needs a position relative to each contract. The cost is paid once per module and is review-visible.
- AST checks (A1–A3) are a small custom layer to maintain. The alternative (lint plugins) is more setup for one project.
- `composition-only-imports-adapters` (#7) may need tuning. The Phase 1 open question O1 in arch doc §10 leaves room for "application/ may import sibling BC's adapter for type signatures" — if that turns out to be needed, the contract relaxes to allow same-BC adapter imports from application only.

## Migration Path

Forward: each contract is added to `backend/pyproject.toml`'s `[[tool.importlinter.contracts]]` array. Tests in `tests/architecture/` are added per AST check. CI picks them up via `make ci`.

If a contract proves too strict in practice (false positives that mask real refactors), the response is either to refine the contract (narrower source/forbidden patterns) or to supersede this ADR with a revised set. Direct relaxation in the TOML without an ADR update is forbidden — the rule is "fix the code, not the contract" per rules file §12.

Reversal (dropping the contract set) would be mechanical (delete TOML entries, delete `tests/architecture/`) — but the entire FC/IS + BC-independence discipline depends on it. Reversal is a category-level decision that would supersede ADR-0004 as well.

## Sources

- `import-linter` docs (forbidden contract type) — https://import-linter.readthedocs.io/en/stable/contract_types.html
- Konsist (Kotlin architecture testing) — https://docs.konsist.lemonappdev.com/
- `the reference codebase` `adapters-no-upward` contract reference — `composition.py:131` cast(UnitOfWork, ...) acknowledgement.
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §9, `docs/ADR/0004-functional-core-imperative-shell.md`, `docs/ADR/0017-system-reads-injection.md`, `docs/ADR/0018-pydantic-at-boundary-only.md`, `docs/ADR/0019-orm-containment-in-adapters.md`, `docs/ADR/0020-unit-of-work.md`, `docs/plans/2026-05-23-reference-codebase-alignment-plan.md` §10.
