# Phase 2 — Plan A: Backend Multi-Tenancy + Backend Deploy (Implementation Plan)

| | |
|---|---|
| **Date** | 2026-05-24 |
| **Status** | Draft — **pending approval** (produced via `/plan --consensus`, deliberate mode; APPROVED at consensus iteration 2; + author decision pass — tenants & data-isolation) |
| **Scope source (frozen)** | [`docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md`](../roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md) |
| **Design spec** | `docs/roadmap/2026-05-22-...-design.md` §10/§13.2 · deployment addendum `2026-05-23-...` §3.3 |
| **This doc is** | Disposable scaffold (`docs/plans/` layer). Archived after the Phase-2a tag lands. Code samples are out of scope — see Conventions. |
| **Authoring rule** | Implementation tasks follow `.claude/rules/*`; on any conflict, the rules win over this plan. |

---

## 0. How to read this plan

- **No production code in this document.** Per the user's planning directive, code is the implementing session's responsibility. This plan carries: file/dir **scaffolding** (paths + one-line purpose), function/port **signatures described in prose**, and **test scenarios** (names + Given/When/Then). It does *not* carry function bodies.
- **Task IDs** are stable handles (`C0-x`, `W1-x`, …). Dependencies are explicit. Tasks in the same **wave** with no listed cross-dependency are **parallel-safe**.
- **Commit discipline**: Chapter 0 lands as the first commits (ADR-0000). Contract changes are their own `feat(contracts):` commit (contract-first §4). One aggregate write per transaction (architecture §8).
- **Definition of done for a task** = its Acceptance Criteria all pass *and* the full CI gate set stays green (`mypy --strict`, `ruff`, `import-linter`, AST checks A1–A3, Konsist/detekt/ktlint, contract codegen drift, **all test tiers including the CI integration job**). An AC that can only be satisfied by a *later* wave is not part of this task's DoD — it is restated as the later task's AC (see W2-TEN ↔ W3-RBAC).

### Locked author decisions (this plan is built on them)
1. **Three tenants = real HMG plants** — `kr` → **Ulsan plant** (inherits the existing `sdf_default` Phase-1 data; Ulsan is a KR city), `us` → **HMGMA** (Hyundai Motor Group Metaplant America, Georgia), `in` → **Chennai / HMIL** (Hyundai Motor India, Sriperumbudur). `sdf_default` is **retired** (not a 4th tenant). Tenant slug = country code; the `factory` entity carries the real plant name + region/tz/locale.
2. **Domain tables are per-tenant** — `factory`/`production_line`/`machine` move *into* each tenant schema (alongside `machine_telemetry`/`line_state`/CAGGs). `public` holds **only** the cross-cutting registry: `tenant`, `app_user`, `membership`. This **supersedes ADR-0003's "shared metadata in `public`" clause** (via ADR-0035); the schema-per-tenant core + RLS-rejection of ADR-0003 stand. Rationale: a machine belongs to exactly one plant/tenant, so it is tenant-owned data, not shared metadata — and a per-tenant `machine` makes every per-tenant CAGG a clean **local** join (no cross-schema), which is *why this is the primary design*.
3. **CAGG fallback order** — primary: per-tenant `machine` (local CAGG join). Secondary fallback (only if per-tenant proves hard at W1-SPIKE): **(A)** denormalize `line_id` into `machine_telemetry` to drop the join. If neither is clean, **the author decides after W1-SPIKE**.
4. **RBAC roles = operator + tenant-admin only** (viewer → operator read-only per design-spec §13.2 reconciliation; **no integration-engineer/A-IE** in Plan A — addendum §3.3). The *publicly-exposed* `admin_demo`/persona-picker/admin-UI/demo-namespace-isolation remain **Phase 2b**; Plan A's tenant-admin is a backend role + a dogfooding seed account.

---

## 1. Requirements Summary

Deliver the **backend** of the Phase-2 multi-tenant manufacturing-DX platform and stand it up on a public VPS. Three factory tenants — **`kr` (Ulsan)**, **`us` (HMGMA, Georgia)**, **`in` (Chennai/HMIL)**:

1. Each tenant is an independent Postgres schema, **created by dogfooding `POST /tenants`** via an **idempotent, rerunnable multi-step provisioning sequence** (schema → Alembic `upgrade head` over `search_path` → `create_hypertable` → CAGG). *Not a single DB transaction* — DDL autocommits; ADR-0035 records the reality + idempotency design (this narrows ADR-0003's "single transactional sequence" wording via a superseding note, not an in-place edit). `sdf_default` is retired; `kr`/Ulsan is seeded fresh through onboarding and inherits the Phase-1 demo content.
2. **Per-tenant data boundary:** `factory`/`production_line`/`machine` + `machine_telemetry`/`line_state` + CAGGs all live in the tenant schema; `public` holds only `tenant`/`app_user`/`membership` (supersedes ADR-0003 metadata clause — see §0.2). Every per-tenant CAGG is a clean local join.
3. Telemetry routed per-tenant: bridge derives tenant from the Sparkplug `group_id`; ingest writes via **connection-scoped** `search_path` (replacing today's single-public-schema write; no pool leakage — §2 pre-mortem #3 / BLOCKER-2). The machine resolver now resolves *within* the tenant schema (local, no cross-schema reach).
4. Access governed by **hand-rolled JWT + argon2** (no auth library) over a **membership** model (`public.membership(user_id, tenant_id, role)`); pure `identity` domain with `can() -> Allowed | Denied`; roles = operator (read-only) + tenant-admin. **Active tenant carried in a JWT claim** (additive — keeps oasdiff green).
5. A **thin cross-tenant enterprise-OEE** query: one cross-BC use case, `UNION ALL` over the caller's member tenants' (now local-join) OEE CAGGs.
6. `monitoring`/`topology` boundaries made explicit; `tenancy`/`identity` BCs added; cross-BC `use_cases/` + `DomainEventDispatcher` wired; fitness gates extended; the WS line-state poller made tenant-aware.
7. `MachineKind` refined to automotive 5-shop (`stamping/body/paint/assembly/inspection`); `machineKey` stays free string in the Kafka contract ⇒ ~0 contract churn.
8. Backend deploy: `docker-compose.prod.yml` (repo root) + Cloudflare Tunnel; always-on per-tenant simulators; 7-day retention; uptime monitoring; **JWT signing-key custody** specified. Platform (Hetzner CX32 vs Oracle Free) = **mid-phase ADR** at the deploy step.

**Out of scope (→ Plan B / deferred):** all React/FE work, public dashboard serving, README credential exposure, FE i18n strings, Phase 2b (public `admin_demo` persona, admin UI, persona picker, demo-namespace isolation, reset cron, UC-003 E2E), general cross-tenant analytics (Phase 3+), RLS/Citus, choosing the deploy platform now.

---

## 2. RALPLAN-DR Summary (deliberate mode)

### Principles
1. **Chapter 0 is the frozen SoT.** Every decision the implementing session needs is an ADR/UC/glossary entry *before* the first implementation commit. `git log` order tells the story.
2. **Contract-first, always.** No REST field/endpoint exists in Python before `sdf-api.yaml`. Prefer **additive** changes (JWT-claim tenant scoping) so the now-blocking oasdiff gate stays green.
3. **Functional Core / Imperative Shell.** Auth crypto, schema DDL, `search_path`, Kafka in adapters; domains pure, sum-typed. Fitness gates extended *with* each new BC, never relaxed.
4. **Isolation by construction, proven by test.** Tenant isolation holds even under connection reuse; every isolation claim has a negative test that runs **in CI**.
5. **Domain-correct placement over inertia.** Tenant-owned entities (factory/line/machine) live in the tenant schema even though it means superseding an early ADR clause — the supersede ADR *is* the engineering-judgment signal, not a cost to avoid. Dogfood the platform; defer the public demo surface honestly to Plan B / Phase 2b.

### Decision Drivers (top 3)
1. **Plan B depends on a stable, merged, contract-complete, additively-evolved API.** → contract-first front-loading.
2. **Auth + schema-per-tenant onboarding are the highest-risk subsystems** (security + non-atomic DDL). The cross-schema-CAGG risk is **retired by the per-tenant `machine` decision** (local join), with a Wave-1 spike confirming per-schema CAGG creation/refresh on a freshly-onboarded schema.
3. **Maximize safe parallelism without breaking `bc-independence`.** Independent BCs built concurrently; shared scaffolding (composition root, `use_cases/`, dispatcher, gate config, **pool search_path safety**) lands first.

### Viable Options (build strategy)

**Option A — Backend-complete-then-deploy, BC-parallel waves, Wave-1 de-risking spike (CHOSEN).**
- *Pros:* matches scope-doc R1 lock; isolates risky subsystems; the spike confirms per-schema CAGG early; exploits `bc-independence`; deploy ships a finished, contract-frozen API for Plan B.
- *Cons:* no end-to-end signal until late. Mitigated by the spike + front-loaded contracts + per-wave CI gates.

**Option B — Walking skeleton.** Rejected as a *strategy* (scope lock; ships an unfinished API Plan B would chase) — but its **risk-retirement virtue is absorbed via W1-SPIKE** (a throwaway probe, discarded after).

**Option C — Strict sequential BC build.** Rejected — serializing independent BCs buys only wall-clock cost (`bc-independence` guarantees they don't import each other).

### Pre-mortem (failure scenarios + mitigation)

1. **Onboarding half-applied a tenant.** DDL autocommit → no single rollback. *Mitigation:* W2-TEN provisioning idempotent/rerunnable (guarded steps); integration test kills mid-sequence and asserts clean re-run convergence; failed-onboarding operational disposition documented (MAJOR-D); ADR-0035 records the DDL-autocommit reality.
2. **Hand-rolled JWT — forgery *or* key leak.** *Mitigation:* alg allow-list, mandatory `exp`/`iat`/`sub`/active-tenant claims, constant-time argon2 (cost params in ADR-0033) — in the adapter; pure tested `can()`. **Signing key = injected secret, never committed** (ADR-0033 + W5). Negative security test set + `security-reviewer` gate.
3. **Wrong-schema read/write.** (a) *unresolvable* tenant falls back to `public`; (b) **pooled connection leaks a prior tenant's `search_path`** → invisible cross-tenant R/W. *Mitigation:* W2-ING removes the public write path (unresolvable → logged drop, never public); W1-SCAFFOLD makes `search_path` **connection-scoped** (`SET LOCAL` in a per-operation txn, or pool acquire/`setup` reset); **no-leak integration test** in CI. KR record lands in `kr`, absent from `us`/`public`.
4. **Per-tenant CAGG can't be created/refreshed in a freshly-onboarded schema.** With the per-tenant `machine` decision the CAGG is a *local* join (the high-risk cross-schema variant is gone), but onboarding still has to create the hypertable + CAGG + refresh policy in a brand-new schema reliably. *Mitigation:* **W1-SPIKE** validates per-schema CAGG creation+refresh on an onboarded schema *before* W1-ALEMBIC baselines on it; it also records whether the secondary fallback **(A)** denormalization would be needed if an unforeseen snag appears. If per-tenant `machine` proves hard, **the author decides post-spike** (per §0.3).

### Expanded test plan → §6.

---

## 3. Build map — waves & parallelism

```
Chapter 0 (docs)  ── FIRST commits (ADR-0000) ──────────────────────────────────────┐
  C0-ADR ∥ C0-UC ∥ C0-GLOSS ∥ C0-ACTORS ∥ C0-DOMAIN ∥ C0-UNKNOWNS                     │
                                                                                      ▼
Wave 1 — Foundations
  W1-SPIKE     [GATE] validate per-tenant CAGG create+refresh on an onboarded schema  ──► feeds ADR-0035, gates W1-ALEMBIC + Wave 2
  W1-CONTRACTS   contracts surface + regen (tenant via JWT claim = additive)           ∥
  W1-SCAFFOLD    composition.py + use_cases/ + DomainEventDispatcher + POOL search_path safety + fitness gates ∥
  W1-CI          .github/workflows/ci.yml: Postgres+Timescale integration job          ∥
  W1-EDGE        Kotlin: bridge tenant-from-group_id + simulator 5-shop + SimulatorScenario ∥
  W1-MK-PY       Python: MachineKind enum 5-shop rename (topology domain)              ∥
  (only W1-ALEMBIC waits on W1-SPIKE; the rest are mutually parallel)
  W1-ALEMBIC     Alembic; per-tenant baseline (factory/line/machine/telemetry/CAGG); public = tenant/app_user/membership; sdf_default retire; seed rename
        │
        ▼
Wave 2 — BCs & routing (parallel)
  W2-ID    identity BC                          [needs W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD]
  W2-TEN   tenancy BC + onboarding + POST /tenants (NO authz AC here — see W3-RBAC)  [needs W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD, W1-SPIKE]
  W2-ING   ingest per-tenant search_path routing + local machine resolve  [needs W1-ALEMBIC, W1-SCAFFOLD]
  W2-FORMAL  monitoring/topology formalization + tenant-scoped readers + WS poller tenant-aware  [needs W1-SCAFFOLD]
        │             │
        ▼             ▼
Wave 3 — Cross-BC & enforcement (parallel)
  W3-RBAC   token→request→DB-session tenant-context seam; auth dependency; operator read-only 403; POST /tenants ⇒ tenant-admin
  W3-OEE    cross-BC enterprise-OEE use case (pure averaging + integration-only UNION ALL over per-tenant CAGGs)
        │
        ▼
Wave 4 — Dogfood demo data
  W4-SEED   create kr/us/in via POST /tenants; real-plant scenarios (Ulsan / HMGMA / Chennai); end-to-end routing verified
        │
        ▼
Wave 5 — Deploy
  W5-DEPLOY  docker-compose.prod.yml (root) + Cloudflare Tunnel + JWT-secret custody + always-on sims + retention + UptimeRobot + rollback
             └─ mid-phase ADR: deploy platform (Hetzner CX32 vs Oracle Free)
        │
        ▼
Phase-end — Promote / living-doc
  P-PROMOTE  UC registry status notes (backend-verified; full `implemented` → Plan B); KNOWN-UNKNOWNS resolutions
```

**Critical path:** Ch0 → W1-SPIKE → W1-ALEMBIC → W2-TEN → W4-SEED → W5-DEPLOY.

---

## 4. Chapter 0 batch (lands first — no implementation commit before this completes)

> Per `phase-iteration.md`: **Create** tasks, all ahead of Wave 1. ADRs are the spine; author them first or with a shared decision sheet. Each ADR/UC/glossary lands as its own commit.

> **Commit-order note (git-log shape):** the Phase-1 plan still sits un-archived in `docs/plans/`. Before landing Phase-2 Chapter 0, confirm whether the Phase-1 plan is archived first (per the phase-tag convention) so Phase-2 Ch0 commits open a clean chapter in `git log`. Sequencing confirmation, not a content change.

### C0-ADR — Decision records
Next free number is **0033** (existing run 0000–0032; **0028–0032 are the frontend/lint ADRs that merged *after* this plan landed** — PRs #17–#19 — so the originally-reserved 0028–0033 block shifted +5 to **0033–0038**; gaps at 0013–0015 are fine).

| ADR | Topic | Must record |
|---|---|---|
| 0033 | Identity & auth model | hand-rolled JWT (PyJWT) + argon2 (**cost params**); membership many-to-many, per-(user,tenant) role; roles = operator/tenant-admin (**no A-IE**); §13.2 "viewer" → operator read-only; crypto+token sign/verify in adapters, pure `can()`; **active tenant = JWT claim** (additive); **signing-key custody** (injected secret, never committed, rotation posture). Public `admin_demo`/persona-picker/admin-UI = Phase 2b, not Plan A |
| 0034 | BC formalization outcome | extract `tenancy`+`identity`; make `monitoring`/`topology` explicit; relation to ADR-0008 + ADR-0009; cross-BC via `use_cases/` + in-process `DomainEventDispatcher`. **Note:** ADR-0009's `contexts/<bc>/ports.py` is read as `ports/<noun>.py` per ADR-0022 (don't edit 0009) |
| 0035 | Multi-schema persistence & tenant data isolation | Alembic multi-schema migrations replace raw `001`–`005` as schema SoT; **per-tenant data boundary — `factory`/`production_line`/`machine` live in the tenant schema; `public` holds only `tenant`/`app_user`/`membership`** → **this ADR supersedes ADR-0003's "shared relational metadata lives in `public`" clause** (schema-per-tenant core + RLS-rejection retained; mark ADR-0003 status "partially superseded by ADR-0035"); **per-tenant CAGG = local join** (primary); **(A) denormalize `line_id` into `machine_telemetry`** documented as the *secondary* fallback if per-tenant proves hard (author decides post-W1-SPIKE); **connection-level `search_path` safety**; **idempotent rerunnable onboarding** + DDL-autocommit reality (supersedes ADR-0003's "single transactional sequence" wording via an in-ADR note); **`sdf_default` retired** (kr/Ulsan onboarded fresh) |
| 0036 | MachineKind automotive 5-shop taxonomy | `stamping/body/paint/assembly/inspection`; `machineKey` stays free string ⇒ no enum/codegen change; enum in domain only; seed/simulator machineKeys + `sparkplug_node_id` `<type>` segment change in lockstep |
| 0037 | Cross-tenant thin enterprise-OEE scope | one cross-BC use case, `UNION ALL` over member tenants' (local-join) CAGGs, membership-driven authz, **no new role**; reframes ADR-0003's "Phase 3+ aggregator" as the *general* analytics layer; **does NOT supersede ADR-0003's core** |
| 0038 | Seeded-credential → role mapping + Cloudflare single-stack | Plan A: backend operator + tenant-admin roles; dogfooding tenant-admin seed account; public `op_demo`/`admin_demo` exposure deferred (addendum §3.3 — `op_demo` Phase 2 public is a Plan-B/README concern); Cloudflare Tunnel single-stack posture (addendum §5) |

> **Mid-phase ADRs (NOT Ch0):** deploy platform (Hetzner CX32 vs Oracle Free) at W5-DEPLOY; CAGG-fallback pivot *iff* W1-SPIKE forces (A) or another design. Numbered **0039+** at decision time.

**AC (C0-ADR):**
- [ ] Each ADR follows `docs/ADR/template.md`; status `Accepted`; cross-references scope doc + extended/superseded ADRs.
- [ ] ADR-0033 resolves §13.2 viewer→operator-read-only, specifies JWT-claim tenant scoping, signing-key custody, argon2 cost params, and that A-IE + public `admin_demo` are out of Plan A.
- [ ] ADR-0035 records the per-tenant data boundary, **explicitly supersedes ADR-0003's metadata-placement clause** (and updates ADR-0003 status to "partially superseded"), states per-tenant CAGG = primary with (A) as documented fallback, connection-scoped `search_path`, idempotent onboarding (no "single transaction" claim), and `sdf_default` retirement.
- [ ] ADR-0037 does **not** supersede ADR-0003's core.
- [ ] ADR-0034 notes the stale ADR-0009 `ports.py` reference without editing 0009.
- [ ] No accepted ADR edited in place; supersede-only for reversals (the ADR-0003 supersede is a *new* ADR-0035 + a status flag on 0003).

### C0-UC — Use-case drafts (`status: draft`; E2E + promote → Plan B)
> **UC numbering (resolved):** UC-001/002 exist; Phase-2b reserves **UC-003** ("UC-003 E2E" in the scope doc). Plan A takes **UC-004/005/006**; one-line reservation note in `USE-CASES.md`.

| UC | Title | Primary actor | BC | Notes |
|---|---|---|---|---|
| UC-004 | Tenant admin onboards a new tenant (backend) | A-TA | tenancy | `POST /tenants` → schema+migrate+hypertable+CAGG; `related_e2e` declared, file in Plan B |
| UC-005 | Operator authenticates & is RBAC-scoped (operator read-only) | A-OP | identity | login → JWT (active-tenant claim) → tenant-scoped read; mutating → 403 |
| UC-006 | Operator queries cross-tenant enterprise OEE | A-OP | (cross-BC use case) | UNION-ALL over member tenants |

**AC (C0-UC):** `_TEMPLATE.md` structure; `status: draft`; exactly one `primary_actor`; `related_e2e` declared (file → Plan B); one registry row per file + UC-003-reserved note; `uv run scripts/check-use-case-coverage.py` green; Gherkin AC ready to become Plan B E2E verbatim.

### C0-GLOSS — Glossary
**AC:** `Tenant` flipped `proposed → accepted`; add `User`/`Membership`/`Role`/`Permission`/`EnterpriseOEE`/`MachineKind`/`SimulatorScenario`; `Machine` examples `press/weld/paint/inspect/pack` → `stamping/body/paint/assembly/inspection`; note `factory`/`line`/`machine` are per-tenant entities; Anti-Glossary check (identifiers match wording verbatim).

### C0-ACTORS — Actor catalog
**AC:** **Confirm only** — `A-OP`/`A-TA` already exist (Phase 1+/2+). No new rows for Plan A (A-IE excluded; A-SV/A-PE out). Record confirmation in the commit message.

### C0-DOMAIN — Domain notes (seed)
**AC:** seed sections for: automotive 5-shop line structure; per-site OT edge (N simulators, tenant from `group_id`); membership/RBAC; **the three real-plant tenants** (Ulsan / HMGMA / Chennai) and their operational-scenario differentiation; per-tenant data ownership (factory/line/machine).

### C0-UNKNOWNS — Known-unknowns (seed + living)
**AC:** seed entries for: deployment resource limits (addendum §8); deploy-platform decision *pending*; **per-tenant CAGG create/refresh on a fresh schema pending W1-SPIKE**; **5-shop abstraction vs real plant reality** (Ulsan/HMGMA/Chennai modeled on the same stamping→inspection abstraction; differentiation by scenario params only — an honest simplification); demo data-signal tuning.

---

## 5. Implementation waves

> Every task: working code + tests + green gates; obeys `.claude/rules/*`; contract changes precede consumers; one aggregate per transaction; sum-type errors; injected clock/UUID/random.

### Wave 1 — Foundations

#### W1-SPIKE — De-risk per-tenant CAGG on a freshly-onboarded schema (GATE)
**Depends on:** Ch0. **Gates:** W1-ALEMBIC, Wave 2. **Parallel with:** other W1.
**Nature:** throwaway de-risking probe (testcontainers integration test, discarded after the decision is recorded in ADR-0035).
**What it proves:** in a brand-new tenant schema, can the onboarding sequence create the hypertable + a `line_oee`-style CAGG (joining the **schema-local** `machine`) + a refresh policy, and read it back over `search_path` — reliably and idempotently? Secondary: if per-tenant `machine` hits an unforeseen snag, confirm whether fallback **(A)** (denormalized `line_id`, no join) would be needed.
**Acceptance Criteria:**
- [ ] Documented empirical answer: per-tenant CAGG (local join) creates + refreshes + reads on a fresh schema → primary design stands; or a snag → fallback **(A)** or an author decision is recorded.
- [ ] Outcome written into **ADR-0035**; any pivot from the per-tenant primary becomes a mid-phase ADR.
- [ ] Probe code removed (or quarantined under a clearly-throwaway path). **Discard verified:** a grep/CI assertion confirms no spike artifact leaks into `apps/*/tests/` or the CI default test run.

#### W1-CONTRACTS — Contract surface + regeneration
**Depends on:** Ch0 (ADR-0033/0037). **Parallel with:** other W1.
**Commit:** `feat(contracts): phase-2 auth, tenant onboarding, enterprise-OEE surfaces`
**Surface to add to `packages/contracts/openapi/sdf-api.yaml`** (described, not written):
- Auth: `POST /auth/login` (credentials → token whose claims include `sub` + active tenant + that tenant's role); tenant-switch surface re-issuing a token with a different active-tenant claim. **Active tenant = token claim; existing monitoring routes keep signatures (additive).**
- Tenancy: `POST /tenants` (tenant-admin only), `GET /tenants` (caller's member tenants).
- Cross-tenant: `GET /enterprise/oee`.
- Schemas: `LoginRequest`, `TokenResponse`, `TenantCreateRequest`, `TenantSummary`, `EnterpriseOee`, error envelopes.
- `machine_telemetry.schema.json`: **unchanged** (machineKey free string).
**Acceptance Criteria / tests:**
- [ ] `spectral lint` passes (pre-codegen).
- [ ] `make all` regenerates Pydantic v2 DTOs + TS types; `git diff --exit-code codegen/` clean (drift gate green).
- [ ] No hand-written FastAPI request/response model (consumers import generated DTOs).
- [ ] **`oasdiff breaking` vs `main` GREEN** — all surfaces additive; existing route signatures unchanged (tenant via claim).
- [ ] `machine_telemetry.schema.json` byte-identical.

#### W1-SCAFFOLD — Composition root, cross-BC seam, **pool `search_path` safety**, fitness gates
**Depends on:** Ch0 (ADR-0034/0035). **Parallel with:** other W1.
**Commit(s):** `feat(api): composition root + use_cases seam + DomainEventDispatcher`; `feat(api): connection-scoped search_path on the asyncpg pool`; `chore(api): extend fitness gates for new BCs + use_cases`.
**Scaffolding:**
- `src/sdf_api/composition.py` — extract DI wiring from `app.py` (`_make_router` wires inline today); `app.py` keeps only HTTP/WS routing. Only place `cast(...)` acknowledges structural Port matches and the `uow.session`/pool escape hatch may appear (AST A3).
- `src/sdf_api/use_cases/` — top-level cross-BC package (first module in W3-OEE).
- `src/sdf_api/shared_kernel/events.py` — hand-rolled `DomainEventDispatcher` (fail-fast; no swallow; no library). Add `shared_kernel/ports/uuid.py`/`random.py` iff a new BC needs injected UUID/random.
- **Pool `search_path` safety (BLOCKER-2):** the shared `asyncpg` pool (`app.py:141`, `ingest/main.py`) must guarantee a connection never carries a prior tenant's `search_path` — `SET LOCAL search_path` in a per-operation txn, or pool acquire/`setup` reset (decided in ADR-0035). Composition-owned.
- Per-BC `ports/unit_of_work.py` Protocol pattern (each BC owns its UoW — ADR-0020); new `tests/contexts/<bc>/fakes.py` per BC.
**Fitness-gate extension (this task owns the edits):** add `tenancy`+`identity` to `bc-independence`; add **`use-cases-no-domain-or-adapters`** (ADR-0023 #4); add `sdf_api.use_cases` to `adapters-no-upward`; AST A1/A2/A3 cover new BC domains/UoWs.
**Acceptance Criteria / tests:**
- [ ] `import-linter` green; a deliberate forbidden import (e.g., `identity.domain` → `tenancy`) **fails** `bc-independence`.
- [ ] **No-leak test (BLOCKER-2):** acquire conn, `SET search_path='kr'`, release; next acquisition observes default `public` — asserted (testcontainers, CI).
- [ ] `DomainEventDispatcher`: registered handler invoked; raising handler propagates (fail-fast).
- [ ] `app.py` constructs no adapters inline; `composition.py` sole adapter importer.
- [ ] `use_cases/` imports under `mypy --strict`; new contract active + green.

#### W1-CI — CI integration job
**Depends on:** Ch0. **Parallel with:** other W1.
**Commit:** `ci: add Postgres+Timescale integration job; wire new lint contracts`
**Scaffolding:** extend `.github/workflows/ci.yml` (today: ruff/lint-imports/mypy/pytest unit, Kotlin, UC-coverage gate — **no integration job**). Add a Postgres+TimescaleDB integration job (`services:` Timescale image or Docker-in-CI for testcontainers) so `apps/api-python/tests/integration` + `apps/ingest-python` integration tests run **in CI**.
**Acceptance Criteria:** onboarding/idempotency, tenant-isolation, no-leak, search_path-routing, per-tenant-CAGG tests run + pass in CI; DoD's "full CI gate set green" true for the safety-critical tier; path-correct for both Python apps.

#### W1-EDGE — Kotlin edge: multi-tenant bridge + 5-shop simulator + scenarios
**Depends on:** Ch0 (ADR-0036). **Parallel with:** all Python W1.
**Commit(s):** `feat(edge): derive tenant from Sparkplug group_id`; `refactor(edge): MachineKind 5-shop machine list`; `feat(edge): per-tenant SimulatorScenario config`.
**Scaffolding:** `bridge/` derives tenant from `group_id` (replacing the `SDF_DEFAULT_TENANT` constant); topic `sdf.${tenantId}.machine.telemetry`, key `${lineId}/${machineKey}` kept. `simulator/Main.kt` `MACHINE_TYPES` → 5-shop; `SimulatorScenario` config (takt/cycle-time, shift, failure/quality/alarm) by env. No `System.currentTimeMillis()`/`Instant.now()` in any Kotlin domain (K1).
**Acceptance Criteria / tests:**
- [ ] Bridge unit test (table-driven kr/us/in): `group_id="kr"` → tenant/topic `kr`; no env constant.
- [ ] Simulator emits the 5-shop set; test asserts list = taxonomy (parity with W1-MK-PY) **and** the `<type>` segment of `sparkplug_node_id` matches.
- [ ] Two distinct `SimulatorScenario`s → measurably different telemetry (deterministic seeded test, injected randomness).
- [ ] `gradle test` + `ktlint` + `detekt` green; Konsist K1/K2 unaffected.

#### W1-MK-PY — Python MachineKind 5-shop rename (domain)
**Depends on:** Ch0 (ADR-0036, C0-GLOSS). **Parallel with:** other W1 (touches `topology/domain/machine.py` + tests only).
**Commit:** `refactor(api): MachineKind → automotive 5-shop taxonomy`
**AC:** `test_machine.py` updated; every variant + exhaustiveness covered; no old name in `sdf_api` (grep); domain purity gates green; glossary wording matches enum verbatim. *(Seed-SQL machine rename owned by W1-ALEMBIC.)*

#### W1-ALEMBIC — Alembic multi-schema migration foundation
**Depends on:** **W1-SPIKE**, Ch0 (ADR-0035). **Parallel with:** other W1 after the spike resolves.
**Commit:** `feat(api): Alembic multi-schema migrations + per-tenant baseline + public registry`
**Scaffolding:**
- `apps/api-python/alembic.ini`, `migrations/env.py` (search_path-aware), `migrations/versions/`.
- **Per-tenant baseline:** `factory`, `production_line`, `machine` (now per-tenant), `machine_telemetry`/`line_state` hypertables, `line_oee` CAGG (local join, per the W1-SPIKE outcome). `machine.sparkplug_node_id` uniqueness is now per-schema.
- **Public baseline:** `public.tenant` (slug, schema_name, region, tz, locale, created_at), `public.app_user` (id, credential hash), `public.membership(user_id, tenant_id, role)` — `(user_id, tenant_id)` unique + role-constrained + FKs. **No domain tables in `public`.**
- **`sdf_default` retired:** `001` (extensions) + the public baseline remain as bootstrap; `002`–`005` per-tenant/seed raw SQL is superseded by Alembic + W4-SEED; `kr`/Ulsan is onboarded fresh.
- **Seed machine-name rename (MAJOR-C):** the seed machine rows (`press/...`, column **`type`**, `sparkplug_node_id` embedding `<type>`) → 5-shop, in lockstep with W1-MK-PY/W1-EDGE.
**Acceptance Criteria / tests (CI integration):**
- [ ] `alembic upgrade head` on an empty tenant schema reproduces the per-tenant object set (hypertable + local-join CAGG; verified via `timescaledb_information`).
- [ ] `upgrade head` twice = no-op; mid-sequence failure + re-run converges.
- [ ] `public` has only `tenant`/`app_user`/`membership` (+ extensions) with stated constraints; `downgrade` defined.
- [ ] `sdf_default` is gone; no leftover ambiguous raw-init.
- [ ] Seed machine rows use 5-shop names; `sparkplug_node_id` `<type>` matches the simulator.

### Wave 2 — Bounded contexts & routing (parallel)

#### W2-ID — Identity BC
**Depends on:** W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD. **Parallel with:** W2-TEN/ING/FORMAL.
**Commit(s):** `feat(api): identity domain (can/Allowed/Denied)`; `feat(api): identity adapters (PyJWT, argon2, Pg user/membership repo)`; `feat(api): identity application (authenticate/authorize)`.
**Scaffolding:**
- `contexts/identity/domain/` — `User`, `Role` (operator | tenant-admin), `Permission`, pure `can(action, role) -> Allowed | Denied`. Frozen dataclasses; no crypto/datetime.now.
- `contexts/identity/ports/` — `user_reader.py`, `membership_reader.py`, `token_port.py`, `password_hasher.py`, `unit_of_work.py`.
- `contexts/identity/adapters/` — `PostgresUserRepo`, `PostgresMembershipRepo` (ORM-contained), `PyJwtTokenAdapter` (alg allow-list; mandatory claims incl. active tenant; **injected signing key**), `Argon2PasswordHasher` (cost params per ADR-0033). Pydantic only at `adapters/http/`.
- `contexts/identity/application/` — `authenticate`, `authorize_tenant_access`.
- `tests/contexts/identity/fakes.py` — `IdentityInMemoryDataset`, `FakeUnitOfWork`, fake token/hasher honoring real-adapter rules.
**Acceptance Criteria / tests:**
- [ ] **Domain (pure, zero mocks):** `can()` per (role × action) → exact variant; operator-mutating → `Denied`. Property test.
- [ ] **JWT adapter (security negative set):** tampered signature, `alg:none`, expired (`exp` past via `FixedClock`), missing `sub`/active-tenant, cross-tenant claim → all rejected with named failures; signing key injected (fixture, no hardcoded secret).
- [ ] **Password:** argon2 verifies correct, rejects wrong; domain has no argon2 import (gate green).
- [ ] **Application (in-memory dataset):** `authenticate` → token with `{sub, active tenant, role}`; `authorize_tenant_access` denies a non-member tenant; assert on dataset/variant, not call patterns (ADR-0024).
- [ ] **Membership:** per-(user,tenant) role independent (operator in `kr`, tenant-admin in `us`).
- [ ] `bc-independence`: `identity` imports no other BC domain.

#### W2-TEN — Tenancy BC + onboarding + `POST /tenants`
**Depends on:** W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD, **W1-SPIKE**. **Parallel with:** W2-ID.
**Commit(s):** `feat(api): tenancy domain (Tenant, SchemaName VO)`; `feat(api): tenancy onboarding adapter (schema+migrate+hypertable+CAGG)`; `feat(api): POST /tenants application + wiring`.
**Scaffolding:**
- `contexts/tenancy/domain/` — `Tenant` (slug, schema-name VO, region/tz/locale); `SchemaName` VO (safe identifier; reject injection as `Rejected`, not raise); onboarding outcome `Onboarded | Rejected(reason) | AlreadyExists`.
- `contexts/tenancy/ports/` — `tenant_registry.py`, `schema_provisioner.py` (create schema + Alembic over search_path + hypertable + **per-tenant CAGG**), `unit_of_work.py`.
- `contexts/tenancy/adapters/` — `PostgresTenantRegistry`, `AlembicSchemaProvisioner` (idempotent steps; connection-scoped search_path).
- `contexts/tenancy/application/` — `onboard_tenant` (idempotent, rerunnable; multi-step DDL per ADR-0035).
**Acceptance Criteria / tests:**
- [ ] **Domain (pure):** `SchemaName` rejects unsafe identifiers (`Rejected`); property test over slug inputs.
- [ ] **Integration (CI):** `POST /tenants` for `kr` creates schema `kr`, runs `upgrade head`, creates per-tenant hypertable + local-join CAGG, registers `public.tenant`; verified via `timescaledb_information`.
- [ ] **Idempotency:** second call → `AlreadyExists`; fault after `CREATE SCHEMA` before CAGG, then re-run → converges.
- [ ] **Isolation:** onboarding `us` does not alter `kr`'s objects.
- [ ] `bc-independence`: `tenancy` imports no other BC domain.
- [ ] **DoD note:** the tenant-admin **403/2xx authz** check is **NOT** in this task (depends on W3-RBAC). Endpoint onboards correctly; authz asserted in W3-RBAC. *(MAJOR-4)*

#### W2-ING — Ingest per-tenant `search_path` routing (local machine resolve)
**Depends on:** W1-ALEMBIC, W1-SCAFFOLD (pool-safety). **Parallel with:** W2-ID/TEN/FORMAL.
**Commit:** `feat(ingest): route telemetry per-tenant via connection-scoped search_path`
**Scaffolding:** `ingest/adapters/writer.py` + `line_state_writer.py` set `search_path` per connection-scoped operation (no leak); remove the single-public-schema path. `adapters/resolver.py` — `MachineResolver` now resolves machine **within the tenant schema** (local, via search_path — no cross-schema reach), keyed by `{lineId}/{machineKey}`; cache per tenant. Unresolved tenant → structured log + drop/park (never `public`).
**Acceptance Criteria / tests (CI integration):**
- [ ] A `kr` telemetry record is written into schema `kr`, **absent** from `us`/`public`.
- [ ] **No-leak:** interleaved `kr` then `us` writes on a reused pooled connection land correctly (W1-SCAFFOLD mechanism).
- [ ] Unresolvable tenant → no public write; structured log/metric.
- [ ] Normalization/domain (`domain/record.py`, `line_activity.py`) unchanged (pure).
- [ ] Per-tenant ingest counter exposed.

#### W2-FORMAL — monitoring/topology formalization + tenant-aware readers & WS poller
**Depends on:** W1-SCAFFOLD. **Parallel with:** other W2.
**Commit:** `refactor(api): formalize monitoring/topology; tenant-scope readers and WS poller`
**Scaffolding:**
- Add `topology/ports/` + `topology/adapters/` for per-tenant topology reads (factory/line/machine now live in the tenant schema → reads are local via search_path).
- monitoring Pg readers (`monitoring/adapters/db.py` — unqualified `_OEE_QUERY`/`PgLineStateReader`) tenant-aware via connection-scoped `search_path`.
- **WS poller (BLOCKER-3):** `app.py:_poll_line_state` (~107–135) runs a global unqualified `line_state` query fanning to **all** subscribers. This task owns making it tenant-aware (per-tenant poll loop or tenant-tagged broadcast filtered by each subscriber's active-tenant claim).
- Expose cross-BC OEE need via `monitoring/ports/oee.py` reader contracts.
**Acceptance Criteria / tests (CI integration):**
- [ ] monitoring line-state / OEE reads scoped to the caller's active tenant (same line id in `kr` vs `us` → respective data).
- [ ] **WS isolation:** a `kr`-scoped subscriber receives **only** `kr` frames, never `us`/`in`.
- [ ] `bc-independence` + `adapters-no-upward` green.
- [ ] UC-001/UC-002 behavior preserved for the active tenant (regression: existing monitoring tests green, adjusted only for the tenant parameter, **not weakened**).

### Wave 3 — Cross-BC & enforcement (parallel)

#### W3-RBAC — Tenant-context seam + authentication & authorization
**Depends on:** W2-ID, W2-TEN, W2-FORMAL. **Parallel with:** W3-OEE.
**Commit(s):** `feat(api): request-scoped tenant context (token→session)`; `feat(api): JWT auth dependency + RBAC enforcement`.
**Scaffolding:**
- **Token→request→DB-session seam (MAJOR-6):** a FastAPI dependency decodes+validates the bearer token (via the identity port), establishes a **request-scoped tenant context** (`contextvar`/`request.state`) the composition root reads to scope the DB session's `search_path`. Lives at composition/boundary (escape hatch — A3); reuses the W1-SCAFFOLD mechanism.
- RBAC: authorize the active tenant against memberships; operator = read-only (every mutating endpoint requires non-operator). Sum-type → `HTTPException` at the boundary only.
**Acceptance Criteria / tests (CI integration):**
- [ ] Missing/invalid token → 401; valid token, non-member tenant → 403.
- [ ] **operator read-only:** every mutating endpoint returns **403** for an operator token (parametrized over the full mutating-endpoint list).
- [ ] **`POST /tenants` requires tenant-admin** (operator → 403; tenant-admin → 2xx) — *the authz AC moved from W2-TEN (MAJOR-4)*.
- [ ] Tenant re-scoping: a token scoped to `kr` cannot read `us` data (seam verified end-to-end).
- [ ] `/healthz`, `/readyz` unauthenticated.

#### W3-OEE — Cross-BC enterprise-OEE use case
**Depends on:** W2-ID, W2-TEN, W2-FORMAL, W1-CONTRACTS. **Parallel with:** W3-RBAC.
**Commit:** `feat(api): cross-tenant enterprise-OEE use case (member-scoped average)`
**Scaffolding:**
- `src/sdf_api/use_cases/enterprise_oee.py` — cross-BC use case importing `identity` (membership) + an OEE reader **port**; **averaging logic is pure** (over a `list[per-tenant OEE]` returned by the port).
- The **cross-schema `UNION ALL` SQL** lives in a dedicated reader **adapter** behind a port (composition-wired); each per-tenant CAGG is a clean local join (per §0.2), and the reader UNION-ALLs their outputs. Port returns `list[per-tenant OEE]` (MAJOR-9).
**Acceptance Criteria / tests:**
- [ ] **Use-case test (per-BC in-memory datasets, never shared):** caller with {kr, us} → average over kr+us; `in` excluded. Pure averaging asserted on the read model.
- [ ] **Integration (CI):** with kr/us/in seeded, the endpoint returns the member-scoped average; the **cross-schema UNION-ALL SQL is integration-tested only**.
- [ ] No new role (membership-driven authz) — verify against ADR-0037.
- [ ] `use-cases-no-domain-or-adapters` + `bc-independence` green.

### Wave 4 — Dogfood demo data

#### W4-SEED — Create kr/us/in via dogfooding + real-plant scenarios
**Depends on:** W2-TEN, W2-ING, W1-EDGE, W3-RBAC.
**Commit(s):** `feat: seed kr/us/in tenants via POST /tenants`; `feat(edge): per-tenant simulator scenarios (Ulsan / HMGMA / Chennai)`.
**Scaffolding:**
- A bootstrap script (not raw SQL) calling `POST /tenants` for `kr`/`us`/`in` as a tenant-admin, then seeding each tenant's factory/line/machine topology + persona accounts + memberships.
- The three factories carry real plant identity (name, region, tz, locale): **`kr` = Ulsan** (Asia/Seoul, ko-KR), **`us` = HMGMA, Georgia** (America/New_York, en-US), **`in` = Chennai/HMIL** (Asia/Kolkata, en-IN).
- Three `SimulatorScenario`s — common full 5-shop line everywhere; differentiate by **operational scenario grounded in the real plants**: Ulsan = mature high-volume, high stable OEE; HMGMA = new EV metaplant ramp-up, lower/improving OEE with teething; Chennai = mature ultra-high-volume, cost-optimized emerging-market profile (distinct product/cost story). Differentiate also by scale (line/station/machine counts) + shift/tz/locale. **No "one process per factory."**
- Persona accounts (operator, tenant-admin) with memberships spanning kr/us/in (addendum §3.3/§5). *(Public credential exposure / persona picker → Plan B / Phase 2b.)*
**Acceptance Criteria / tests:**
- [ ] A fresh stack + seed yields exactly 3 tenant schemas, each via `POST /tenants` (not hand-built); rerun idempotent.
- [ ] Each tenant runs the full 5-shop line; the three scenarios produce **distinguishable** steady-state OEE (asserted to differ beyond noise — Ulsan/HMGMA/Chennai tell distinct stories).
- [ ] One operator + one tenant-admin account hold memberships across kr/us/in; enterprise-OEE for that operator spans all three.
- [ ] **Domain-reasonableness review** (`architect`/human): seeded takt/failure/OEE plausible per ISO 22400 and per each plant's profile.

### Wave 5 — Deploy

#### W5-DEPLOY — Backend public deploy (no FE)
**Depends on:** W4-SEED. **Last wave.**
**Commit(s):** `docs(adr): deploy platform decision`; `feat(deploy): docker-compose.prod.yml + Cloudflare Tunnel + JWT secret + always-on simulators`; `feat(ops): retention + UptimeRobot monitor`.
**Scaffolding:**
- **Mid-phase ADR (platform):** Hetzner CX32 vs Oracle Free — decision + rationale + conditional multi-arch/ARM build branch (only if Oracle).
- `docker-compose.prod.yml` **at repo root** (matching `docker-compose.yml`) — prod profile: timescale, broker, ingest, api, **3 per-tenant simulators (kr/us/in)**, bridge, Cloudflare Tunnel sidecar. **Remove the nonexistent dashboard build target** (`docker-compose.yml:101-102`).
- **JWT signing-key custody (BLOCKER-A):** injected secret (env/mounted file), never committed; documented in compose/ops + ADR-0033.
- `restart: unless-stopped` on simulators; 7-day TimescaleDB retention; Cloudflare Tunnel config; UptimeRobot monitor on API health + down-alert.
- **Rollback note (MAJOR-D):** failed Tunnel/compose cutover; disposition of a tenant onboarded with a broken schema in prod.
**Acceptance Criteria / tests:**
- [ ] `docker compose -f docker-compose.prod.yml config` validates; no nonexistent build target.
- [ ] API reachable over HTTPS (valid cert) via Cloudflare Tunnel (smoke evidence).
- [ ] JWT signing key from an injected secret; grep AC: no secret literal committed.
- [ ] Per-tenant simulators `restart: unless-stopped`; recover after a simulated kill.
- [ ] 7-day retention policy present + verified.
- [ ] UptimeRobot monitor + down-alert (config/screenshot evidence).
- [ ] Platform ADR + rollback note committed before platform-specific compose/build lands.

### Phase-end — Promote / living-doc

#### P-PROMOTE — Status changes & resolutions
**Depends on:** all implementation waves.
**Commit:** `docs: phase-2a status notes + known-unknowns resolutions`
**AC:**
- [ ] UC-004/005/006 rows annotated **backend-verified**; full `status: implemented` **deferred to Plan B** (coverage gate needs an existing `related_e2e` file). Do not flip now.
- [ ] KNOWN-UNKNOWNS: platform decision resolved (→ platform ADR); per-tenant CAGG resolved (→ W1-SPIKE/ADR-0035); 5-shop-abstraction-vs-real-plant note kept; demo data-signal tuning updated.
- [ ] `uv run scripts/check-use-case-coverage.py` green.

---

## 6. Expanded Test Plan (deliberate mode)

| Tier | Coverage | Where (runs in) | Gate |
|---|---|---|---|
| **Unit / domain (pure, zero mocks)** | `can()` per role×action; `SchemaName`/onboarding sum types; `MachineKind` exhaustiveness; JWT-claim domain rules; DomainEventDispatcher fail-fast | `tests/contexts/*/domain/`, `tests/shared_kernel/` — CI unit | pytest; import-linter domain-purity; AST A1/A2 |
| **Use-case (per-BC in-memory dataset)** | authenticate/authorize; onboard_tenant; enterprise-OEE pure averaging | `tests/contexts/*/application/`, `tests/use_cases/` — CI unit | `use-cases-no-domain-or-adapters`; one dataset per BC |
| **Integration (testcontainers Postgres+Timescale)** | onboarding + idempotency; **per-tenant CAGG create/refresh**; **search_path no-leak**; ingest per-tenant routing isolation; tenant-scoped reads + **WS isolation**; enterprise-OEE UNION ALL; RBAC 401/403 matrix | `tests/integration/` — **CI integration job (W1-CI), NOT local-only** | testcontainers only here |
| **Security (negative)** | tampered/`alg:none`/expired/missing-claim/cross-tenant tokens; argon2 wrong-password; **signing-key not committed**; operator-mutating 403 matrix; `SchemaName` injection rejection | identity adapter + API integration — CI | `security-reviewer` phase-end |
| **Contract** | spectral lint; codegen drift; **`oasdiff breaking` (blocking, expected GREEN — additive)**; machine_telemetry unchanged | `packages/contracts` `make verify` + CI | contract-first §3 |
| **Architecture/fitness** | extended import-linter (new BCs, use_cases); Konsist K1/K2; AST A1–A3 | `tests/architecture/`, Konsist — CI | no opt-outs |
| **Observability** | per-tenant ingest counter; unresolved-tenant alert/log; API health; UptimeRobot; always-on simulator restart | ingest + deploy | W2-ING + W5-DEPLOY |
| **De-risking probe** | per-tenant CAGG feasibility on a fresh schema (throwaway) | W1-SPIKE (discarded) | ADR-0035 outcome |
| **E2E (Gherkin)** | UC-004/005/006 acceptance scenarios authored in Ch0 | **deferred to Plan B** | Plan B coverage gate |

---

## 7. Global Acceptance Criteria

- [ ] 3 tenant schemas (`kr`/Ulsan, `us`/HMGMA, `in`/Chennai) created **by dogfooding `POST /tenants`** via an **idempotent, rerunnable** sequence (not one DB transaction); `sdf_default` retired.
- [ ] Domain tables (factory/line/machine + telemetry/state + CAGG) are **per-tenant**; `public` holds only tenant/app_user/membership (ADR-0035 supersedes ADR-0003 metadata clause).
- [ ] Ingest routes telemetry into the correct tenant schema via **connection-scoped** `search_path` (no pool leak); machine resolved locally.
- [ ] `tenancy`/`identity` BCs formalized; monitoring/topology explicit (incl. tenant-aware WS poller); cross-BC `use_cases/` + `DomainEventDispatcher` wired; fitness gates extended & green.
- [ ] Hand-rolled JWT (issue/verify, injected signing key) + argon2; pure `identity` `can()`; zero auth library.
- [ ] `public.app_user` + `public.membership`; per-(user,tenant) role; persona accounts seeded across kr/us/in.
- [ ] operator read-only (every mutating endpoint 403); `POST /tenants` requires tenant-admin.
- [ ] Cross-tenant enterprise-OEE endpoint returns the member-scoped UNION-ALL average over per-tenant CAGGs.
- [ ] `MachineKind` = 5-shop; enum + simulator + **seed** + GLOSSARY/DOMAIN-NOTES updated; Kafka contract unchanged; codegen drift green.
- [ ] 3 per-tenant simulators (kr/us/in) run; bridge derives tenant from `group_id`; each encodes a distinct real-plant operational scenario.
- [ ] All new REST surfaces contract-first + **additive** (oasdiff blocking, green); no hand-written request/response models.
- [ ] Backend deploy: prod compose (root) + Cloudflare Tunnel; HTTPS reachable; **JWT secret injected, not committed**; always-on simulators; 7-day retention; UptimeRobot + alert; rollback note.
- [ ] CI green incl. the **integration job**: mypy strict, ruff, import-linter (new contracts), AST, Konsist/detekt/ktlint, contract drift, all test tiers.
- [ ] Chapter 0 batch landed first (ADR-0000).

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Per-tenant CAGG can't create/refresh on a fresh onboarded schema | Low-Med | High | **W1-SPIKE** before baseline; per-tenant local join is the low-risk primary; (A) denormalize as documented 2nd fallback; author decides post-spike | W1-SPIKE, W1-ALEMBIC |
| `search_path` leaks across pooled connections | Med | High | Connection-scoped `SET LOCAL`/pool reset; **no-leak integration AC in CI** | W1-SCAFFOLD, W2-ING/FORMAL |
| WS poller broadcasts all tenants | Med | High | Tenant-aware poller; WS isolation AC | W2-FORMAL |
| Half-applied onboarding (DDL autocommit) | Med | High | Idempotent/rerunnable; fault-injection test; ADR-0035; rollback note | W2-TEN, W1-ALEMBIC |
| Hand-rolled JWT forgery | Med | High | Alg allow-list, mandatory claims, negative test set, `security-reviewer` | W2-ID, W3-RBAC |
| JWT signing-key leaked/committed | Med | High | Injected secret; ADR-0033; grep AC | W2-ID, W5-DEPLOY |
| Isolation tests run only locally | Med | High | **W1-CI** integration job | W1-CI |
| ADR-0003 supersede done carelessly (orphaned references) | Low | Med | ADR-0035 explicitly supersedes the metadata clause + flips ADR-0003 status; grep for stale `public.machine` refs | C0-ADR, W1-ALEMBIC |
| Existing-route tenant scoping breaks blocking oasdiff | Low-Med | Med | Tenant via **JWT claim** (additive) | W1-CONTRACTS |
| Real-plant 5-shop abstraction reads as inaccurate | Low | Low-Med | KNOWN-UNKNOWNS note (honest simplification); scenario params, not fake processes | C0-UNKNOWNS, W4-SEED |
| Demo OEE stories indistinguishable / implausible | Med | Med | Distinct-OEE assertion + domain-reasonableness review | W4-SEED |
| Platform (Oracle ARM) needs multi-arch build | Med | Low-Med | Conditional multi-arch branch; mid-phase platform ADR | W5-DEPLOY |

---

## 9. Verification Steps (phase-level)

1. `cd packages/contracts && make verify` → spectral + drift + **oasdiff (blocking, green)**.
2. `cd apps/api-python` → `uv run mypy --strict`, `ruff check`, `lint-imports` (extended), `pytest` (domain + application + architecture). Integration tier runs in CI via W1-CI; locally `pytest tests/integration` when Docker is available.
3. `cd apps/ingest-python` → `pytest` incl. integration routing + no-leak (CI integration job).
4. `cd apps/ot-gateway-kotlin` → `./gradlew test ktlintCheck detekt`; Konsist green.
5. `uv run scripts/check-use-case-coverage.py` → UC registry consistent.
6. Stand up `docker-compose.prod.yml` (root); dogfood-seed kr/us/in; hit `/auth/login`, tenant-scoped reads, WS (single-tenant frames), `POST /tenants` (RBAC matrix), `/enterprise/oee`; confirm HTTPS via Tunnel + UptimeRobot; confirm JWT secret is injected (not in the repo).
7. `security-reviewer` pass on auth + key custody; `code-reviewer` pass on the phase diff.
8. Confirm the `ci.yml` integration job ran the isolation/no-leak/onboarding/per-tenant-CAGG tests green.
9. Confirm `git log --oneline` shows Chapter 0 first, then waves, then promote/living-doc.

---

## 10. ADR (consensus decision record for this plan)

- **Decision:** Execute Phase-2a as **Option A — backend-complete-then-deploy with BC-parallel waves and a Wave-1 de-risking spike**, on a **per-tenant data boundary** (factory/line/machine in the tenant schema; `public` = tenant/app_user/membership), with three real-plant tenants (Ulsan/HMGMA/Chennai).
- **Drivers:** (1) Plan B needs a frozen, contract-clean, additively-evolved API; (2) auth + onboarding are the highest-risk subsystems — and the per-tenant `machine` decision *removes* the cross-schema-CAGG risk (local join), leaving the spike to confirm per-schema CAGG creation/refresh; (3) `bc-independence` enables real identity∥tenancy parallelism.
- **Alternatives considered:** B walking-skeleton (rejected as a strategy; risk-retirement virtue absorbed via W1-SPIKE); C strict-sequential BCs (rejected — forfeits independence-guaranteed parallelism). For data placement: keeping `machine` in `public` + a cross-schema CAGG (rejected as primary — leaves cross-schema reads everywhere and risks a CAGG that can't be created/isolated; "preserving ADR-0003" is not a real advantage when the clause wasn't deeply reasoned for `machine`); (A) denormalization (kept as secondary fallback only).
- **Why chosen:** Option A satisfies all three drivers without violating the scope-doc lock; the per-tenant boundary is the domain-correct placement (machine is tenant-owned), makes CAGGs clean local joins, and the superseding ADR is itself the engineering-judgment signal.
- **Consequences:** no end-to-end signal until W4 (mitigated by spike + front-loaded contracts + CI gates); ADR-0003's metadata clause is superseded (clean supersede, status-flagged, no in-place edit); the implementing session must respect wave ordering (spike→Alembic, W2-TEN authz→W3) for DoD honesty.
- **Follow-ups:** mid-phase platform ADR + (conditional) CAGG-fallback ADR; Plan B (FE + FE deploy + public credential exposure + persona picker) consumes the frozen API + Ch0 Gherkin ACs; Phase 2b deferred.

---

## 11. Changelog (consensus review + author decisions)

**Consensus loop:** Planner draft → Architect (APPROVE-WITH-CHANGES, 3 blockers / 6 majors / 4 minors) → Critic (REVISE; confirmed all 13 + added 6) → revision (iteration 2) → Critic **APPROVED** (18/18 resolved against live source; W1-SPIKE↔Ch0 coherence holds; deliberate gates satisfied). Blockers B1–B3 + A–B and majors 4–9 + C–D + minors 10–13 all applied (search_path no-leak, WS poller, cross-schema CAGG spike, JWT key custody, CI integration job, transactional-sequence wording, tenant-context seam, sdf_default cutover, additive JWT-claim, enterprise-OEE split, seed rename, rollback, ADR-0009 note, UC-003 reservation, compose path).

**Author decision pass (post-APPROVED):**
- **Tenants = real HMG plants:** `kr` → Ulsan (inherits Phase-1 `sdf_default` data; Ulsan ∈ Korea), `us` → HMGMA (Georgia), `in` → Chennai/HMIL. `sdf_default` **retired** (not a 4th tenant). Threaded through W1-ALEMBIC, W2-*, W4-SEED, DOMAIN-NOTES, scenarios. *(Singapore/HMGICS rejected — cell-based, not a 5-shop line.)*
- **Per-tenant data boundary (1순위):** factory/line/machine move into the tenant schema; `public` = tenant/app_user/membership only. **ADR-0035 supersedes ADR-0003's "shared metadata in public" clause** (status-flag, no in-place edit). Removes cross-schema CAGG risk (local join); W1-SPIKE rescoped to per-schema CAGG create/refresh on a fresh schema. **(A) denormalization = documented 2nd fallback; author decides post-spike if per-tenant proves hard.** (Reframed per author note: "ADR 안 깨짐"은 장점이 아님 — placement chosen on domain-correctness, not ADR inertia.)
- **RBAC = operator + tenant-admin only** (no A-IE; viewer→operator read-only). Public `admin_demo`/persona-picker/admin-UI confirmed Phase 2b, not Plan A (addendum §3.3) — recorded in ADR-0033/0038.
- KNOWN-UNKNOWNS: added the "5-shop abstraction vs real-plant reality" honest-simplification note.
