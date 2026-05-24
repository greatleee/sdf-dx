# ADR-0036: `MachineKind` — automotive five-shop taxonomy

- **Status:** accepted
- **Date:** 2026-05-25
- **Phase:** 2

## Context

Phase 1 modeled a `Machine`'s kind with a generic placeholder set — `press / weld / paint / inspect / pack` (`MachineKind` in `topology/domain/machine.py`, the `MACHINE_TYPES` list in the Kotlin simulator, and the `<type>` segment of the seed `sparkplug_node_id` `sdf_default/line-a/<type>`). That set was chosen as a plausible five-station line shape, not as a faithful model of an automotive plant. Phase 2's whole point is three *realistic* automotive tenants (Ulsan / HMGMA / Chennai) each running a full vehicle assembly line, so the placeholder taxonomy now reads as inaccurate against the domain the project claims to model.

A real automotive general-assembly plant is conventionally organized into a fixed sequence of *shops*: **stamping → body (body-in-white / weld) → paint → general assembly → inspection**. This is the standard plant-floor decomposition for vehicle manufacturing, and grounding `MachineKind` on it makes the simulated line legible to anyone who knows the domain. The refinement is therefore a domain-correctness fix, not a feature.

The key constraint is the cost surface. `machineKey` is a **free-form string** in the Kafka payload contract (`packages/contracts/kafka-payloads/machine_telemetry.schema.json`) — the wire never enumerated the five station names. The taxonomy lives only in the *domain* (Python `topology` + the Kotlin edge), the simulator's machine list, the seed data, and `GLOSSARY`/`DOMAIN-NOTES`. So refining the set touches no schema enum, triggers no codegen, and keeps the contract drift gate green (~0 contract churn).

## Decision

**`MachineKind` is refined to the automotive five-shop taxonomy: `stamping`, `body`, `paint`, `assembly`, `inspection`.** This replaces the Phase-1 placeholder set `press / weld / paint / inspect / pack`. The enum members map to the conventional plant-floor shop sequence (stamping → body → paint → general assembly → inspection).

**`machineKey` stays a free string in the Kafka contract.** `machine_telemetry.schema.json` is **not** changed — no enum, no `oneOf`, no codegen regeneration, no new contract commit. The taxonomy is a **domain-layer** concept only: the `MachineKind` `StrEnum` in `topology/domain/machine.py` (Python) and the corresponding edge-side machine list (Kotlin). The wire contract continues to carry `machineKey` as an opaque string; mapping that string to a `MachineKind` is a domain concern, and an unrecognized key is a domain-side decision, not a schema-validation failure.

**Three call sites change in lockstep with the enum** — because they must agree on the same five identifiers or the edge↔ingest↔domain join breaks:

1. **Seed `machineKey`s** — the seeded `machine` rows' kind/key values use the five-shop names.
2. **Simulator machine list** — the Kotlin `MACHINE_TYPES` list emits the five-shop set.
3. **The `<type>` segment of `sparkplug_node_id`** — the `<type>` token (today `sdf_default/line-a/<type>`) uses the five-shop names, kept identical to the simulator's emitted keys and the seed rows so the machine resolver's `{lineId}/{machineKey}` lookup still resolves.

These three move together with the domain enum in one taxonomy change; none of them is a contract-schema change.

## Consequences

### Positive
- The simulated line now matches the real automotive plant decomposition (stamping → body → paint → assembly → inspection), so the demo is legible to a domain reader and consistent with `GLOSSARY`/`DOMAIN-NOTES`.
- Zero contract churn: no `machine_telemetry.schema.json` edit, no codegen, the drift and `oasdiff` gates stay green. The free-string `machineKey` decision (ADR-0005/ADR-0011 wire shape) is what buys this.
- The taxonomy is owned in exactly one place per language (Python domain enum, Kotlin edge list), and the wire stays decoupled from it — adding or renaming a shop later is a domain + seed + simulator change, never a contract migration.

### Negative / Trade-offs
- A free-string `machineKey` means a typo or an unknown shop name is *not* caught by schema validation at the wire — it surfaces only when the domain maps the key, so the edge/seed/`sparkplug_node_id`/domain agreement is a discipline the lockstep change must hold (and tests must assert parity across the simulator list and the enum).
- The five-shop set is still a deliberate abstraction of any specific real plant (e.g., sub-shops, sub-assembly, logistics are collapsed). Differentiation between the three tenants is by operational scenario, not by a different shop taxonomy — recorded honestly in `KNOWN-UNKNOWNS` as a simplification, not a claim of plant-level fidelity.

## Migration Path

Forward: if a later phase needs the taxonomy enforced at the wire (e.g., a consumer must reject unknown shops at parse time), promote `machineKey` from a free string to a constrained enum in `machine_telemetry.schema.json` — a contract change under contract-first (ADR-0005): edit the schema first, regenerate, then wire. That is a deliberate future decision, explicitly out of Phase-2 scope (the scope doc lists "new `MachineKind`/Sparkplug *enum* constraints" as a non-goal).

Reversal: reverting to the placeholder set would re-introduce the domain inaccuracy and is not contemplated; a future taxonomy revision supersedes this ADR rather than reverting it, and (being domain-only) is again a domain + seed + simulator change with no contract impact.

## Sources

- [ADR-0011](0011-sparkplug-namespace.md) — Sparkplug topic/namespace and the Kafka downstream shape; the per-Machine kind rides as a compound metric name / `machineKey`, not a topic segment, which is why the kind set is a free string on the wire.
- [ADR-0005](0005-contract-first-llm-drift.md) — contract-first direction: a wire enum change would require editing the schema first and regenerating; keeping `machineKey` free-string is what makes this taxonomy a zero-contract-churn domain change.
- Automotive general-assembly plant organization — vehicle plants are conventionally decomposed into stamping → body/weld → paint → general-assembly → inspection shops (standard manufacturing-floor sequence; grounds the five-shop choice).
- Internal: `docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md` (MachineKind 5-shop refinement; `machineKey` stays free string ⇒ ~0 contract churn); `docs/spec/GLOSSARY.md` (`topology` → *Machine* examples updated to the five-shop set); `apps/api-python/src/sdf_api/contexts/topology/domain/machine.py` (`MachineKind` enum).
