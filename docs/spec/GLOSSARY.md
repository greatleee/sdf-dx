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

- BC scopes (Phase 1): `monitoring`, `topology`, `edge`, `shared`. Phase 2 adds `tenancy`, `identity`. Phase 4+ may add `quality` or `maintenance`.
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

A physical site containing one or more *Lines*. Has timezone and locale. Phase 2: each Factory belongs to a *Tenant* and lives in the tenant schema (per ADR-0035). The three Phase 2 factories are real HMG plants: **Ulsan** (kr, Asia/Seoul, ko-KR), **HMGMA Georgia** (us, America/New_York, en-US), **Chennai/HMIL** (in, Asia/Kolkata, en-IN).

- Code: `Factory` type, `factory` table (per-tenant schema).
- ISA-95 mapping: corresponds to *Site*, **not** *Enterprise*. ISA-95 *Enterprise* is unmodeled (out of Phase 1–4 scope).
- *See also:* `Tenant`.

### Line (Production Line)
*Status:* accepted. *Source:* ISA-95 (Work Center / Production Line).

A coordinated sequence of *Machines* producing a finished unit, grouped under one *Factory*. Phase 2: lives in the tenant schema (per ADR-0035 — `production_line` is a per-tenant entity).

- Code: `Line` (Kotlin), `ProductionLine` (Python `topology` model), `production_line` table (per-tenant schema).
- *Same word, different BC:* in `monitoring`, "Line" is a state-bearing object (carries *Line state*); in `topology`, it's a structural node. The ID type `LineId` is shared via `shared_kernel`.
- *See also:* `Tenant`, `Factory`.

### Machine
*Status:* accepted. *Source:* ISA-95 (Equipment / Work Unit).

A single physical device within a *Line*, identified by `sparkplug_node_id`. Phase 2: 5 per line, following the automotive 5-shop taxonomy (`stamping`, `body`, `paint`, `assembly`, `inspection`) per ADR-0036.

`machine` is a **per-tenant entity** — it lives in the tenant schema, not in `public` (ADR-0035). The same applies to `factory` and `production_line`. The *Tenant* is the isolation boundary for all topology data.

- Code: `Machine` type, `machine` table (per-tenant schema). `kind` column holds the `MachineKind` enum.
- *Synonyms / external aliases:* "asset" (PTC / AVEVA). **Do not adopt** — "asset" elsewhere connotes financial accounting.
- *See also:* `MachineKind`, `Tenant`.

### MachineKind
*Status:* accepted. *Source:* ADR-0036; automotive 5-shop manufacturing taxonomy.

An enum classifying the role of a *Machine* within a production line, using the canonical automotive 5-shop sequence: `stamping | body | paint | assembly | inspection`.

- Code: `MachineKind` type (enum in `topology` domain), `kind` column on `machine` table.
- `machineKey` in the Kafka contract remains a free string (no enum constraint at the wire layer); `MachineKind` lives in the domain only.
- Phase 1 used `press/weld/paint/inspect/pack` — retired by ADR-0036.
- *See also:* `Machine`.

---

## edge (Sparkplug B world)

### SimulatorScenario
*Status:* accepted. *Source:* internal (ADR-0036; W1-EDGE).

A configuration profile for the Kotlin device simulator that determines the operational character of a simulated tenant's telemetry: takt time, shift schedule, failure rate, quality rate, alarm frequency, and cycle-time variability. Three scenarios encode the three real HMG plants: **Ulsan** (mature high-volume, high stable OEE), **HMGMA** (new EV metaplant ramp-up, lower/improving OEE), **Chennai/HMIL** (mature ultra-high-volume, cost-optimized). Scenarios differ by params, not by process — every factory runs the full 5-shop line.

- Code: `SimulatorScenario` config type (Kotlin, `apps/ot-gateway-kotlin/simulator/`).
- *See also:* `MachineKind`, `Tenant`.

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

## tenancy

### Tenant
*Status:* accepted. *Source:* internal (ADR-0003 schema-per-tenant; ADR-0035 per-tenant data boundary).

A logical isolation boundary aligned with one or more *Factories*. In Phase 1, exactly one implicit tenant `sdf_default` (retired in Phase 2); in Phase 2+, schema-per-tenant onboarding via `POST /tenants`. Each Tenant maps to exactly one Postgres schema; `factory`/`production_line`/`machine` are **per-tenant entities** — they live in the tenant schema, not in `public` (ADR-0035). `public` holds only the cross-cutting registry: `tenant`, `app_user`, `membership`.

- Code: `Tenant` type, `tenant` table (in `public`).
- *Synonyms / external aliases:* "customer", "account", "organization" — **do not adopt**; those carry CRM/billing semantics that we do not model.

---

## identity

### User
*Status:* accepted. *Source:* internal (ADR-0033).

A human principal with a stored credential (argon2 hash). A User has zero or more *Memberships*, each granting a *Role* within a specific *Tenant*. Users span tenants — the same person can be an operator in one tenant and a tenant-admin in another.

- Code: `User` type, `app_user` table (in `public`). (`app_user` avoids collision with the reserved SQL keyword `user`.)
- *See also:* `Membership`, `Role`.

### Membership
*Status:* accepted. *Source:* internal (ADR-0033).

The association between a *User* and a *Tenant* that grants a specific *Role*. The pair `(user_id, tenant_id)` is unique — one role per user per tenant. Multiple memberships give a user access to multiple tenants simultaneously (with independently-settable roles per tenant).

- Code: `Membership` type, `membership` table (in `public`, columns `user_id`, `tenant_id`, `role`).
- *See also:* `User`, `Role`, `Tenant`.

### Role
*Status:* accepted. *Source:* internal (ADR-0033).

An enumerated capability level attached to a *Membership*. Phase 2 values: `operator` (read-only access; mutating endpoints return 403) and `tenant-admin` (full access including `POST /tenants`). Design-spec §13.2's "viewer" is absorbed into `operator read-only`. A-IE (integration-engineer) is out of Plan A scope.

- Code: `Role` type (enum), `role` column on `membership`.
- *See also:* `Permission`, `Membership`.

### Permission
*Status:* accepted. *Source:* internal (ADR-0033).

The outcome of evaluating whether a *Role* may perform an action: `Allowed | Denied`. Expressed as the pure domain function `can(action, role) -> Allowed | Denied`. No external RBAC library; the `identity` domain is the sole authority.

- Code: `Permission` (the sum-type result), `can` (the function), `Allowed`/`Denied` (the cases).
- *See also:* `Role`.

---

## shared

### EnterpriseOEE
*Status:* accepted. *Source:* internal (ADR-0037). *Cross-BC:* spans `identity` (membership) + `monitoring` (OEE CAGGs).

A cross-BC read model that aggregates *OEE* across the caller's member *Tenants*. Computed as a simple average over a `UNION ALL` of the per-tenant `line_oee_*` (`_5m`/`_1h`/`_shift`) continuous aggregates. Membership-driven — the caller sees only tenants they belong to. Distinct from the general cross-tenant analytics layer (Phase 3+); this is a single thin metric.

- Code: `EnterpriseOEE` type (cross-BC read model in `src/sdf_api/use_cases/`), `GET /enterprise/oee` endpoint.
- *Do not confuse with:* per-tenant OEE (the `OEE` entry under `monitoring`) or TEEP.

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
| "Customer" / "Account" / "Organization" | Carry CRM/billing semantics not modeled here. | *Tenant*. |
| "Viewer" (role name) | Design-spec §13.2 used "viewer" for the read-only role; absorbed into *operator* (read-only) per ADR-0033. | `operator` (with the understanding that operator = read-only in code and specs). |
| "Integration engineer" (role name in Plan A) | A-IE is explicitly out of Plan A scope (ADR-0033/0038). Do not add `integration_engineer` to the `Role` enum or use it as a code identifier in Phase 2. | Reserved for a later phase ADR if needed. |
| "Enterprise" (as a topology level) | ISA-95 *Enterprise* is the top of the role-based equipment hierarchy; we deliberately do not model it. *EnterpriseOEE* is our term for the cross-tenant KPI read model — the word "enterprise" there means "spanning the caller's tenants", not the ISA-95 level. | Use *EnterpriseOEE* for the cross-tenant KPI; never use "enterprise" to refer to an ISA-95 topology node. |
