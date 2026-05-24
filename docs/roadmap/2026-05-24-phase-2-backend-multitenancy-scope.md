# Phase 2 Scope Decision — Backend Multi-Tenancy + Backend Deploy (Plan A)

| | |
|---|---|
| **Date** | 2026-05-24 |
| **Status** | Accepted — scope decision for Phase 2, produced via structured pre-planning interview (deep-interview). |
| **Scope** | Splits Phase 2 into **Plan A** (backend + backend deploy, this doc) and **Plan B** (frontend + frontend deploy, a separate later interview/plan). Input to `docs/plans/` Phase 2 plan authoring. |
| **Relationship** | *Extends, does not supersede*, `2026-05-22-...-design.md` §10/§13.2 (Phase 2 def) and `2026-05-23-public-live-demo-deployment-addendum.md`. Records the Plan A/B split + locked Phase-2 backend decisions. |
| **Author** | cd.lee.dev@gmail.com (+ Claude as pair) |

---

## Provenance / interview metadata
- Method: deep-interview (Socratic, ambiguity-gated), 9 rounds (3 reframed mid-interview by user correction)
- Final ambiguity: ~10% (threshold 20%, source: default)
- Type: brownfield
- Status: PASSED

## Scope note
This doc covers **Plan A only** (Phase 2 backend + backend deploy). **Plan B** (Phase 2 frontend + frontend deploy) is a *separate later interview*. The Phase 1 monitoring dashboard is being built in **another session** and is out of scope here. **Phase 2b** (A-TA visitor persona, admin UI, persona picker, demo-namespace isolation, UC-003 E2E) remains deferred per the deployment addendum.

## Clarity Breakdown (brownfield weights)
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.92 | 0.35 | 0.322 |
| Constraint Clarity | 0.90 | 0.25 | 0.225 |
| Success Criteria | 0.85 | 0.25 | 0.213 |
| Context Clarity | 0.95 | 0.15 | 0.143 |
| **Total Clarity** | | | **0.902** |
| **Ambiguity** | | | **0.098** |

## Topology (Plan A active components)
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| BC formalization | active | Make `monitoring`/`topology` boundaries explicit; add `tenancy`/`identity` BCs; wire cross-BC `use_cases/` + `DomainEventDispatcher` (ADR-0008/0009 operational) | AC: import-linter independence + Konsist extended to new BCs |
| Tenancy BC + onboarding | active | schema-per-tenant; Alembic multi-schema; `POST /tenants` (schema→migrate→hypertable→CAGG, one txn); `search_path` ingest routing | dogfood `POST /tenants` to create KR/US/IN |
| Identity BC + auth | active | hand-rolled JWT (PyJWT/argon2 in adapters); pure domain `can()`; membership model; 3 real roles | RBAC enforced at API |
| Cross-tenant enterprise OEE | active | thin cross-BC use case, UNION ALL over caller's member tenants' CAGGs | API only; FE view → Plan B |
| Demo seed (KR/US/IN) | active | 3 realistic full auto lines; differentiate by operational scenario + product/scale + tz/locale; per-tenant simulators | concrete content authored at execution + domain-reasonableness review |
| MachineKind 5-shop refinement | active | rename generic `press/weld/paint/inspect/pack` → automotive `stamping/body/paint/assembly/inspection` | domain enum + sim + seed + docs; `machineKey` stays free-string → ~0 contract churn |
| Backend deploy | active | `docker-compose.prod.yml` + Cloudflare Tunnel; always-on per-tenant simulators; 7-day retention; uptime monitoring | platform decision = mid-phase ADR (deferred) |
| **Phase 2 FE + FE deploy** | **deferred → Plan B** | tenant switcher, login UI, landing splash, FE i18n, enterprise-OEE view, README credential exposure, FE deploy | separate later interview |
| **Phase 1 monitoring UI** | **out of scope** | being built in another session | not this project's work here |
| **Phase 2b** | **deferred** | admin UI, persona picker, demo-namespace isolation, 1h reset cron, UC-003 E2E | separate optional plan, post-Phase-2 trigger |

## Goal
Deliver the **backend** of the Phase 2 multi-tenant manufacturing-DX platform and stand it up on a public VPS, such that three realistic factory tenants (KR/US/IN) each run a full automotive production line as an independent Postgres schema, telemetry is routed per-tenant, access is governed by hand-rolled JWT + real RBAC over a membership model, and a thin cross-tenant enterprise-OEE query exists — all contract-first, tested, and running 24/7 — leaving a stable, documented API surface for the Plan B frontend to consume.

## Constraints
- **Plan A = backend + backend deploy only.** All UI lands in Plan B. Deploy in Plan A means: prod compose + Cloudflare Tunnel + reachable API + always-on data pipeline + monitoring; it does **not** serve a dashboard (no FE yet).
- **Build spine:** Chapter 0 (ADRs/UCs/living docs) → backend (BC formalization → tenancy+onboarding → identity → cross-tenant → seed) tested → backend deploy. (Backend-complete-then-deploy; no walking-skeleton.)
- **Tenancy = schema-per-tenant** exactly per ADR-0003 (shared metadata in `public`; per-tenant hypertables + CAGGs). RLS not used.
- **Identity is hand-rolled** (PyJWT + argon2), no auth library. Pure `identity` domain: `User`/`Role`/`Permission` value objects, `can(action) -> Allowed | Denied` sum-type. JWT signing/verify + password hashing live in adapters (FC/IS).
- **Accounts = actor personas**, not a generic "demo" abstraction (addendum §3.3: visitors *wear* an existing primary actor role). One account per persona; **operator + tenant-admin** at minimum (A-SV=Phase3, A-PE=Phase4 excluded; A-IE optional/absorbed).
- **User↔tenant = membership many-to-many**: `public.membership(user_id, tenant_id, role)`; role is **per-(user,tenant)** and independently settable. JWT carries `{sub, active tenant, that tenant's role}`; switching re-scopes; backend authorizes the requested tenant against the caller's memberships. Seeded persona accounts hold memberships across KR/US/IN.
- **RBAC roles = actor personas** (operator / tenant-admin [/ integration-engineer]). Reconcile design-spec §13.2's "viewer" by absorbing it into operator read-only (Ch0 ADR/GLOSSARY).
- **operator = read-only** (all mutating endpoints → 403). **tenant-admin** required for `POST /tenants`.
- **Multi-tenant data = N per-site simulator instances** (one container per tenant). Bridge must derive tenant from the Sparkplug `group_id` (today it's a constant constructor param). Ingest must switch from public-schema writes to per-tenant `search_path` routing (today single public schema).
- **Cross-tenant OEE is thin**: one cross-BC use case, UNION ALL over member tenants' `line_oee` CAGGs → enterprise average. Membership-driven authz, **no new role**. ADR-0003's "Phase 3+ aggregator" is reframed (Ch0 ADR) as the *general* analytics layer, distinct from this single demo metric.
- **Tenants differ realistically**: every factory runs a full multi-process auto line (stamping→body→paint→assembly→inspection); differentiation is by **operational scenario** (distinct OEE stories via per-sim cycle-time/failure/quality/alarm params), **product/scale** (line counts, station/machine counts), and **shift/tz/locale** — never "one process per factory."
- **`MachineKind` refined to automotive 5-shop** (stamping/body/paint/assembly/inspection). `machineKey` remains a free string in the Kafka contract ⇒ no schema enum change, no codegen regen; only domain enum + simulator + seed + docs change.
- **Deploy platform decision is deferred** to the deploy step (mid-phase ADR, per ADR-0000). Ch0 records platform=TBD; plan carries a conditional **multi-arch (ARM) build branch** (needed only if Oracle Free is chosen over Hetzner CX32).
- **Contract-first** (ADR-0005): every new REST surface (auth, `POST /tenants`, tenant listing, enterprise OEE) is added to `packages/contracts/openapi/sdf-api.yaml` first, then regenerated; codegen drift gate stays green.
- **Architecture rules unchanged** (`.claude/rules/*`, ADRs 0004/0009/0016–0024): error-as-value, clock/UUID/random injection, ORM containment, ports-as-folder, per-BC UoW + fakes, import-linter + Konsist + AST gates extended to the new BCs.

## Non-Goals
- Any frontend / React work (→ Plan B).
- Serving a public dashboard / README credential exposure / landing splash (→ Plan B).
- Phase 2b: admin UI, persona picker, demo-namespace isolation, 1h reset cron, UC-003 E2E.
- General cross-tenant analytics layer (multi-KPI, filters) — stays Phase 3+ per ADR-0003.
- Finishing the Phase 1 monitoring UI (different session).
- Choosing the deploy platform now (mid-phase ADR).
- New `MachineKind`/Sparkplug *enum* constraints (machineKey stays free string).
- FE i18n translations (factory `locale` already flows through the API; UI strings → Plan B).
- RLS / Citus (migration-path only, not triggered).

## Acceptance Criteria (Plan A)
- [ ] 3 tenant schemas (KR/US/IN) exist, **created by dogfooding `POST /tenants`** (schema → Alembic `upgrade head` w/ `search_path` → `create_hypertable` → CAGG, single transactional sequence; idempotent/rerunnable).
- [ ] Ingest routes telemetry into the correct tenant schema via `search_path` (replaces current single-public-schema write).
- [ ] `tenancy/` and `identity/` BCs formalized; `monitoring`/`topology` boundaries made explicit; cross-BC `src/sdf_api/use_cases/` + `DomainEventDispatcher` wired; import-linter independence + Konsist rules extended to the new BCs and stay green.
- [ ] Hand-rolled JWT auth works (issue/verify); argon2 password hashing; pure `identity` domain with `can() -> Allowed|Denied`; zero auth library.
- [ ] `public.app_user` + `public.membership(user_id, tenant_id, role)`; role is per-(user,tenant). operator + tenant-admin persona accounts seeded with memberships across KR/US/IN.
- [ ] **operator is read-only**: every mutating endpoint returns 403 for operator (asserted at the API/integration level).
- [ ] `POST /tenants` requires tenant-admin role.
- [ ] Cross-tenant **enterprise-OEE endpoint** returns a UNION-ALL average over the caller's member tenants' CAGGs.
- [ ] `MachineKind` is the automotive 5-shop set (stamping/body/paint/assembly/inspection); domain enum + simulator machine list + `005_seed.sql` + GLOSSARY/DOMAIN-NOTES updated; Kafka contract unchanged (machineKey free string); codegen drift gate green.
- [ ] N per-tenant simulator containers (kr/us/in) run; bridge derives tenant from Sparkplug `group_id`; each simulator encodes a **distinct operational scenario** (different OEE story).
- [ ] All new REST surfaces are **contract-first** in `sdf-api.yaml` → regenerated DTOs; no hand-written request/response models.
- [ ] **Backend deploy**: `docker-compose.prod.yml` + Cloudflare Tunnel; backend API reachable over HTTPS (valid cert); per-tenant simulators always-on (`restart: unless-stopped`); 7-day TimescaleDB retention (demo); UptimeRobot monitor on API health + down-alert.
- [ ] CI green: mypy strict, ruff, import-linter (new contracts), AST checks, Konsist/detekt/ktlint, contract codegen drift, all tests (domain pure/no-mocks, per-BC use-case with in-memory datasets, integration testcontainers for onboarding + search_path routing).
- [ ] Chapter 0 batch landed first (ADRs + draft UCs + living-doc seeds) before any Phase 2 implementation commit (ADR-0000).

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| "Phase 1 is done through Section E" | Sections G (React) + H (E2E) never built; FE + coverage gate missing | Phase 1 monitoring UI handled in another session; FE excluded from Plan A |
| Phase 2 = one plan incl. FE + deploy | FE planning needs a stable merged API; deploy ships the FE | Split: **Plan A** = backend + backend deploy; **Plan B** = FE + FE deploy |
| `op_demo` is a special cross-tenant "demo viewer" | No demo abstraction in docs (addendum §3.3) | Accounts = actor personas; one operator account spans portfolio tenants via the switcher |
| Need to choose user↔tenant access model | Addendum §3.3/§6 already decided it | One account per persona; membership grants per-(user,tenant) role; resolved by docs |
| Cross-tenant OEE is Phase 2 | §13.2 (P2) vs §5.2/ADR-0003 (P3+) conflict | Thin demo metric in Plan A; general analytics layer stays P3+ (Ch0 ADR) |
| Differentiate factories by process (KR stamping/US assembly) | A real auto plant runs all shops; one-process-per-factory is unrealistic | Common full line everywhere; differentiate by operational scenario + scale + tz/locale |
| "Let me define scenarios" = a richness level | It's a *who/when authors content* axis, orthogonal to richness | Richest realistic = structural variation (option 2); author concrete content at execution + domain review |
| 5-shop rename is heavy contract churn | machineKey is a free string, MachineKind only in domain | ~0 contract churn; domain enum + sim + seed + docs only |
| Decide deploy platform now | Contingent on external Oracle-signup unknown | Defer to deploy step (mid-phase ADR); conditional multi-arch branch |

## Technical Context (brownfield findings)
- **api-python** (`sdf_api`): BCs `monitoring` (LineState/OEE read-side, Pg readers, WS broadcaster) + `topology` (Factory/Line/Machine, no adapters). `shared_kernel/ids.py` already has `TenantId` + `DEFAULT_TENANT="sdf_default"`. Composition lives in `app.py` (no separate `composition.py`, no top-level `use_cases/` yet). Routes: `/api/v1/lines/{id}/state`, `/oee`, `/ws/line-state`, `/healthz`, `/readyz`. **No JWT, no auth, no tenant param on routes.**
- **ingest-python** (`sdf_ingest`): consumes `sdf\..*\.machine\.telemetry`; `Normalized` carries `tenant_id` but **writes to a single public schema (no search_path)**; `MachineResolver` resolves `{tenant}/{lineId}/{machineKey}` → UUIDs via `machine.sparkplug_node_id`.
- **ot-gateway-kotlin**: `simulator` (Main.kt `MACHINE_TYPES=["press","weld","paint","inspect","pack"]`, env `SDF_GROUP_ID`/`SDF_LINE_ID`), `bridge` (tenant from env `SDF_DEFAULT_TENANT` *constructor constant*; topic `sdf.${tenantId}.machine.telemetry`; Kafka key `${lineId}/${machineKey}`).
- **contracts**: `sdf-api.yaml` has no tenant/auth surfaces; `machine_telemetry.schema.json` `machineKey` = free string; Sparkplug proto vendored (do not edit).
- **infra**: `docker-compose.yml` (timescale, hivemq, redpanda, simulator, bridge, ingest, api, + dashboard build target that doesn't exist). DB init = raw SQL (`001`–`005`), **no Alembic**, single public schema, CAGG `line_oee_5m` exists, seed = 1 factory (Ulsan) / 1 line / 5 machines, `sparkplug_node_id='sdf_default/line-a/<type>'`.
- **No** search_path, JWT, Alembic, Redis, i18n-runtime anywhere.
- Binding: ADRs 0001–0027, `.claude/rules/*`, design spec + deployment addendum, GLOSSARY (Tenant proposed→accepted P2; lists `tenancy`/`identity` as P2 BCs).

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Tenant | core domain | id/slug, schema name | 1 Tenant ↔ 1 Postgres schema; has many Factories |
| Factory | core domain (topology) | id, name, region, timezone, locale | belongs to Tenant; has many ProductionLines |
| ProductionLine | core domain (topology/monitoring) | id, factory_id, name, isa95_role | has many Machines; state-bearing in monitoring |
| Machine | core domain (topology) | id, line_id, kind (MachineKind 5-shop), sparkplug_node_id | belongs to ProductionLine |
| MachineKind | value object | enum: stamping, body, paint, assembly, inspection | classifies Machine |
| User | core domain (identity) | id, credential (argon2 hash) | has many Memberships |
| Membership | core domain (identity) | user_id, tenant_id, role | links User × Tenant → Role |
| Role | value object (identity) | operator \| tenant-admin \| (integration-engineer) | drives Permission |
| Permission | value object (identity) | `can(action) -> Allowed \| Denied` | derived from Role |
| LineState | value object (monitoring) | RUNNING\|IDLE\|DOWN\|CHANGEOVER | of a ProductionLine |
| OEE | value object (monitoring) | availability, performance, quality, oee | computed per Line/window (ISO 22400) |
| EnterpriseOEE | read model (cross-BC) | avg over member tenants | UNION ALL of per-tenant OEE CAGGs |
| SimulatorScenario | config (edge) | takt, shift, failure/quality/alarm profile | one per tenant simulator |

## Chapter 0 outputs (for the plan author)
- **ADRs (Ch0):** identity/auth model (hand-rolled JWT + membership + RBAC roles=personas + §13.2 viewer reconciliation); BC formalization outcome (tenancy/identity extraction vs ADR-0008 triggers); Alembic multi-schema migration; MachineKind automotive 5-shop taxonomy; cross-tenant thin-scope (reframes ADR-0003 P3+); seeded-credential→role mapping (addendum §5); Cloudflare single-stack (addendum §5).
- **ADR (mid-phase, NOT Ch0):** public deployment platform (Hetzner CX32 vs Oracle Free) — written at the deploy step.
- **UCs (Ch0 draft; E2E + promote in Plan B):** tenant onboarding (backend), operator authn + RBAC (operator read-only), enterprise-OEE query.
- **GLOSSARY (Ch0):** Tenant proposed→accepted; add User/Membership/Role/Permission/EnterpriseOEE; update Machine examples + add MachineKind 5-shop terms.
- **DOMAIN-NOTES (Ch0 seed):** automotive 5-shop line structure; per-site OT edge (N simulators); membership/RBAC; operational-scenario differentiation.
- **KNOWN-UNKNOWNS (Ch0 seed + living):** deployment limits (addendum §8); platform decision pending; demo data-signal tuning.

## Interview Transcript
<details>
<summary>Full Q&A (9 rounds)</summary>

- **R0 Topology:** 8-component Phase 2 enumerated; flagged that React dashboard + E2E (Phase 1 G/H) don't exist. User: "One plan, deploy included." → later revised (R3).
- **R1 Build spine:** User: "Backend-complete, then FE, then deploy."
- **R2 Auth approach:** User: "Hand-rolled JWT + pure identity BC, 3 real roles, real RBAC."
- **R3 (revised) Sequencing:** User split into **Plan A = P2 backend + BE deploy**, **Plan B (later interview) = P2 FE + FE deploy**; Phase 1 monitoring UI = other session (out of scope).
- **R4 Contrarian — MT data source:** User: "N simulator instances (per-site edge)."
- **R5 Identity model:** User corrected the framing (no "demo" account; accounts = actor personas; decided in addendum §3.3). Resolved to membership model with per-(user,tenant) role; confirmed per-tenant permissions are independently settable.
- **R6 Simplifier — cross-tenant:** User: "Thin enterprise-OEE endpoint in Plan A" (membership-driven, FE view → Plan B).
- **R7 Deploy platform:** User: "Defer to deploy step (mid-phase ADR)"; conditional multi-arch branch.
- **R8 Tenant seed:** User: "공장별 한 공정만은 비현실적; rich가 좋지만 다른 시나리오 필요, 현실성 있게." → common full auto line + operational-scenario differentiation.
- **R9 Realism scope + MachineKind:** clarified option-3 is a who/when-authors axis not a richness level; richest realistic = structural variation; User: include **MachineKind → automotive 5-shop** refinement in Plan A.

</details>
