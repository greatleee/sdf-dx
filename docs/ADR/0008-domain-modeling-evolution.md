# ADR-0008: Domain modeling evolution (directory-based → bounded contexts)

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1 (decision lands now); 2 (bounded contexts formalized)

## Context

Bounded contexts are the right destination, but adopting them all at once early is a known failure mode. With one developer and a domain still being learned (line monitoring, topology, OEE per ISO 22400, Sparkplug B), the context boundaries are not yet known with enough confidence to pour concrete around them. Premature BC ceremony — per-BC ports, cross-BC events, an independence contract — turns a guess about boundaries into a structure that is expensive to undo once code depends on it.

Spec §2.2 already lays out the phasing: Phase 1 has intuitive separation (`monitoring/`, `topology/`); Phase 2 makes BC boundaries explicit and adds `tenancy/` and `identity/`; Phase 4 may add `quality/` or `maintenance/`. It also names the BC-extraction triggers. What spec §2.2 does *not* do is record this as a decision at ADR status, with the triggers stated as a checklist and the structural timeline pinned.

This ADR owns exactly that: the structural-evolution timeline and the extraction triggers. It does **not** re-argue cross-BC communication. The mechanics — cross-BC synchronous queries as top-level use cases in `src/sdf_api/use_cases/`, cross-BC state propagation via an in-process `DomainEventDispatcher`, and BC peer-independence enforced by the `import-linter` independence contract — are owned in full by [ADR-0009](0009-inter-context-communication.md). The pure-core shape each context is modeled in (functional core / imperative shell) is owned by [ADR-0004](0004-functional-core-imperative-shell.md). The "Bounded Context" concept itself is defined in the project [`GLOSSARY`](../spec/GLOSSARY.md).

(Note: spec §2.2 lists "도메인 이벤트(Kafka)" among cross-BC mechanisms; that line is superseded by ADR-0009, which keeps domain events in-process and reserves Kafka for telemetry. This ADR follows ADR-0009.)

## Decision

### D-1 — Bounded contexts are adopted gradually, not up front

The structural timeline:

- **Phase 1 — directory-based separation, no full BC ceremony.** `contexts/monitoring/` and `contexts/topology/` separate the model by directory. They follow the FC/IS layering of ADR-0004 internally, but there is no cross-BC port surface, no `DomainEventDispatcher` wiring, and the independence contract is the only BC-level rule in force. The separation is a hypothesis about boundaries, kept cheap so it stays cheap to revise.
- **Phase 2 — explicit BC boundaries.** The boundaries are formalized and two new contexts are introduced: `tenancy/` and `identity/`. This is the phase where the ADR-0009 cross-BC mechanics become operational, because Phase 2 is when the first genuinely cross-BC interaction lands.
- **Phase 4 — further contexts as the domain demands.** `quality/` or `maintenance/` may be extracted.

A directory under `contexts/` in Phase 1 is therefore a *candidate* BC, not yet a fully ceremonied one. The promotion from "directory" to "bounded context with explicit boundary" happens in Phase 2, gated by the triggers below.

### D-2 — A candidate is extracted into its own bounded context only when a trigger fires

Three triggers. A boundary is justified when one or more clearly applies — not by structural aesthetics:

1. **Ubiquitous-language conflict.** The same word means different things in two parts of the model (e.g., a "line" in monitoring vs. a "line" in topology), and forcing one definition distorts at least one side. A genuine language clash is the strongest signal for a boundary.
2. **Independent lifecycle.** The two parts change for different reasons and on different cadences — one can be deployed, versioned, or rewritten without dragging the other along.
3. **Plausibly different team ownership.** It is realistic that a different team (or, here, a different mental mode) would own each part. Conway's-law alignment: the boundary tracks who would own what.

When none of the three applies, the parts stay in one context (or one directory) regardless of how tempting a split looks structurally.

## Consequences

### Positive
- Boundaries are committed only once evidence (a fired trigger) exists, so the BC structure reflects learned domain reality rather than an early guess.
- Phase 1 stays light: two directories and one independence contract, no port/event ceremony to maintain before there is cross-BC interaction to justify it.
- The triggers give a reviewable test for "should this be its own BC?" — the answer is a checklist, not taste.
- Aligns with ADR-0009's phasing: the cross-BC machinery is defined now but only wired when Phase 2 actually needs it.

### Negative / Trade-offs
- Directory-based separation without full ceremony can tempt a Phase 1 cross-directory import that a formal BC would forbid. The independence contract is in force precisely to prevent this; the gap between "directory" and "fully ceremonied BC" must be watched in review.
- Deferring boundary decisions means some refactoring at Phase 2 when boundaries are formalized — the cost of learning the domain before committing. This is the intended trade (cheap-to-revise now vs. expensive-to-undo later).
- Three triggers are judgment calls, not mechanical checks. Two reasonable people can disagree on whether a language conflict is "genuine." Review absorbs this.

## Migration Path

Forward: in Phase 2, evaluate each Phase 1 directory against the three triggers, formalize the boundaries that pass, and introduce `tenancy/` and `identity/`. Wiring the cross-BC mechanics at that point is ADR-0009's migration path, not this one's.

Reversal is asymmetric, and that asymmetry is the whole point of phasing:

- **While separation is directory-only (Phase 1):** over-separation is cheap to undo — collapse two directories back into one *before any code depends on the split*. No ports or events exist to unwind.
- **Once cross-BC ports/events exist (Phase 2+):** the cost rises sharply. Collapsing a real BC means unwinding its port surface and event handlers. This is why the directory-only stage exists: to keep reversal cheap until a trigger justifies paying the higher price.

## Sources

- Eric Evans, *Domain-Driven Design* (Addison-Wesley 2003) — Bounded Context and Context Mapping. https://www.domainlanguage.com/ddd/
- Vaughn Vernon, *Implementing Domain-Driven Design* (Addison-Wesley 2013) — strategic design and identifying context boundaries.
- Internal: `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2.2 (phase timeline + the three triggers) and §12 (ADR roadmap); [ADR-0009](0009-inter-context-communication.md) (cross-BC mechanics, operational at Phase 2); [ADR-0004](0004-functional-core-imperative-shell.md) (FC/IS shape of each context); [`GLOSSARY`](../spec/GLOSSARY.md) — "Bounded Context (BC)" entry.
