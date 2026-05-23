# ADR-0009: Inter-context communication — top-level use cases + in-process domain event dispatcher

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1 (decision lands now); 2 (first cross-BC code lands when `tenancy/` and `identity/` are introduced)

## Context

Spec §2.2 sets BC evolution by phase: Phase 1 has informal separation (`monitoring/`, `topology/`); Phase 2 adds `tenancy/`, `identity/`; Phase 4 adds `quality/` or `maintenance/`. By Phase 4 the codebase will have 4–5 BCs in one process.

Cross-BC interaction comes in two distinct shapes, and they need different mechanisms:

- **(a) Synchronous queries** — "give me line state + machine metadata for a single HTTP response." Requires reading from two BCs' read models *now*. Events cannot answer this without an upstream CQRS read model.
- **(b) State propagation** — "monitoring detected line went down; quality plan should react." Naturally asynchronous, decoupled.

Conflating these onto one mechanism is the most common mistake. Picking "events for everything" produces unmaintainable CQRS-lite hacks for trivial joins; picking "ports for everything" creates directional BC coupling that the project's `import-linter` `independence` contract explicitly forbids.

Forces specific to this project:

- Kafka is already in the stack (telemetry pipeline). Tempting to use it for domain events too — but telemetry messages and domain events are at *different abstraction layers* (integration vs intra-app), and bundling them onto one broker requires topic/payload-namespace discipline and an extra integration-test surface per Kafka domain event.
- All BCs live in one Python process (`api-python`) for Phase 1~4 per spec §3.
- 2~5 BC scale is too small to justify infrastructure (in-memory bus library, Kafka topics, outbox tables) for cross-BC propagation.

## Decision

**(a) Cross-BC synchronous queries live in `src/sdf_api/use_cases/`**, a top-level directory outside any BC. Each BC exposes ports (`contexts/<bc>/ports.py`); cross-BC use cases depend on multiple BCs' ports only, never their `domain/` or `adapters/`. BC-local use cases continue to live in `contexts/<bc>/application/` and may not import any other BC.

**(b) Cross-BC state propagation uses an in-process `DomainEventDispatcher`** defined in `shared_kernel/events.py`. Core (`domain/`) returns domain events as values (part of a sum-type return); shell calls `dispatcher.dispatch(event)` after IO succeeds. Handlers register at composition time. Handler exceptions propagate (fail-fast); the dispatcher does not catch.

**(c) Kafka is not used for domain events.** It remains reserved for the telemetry pipeline.

**(d) BCs stay peers.** `import-linter` `independence` contract between `monitoring`, `topology`, `tenancy`, `identity`, etc. stays in force. BCs never import each other.

## Consequences

### Positive
- BCs remain peers; no directional coupling.
- Cross-BC use cases are greppable in one place (`use_cases/`).
- Domain event dispatch is in-process — same stack trace, same async context, same DB transaction when wanted.
- Zero new infrastructure dependency for domain events. Phase 1 demo footprint unchanged.
- Fail-fast policy surfaces inconsistency immediately; silent best-effort behavior would diverge from apparent control flow.
- Migration to Kafka is local (swap `DomainEventDispatcher` implementation) when BCs split to separate services.

### Negative / Trade-offs
- `use_cases/` directory must be disciplined — only cross-BC use cases. A BC-local use case landing there is the leading smell to watch for.
- Adding a new BC means expanding the composition root with handler registrations.
- Synchronous dispatch means the total handler-set per event must complete within the HTTP request timeout (Phase 1: not an issue; Phase 3 may need outbox if handler-set grows).
- An in-process crash mid-dispatch loses unprocessed handlers' work. Acceptable for Phase 1~4; ADR superseded if durability becomes load-bearing.

## Migration Path

Three triggers and their responses:

1. **BCs split to separate processes/services.** `DomainEventDispatcher.dispatch` becomes a Kafka producer; consumer side is a Kafka consumer that invokes the same handler functions. The function-level interface (`async def handle(event: T)`) does not change.
2. **Need for durability (handler must survive process crash).** Introduce an outbox pattern: dispatcher writes event row to Postgres in the same transaction as state change; background worker drains and dispatches. No Kafka required if BCs remain in-process.
3. **Handler-set too large for synchronous dispatch.** Either move to asyncio task spawn (in-process async) or to outbox + background worker.

## Sources

- Eric Evans, *Domain-Driven Design* (2003) — Context Mapping (Open Host Service, Shared Kernel, Customer-Supplier).
- Vaughn Vernon, *Implementing Domain-Driven Design* (Addison-Wesley 2013) — Application Service patterns + Domain Event implementation.
- Harry Percival & Bob Gregory, *Architecture Patterns with Python* (O'Reilly 2020) — chapters on services, events, and the trade-offs between in-process and broker-based dispatch.
- "Outbox Pattern" — Chris Richardson, microservices.io. https://microservices.io/patterns/data/transactional-outbox.html
- Internal: `docs/architecture/2026-05-23-code-architecture.md` §3, `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2.2.
