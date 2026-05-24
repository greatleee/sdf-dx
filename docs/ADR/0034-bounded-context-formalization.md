# ADR-0034: Bounded-context formalization — extract `tenancy` + `identity`, make `monitoring` + `topology` explicit

- **Status:** accepted
- **Date:** 2026-05-25
- **Phase:** 2

## Context

ADR-0008 set the structural timeline: Phase 1 keeps `monitoring/` and `topology/` as directory-based *candidate* boundaries with no cross-BC port surface, no `DomainEventDispatcher` wiring, and only the `import-linter` independence contract in force. Phase 2 is the phase that "formalizes the boundaries and introduces `tenancy/` and `identity/`" — gated by the three extraction triggers (ubiquitous-language conflict, independent lifecycle, plausibly-different ownership). ADR-0008 deferred this work *to* Phase 2 on purpose, and Phase-2 Plan A is the first genuinely cross-BC interaction (a tenant-scoped, membership-authorized read path). The promotion from "directory" to "bounded context" is now due, and it must be recorded as a decision rather than happening implicitly as code lands.

This ADR owns the Phase-2 *outcome* of that timeline: which candidates promote, which new contexts are extracted, and under which trigger. It does **not** re-argue the cross-BC mechanics — those are owned in full by ADR-0009 (top-level `use_cases/` for synchronous queries; in-process `DomainEventDispatcher` for state propagation; Kafka reserved for telemetry; BCs as enforced peers) — and it does not re-argue the gradual-adoption policy, which is ADR-0008's. It cites both and follows them.

## Decision

**Four bounded contexts are made explicit in Phase 2.**

- **`monitoring`** and **`topology`** are promoted from Phase-1 candidate directories to formal bounded contexts. The trigger is **ubiquitous-language conflict** (ADR-0008 D-2 #1): a *Line* in `monitoring` is a state-bearing thing (`RUNNING | IDLE | DOWN | CHANGEOVER`, OEE per window), whereas a *Line* in `topology` is a structural thing (a `Factory`'s child owning `Machine`s). Forcing one `Line` definition distorts one side; that is the strongest signal for a boundary.
- **`tenancy`** is **extracted** as a new BC (`Tenant`, `SchemaName` value object, onboarding outcomes). Trigger: **independent lifecycle** — tenant provisioning (schema DDL, hypertable, CAGG, registry) changes for entirely different reasons than line monitoring, and a `Tenant` is a cross-cutting concept no monitoring/topology rule owns.
- **`identity`** is **extracted** as a new BC (`User`, `Role`, `Permission`, `Membership`, pure `can(action, role) -> Allowed | Denied`). Trigger: **plausibly-different ownership** — authentication/authorization is a security concern with its own change cadence and its own (mental) owner, distinct from manufacturing-domain logic.

**Cross-BC interaction follows ADR-0009 unchanged.** (a) Synchronous cross-BC queries — the only one in Plan A is enterprise-OEE — live in top-level `src/sdf_api/use_cases/`, depending on multiple BCs' **ports only**, never their `domain/` or `adapters/`. (b) Cross-BC state propagation, when it appears, emits a `DomainEvent` value from core and is dispatched by the **hand-rolled** `DomainEventDispatcher` in `shared_kernel/events.py` — **in-process, not Kafka, not a bus library**. (d) The four BCs stay peers: the `import-linter` independence contract is extended to cover `tenancy` and `identity` and stays in force; no BC imports another BC's internals.

**Reconciliation note — ADR-0009's port path (recorded here, ADR-0009 is NOT edited).** ADR-0009's Decision (a) names each BC's port surface as `contexts/<bc>/ports.py` (a single module). That wording predates ADR-0022, which replaced the single-file convention with a **`contexts/<bc>/ports/<noun>.py` folder, file-per-feature** layout (one Port Protocol per file; per-BC `unit_of_work.py`; cross-cutting Ports under `shared_kernel/ports/<name>.py`). Wherever ADR-0009 says `ports.py`, read it as the ADR-0022 folder form. This note records the reconciliation **in ADR-0034**; per the supersede-don't-edit policy, ADR-0009 is left untouched and is not superseded — only its stale path spelling is reconciled forward to ADR-0022.

## Consequences

### Positive
- The Phase-2 BC set is committed against ADR-0008's triggers, so each boundary has a named justification rather than structural aesthetics.
- `tenancy` and `identity` arrive with the cross-BC machinery (ADR-0009) becoming operational exactly when the first cross-BC interaction lands — as ADR-0008 planned.
- Independence stays mechanically enforced: extending the `import-linter` contract to four BCs keeps them peers, so the new contexts cannot quietly couple to monitoring/topology.
- The ADR-0009 ↔ ADR-0022 path drift is resolved on the record without an in-place ADR edit, keeping the decision log append-only.

### Negative / Trade-offs
- Four BCs in one process is more port/UoW/fakes ceremony than Phase 1's two directories; each new BC expands the composition root with handler/adapter wiring (the cost ADR-0008 accepted for Phase 2).
- The `monitoring`/`topology` *Line* language split is now load-bearing: a future feature that needs one unified `Line` view must cross the boundary via a `use_cases/` query, not a direct import.
- Synchronous cross-BC dispatch means the enterprise-OEE handler-set must complete within the request timeout — fine at three tenants, revisited (per ADR-0009 migration path) only if the handler-set grows.

## Migration Path

Forward: further contexts (`quality`, `maintenance`) extract in Phase 4 under the same ADR-0008 triggers; each addition extends the independence contract and the composition root. Should a BC need to split to its own process, ADR-0009's migration path applies (swap the `DomainEventDispatcher` for a Kafka producer/consumer at the function-level handler interface) — this ADR does not change that.

Reversal: collapsing a Phase-2 BC back is now the *expensive* side of ADR-0008's asymmetry — cross-BC ports and (eventual) event handlers must be unwound. That cost is the deliberate consequence of formalizing the boundary now that a trigger has fired; it is not undertaken without a new superseding ADR.

## Sources

- [ADR-0008](0008-domain-modeling-evolution.md) — gradual BC adoption, the Phase-2 formalization timeline, and the three extraction triggers this ADR applies.
- [ADR-0009](0009-inter-context-communication.md) — cross-BC mechanics (top-level `use_cases/`, in-process `DomainEventDispatcher`, Kafka-reserved-for-telemetry, enforced peer independence); operational from Phase 2. **Not edited by this ADR.**
- [ADR-0022](0022-ports-as-folder-file-per-feature.md) — `contexts/<bc>/ports/<noun>.py` folder/file-per-feature layout that the reconciliation note maps ADR-0009's `ports.py` onto.
- Internal: `docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md` (Plan A scope: BC formalization + `tenancy`/`identity` extraction + cross-BC `use_cases/` + `DomainEventDispatcher`); `docs/spec/GLOSSARY.md` — "Bounded Context (BC)" entry.
