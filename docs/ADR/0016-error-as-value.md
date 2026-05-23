# ADR-0016: Error representation — core returns failures as values via sum types

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

ADR-0004 (FC/IS) makes domain functions pure. The natural follow-on question — *how do failures cross the function boundary?* — needs an explicit answer, because LLM-generated code defaults to throwing exceptions in both Python and Kotlin, which:

- Bypasses the type system (caller can't see what failures are possible from a signature).
- Breaks exhaustiveness checks at the call site.
- Conflates *expected domain failures* (the operation is rejecting input as a normal outcome) with *unexpected bugs* (assertion violations).

The project is polyglot Python + Kotlin. The error idiom needs to work in both without requiring an external library on either side (otherwise the lib itself becomes an axis of drift). Candidates considered:

- Throw exceptions in core → conflicts with FC/IS purity; loses exhaustiveness.
- `Result<T, E>` via library (`returns` for Python, stdlib `Result` for Kotlin) → introduces library coupling for a pattern that sealed classes / tagged unions express natively. `Result` also discards type information on the error side or stringly-types it.
- `arrow-kt` `Either` → powerful, but a heavyweight dependency; Python has no clean counterpart, so the idiom diverges between languages.
- **Self-defined sum types** (sealed interface in Kotlin, tagged dataclass union in Python) → zero external dependency, native to both languages, full type information on every case, exhaustive at the call site.

The phase 1 plan code samples written before this decision use `raise X` (e.g., `raise InvalidTransition`, `raise UnknownMachine`). They will be revised at execution time per the plan's forward-reference rule (`docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md` header).

## Decision

Core returns failure shapes as part of the function's return type using sum types. Idioms:

- **Kotlin**: `sealed interface <Op>Outcome` + `data class` cases. Discriminate with `when`; compiler enforces exhaustiveness.
- **Python**: `@dataclass(frozen=True)` cases composed with `Union` (`|`). Discriminate with `match` or `isinstance`.

The shell may translate sum cases to exceptions at the HTTP / Kafka boundary (FastAPI `HTTPException`, Kafka DLQ routing).

External error-handling libraries (`arrow-kt`, `returns`) are **forbidden in domain** and enforced via `import-linter` / Konsist (`docs/architecture/2026-05-23-code-architecture.md` §9).

"Expected failure" = a normal outcome the caller might reasonably handle (e.g., `Rejected`, `NotFound`). "Unexpected failure" = programmer error / invariant violation; this may still raise — those are bugs, not domain outcomes.

## Consequences

### Positive
- Exhaustiveness checks at the call site catch unhandled cases at compile / type-check time.
- Failure reasons are typed (case names), not stringly-typed.
- Domain stays self-contained — no monad library coupling.
- Property-based tests can assert outcome shapes without try/except scaffolding.

### Negative / Trade-offs
- More verbose than `raise/throw`. Trade explicitness for brevity.
- Phase 1 plan code samples (written before this ADR) use `raise X`; revision happens during execution per plan's forward-reference rule.
- Python's `match` is 3.10+; not a concern for this project (3.12) but worth noting for portability.
- Boundary translation code (sum → HTTPException) must be written; small ongoing cost.

## Migration Path

Introducing a Result-monad library later is cheap (sealed classes don't preclude wrapping). Reversal (returning to raise/throw) would be more disruptive — all call sites would need rework. The decision favors the harder-to-reverse direction up front.

## Sources

- Scott Wlaschin, *Domain Modeling Made Functional* (Pragmatic 2018) — sum types as domain outcomes.
- Kotlin sealed interfaces — https://kotlinlang.org/docs/sealed-classes.html
- Python `match` (PEP 634) — https://peps.python.org/pep-0634/
- Python typing union syntax (PEP 604, 3.10+) — https://peps.python.org/pep-0604/
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §4.
