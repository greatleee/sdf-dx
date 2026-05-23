# ADR-0011: Sparkplug B topic namespace

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

The edge BC ingests machine telemetry over MQTT using Sparkplug B. ADR-0005 commits this repo to contract-first inter-service schemas and names the vendored Eclipse Tahu Sparkplug B `.proto` (`packages/contracts/sparkplug/*.proto`) as the contract source of truth for the Edge↔Bus surface. What ADR-0005 does *not* fix is the **topic namespace** — the string structure under which Sparkplug messages are published and how this project's domain concepts (*Factory*, *Line*, *Machine* from the topology BC; *Edge Node*, *Device* from the edge BC) map onto Sparkplug's `group_id` / `edge_node_id` / `device_id` levels.

That mapping is a load-bearing decision known at planning time: every Edge publisher, the MQTT-to-Kafka bridge's subscription pattern, and the downstream Kafka topic names all depend on it. Getting it wrong later means re-flashing topic strings across publishers and re-subscribing the bridge. It belongs in Chapter 0.

The Sparkplug B specification (v3.0, Eclipse Foundation) fixes the topic grammar; what remains is the *domain mapping* and which optional levels Phase 1 uses. The Phase 1 fleet is small and flat: one implicit tenant, a handful of *Lines*, five *Machines* per *Line* (`press`, `weld`, `paint`, `inspect`, `pack` per GLOSSARY `topology`). That shape drives the simplifications below.

## Decision

### D-1. Topic shape

Topics follow the Sparkplug B v3.0 namespace grammar:

```
spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]
```

`spBv1.0` is the fixed Sparkplug B namespace token. The `device_id` level is optional and present only on Device-level (`D*`) messages.

### D-2. Phase 1 domain mapping

- **`group_id` = `sdf_default`** — the single implicit tenant of Phase 1 (GLOSSARY `shared` → *Tenant*: "exactly one implicit tenant `sdf_default`"). Phase 2 schema-per-tenant onboarding turns this into a per-tenant group.
- **`edge_node_id` = `<line slug>`** — one *Edge Node* per *Line*, so **`edge_node_id == line_id`** (GLOSSARY `edge` → *Edge Node*: "one Edge Node per Line").
- **Device level UNUSED.** The five *Machines* of a *Line* are **not** modeled as separate Sparkplug *Devices*. They are addressed via **compound metric names** within the Edge Node's payload (e.g., a metric named `press/run_state`, `weld/cycle_count`), not by a `device_id` topic segment. This is the simplification GLOSSARY `edge` → *Device* already records ("Machines are addressed as compound metric names rather than separate Sparkplug Devices (see ADR-0011)").

### D-3. Message types covered

Node-level (no `device_id`):

- **NBIRTH** — published on Edge Node connect; carries the full metric definition set and resets the sequence number to 0.
- **NDATA** — per data update; carries metric value changes.
- **NDEATH** — registered as the MQTT Last-Will-and-Testament; published by the broker when the Edge Node disconnects ungracefully.

Device-level (`D*` variants — **defined by the spec, unused in Phase 1** per D-2): **DBIRTH / DDATA / DDEATH.** Listed for completeness; no Phase 1 publisher emits them.

Command and state:

- **NCMD / DCMD** — Host → Edge command messages (node / device scope). Phase 1 uses NCMD only, and only to request a *Rebirth*.
- **STATE** — the Sparkplug Host (primary application) birth/death message announcing Host online/offline, on `spBv1.0/STATE/<host_id>` (its own retained topic outside the per-node structure).

### D-4. Sequence number and Rebirth

Every Sparkplug message carries an **8-bit sequence number (`seq`) in `0..255` that wraps** (GLOSSARY `edge` → *Sequence number*). NBIRTH resets `seq` to 0; each subsequent message on that Edge Node increments it. A **gap** in the received sequence implies message loss → the consumer requests a **Rebirth** (NCMD with the `Node Control/Rebirth` metric set), which makes the Edge re-issue NBIRTH (GLOSSARY `edge` → *Rebirth*). This is the spec's stateful-recovery mechanism and the reason NBIRTH carries the full metric set, not a delta.

### D-5. Downstream Kafka topic naming

After the MQTT-to-Kafka bridge normalizes Sparkplug payloads (validated against the Kafka JSON Schema per ADR-0005), they land on Kafka topics named:

```
sdf.{tenant}.machine.{type}
```

with `{tenant}` = `sdf_default` in Phase 1. The Sparkplug topic namespace is an edge-BC concern; the Kafka topic namespace is the telemetry-pipeline concern downstream of the bridge — the two are deliberately distinct shapes.

### D-6. Relationship to ADR-0005

This ADR **instantiates** ADR-0005's commitment that the vendored Eclipse Tahu Sparkplug B `.proto` is the contract SoT: the message *payloads* (NBIRTH/NDATA/etc. bodies) are the generated Protobuf types from that `.proto`; this ADR fixes only the *topic string* that carries them and the *domain mapping* of the topic levels. The `.proto` is not re-authored here.

## Consequences

### Positive
- The topic-to-domain mapping is fixed before any Edge publisher or bridge code is written — no later re-flashing of topic strings.
- Compound-metric-naming for Machines keeps the Phase 1 fleet flat: one Edge Node per Line, no Device-level birth/death lifecycle to manage for five machines each.
- `edge_node_id == line_id` makes the bridge's routing trivial — the topic segment *is* the join key to the topology BC's *Line*.
- Wording is consistent with the GLOSSARY `edge` entries (Edge Node, Device, NBIRTH/NDEATH/NDATA, Rebirth, Sequence number) and the `shared` *Sparkplug Topic Namespace* entry, so code identifiers and spec prose do not drift.

### Negative / Trade-offs
- Compound metric names move the per-Machine structure *out of the topic tree and into the payload*. A consumer cannot subscribe to a single Machine via an MQTT topic filter; it receives the whole Edge Node's NDATA and demultiplexes by metric-name prefix. Acceptable at five machines per line; revisited in Migration below.
- No per-Device retained NBIRTH/NDEATH means there is no Sparkplug-native per-Machine "last known good" birth state — Machine-level liveness is derived from the Line's Edge Node state plus metric staleness, not from a Device death message.
- `group_id = sdf_default` hard-codes single-tenancy at the topic level for Phase 1; Phase 2 multi-tenancy must rewrite the group segment across publishers and bridge subscriptions.

## Migration Path

Forward: when **per-Device granularity is needed** — e.g., independent per-Machine liveness via retained DBIRTH/DDEATH, or per-Machine MQTT topic filtering — split the namespace to use the `<edge_node_id>/<device_id>` level (`device_id` = machine key) and update the bridge's subscription pattern from the node-level filter (`spBv1.0/sdf_default/+/<edge>`) to include the device level (`spBv1.0/sdf_default/+/<edge>/+`). The Edge publishers begin emitting `D*` messages per Machine. This is additive to the spec grammar already adopted in D-1.

Forward (multi-tenancy): Phase 2 replaces `group_id = sdf_default` with a per-tenant group, in lockstep with ADR-0003 schema-per-tenant onboarding.

Reversal is not meaningful — Sparkplug B is the chosen edge protocol (design spec §15); abandoning the namespace would mean abandoning Sparkplug, a protocol-level decision out of scope here.

## Sources

- Sparkplug Specification v3.0.0 (Eclipse Foundation, 2023) — §5 (operational behavior: sequence numbers, BIRTH/DEATH/DATA, Rebirth) and §6 (topic namespace, `spBv1.0/group_id/message_type/edge_node_id/[device_id]`) — https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification-3.0.0.pdf
- Eclipse Tahu (Sparkplug reference implementation and `.proto`) — https://github.com/eclipse-sparkplug/sparkplug
- Internal: `docs/ADR/0005-contract-first-llm-drift.md` (Sparkplug B `.proto` as contract SoT — this ADR instantiates that commitment), `docs/spec/GLOSSARY.md` (`edge` BC entries + `shared` → *Sparkplug Topic Namespace*); design spec §15 (`docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`).
