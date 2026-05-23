# ADR-0018: Pydantic position — boundary only, not in domain

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

Pydantic is the de facto standard for Python data validation at API boundaries. FastAPI (used in this project) is built on top of it. Most Python projects with a serious data layer use Pydantic somewhere.

Spec §3.1 ("Pydantic이 표현력 강함") mentions Pydantic in the context of the ISA-95 data model. Read literally, this could justify putting Pydantic into the domain layer. Phase 1 plan, however, uses `@dataclass(frozen=True, slots=True)` for domain ID types — a tacit dataclass-in-domain choice without an explicit ADR.

The first-order purity question: does Pydantic-in-domain break ADR-0004's "zero IO + zero validation lib" rule? Pydantic models are pure data containers + synchronous validation — they do not perform IO and they are deterministic. Test purity (zero mocks/stubs/fakes) is *preserved* with Pydantic in domain.

But the second-order concerns are real:

1. **Two notions of validation get conflated.** Pydantic's `@field_validator` is *input shape* validation (boundary concern); domain invariants are *transition/relational* concerns expressed in sum types and functions. Mixing them inside a single Pydantic model is the most common slippage. Cosmic-python (Percival & Gregory) explicitly separates the two for this reason.
2. **Serialization knowledge leaks into core.** Pydantic models carry `.model_dump_json()` / OpenAPI schema generation. JSON is a boundary concern; a pure domain type should not implicitly know how to JSON-serialize itself.
3. **Pydantic API drift.** v1 → v2 was a breaking change (`@validator` → `@field_validator`, `Config` class → `model_config = ConfigDict(...)`, etc.). Coupling domain types to Pydantic version is unnecessary risk.
4. **Reference architecture alignment.** This project's architecture (FC/IS + DDD-flavor + monorepo) is closest to cosmic-python. That reference book explicitly uses dataclass for domain and Pydantic only at boundary. Reviewers familiar with the book will read the code through that lens.
5. **Performance** (minor). For 1,000 msg/sec hot-path ingest (spec Phase 3 AC), `@dataclass(frozen=True, slots=True)` is faster than Pydantic v2 BaseModel, though both are sufficient.

A "hybrid" option (Pydantic in domain but used as a frozen dataclass — no validators, no serialization) was considered and rejected: it pays the dependency cost without using the value.

## Decision

**Domain** (`contexts/*/domain/`, `shared_kernel/`): stdlib `@dataclass(frozen=True, slots=True)` only. Pydantic is forbidden, enforced via `import-linter` `forbidden` contract (`docs/architecture/2026-05-23-code-architecture.md` §9.1, contract #2).

**Shell** (`contexts/*/adapters/`, `use_cases/`, HTTP DTOs, Kafka payload validation, OpenAPI schemas, configuration via `pydantic-settings`): Pydantic is the standard tool.

The boundary DTO is a separate type from the domain type. Explicit conversion functions (`from_domain(...)`, `to_domain(...)`) move data across the boundary. Domain → DTO never happens implicitly.

Spec §3.1's reference to Pydantic for the ISA-95 data model is interpreted as boundary use (HTTP DTOs for ISA-95-shaped messages, validation of incoming Kafka payloads against JSON Schema-derived Pydantic models). This is consistent with this ADR and does not contradict the spec.

## Consequences

### Positive
- Two notions of validation stay separated by file location — *boundary validation* in shell DTOs, *domain invariants* in core sum types and functions.
- Domain types insulated from Pydantic API churn.
- Reference-architecture alignment makes the codebase legible to readers familiar with cosmic-python.
- Phase 1 plan code already uses stdlib dataclass — convention matches existing intent.
- Domain types are introspectable as plain Python objects without Pydantic's runtime overhead.

### Negative / Trade-offs
- Each "concept" has two types (domain `LineState` + boundary `LineStateDTO`) with manual conversion.
- Lose Pydantic's automatic OpenAPI schema generation for domain types (but OpenAPI is a boundary artifact anyway, so the cost is in the right place).
- A new developer (or LLM) reaching for Pydantic-in-domain by reflex will trip the lint rule until they internalize this ADR.

## Migration Path

If a future major Pydantic version provides a clean "pure-data" mode that decouples validation from serialization, and the cosmic-python guidance shifts, this ADR can be superseded. Adapter-style migration: introduce Pydantic to one BC's domain, run side-by-side, decide.

Reversal (allow Pydantic everywhere) would be easy mechanically (relax the lint rule); the cost is forfeiting the separation discipline this ADR encodes.

## Sources

- Pydantic v2 docs — https://docs.pydantic.dev/latest/
- Pydantic migration guide (v1 → v2) — https://docs.pydantic.dev/latest/migration/
- Harry Percival & Bob Gregory, *Architecture Patterns with Python* (O'Reilly 2020) — cosmic-python — explicit separation of domain dataclass from boundary Pydantic. https://www.cosmicpython.com/
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §8.3, `docs/ADR/0004-functional-core-imperative-shell.md`.
