# ADR-0017: System reads (clock / UUID / random) — inject from shell

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

ADR-0004 requires deterministic domain functions. Clock reads, UUID generation, and randomness are non-deterministic — calls like `datetime.now()`, `uuid.uuid4()`, `random.random()`, `Instant.now()`, `UUID.randomUUID()` make a function impure and its tests non-reproducible.

LLM-generated code reaches for these system reads instinctively. Without an explicit rule and lint enforcement, domain code accumulates silent purity violations that are not caught by structural import lint alone (the `datetime` module itself is legitimately used for the *type*).

Time / UUID / randomness all share the same problem shape: *the value should come from outside the function*. Bundling them into one rule keeps the convention small and memorable.

## Decision

Core (`contexts/*/domain/`, `shared_kernel/`) may not invoke any system-read function. Specifically forbidden inside domain:

- Python: `datetime.now()`, `datetime.utcnow()`, `time.time()`, `uuid.uuid4()`, `secrets.*`, `random.*`.
- Kotlin: `Instant.now()`, `System.currentTimeMillis()`, `UUID.randomUUID()`, `Random.*`.

Type imports remain allowed (e.g., `from datetime import datetime` for type annotations; `import java.time.Instant` for the type).

Shell provides the value via:

- **Python**: function-argument injection (`now: Callable[[], datetime]`) for single-purpose; `Clock` Protocol when multiple methods are needed.
- **Kotlin**: `java.time.Clock` (stdlib) as a constructor argument; `Clock.systemUTC()` in production, `Clock.fixed(...)` in tests.

Enforcement:

- `import-linter` `forbidden` contract for module-level imports of `random`, `secrets`.
- Custom AST-walking pytest in `tests/architecture/` catches call-site usages of `datetime.now`, `uuid.uuid4`, `time.time` that `import-linter` can't see (it operates at module level, not call level).
- Konsist test in Kotlin for analogous call-site rules.

## Consequences

### Positive
- Domain tests are fully reproducible — same input always gives the same output.
- Frozen-clock testing is trivial and uniform across the codebase.
- Property-based tests (Hypothesis / Kotest) become safe — no flakiness from real clocks.
- Same convention covers all system reads, not just time. New system reads (file IO, env vars) fall under the same FC/IS rule (ADR-0004) and don't need a separate ADR.

### Negative / Trade-offs
- Function signatures have an extra `now` / `clock` parameter. Slight readability cost.
- Composition root has to wire real-clock implementations for production.
- `import-linter` alone can't enforce call-site rules; custom AST check is needed (small maintenance cost).

## Migration Path

Irreversible by design. The determinism guarantee is the value; relaxing it reintroduces flakiness. If ever rolled back, the cost is identifying every injected clock parameter and replacing it with a direct system call — mechanical but tedious.

## Sources

- Miško Hevery, "Writing Testable Code" — guides on DI for system reads (2008). https://misko.hevery.com/code-reviewers-guide/
- Java `java.time.Clock` — https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/time/Clock.html
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §5.
