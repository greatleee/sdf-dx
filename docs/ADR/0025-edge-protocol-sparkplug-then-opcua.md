# ADR-0025: Edge telemetry protocol — Sparkplug B in Phase 1, OPC UA deferred to Phase 4

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

The edge BC ingests machine telemetry. Two industrial protocols dominate the field: **OPC UA** (OPC Foundation) and **MQTT Sparkplug B** (Eclipse Foundation). The design spec lists both as domain sources (§15) and earmarks *OPC UA for Machinery* as a Phase 4 candidate (`DOMAIN-NOTES.md`), while Phase 1 already commits to Sparkplug B — ADR-0005 names the vendored Eclipse Tahu `.proto` as the Edge↔Bus contract SoT, and ADR-0011 fixes its topic namespace.

But the *protocol-selection* decision itself — why Sparkplug B carries Phase 1 and OPC UA waits until Phase 4 — was never recorded. ADR-0011 explicitly declared it "a protocol-level decision out of scope here" and deferred to design spec §15; on inspection §15 is only a sources bibliography (it lists both protocols with no selection rationale). The deferral therefore lands on a non-decision. This ADR fills that gap. Per the Chapter 0 rule (`phase-iteration.md`: one ADR per load-bearing decision known at planning time), the edge protocol qualifies — every Edge publisher, the Sparkplug→Kafka bridge, and downstream Kafka topics depend on it.

One misframing must be ruled out first: Sparkplug B is **not** "a lightweight alternative to OPC UA." The two solve different problems and are routinely deployed together — OPC UA **southbound** (machine → edge gateway: semantically rich, self-describing, typed device data) and Sparkplug B / MQTT **northbound** (edge → bus / Unified Namespace: decoupled pub/sub transport). The industry shorthand is *"OPC UA organizes the data; MQTT moves it."* The real selection question is therefore *which job each phase needs*, not *which protocol is better*.

## Decision

### D-1. Phase 1 uses Sparkplug B for the northbound edge→bus transport.

Phase 1's job is to move telemetry from a *simulated* fleet (S-SIM, Kotlin) to the Kafka pipeline — a northbound transport problem. Sparkplug B / MQTT is the right-sized tool for it irrespective of weight: pub/sub decoupling (publishers and the bridge never address each other directly), report-by-exception, and a built-in birth/death + sequence-number state model for liveness and loss detection (ADR-0011 D-3/D-4). Because the fleet is simulated, there is no real PLC address space to browse — OPC UA's distinguishing capability has nothing to act on in Phase 1.

### D-2. OPC UA is deferred to Phase 4, as an additive southbound semantic layer — not a replacement.

OPC UA's value — typed information modeling, companion specs (OPC UA for Machinery, OPC 40001-1), self-describing device semantics, integrated security — materialises only when (a) there are devices worth modeling semantically and (b) that semantic richness is itself the deliverable. Both are Phase 4 concerns (richer equipment modeling; predictive-maintenance inference integration per design spec §16). Introducing OPC UA in Phase 4 is therefore *additive*: it slots in southbound (device / gateway), feeding the same Sparkplug B northbound spine — not a rewrite of Phase 1.

### D-3. Phasing rationale: pay for weight when its benefit appears, not before.

The portfolio ramps complexity by phase — lightweight, high-leverage capabilities first; heavier, semantically richer ones as the model deepens. OPC UA's setup cost is real and documented: mandatory certificate-based authentication with negotiated security policies, an address space / information model to author, and client/server stacks measured in megabytes rather than kilobytes, versus MQTT/Sparkplug's lightweight pub/sub. But cost is **not** the load-bearing reason to defer — **benefit timing** is. Paying OPC UA's setup cost in Phase 1 buys nothing, because a simulated fleet has no semantic device model for it to expose; the same cost in Phase 4 buys exactly the semantic device layer that phase is about. (Setup complexity is thus a *supporting* point only: a reviewer who observes "MQTT also needs TLS, and OPC UA has simulators/SDKs" is correct, and that observation does not weaken D-1/D-2.)

## Consequences

### Positive
- The Phase-1-vs-Phase-4 protocol weighting now has a recorded rationale; the question ADR-0011 deferred is answered.
- The complementary north/southbound framing keeps the Phase 4 OPC UA introduction additive — the Sparkplug spine persists, no Phase 1 rework.
- Matches the documented industry pattern (OPC UA at the equipment, Sparkplug B for site-wide telemetry / UNS), so the choice reads as deliberate rather than arbitrary.

### Negative / Trade-offs
- Phase 1 has no semantically self-describing device model; metric meaning lives in convention (compound metric names, ADR-0011 D-2) and the Kafka JSON Schema (ADR-0005), not in an OPC UA address space. Acceptable for a simulated fleet; revisited when OPC UA lands.
- The portfolio shows no real OPC UA integration until Phase 4 (if reached). For an automotive plant — where OPC UA is the dominant field standard — this is an explicit, declared scope choice (`KNOWN-UNKNOWNS.md` scope section), not an oversight.
- Sparkplug B and OPC UA increasingly overlap (OPC UA PubSub over MQTT exists); the clean north/south split is a modeling simplification, not a hard industry boundary.

## Migration Path

Forward (Phase 4): add an OPC UA southbound path — an OPC UA server (or simulator) exposing devices per OPC UA for Machinery (OPC 40001-1 + DI / OPC 10000-100), consumed by an edge gateway that continues to publish Sparkplug B northbound. The Phase 1 transport contract (ADR-0005 / ADR-0011) is unaffected.

Reversal: choosing OPC UA *instead* of Sparkplug B for the Phase 1 northbound would abandon ADR-0005's Tahu `.proto` contract SoT and ADR-0011's namespace, and would impose OPC UA's setup cost with no Phase 1 benefit. Explicitly rejected here.

## Sources

- [A Comparison of OPC UA and MQTT Sparkplug — HiveMQ](https://www.hivemq.com/resources/iiot-protocols-opc-ua-mqtt-sparkplug-comparison/)
- [A Comparison of IIoT Protocols: MQTT Sparkplug vs OPC-UA — EMQ](https://www.emqx.com/en/blog/a-comparison-of-iiot-protocols-mqtt-sparkplug-vs-opc-ua)
- [OPC UA vs. MQTT Sparkplug: When to Use Which in Brownfield Plants — Artisan](https://www.artisantec.io/post/opc-ua-vs-mqtt-sparkplug-when-to-use-which-in-brownfield-plants)
- [OPC-UA and MQTT Data Architecture for Smart Factories — iFactory](https://ifactoryapp.com/greenfield-consulting/opc-ua-mqtt-data-architecture-smart-factory)
- Internal: design spec §15 (Domain Sources) + §16 (Non-Goals); `DOMAIN-NOTES.md` (OPC UA for Machinery = Phase 4 candidate); ADR-0005 (Sparkplug `.proto` as contract SoT); ADR-0011 (Sparkplug topic namespace — deferred this selection); `KNOWN-UNKNOWNS.md` (SDF scope section).
