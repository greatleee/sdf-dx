# Domain Absorption Notes

Working notes from absorbing the manufacturing domain via standards docs + vendor manuals. Each section cites a primary source.

## ISA-95 — Enterprise/Control integration
- Two **orthogonal** models — don't conflate them:
  - (a) *Functional levels*: L0 physical → L1 sensing/actuation → L2 supervisory control → L3 MES/MOM → L4 ERP. This portfolio operates at **L0–L2** (sensors, control, edge aggregation). Note **MES is L3**, above our scope — so we say "edge", not "MES-edge".
  - (b) *Role-based equipment hierarchy* (a separate axis from the levels): Enterprise → Site → Area → Work Center → Work Unit. We model Factory → Line → Machine onto Site → Production Line (a Work Center sub-type) → Work Unit.
- Simplification: Work Center / Work Unit are role-groupings; ISA-95 also defines concrete sub-types (Process Cell / Production Line / Production Unit / Work Cell) and lower engineered levels (Equipment Module / Control Module). Our 3-tier model is a deliberate teaching-level slice.
- Source: [ANSI/ISA-95.00.01-2010 (IEC 62264-1 Mod) — Enterprise-Control System Integration, Part 1: Models and Terminology](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa95). (A 2025 edition now exists; 2010 is the edition modeled here.)

## ISO 22400 — KPI definitions
- OEE = Availability × Performance × Quality. ISO 22400-2's normative names are Availability × *Effectiveness* × *Quality ratio*; we keep the Nakajima/TPM names *Performance* / *Quality* (aliases).
- Availability = APT / PBT (Actual Production Time / Planned Busy Time).
- Performance = (Ideal Cycle Time × Produced Quantity) / APT. (ISO term for "Ideal Cycle Time" is *planned run time per item, PRI*.)
- Quality = Good Quantity / Produced Quantity. (ISO *Quality ratio*; Good Quantity excludes rework.)
- Availability and Quality ∈ [0, 1] by construction; **Performance can exceed 1** if the ideal cycle time is set loose, so OEE is only nominally bounded — see `KNOWN-UNKNOWNS.md`.
- Source: [ISO 22400-2:2014, §6 "Description of KPIs"](https://www.iso.org/standard/56847.html). (KPI definitions live in clause 6; clause 5 is the input *elements*. 2014 is the current edition — a revision is only at draft (ISO/DIS 22400-2) as of 2026-05.)

## Sparkplug B — payload + topic spec
- Topic: `spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]` ("spBv1.0" stays literal even at spec v3.0 — it versions the payload encoding, not the spec).
- Message types: NBIRTH, NDATA, NDEATH (node); DBIRTH, DDATA, DDEATH (device); NCMD, DCMD (commands); STATE (host online/offline — a single message with a boolean field, not separate birth/death types).
- `seq` rolls 0..255 per message, **reset to 0 by each NBIRTH**; gap detection prompts rebirth (NCMD `Node Control/Rebirth`). Distinct from `bdSeq` (per-session birth/death counter).
- Source: [Sparkplug Specification v3.0, Eclipse Foundation](https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification-3.0.0.pdf).

## OPC UA Companion Specifications
- Phase 4 candidate: OPC UA for Machinery (OPC 40001-1, "Machinery Basic Building Blocks"). Downstream machinery specs normatively reference both OPC 40001-1 and OPC UA DI (OPC 10000-100) in parallel — better described as building *on* OPC 40001-1 + DI than as a pure "DI extension".
- Source: [OPC Foundation — OPC UA for Machinery](https://opcfoundation.org/markets-collaboration/opc-ua-for-machinery/).

---

## Phase 2 — Multi-Tenancy Domain Notes

*Added 2026-05-25. Covers Plan A: backend multi-tenancy scope.*

### Automotive 5-shop line structure

A complete automotive body+paint+trim assembly plant is traditionally organized into five sequential shops, each with distinct equipment types, cycle times, and quality concerns:

1. **Stamping** — press lines stamp flat sheet steel into body panels. High-force, high-throughput; failure modes include die wear and sheet misalignment. Relatively low operator count, high capital intensity.
2. **Body** (Body-in-White / BIW) — welding stations assemble stamped panels into the body shell. Robotic MIG/spot welding; quality KPI is weld integrity. Body-in-White defines the vehicle's structural skeleton and is among the most automation- and capital-intensive shops.
3. **Paint** — body shells are primed, painted, and clear-coated in an environmentally controlled booth sequence. Long cycle times (drying/curing); volatile-organic-compound (VOC) concerns. A paint-shop stoppage is one of the most expensive in automotive because in-process bodies cannot wait indefinitely.
4. **Assembly** — the painted body receives powertrain, interior, and electrical harnesses in a moving-line takt cadence. Highest operator count; quality gate is end-of-line (EOL) audit. EV plants (HMGMA) have a simplified powertrain assembly compared to ICE.
5. **Inspection** — final vehicle inspection, headlamp alignment, water test, rolling-road dynamometer. Defects found here are late-stage rework — Quality ratio is most sensitive at this stage.

Our model: every *Line* in every *Factory* runs all five shops as a sequential set of *Machines* (`MachineKind`: `stamping → body → paint → assembly → inspection`). The 5-shop ordering is the canonical data-path assumption; we do not model inter-shop buffers or re-sequencing (out of scope).

Source: general automotive manufacturing domain knowledge; cross-checked against Hyundai Motor Group public plant descriptions. (The 5-shop *sequence* is automotive convention, not an ISA-95 prescription — ISA-95 / IEC 62264 governs the equipment hierarchy and manufacturing-operations-management activity models, not physical shop layout.)

### Per-site OT edge — N simulators, tenant from group_id

Phase 2 uses **one Kotlin simulator container per tenant** (three containers: kr, us, in). Each simulator publishes Sparkplug B messages with `group_id = <tenant_slug>` (e.g., `kr`, `us`, `in`). The Sparkplug→Kafka bridge derives the tenant slug directly from `group_id` — no hardcoded constant, no env var mapping. This is the sole authoritative source of tenant identity on the OT edge.

Ingest routes each `MachineTelemetry` Kafka record to the correct Postgres schema by reading the tenant field derived from `group_id`, setting a connection-scoped `search_path`, and resolving the machine locally within that schema. The `sdf_default` group/tenant is retired in Phase 2.

Per-tenant simulators run `restart: unless-stopped` in the prod compose; each encodes a distinct `SimulatorScenario` to produce meaningfully different OEE stories per plant.

### Membership / RBAC model

The identity model is a **many-to-many user↔tenant** relationship mediated by the `membership` table:

- `public.app_user(id, credential_hash)` — credential hash is argon2id; domain has no crypto import.
- `public.membership(user_id, tenant_id, role)` — `(user_id, tenant_id)` unique; one role per user-tenant pair; roles are independently settable across tenants (a user can be `operator` in `kr` and `tenant-admin` in `us`).
- **Roles (Phase 2):** `operator` (read-only; all mutating endpoints return 403) and `tenant-admin` (full access, including `POST /tenants`). Design-spec §13.2 "viewer" is absorbed into `operator read-only`.
- **Active tenant:** carried as a JWT claim alongside `sub` and `role`. A token is scoped to exactly one active tenant at a time; switching tenants re-issues a token with a different active-tenant claim.
- **Pure domain:** the function `can(action, role) -> Allowed | Denied` lives in `contexts/identity/domain/`. No auth library. Crypto (argon2, PyJWT) lives in adapters only.
- **A-IE (integration-engineer role):** out of Plan A scope. Not added to the `Role` enum in Phase 2.

### Three real-plant tenants — Ulsan / HMGMA / Chennai

Phase 2 seeds three tenants using real Hyundai Motor Group plants as the grounding anchor. Differentiation is **by operational scenario parameters, not by process** — every factory runs the full stamping→body→paint→assembly→inspection line.

| Tenant slug | Factory | Region | Timezone | Locale | Operational profile |
|---|---|---|---|---|---|
| `kr` | **Ulsan Plant** | Asia/Seoul | Asia/Seoul | ko-KR | Mature, high-volume, high stable OEE. The oldest and largest Hyundai plant; multiple lines running at near-peak efficiency. Inherits the Phase-1 `sdf_default` demo content (re-seeded fresh via `POST /tenants`). |
| `us` | **HMGMA** (Hyundai Motor Group Metaplant America, Bryan County, Georgia) | America/New_York | America/New_York | en-US | New EV-focused metaplant, commenced production 2024–2025. Ramp-up phase: lower OEE with improving trend; teething issues in body/paint shops; higher alarm rate; shorter shift history. |
| `in` | **HMIL** (Hyundai Motor India, Sriperumbudur / Chennai) | Asia/Kolkata | Asia/Kolkata | en-IN | Mature, ultra-high-volume, cost-optimized for the emerging-market segment. Very high throughput, tighter margins, leaner staffing; Quality ratio emphasis. Second-largest Hyundai plant globally by volume. |

Key modeling decision: **no factory gets a single process** ("one shop per factory" is the common wrong assumption when building multi-tenant demos). All three factories run all five shops. The scenario differences manifest through `SimulatorScenario` params: takt time, cycle-time variability, failure rate, quality rejection rate, alarm frequency, and shift count.

Phase-2 data ownership: `factory`, `production_line`, and `machine` rows for each plant live in their respective tenant schemas (`kr`, `us`, `in`), not in `public`.

### Per-tenant data ownership

`factory`, `production_line`, and `machine` are **per-tenant entities** (ADR-0035). This is the primary design choice that makes per-tenant Continuous Aggregates (CAGGs) clean local joins — there is no cross-schema reference needed to join `machine_telemetry` to `machine`.

`public` holds only the cross-tenant registry: `tenant`, `app_user`, `membership`. No domain data (topology, telemetry, line state, OEE) lives in `public` after Phase 2 migration.

The isolation boundary consequence: a query inside tenant schema `kr` can reference `machine` without schema qualification; the connection-scoped `search_path = kr, public` makes this resolve to `kr.machine`. `public` is on the `search_path` only for registry lookups (`tenant`/`membership`); since it holds no domain tables, a per-tenant CAGG join has nothing to fall through to and cannot reach across schemas (ADR-0035). Cross-tenant queries (e.g., enterprise OEE) must explicitly enumerate the schemas via `UNION ALL` — they cannot use a single unqualified join.
