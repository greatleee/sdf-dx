# Glossary — Ubiquitous Language

Domain vocabulary used in code, specs, and conversation. Each term is scoped to a *Bounded Context*. The same word may legitimately mean different things across BCs — that is intentional, and each scope gets its own entry.

## How to use this

- **Code**: identifier names must match a term verbatim, modulo language convention (snake_case for Python columns/vars, PascalCase for types).
- **Specs**: use-case bodies, ADRs, and AI-WORKFLOW notes refer to terms exactly as defined here. No synonyms outside the *Synonyms / external aliases* block.
- **Conversation / demos**: ground claims in these terms. Don't pick up vendor jargon mid-stream.

## Adding a term

1. Encounter a new domain noun/verb in a UC, ADR, or PR discussion → add the entry *before* merging the change that uses it.
2. Same word, different meaning in a *different* BC → add a **separate** entry under that BC. Cross-link both with "*See also:* ...".
3. Standard / vendor uses a different word for the same thing → list under *Synonyms / external aliases* (and prefer **our** word in code/specs).

## Conventions

- BC scopes (Phase 1): `monitoring`, `topology`, `edge`, `shared`. Phase 2+ adds `tenancy`, `identity`. Phase 4+ may add `quality` or `maintenance`.
- Status: `accepted` (use freely) | `proposed` (still soft, may be renamed before BC extraction).
- Each entry cites a *Source* — primary standard, ADR, or RFC — to anchor authority.

---

## monitoring

### Line state
*Status:* accepted. *Source:* ISA-95 L2; modeled in `apps/api-python/src/sdf_api/contexts/monitoring/domain/line_state.py`.

The current operational status of a *Line*. Closed enum: `RUNNING | IDLE | DOWN | CHANGEOVER`.

- Code: `LineState` (type), `line_state` (table), `state` (column).
- *Synonyms / external aliases:* "라인 상태" (Korean UI). Vendor systems use "machine status" — **do not adopt**, scope differs (per-machine vs per-line).
- *See also:* `Machine` under `topology`. Per-machine status, if introduced, would be a separate concept.

### OEE — Overall Equipment Effectiveness
*Status:* accepted. *Source:* ISO 22400-2:2014 §6 (Description of KPIs); modeled in `monitoring/domain/oee.py`.

`OEE = Availability × Performance × Quality`. ISO 22400-2's own normative names are *Effectiveness* (our "Performance") and *Quality ratio* (our "Quality"); we keep the widely-used Nakajima/TPM names in code and treat the ISO terms as aliases. `Availability` and `Quality` are bounded in [0, 1] by construction; `Performance` can exceed 1 when the ideal cycle time is set loose, so OEE is only *nominally* [0, 1] (see `KNOWN-UNKNOWNS.md`).

- *Synonyms / external aliases:* "효율" (operator screens); ISO 22400-2 *Effectiveness* / *Quality ratio* for the P and Q factors. (No verified vendor alias — do not assert one without a source.)
- *Do not confuse with:* TEEP (`Utilization × OEE`). TEEP is a separate KPI — a TPM/Vorne construct, **not** an ISO 22400-2 KPI; see Phase 5 live-demo Scenario A.

### Availability / Performance / Quality (A / P / Q)
*Status:* accepted. *Source:* ISO 22400-2:2014 §6.

- `Availability = APT / PBT` (Actual Production Time / Planned Busy Time) — ISO 22400-2 defined terms.
- `Performance = (Ideal Cycle Time × Produced Quantity) / APT`. ISO 22400-2 names this factor *Effectiveness* and calls "Ideal Cycle Time" the *planned run time per item (PRI)*; the formula is identical.
- `Quality = Good Quantity / Produced Quantity` (ISO 22400-2: *Quality ratio*; `Good Quantity` excludes reworked parts).

Phase 1 simplification: A is approximated as 1.0 (CAGG bucket treated as PBT). See ADR-0012 and `KNOWN-UNKNOWNS.md`.

### Continuous Aggregate (CAGG)
*Status:* accepted. *Source:* TimescaleDB vendor term.

A materialized view that incrementally summarizes time-bucketed hypertable data. We use `line_oee_5m` to roll counts into 5-minute buckets.

- *Synonyms / external aliases:* "rollup table" (informal). **Do not say** — it loses the incremental-refresh semantic that justifies CAGG over a plain `MATERIALIZED VIEW`.

### Alarm
*Status:* proposed (Phase 1 has the table; rule engine is Phase 3). *Source:* internal.

A timestamped record of a rule-violation event tied to a *Line*. Has `severity ∈ {INFO, WARN, CRITICAL}`, optional `acked_at` / `ack_by`.

- *Synonyms / external aliases:* "alert" — **do not adopt**; "alert" elsewhere means an observability paging event (Prometheus) and conflating the two creates ambiguity in Phase 3.

---

## topology

### Factory
*Status:* accepted. *Source:* ISA-95 (Site level).

A physical site containing one or more *Lines*. Has timezone and locale.

- Code: `Factory` type, `factory` table.
- ISA-95 mapping: corresponds to *Site*, **not** *Enterprise*. ISA-95 *Enterprise* is unmodeled (out of Phase 1–4 scope).

### Line (Production Line)
*Status:* accepted. *Source:* ISA-95 (Work Center / Production Line).

A coordinated sequence of *Machines* producing a finished unit, grouped under one *Factory*.

- Code: `Line` (Kotlin), `ProductionLine` (Python `topology` model), `production_line` table.
- *Same word, different BC:* in `monitoring`, "Line" is a state-bearing object (carries *Line state*); in `topology`, it's a structural node. The ID type `LineId` is shared via `shared_kernel`.

### Machine
*Status:* accepted. *Source:* ISA-95 (Equipment / Work Unit).

A single physical device within a *Line*, identified by `sparkplug_node_id`. Phase 1: 5 per line (`press`, `weld`, `paint`, `inspect`, `pack`).

- Code: `Machine` type, `machine` table.
- *Synonyms / external aliases:* "asset" (PTC / AVEVA). **Do not adopt** — "asset" elsewhere connotes financial accounting.

---

## edge (Sparkplug B world)

### Edge Node
*Status:* accepted. *Source:* Sparkplug Specification v3.0 §6.

A networked device acting as a Sparkplug *publisher* for one or more *Devices*. In our Phase 1 model: one Edge Node per *Line* (`edge_node_id == line_id`).

- *Do not abbreviate to* "node" — collides with Kubernetes / Kafka usage.

### Device (Sparkplug)
*Status:* accepted. *Source:* Sparkplug Specification v3.0 §6.

A subordinate of an Edge Node, addressed via the topic `spBv1.0/<group>/<msg_type>/<edge>/<device>`. In Phase 1, *Machines* are addressed as compound metric names rather than separate Sparkplug Devices (see ADR-0011).

### NBIRTH / NDEATH / NDATA
*Status:* accepted. *Source:* Sparkplug v3.0 §5.

Sparkplug B *node-level* message types — published on connect, on (Last-Will) disconnect, and per data update respectively. `D*` variants exist for *Device-level*.

### Rebirth
*Status:* accepted. *Source:* Sparkplug v3.0 §5.

Re-issuing a BIRTH after sequence-number gap detection. The spec's normative trigger is an NCMD from the Host carrying the `Node Control/Rebirth` metric set to `true`; an Edge MAY additionally re-birth on internally detected inconsistency (implementation-defined, not required by the spec).

### Sequence number (seq)
*Status:* accepted. *Source:* Sparkplug v3.0 §5.

Monotonically increasing 8-bit counter on every Sparkplug message (0..255, wraps). Reset to 0 by each NBIRTH, then incremented per message. Gap implies message loss → request *Rebirth*.

- *Do not confuse with* `bdSeq` (birth/death sequence) — a separate 0..255 counter carried in NBIRTH/NDEATH that increments per MQTT session (not per message), used to correlate a stale Last-Will NDEATH with its originating session.

---

## shared

### Tenant
*Status:* proposed in Phase 1, accepted in Phase 2. *Source:* internal (ADR-0003 schema-per-tenant).

A logical isolation boundary aligned with one or more *Factories*. In Phase 1, exactly one implicit tenant `sdf_default`; in Phase 2+, schema-per-tenant onboarding.

- *Synonyms / external aliases:* "customer", "account", "organization" — **do not adopt**; those carry CRM/billing semantics that we do not model.

### Sparkplug Topic Namespace
*Status:* accepted. *Source:* ADR-0011, Sparkplug v3.0 §6.

`spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]`. Phase 1 mapping: `group_id = sdf_default`, `edge_node_id = <line slug>`, device level unused (metrics carry the machine key).

### Bounded Context (BC)
*Status:* accepted. *Source:* DDD (Evans, 2003).

A region of the model where a particular *Ubiquitous Language* applies consistently. This file is scoped *by* BC; identifiers can repeat across BCs with different meanings.

- Phase 1 BCs realized in code: `monitoring`, `topology` (Python `contexts/`); `edge` partially (Kotlin `sparkplug_edge`).
- Phase 2 introduces: `tenancy`, `identity`.

---

## Anti-glossary — terms we deliberately *don't* use

These are common in the industry but ambiguous, vendor-locked, or load-bearing for the wrong reasons. Avoid in code and specs.

| Term | Why we avoid it | Use instead |
|---|---|---|
| "Equipment" | ISA-95's umbrella term for any node of the role-based equipment hierarchy (Enterprise → … → Control Module) — orthogonal to the functional levels L0–L4, so too broad to pin a precise level. | *Machine*, *Line*, *Factory* — pick the precise level. |
| "Telemetry stream" | Collides with OTel/monitoring "telemetry". | *Sparkplug data* (when about the edge), *machine telemetry* (when about a DB row). |
| "Real-time" | Implausibly precise; we are seconds-latency at best. | "live" (sub-second observable), or quote the actual SLA. |
| "Smart factory" | Vendor marketing. | "manufacturing platform", "DX platform", or the concrete capability. |
| "Status" | Used interchangeably with *Line state* and HTTP status — ambiguous. | *Line state*, or be explicit ("HTTP response status"). |
