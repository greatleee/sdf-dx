# ADR-0001: Polyglot architecture (Python + Kotlin)

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

Design spec §3.2 identifies the architectural split: Kotlin handles OT/protocol-adapter work (OPC UA, MQTT, Sparkplug B); Python owns domain logic, API, and stream ingestion; TypeScript/React owns the dashboard. This ADR records the load-bearing rationale so the polyglot choice is not re-litigated per session.

The core force is the industrial-protocol library ecosystem. JVM has three mature, production-grade libraries covering the full OT communication surface:

- **Eclipse Milo** — OPC UA client/server SDK, the de facto JVM implementation.
- **Eclipse Paho** — MQTT client, the reference implementation used across industrial vendors.
- **Eclipse Tahu** — Sparkplug B reference implementation (originates at Cirrus Link, now Eclipse).

Python equivalents exist but are fragmented and immature. `asyncua` covers OPC UA adequately for polling but lacks the depth of Milo's session management and subscription model; there is no production-equivalent Sparkplug B Python library. Choosing Python for the OT layer would mean either accepting library risk or hand-rolling protocol logic — neither is acceptable when the JVM alternative is the industry standard.

Python is chosen for domain logic and API for complementary reasons: OEE formulas and ISA-95 data models map cleanly onto Python dataclasses and Pydantic (at the boundary); rapid product polish is straightforward; and the author's senior judgment is most demonstrable in a familiar stack. The "AI-augmented senior judgment" thesis — the portfolio's headline signal — is shown in the domain and API tier where modelling decisions are dense and reviewable, not in the protocol adapter.

The split mirrors real industrial system structure: OT adapters in JVM/native (the Ignition Gateway, AVEVA OPC-DA bridge, Siemens SIMATIC pattern) versus application and analytics in Python/Node.

Phase 1 language allocation:
- **Kotlin**: `ot-gateway`, `device-simulator`, `sparkplug-bridge`
- **Python**: `ingest` (stream processor), `api` (domain + BFF)
- **TypeScript/React**: `dashboard`

The polyglot consumer set — Kotlin gateways, Python ingest, TypeScript frontend — is what makes ADR-0005's schema-first contract direction load-bearing. Without a committed schema as SoT, each language boundary becomes a hallucination surface for generated code. ADR-0005 exists precisely because this polyglot configuration requires it.

## Decision

Phase 1 is a polyglot monorepo. Kotlin is confined to the OT/protocol-adapter role (`ot-gateway`, `device-simulator`, `sparkplug-bridge`). Python owns domain logic and the API tier. TypeScript/React owns the dashboard. Language allocation does not change within Phase 1.

Cross-language contracts are governed by ADR-0005 (OpenAPI 3.1, Sparkplug B Protobuf, JSON Schema as SoT — codegen, never hand-written, at every language boundary).

## Consequences

### Positive

- JVM's mature industrial-protocol library ecosystem is used where it is load-bearing, and nowhere else.
- Domain logic and API stay in Python, where senior judgment is most legible to interviewers and where the FC/IS + contract-first discipline (ADR-0004, ADR-0005) is most fully expressed.
- The monorepo lets a single PR span OT adapter + ingest + API + dashboard changes — interview walkthrough and cross-language traceability are both served.
- Real industrial system structure is mirrored, not invented: OT adapter in JVM, application in Python/Node is the pattern at Ignition, AVEVA, and Siemens.
- Portfolio signal: `git log` shows Kotlin gateway commit → Python domain commit → TypeScript dashboard commit with OpenAPI contract commit between them.

### Negative / Trade-offs

- Two JVMs and one Python interpreter in local dev raises the minimum machine spec and compose-up time. Mitigation: Kotlin services are thin adapters; their container images are small.
- Contributors need JVM familiarity to touch the gateway layer. For Phase 1 this is the author only; no hiring concern yet.
- Kotlin `build.gradle.kts` + Gradle wrapper add toolchain surface. A missing JDK 21 silently breaks the Kotlin build.
- The polyglot split is a structural bet: if Eclipse Milo / Paho / Tahu are the wrong protocol libraries, the Kotlin layer must be replaced. Assessed as low risk — Eclipse Foundation stewardship + broad industrial adoption.

## Migration Path

If the Python industrial-protocol ecosystem matures to production-grade parity (specifically: a stable, maintained Sparkplug B SDK and a Milo-equivalent OPC UA library), the Kotlin layer could shrink toward zero. Exit cost: replace three Kotlin services with Python equivalents, update `packages/contracts/sparkplug/*.proto` generators. No domain code changes required. Estimated effort: 2–4 weeks depending on OPC UA subscription model complexity.

## Sources

- [Eclipse Milo — OPC UA SDK for Java/Kotlin](https://github.com/eclipse/milo)
- [Eclipse Paho — MQTT client for Java](https://github.com/eclipse/paho.mqtt.java)
- [Eclipse Tahu — Sparkplug B reference implementation](https://github.com/eclipse/tahu)
- [Pydantic v2 — Python data validation](https://docs.pydantic.dev/latest/)
- Internal — design spec §3.1, §3.2 (`docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`); ADR-0004 (Functional Core / Imperative Shell); ADR-0005 (contract-first inter-service schemas).
