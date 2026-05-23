# ADR-0004: Functional Core / Imperative Shell

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

This project's headline thesis is "AI-native senior absorbing an unfamiliar domain with *honest standards-based modeling* and *formal LLM drift containment*" (spec §1.1). Two forces specifically pull toward FC/IS:

1. **AI-assisted code must be drift-checkable.** LLM-generated domain code frequently sneaks in IO, validation libraries, or hidden state. Without a *structural* purity rule that lint tools can verify, drift is only catchable by human review — and that doesn't scale to the rate of LLM output.
2. **Domain complexity (OEE per ISO 22400, Sparkplug B parsing, line state machines) must be testable in isolation.** Mock-heavy tests around impure domains rot the moment the schema shifts; pure-function domains stay testable indefinitely.

Alternatives considered: classical layered architecture with services + repositories (loses purity guarantee), hexagonal without the purity rule (allows IO in domain, defeats drift containment).

## Decision

Adopt Functional Core / Imperative Shell (Bernhardt 2012). The load-bearing rule is operationalized as:

**Domain modules (`contexts/*/domain/`, `shared_kernel/`) contain zero IO imports and zero validation-library imports.** All side effects, validation against external schemas, and external library usage live in adapters or application/use-case modules (shell).

Enforcement is mechanical, not cultural: `import-linter` `forbidden` contracts (Python) + Konsist architecture tests (Kotlin), wired into CI per spec §6. Specific contracts and call-site checks are documented in `docs/architecture/2026-05-23-code-architecture.md` §9.

## Consequences

### Positive
- Domain tests need **zero mocks, stubs, or fakes** (spec §2.1 §7) — they run sub-second, can be property-based.
- LLM-introduced impurity is caught by lint, not by reviewer attention.
- Reviewers (interview readers) can trust that anything in `domain/` is pure by structural guarantee, not by hope.
- Property-based testing (Hypothesis / Kotest) becomes safe and useful.
- Migration to events / different infrastructure is local to the shell.

### Negative / Trade-offs
- Adapter layer is verbose: row→domain mapping written by hand.
- Two notions of "validation" must be kept distinct: input shape (boundary, Pydantic) vs domain invariant (core, sum types). Easy to confuse.
- Domain types cannot use ORM annotations (ADR-0018, see also arch doc §8) — convenience cost.

## Migration Path

Irreversible by design. The purity guarantee is the value; relaxing it returns to the impure-domain status quo. If ever needed, exit is via incremental adapter inversion: identify a domain function with an IO call, extract the IO to an injected callable, repeat.

## Sources

- Gary Bernhardt, "Boundaries" (Ruby Conf 2012). https://www.destroyallsoftware.com/talks/boundaries
- Harry Percival & Bob Gregory, *Architecture Patterns with Python* (O'Reilly 2020). https://www.cosmicpython.com/
- Scott Wlaschin, *Domain Modeling Made Functional* (Pragmatic 2018) — same principle applied to F#.
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §1, `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2.1.
