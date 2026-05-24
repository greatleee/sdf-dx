# Phase 2 — Plan A: Backend Multi-Tenancy + Backend Deploy (Implementation Plan)

| | |
|---|---|
| **Date** | 2026-05-24 |
| **Status** | Draft — **pending approval** (produced via `/plan --consensus`, deliberate mode; APPROVED at consensus iteration 2) |
| **Scope source (frozen)** | [`docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md`](../roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md) |
| **Design spec** | `docs/roadmap/2026-05-22-...-design.md` §10/§13.2 · deployment addendum `2026-05-23-...` |
| **This doc is** | Disposable scaffold (`docs/plans/` layer). Archived after the Phase-2a tag lands. Code samples are out of scope — see Conventions. |
| **Authoring rule** | Implementation tasks follow `.claude/rules/*`; on any conflict, the rules win over this plan. |

---

## 0. How to read this plan

- **No production code in this document.** Per the user's planning directive, code is the implementing session's responsibility. This plan carries: file/dir **scaffolding** (paths + one-line purpose), function/port **signatures described in prose**, and **test scenarios** (names + Given/When/Then). It does *not* carry function bodies.
- **Task IDs** are stable handles (`C0-x`, `W1-x`, …). Dependencies are explicit. Tasks in the same **wave** with no listed cross-dependency are **parallel-safe**.
- **Commit discipline**: Chapter 0 lands as the first commits (ADR-0000). Contract changes are their own `feat(contracts):` commit (contract-first §4). One aggregate write per transaction (architecture §8).
- **Definition of done for a task** = its Acceptance Criteria all pass *and* the full CI gate set stays green (`mypy --strict`, `ruff`, `import-linter`, AST checks A1–A3, Konsist/detekt/ktlint, contract codegen drift, **all test tiers including the CI integration job**). An AC that can only be satisfied by a *later* wave is not part of this task's DoD — it is restated as the later task's AC (see W2-TEN ↔ W3-RBAC).

---

## 1. Requirements Summary

Deliver the **backend** of the Phase-2 multi-tenant manufacturing-DX platform and stand it up on a public VPS:

1. Three factory tenants (KR/US/IN) each as an independent Postgres schema, **created by dogfooding `POST /tenants`** via an **idempotent, rerunnable multi-step provisioning sequence** (schema → Alembic `upgrade head` over `search_path` → `create_hypertable` → CAGG). *This is **not** a single DB transaction* — `CREATE SCHEMA`/`create_hypertable`/CAGG involve DDL autocommit; ADR-0030 records the reality and the idempotency design. *(This narrows the frozen scope doc's / ADR-0003's "single transactional sequence" wording; recorded as a superseding note in ADR-0030, not edited in place.)*
2. Telemetry routed per-tenant: bridge derives tenant from the Sparkplug `group_id`; ingest writes via per-tenant `search_path` (replacing today's single-public-schema write), with **connection-scoped** `search_path` (no pool leakage — see §2 pre-mortem #3 / BLOCKER-2).
3. Access governed by **hand-rolled JWT + argon2** (no auth library) over a **membership** model (`public.membership(user_id, tenant_id, role)`); pure `identity` domain with `can() -> Allowed | Denied`; RBAC roles = actor personas (operator read-only, tenant-admin). **Active tenant is carried in a JWT claim** (additive to existing routes — keeps oasdiff green).
4. A **thin cross-tenant enterprise-OEE** query: one cross-BC use case, `UNION ALL` over the caller's member tenants' OEE CAGGs.
5. `monitoring`/`topology` boundaries made explicit; `tenancy`/`identity` BCs added; cross-BC `use_cases/` + `DomainEventDispatcher` wired; fitness gates extended to the new BCs; **the WS line-state poller made tenant-aware**.
6. `MachineKind` refined to the automotive 5-shop taxonomy (`stamping/body/paint/assembly/inspection`); `machineKey` stays a free string in the Kafka contract ⇒ ~0 contract churn.
7. Backend deploy: `docker-compose.prod.yml` (repo root) + Cloudflare Tunnel; always-on per-tenant simulators; 7-day retention; uptime monitoring; **JWT signing-key custody** specified. Platform choice (Hetzner CX32 vs Oracle Free) is a **mid-phase ADR** at the deploy step.

**Out of scope (→ Plan B / deferred):** all React/FE work, public dashboard serving, README credential exposure, FE i18n strings, Phase 2b (admin UI, persona picker, demo-namespace isolation, reset cron, UC-003 E2E), general cross-tenant analytics (Phase 3+), RLS/Citus, choosing the deploy platform now.

---

## 2. RALPLAN-DR Summary (deliberate mode)

### Principles
1. **Chapter 0 is the frozen SoT.** Every decision the implementing session needs is an ADR/UC/glossary entry *before* the first implementation commit. `git log` order tells the story (portfolio surface).
2. **Contract-first, always.** No REST field/endpoint exists in Python before it exists in `sdf-api.yaml`. The drift gate is the arbiter. Prefer **additive** changes (JWT-claim tenant scoping) so the now-blocking oasdiff gate stays green.
3. **Functional Core / Imperative Shell is non-negotiable.** Auth crypto, schema DDL, `search_path`, and Kafka all live in adapters; domains stay pure and return sum types. Fitness gates (`import-linter`/Konsist/AST) are extended *with* each new BC, never relaxed.
4. **Isolation by construction, proven by test.** Tenant isolation must hold even under connection reuse; every isolation claim has a negative test that runs **in CI**, not just locally.
5. **Dogfood the platform; defer honestly.** The three demo tenants are created through the real `POST /tenants`; thin where the scope says thin (enterprise-OEE = one metric); deferred where deferred (platform ADR at deploy time, FE in Plan B).

### Decision Drivers (top 3)
1. **Plan B depends on a stable, merged, contract-complete API.** → favors backend-complete-then-deploy + contract-first front-loading + additive contract changes.
2. **Auth + schema-per-tenant onboarding + cross-schema aggregation are the highest-risk subsystems** (security + irreversible/non-atomic DDL + TimescaleDB cross-schema CAGG feasibility). → favors isolating them as independent BCs *and front-loading a de-risking spike* before they touch deploy.
3. **Maximize safe parallelism without breaking `bc-independence`.** The two new BCs are independent by contract → built concurrently; shared scaffolding (composition root, `use_cases/`, dispatcher, gate config, **pool search_path safety**) lands first as a foundation wave.

### Viable Options (build strategy)

**Option A — Backend-complete-then-deploy, BC-parallel within waves, with a Wave-1 de-risking spike (CHOSEN, refined).**
Foundations wave (spike + contracts + Alembic + BC scaffolding + CI + edge) → two independent BCs (identity, tenancy) ∥ ingest routing ∥ monitoring formalization → cross-BC + enforcement → dogfood seed → deploy. Platform ADR mid-phase.
- *Pros:* matches scope-doc R1 lock; isolates the risky subsystems; the spike retires the highest-uncertainty fact (cross-schema CAGG) in Wave 1; exploits `bc-independence` for real parallelism; deploy ships a finished, contract-frozen API for Plan B.
- *Cons:* no end-to-end signal until late. *Mitigated* by W1-SPIKE (de-risks the worst unknown early) + front-loaded contracts + per-wave gates.

**Option B — Walking skeleton (deploy a thin auth+1-tenant slice first).**
- *Pros:* earliest URL; continuous signal; **and** (steelman) would retire the cross-schema-CAGG/`search_path` risk in Wave 1 by forcing a real vertical slice.
- *Cons:* **explicitly rejected by the scope doc** ("Backend-complete-then-deploy; no walking-skeleton"); deploys an unfinished API Plan B would chase; multiplies deploy/ops churn.
- *Invalidation + synthesis:* the *risk-retirement* virtue of B is real and is **absorbed into Option A via W1-SPIKE** (a throwaway de-risking probe, no deploy, no API surface, discarded after) — so we keep A's finished-API guarantee while gaining B's early-risk-retirement.

**Option C — Strict sequential BC build.**
- *Cons:* forfeits the `bc-independence`-guaranteed parallelism for no quality gain (the BCs don't import each other).
- *Invalidation:* serializing independent BCs buys only wall-clock cost.

**Chosen: Option A (refined with W1-SPIKE).** Drivers 1–3 point to it; B is locked out as a *strategy* but its risk-retirement value is absorbed; C wastes the independence guarantee.

### Pre-mortem (failure scenarios + mitigation)

1. **"Onboarding half-applied a tenant."** `POST /tenants` creates the schema, runs Alembic, then fails at `create_hypertable`/CAGG — DDL autocommit means no single rollback. *Mitigation:* W2-TEN provisioning is **idempotent and rerunnable** (each step guarded / `IF NOT EXISTS`); integration test kills the sequence mid-way and asserts a clean re-run converges; failed-onboarding operational disposition documented (MAJOR-D). ADR-0030 records the DDL-autocommit reality instead of pretending one BEGIN/COMMIT wraps it.
2. **"Hand-rolled JWT shipped a security hole — forgery *or* key leak."** (a) verify path accepts `alg:none`/skips signature/expiry, or leaks tenant scope; (b) **the signing secret is hardcoded/committed/unmanaged** on a public Tunnel deploy. *Mitigation:* W2-ID pins an algorithm allow-list, mandatory `exp`/`iat`/`sub`/active-tenant claims, constant-time argon2 (cost params chosen in ADR-0028) — all in the adapter; pure tested `can()`. **JWT signing key is an injected secret (env/mounted), never committed, custody documented in ADR-0028 + W5-DEPLOY** (BLOCKER-A). Negative security test set + `security-reviewer` phase-end gate; tenant-scope authz enforced at the boundary and integration-tested.
3. **"Ingest/readers wrote or read the wrong schema."** Two distinct failure modes: (a) *unresolvable* tenant falls back to `public`; (b) **a pooled connection carrying `SET search_path='kr'` is returned to the pool and leaks to the next, unrelated borrower** → invisible cross-tenant read/write. *Mitigation:* W2-ING removes the public write path entirely (unresolvable → logged drop/park, never public). W1-SCAFFOLD makes `search_path` **connection-scoped** (`SET LOCAL` inside a per-operation transaction, or a pool acquire/`setup` callback that resets `search_path`); a **no-leak integration test** asserts a released connection does not carry a prior tenant's `search_path`. Integration test: a KR record lands in `kr`, absent from `us`/`public`. Observability: per-tenant ingest counter + unresolved-tenant alert.
4. **"The per-tenant CAGG can't reference `public.machine` — or it bleeds across tenants."** The existing CAGG (`infra/timescale/init/004_continuous_aggregates.sql`) does `FROM machine_telemetry JOIN machine GROUP BY m.line_id`. With `machine` shared in `public` (ADR-0003), a per-tenant CAGG either (a) can't be created (TimescaleDB cross-schema CAGG join restrictions) or (b) aggregates across tenants. *Mitigation:* **W1-SPIKE** empirically resolves this in Wave 1 *before* W1-ALEMBIC baselines on it: prove a `public.machine`-joining per-tenant CAGG can be created + refreshed + read over `search_path` in a fresh schema, or pick a fallback (denormalize `line_id`/`tenant` into the hypertable to drop the join; per-tenant `machine`; or materialized view). ADR-0030 records the intended design + the spike-validated outcome; a pivot is a mid-phase ADR.

### Expanded test plan → see §6.

---

## 3. Build map — waves & parallelism

```
Chapter 0 (docs)  ── must be the FIRST commits (ADR-0000) ───────────────────────────┐
  C0-ADR ∥ C0-UC ∥ C0-GLOSS ∥ C0-ACTORS ∥ C0-DOMAIN ∥ C0-UNKNOWNS                     │
                                                                                      ▼
Wave 1 — Foundations
  W1-SPIKE     [GATE] de-risk cross-schema CAGG ↔ public.machine over search_path  ──► feeds ADR-0030, gates W1-ALEMBIC + Wave 2
  W1-CONTRACTS   contracts surface + regen (auth, /tenants, enterprise-oee; tenant via JWT claim = additive)   ∥
  W1-SCAFFOLD    composition.py + use_cases/ + DomainEventDispatcher + POOL search_path safety + fitness gates  ∥
  W1-CI          extend .github/workflows/ci.yml: integration job (Postgres+Timescale) + new lint contracts     ∥
  W1-EDGE        Kotlin: bridge tenant-from-group_id + simulator 5-shop list + SimulatorScenario                ∥
  W1-MK-PY       Python: MachineKind enum 5-shop rename (topology domain)                                       ∥
  (W1-CONTRACTS/SCAFFOLD/CI/EDGE/MK-PY are mutually parallel; only W1-ALEMBIC waits on W1-SPIKE)
  W1-ALEMBIC     introduce Alembic; baseline per SPIKE outcome; public tables; sdf_default cutover; seed rename
        │
        ▼
Wave 2 — BCs & routing (parallel; depend on Wave 1)
  W2-ID    identity BC                         [needs W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD]
  W2-TEN   tenancy BC + onboarding + POST /tenants (NO authz AC here — see W3-RBAC)  [needs W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD, W1-SPIKE]
  W2-ING   ingest per-tenant search_path routing (connection-scoped)  [needs W1-ALEMBIC, W1-SCAFFOLD pool-safety]
  W2-FORMAL  monitoring/topology formalization + tenant-scoped readers + WS poller tenant-aware  [needs W1-SCAFFOLD]
        │             │
        ▼             ▼
Wave 3 — Cross-BC & enforcement (parallel; depend on Wave 2 identity+tenancy)
  W3-RBAC   token→request→DB-session tenant-context seam; auth dependency; operator read-only 403; POST /tenants ⇒ tenant-admin
  W3-OEE    cross-BC enterprise-OEE use case (pure averaging + integration-only UNION ALL)
        │
        ▼
Wave 4 — Dogfood demo data
  W4-SEED   create KR/US/IN via POST /tenants; per-tenant simulator scenarios; end-to-end routing verified
        │
        ▼
Wave 5 — Deploy
  W5-DEPLOY  docker-compose.prod.yml (root) + Cloudflare Tunnel + JWT-secret custody + always-on sims + retention + UptimeRobot + rollback note
             └─ mid-phase ADR: deploy platform (Hetzner CX32 vs Oracle Free) written HERE
        │
        ▼
Phase-end — Promote / living-doc
  P-PROMOTE  UC registry status notes (backend-verified; full `implemented` deferred to Plan B); KNOWN-UNKNOWNS resolutions
```

**Critical path:** Ch0 → W1-SPIKE → W1-ALEMBIC → W2-TEN → W4-SEED → W5-DEPLOY.
**Widest parallelism:** Wave 1 (5 tasks alongside the spike), Wave 2 (4 tasks).

---

## 4. Chapter 0 batch (lands first — no implementation commit before this completes)

> Per `phase-iteration.md`: these are **Create** tasks, all ahead of Wave 1. ADRs are the spine the others cite; author them first or with a shared decision sheet. Each ADR/UC/glossary lands as its own commit.

### C0-ADR — Decision records
Next free number is **0028** (existing run 0000–0027; note 0013–0015 are absent — gaps are fine, 0028 is next-free). Proposed set (author may merge closely-related decisions; one decision per ADR):

| ADR | Topic | Must record |
|---|---|---|
| 0028 | Identity & auth model | hand-rolled JWT (PyJWT) + argon2 (**cost params chosen**); membership many-to-many with per-(user,tenant) role; RBAC roles = actor personas; **reconcile design-spec §13.2 "viewer"** → operator read-only; crypto + token sign/verify in adapters, pure `can()` in domain; **active tenant carried as a JWT claim** (additive, no existing-route signature change); **signing-key custody**: injected secret (env/mounted), never committed, rotation posture |
| 0029 | BC formalization outcome | extract `tenancy` + `identity`; make `monitoring`/`topology` explicit; relation to ADR-0008 triggers + ADR-0009; cross-BC via `use_cases/` + in-process `DomainEventDispatcher` (no Kafka for domain events). **Note:** ADR-0009's `contexts/<bc>/ports.py` phrasing is read as `ports/<noun>.py` per ADR-0022 (do not edit 0009 in place) |
| 0030 | Multi-schema persistence & tenant data isolation | Alembic multi-schema migrations replace raw `001`–`005` as schema SoT; **public/per-tenant object boundary** (machine/line/factory in `public` per ADR-0003; hypertable + CAGG per-tenant); **cross-schema CAGG strategy** (schema-qualified `public.machine`; **validated by W1-SPIKE**; fallback options enumerated — denormalize/per-tenant-machine/matview); **connection-level `search_path` safety** (no pool leakage); **idempotent rerunnable onboarding** + DDL-autocommit reality (supersedes the "single transactional sequence" wording in ADR-0003/scope doc with an in-ADR note); **`sdf_default` disposition** + raw-init→Alembic cutover (decide: retire `sdf_default`; keep `001`/extensions + `public` bootstrap vs. fully supersede) |
| 0031 | MachineKind automotive 5-shop taxonomy | `stamping/body/paint/assembly/inspection`; `machineKey` stays free string ⇒ no enum/codegen change; enum in domain only; seed/simulator machineKeys + `sparkplug_node_id` `<type>` segment change in lockstep |
| 0032 | Cross-tenant thin enterprise-OEE scope | one cross-BC use case, `UNION ALL` over member tenants' OEE CAGGs, membership-driven authz, **no new role**; reframes ADR-0003's "Phase 3+ aggregator" as the *general* analytics layer; **does NOT supersede ADR-0003** |
| 0033 | Seeded-credential → role mapping + Cloudflare single-stack | persona accounts (operator, tenant-admin) seeded with memberships across KR/US/IN (addendum §3.3/§5); Cloudflare Tunnel single-stack deploy posture (addendum §5) |

> **Mid-phase ADRs (NOT Chapter 0):** **deploy platform** (Hetzner CX32 vs Oracle Free) at W5-DEPLOY; **CAGG-design pivot** *iff* W1-SPIKE falsifies the intended cross-schema strategy. Numbered 0034+ at decision time (ADR-0000).

> **Commit-order note (git-log portfolio shape):** the Phase-1 plan still sits un-archived in `docs/plans/`. Before landing Phase-2 Chapter 0, confirm whether the Phase-1 plan is archived first (per the phase-tag archival convention) so the Phase-2 Ch0 commits open a clean chapter in `git log` rather than interleaving with the prior phase's scaffold. This is a sequencing confirmation, not a content change.

**AC (C0-ADR):**
- [ ] Each ADR follows `docs/ADR/template.md`; status `Accepted`; cross-references the scope doc + extended/superseded ADRs.
- [ ] ADR-0028 resolves the §13.2 `admin/operator/viewer` triplet (viewer → operator read-only) **and** specifies JWT-claim tenant scoping + signing-key custody + argon2 cost params.
- [ ] ADR-0030 records the public/per-tenant boundary, the cross-schema CAGG strategy (with spike-validation hook + fallbacks), connection-scoped `search_path`, idempotent onboarding (no "single transaction" claim), and the `sdf_default` cutover **with no dangling "or"**.
- [ ] ADR-0032 explicitly states it does **not** supersede ADR-0003.
- [ ] ADR-0029 notes the stale ADR-0009 `ports.py` reference without editing 0009.
- [ ] No accepted ADR edited in place (doc immutability); supersede-only for reversals.

### C0-UC — Use-case drafts (`status: draft`; E2E + promote → Plan B)
> **UC numbering (resolved, not open):** UC-001/002 exist; the scope doc's Phase-2b deferred list references "**UC-003 E2E**" → **UC-003 is reserved** (acknowledge-alarm / Phase 2b). Plan A takes **UC-004/005/006**. A one-line reservation note goes in `USE-CASES.md`. *(No open question carried into frozen Ch0.)*

| UC | Title | Primary actor | BC | Notes |
|---|---|---|---|---|
| UC-004 | Tenant admin onboards a new tenant (backend) | A-TA | tenancy | `POST /tenants` → schema+migrate+hypertable+CAGG; `related_e2e` declared, file lands in Plan B |
| UC-005 | Operator authenticates & is RBAC-scoped (operator read-only) | A-OP | identity | login → JWT (active-tenant claim) → tenant-scoped read; mutating endpoints 403 |
| UC-006 | Operator queries cross-tenant enterprise OEE | A-OP | (cross-BC use case) | UNION-ALL over member tenants |

**AC (C0-UC):**
- [ ] Each UC file uses `_TEMPLATE.md` (frontmatter + Goal→…→Gherkin AC→Out-of-scope→Open-questions); `status: draft`; exactly one `primary_actor`; `related_e2e` declared (file deferred to Plan B).
- [ ] One registry row per file and vice-versa; `USE-CASES.md` carries the UC-003-reserved note.
- [ ] `uv run scripts/check-use-case-coverage.py` passes (draft rows need no E2E file).
- [ ] Gherkin AC concrete enough to become a Plan B E2E spec verbatim.

### C0-GLOSS — Glossary
**AC:** `Tenant` flipped `proposed → accepted`; new terms `User`/`Membership`/`Role`/`Permission`/`EnterpriseOEE`/`MachineKind`/`SimulatorScenario` added with source+status; `Machine` examples updated `press/weld/paint/inspect/pack` → `stamping/body/paint/assembly/inspection`; Anti-Glossary checked (code identifiers match wording verbatim).

### C0-ACTORS — Actor catalog
**AC:** **Confirm only** — `A-OP` and `A-TA` already exist as Phase 1+/2+ rows; no new rows for Plan A (`A-IE` optional/absorbed; `A-SV`/`A-PE` out). Record the confirmation in the commit message; do not add rows.

### C0-DOMAIN — Domain notes (seed)
**AC:** seed sections for: automotive 5-shop line structure; per-site OT edge (N simulators, tenant from `group_id`); membership/RBAC; operational-scenario differentiation.

### C0-UNKNOWNS — Known-unknowns (seed + living)
**AC:** seed entries for: deployment resource limits (addendum §8); deploy-platform decision *pending* (→ future mid-phase ADR); **cross-schema CAGG feasibility pending W1-SPIKE**; demo data-signal tuning. (Living updates continue through the phase at the point of resolution.)

---

## 5. Implementation waves

> Every task: working code + tests + green gates; obeys `.claude/rules/*`; contract changes precede consumers; one aggregate per transaction; sum-type errors; injected clock/UUID/random.

### Wave 1 — Foundations

#### W1-SPIKE — De-risk cross-schema CAGG over `search_path` (GATE)
**Depends on:** Ch0. **Gates:** W1-ALEMBIC, all of Wave 2. **Parallel with:** W1-CONTRACTS/SCAFFOLD/CI/EDGE/MK-PY.
**Nature:** throwaway de-risking probe (testcontainers integration test, discarded after the decision is recorded in ADR-0030 — *not* shipped code).
**What it proves:** in a fresh non-`public` schema, can a per-tenant `line_oee`-style CAGG that joins `public.machine` be **created**, **refreshed** (policy), and **read** over a tenant `search_path` — and does it aggregate only that tenant's rows (no cross-tenant bleed via shared `public.machine`)?
**Acceptance Criteria:**
- [ ] A documented empirical answer: PASS (schema-qualified `public.machine` join works + isolates) → intended design stands; or FAIL → the chosen fallback (denormalize `line_id`/`tenant` into `machine_telemetry` to drop the join / per-tenant `machine` / materialized view) is selected.
- [ ] Outcome written into **ADR-0030**; if a fallback is chosen, a mid-phase ADR records the pivot and W1-ALEMBIC/W2-ING/W3-OEE adjust accordingly.
- [ ] The probe code is removed (or quarantined under a clearly-throwaway path) — it is not part of the shipped suite. **Discard verified:** a grep/CI assertion confirms no spike artifact leaks into `apps/*/tests/` (non-throwaway) or the CI default test run.

#### W1-CONTRACTS — Contract surface + regeneration
**Depends on:** Ch0 (ADR-0028/0032). **Parallel with:** other W1.
**Commit:** `feat(contracts): phase-2 auth, tenant onboarding, enterprise-OEE surfaces`
**Surface to add to `packages/contracts/openapi/sdf-api.yaml`** (described, not written):
- Auth: `POST /auth/login` (credentials → access token whose claims include `sub` + active tenant + that tenant's role); a tenant-switch surface that re-issues a token with a different active-tenant claim. **Active tenant is a token claim — existing monitoring routes keep their signatures (additive).**
- Tenancy: `POST /tenants` (tenant-admin only), `GET /tenants` (caller's member tenants).
- Cross-tenant: `GET /enterprise/oee` — enterprise-OEE read model.
- Schemas: `LoginRequest`, `TokenResponse`, `TenantCreateRequest`, `TenantSummary`, `EnterpriseOee`, error envelopes.
- `machine_telemetry.schema.json`: **unchanged** (machineKey stays free string).
**Acceptance Criteria / tests:**
- [ ] `spectral lint` passes on the edited `sdf-api.yaml` (quality gate, pre-codegen).
- [ ] `make all` regenerates Pydantic v2 DTOs + TS types; `git diff --exit-code codegen/` clean after commit (drift gate green).
- [ ] No hand-written FastAPI request/response model anywhere (consumers import generated DTOs).
- [ ] **`oasdiff breaking` vs `main` is GREEN** — all Phase-2 surfaces are additive; existing route signatures are unchanged (tenant via claim, not param). If any break is truly unavoidable, it is documented and the oasdiff gate exception is explicit (contract-first §3 default = fix the spec).
- [ ] `machine_telemetry.schema.json` byte-identical.

#### W1-SCAFFOLD — Composition root, cross-BC seam, **pool `search_path` safety**, fitness gates
**Depends on:** Ch0 (ADR-0029/0030). **Parallel with:** other W1.
**Commit(s):** `feat(api): composition root + use_cases seam + DomainEventDispatcher`; `feat(api): connection-scoped search_path on the asyncpg pool`; `chore(api): extend fitness gates for new BCs + use_cases`.
**Scaffolding (paths + purpose):**
- `src/sdf_api/composition.py` — extract DI wiring from `app.py` (`_make_router` currently wires inline); `app.py` keeps only HTTP/WS routing. The composition root is the **only** place `cast(...)` acknowledges structural Port matches and the `uow.session`/pool escape hatch may appear (AST A3).
- `src/sdf_api/use_cases/` — top-level cross-BC package (`__init__`; first module in W3-OEE).
- `src/sdf_api/shared_kernel/events.py` — hand-rolled `DomainEventDispatcher` (fail-fast; no swallow; no library). Add `shared_kernel/ports/uuid.py`/`random.py` iff a new BC needs injected UUID/random.
- **Pool `search_path` safety (BLOCKER-2):** the shared `asyncpg` pool (`app.py:141`, `ingest/main.py`) must guarantee a connection never carries a prior tenant's `search_path`. Mechanism (decided in ADR-0030): `SET LOCAL search_path` inside a per-operation transaction, **or** a pool acquire/`setup` callback that resets `search_path`. This is composition-owned (touches the pool/session escape hatch).
- Per-BC `ports/unit_of_work.py` Protocol pattern documented for the new BCs (each BC owns its UoW — ADR-0020).
- New `tests/contexts/<bc>/fakes.py` per new BC; `tests/shared_kernel/fakes.py` extension point.
**Fitness-gate extension (this task owns the edits):**
- `pyproject.toml` `[tool.importlinter]`: add `tenancy`+`identity` to `bc-independence` modules; add the **`use-cases-no-domain-or-adapters`** contract (ADR-0023 #4); add `sdf_api.use_cases` to `adapters-no-upward` forbidden targets; verify domain-* globs cover new BCs.
- AST A1/A2/A3 in `tests/architecture/test_call_sites.py` pick up new BC domains; A3 covers new UoWs.
**Acceptance Criteria / tests:**
- [ ] `import-linter` green with the extended set; a deliberate forbidden import (e.g., `identity.domain` importing `tenancy`) **fails** `bc-independence` (negative check documented).
- [ ] **No-leak test (BLOCKER-2):** acquire a pool connection, set `search_path='kr'`, release; the next acquisition of that connection observes the default (`public`) `search_path` — asserted (testcontainers, runs in CI).
- [ ] `DomainEventDispatcher` unit test: registered handler invoked on dispatch; a raising handler propagates (fail-fast, not swallowed).
- [ ] `app.py` constructs no adapters inline; `composition.py` is the sole adapter importer (composition-only contract green).
- [ ] `use_cases/` imports under `mypy --strict`; new use-cases contract active and green.
- [ ] Existing monitoring/topology tests unaffected.

#### W1-CI — CI integration job
**Depends on:** Ch0. **Parallel with:** other W1.
**Commit:** `ci: add Postgres+Timescale integration job; wire new lint contracts`
**Scaffolding:** extend `.github/workflows/ci.yml` (exists; today runs ruff/lint-imports/mypy/pytest unit, Kotlin, UC-coverage gate — **no integration job**).
- Add an integration job providing Postgres+TimescaleDB (a `services:` Timescale image, or Docker-in-CI for testcontainers) so `apps/api-python/tests/integration` + `apps/ingest-python` integration tests run **in CI**, not just locally.
- Ensure the extended `import-linter` contracts and the new test tiers are invoked.
**Acceptance Criteria:**
- [ ] The integration job runs the onboarding/idempotency, tenant-isolation, no-leak, and search_path-routing tests in CI and they pass.
- [ ] DoD's "full CI gate set stays green" is now *true* for the safety-critical tier (not local-only).
- [ ] Job is path-correct for both `apps/api-python` and `apps/ingest-python`.

#### W1-EDGE — Kotlin edge: multi-tenant bridge + 5-shop simulator + scenarios
**Depends on:** Ch0 (ADR-0031). **Parallel with:** all Python W1.
**Commit(s):** `feat(edge): derive tenant from Sparkplug group_id`; `refactor(edge): MachineKind 5-shop machine list`; `feat(edge): per-tenant SimulatorScenario config`.
**Scaffolding:**
- `bridge/` — replace the constant tenant constructor param (`SDF_DEFAULT_TENANT`) with derivation from Sparkplug `group_id`; keep topic `sdf.${tenantId}.machine.telemetry` and key `${lineId}/${machineKey}`.
- `simulator/Main.kt` — `MACHINE_TYPES` → `["stamping","body","paint","assembly","inspection"]`; `SimulatorScenario` config (takt/cycle-time, shift, failure/quality/alarm profile) selected by env.
- No `System.currentTimeMillis()` / `Instant.now()` etc. in any Kotlin domain (K1).
**Acceptance Criteria / tests:**
- [ ] Bridge unit test (table-driven kr/us/in): `group_id="kr"` → tenant/topic `kr`; no env constant consulted.
- [ ] Simulator emits the 5-shop set; test asserts the list equals the taxonomy (cross-language parity with W1-MK-PY) **and** the `<type>` segment of emitted `sparkplug_node_id` matches.
- [ ] Two distinct `SimulatorScenario`s produce measurably different telemetry (e.g., failure-injection rate) — deterministic seeded test (injected randomness).
- [ ] `gradle test` + `ktlint` + `detekt` green (bridge + simulator); Konsist K1/K2 unaffected (edge = adapters, not new domain).

#### W1-MK-PY — Python MachineKind 5-shop rename (domain)
**Depends on:** Ch0 (ADR-0031, C0-GLOSS). **Parallel with:** other W1 (touches `topology/domain/machine.py` + its tests only).
**Commit:** `refactor(api): MachineKind → automotive 5-shop taxonomy`
**Scaffolding:** `contexts/topology/domain/machine.py` — `MachineKind` values → 5-shop. *(Seed-SQL machine-name rename is owned by **W1-ALEMBIC** — see MAJOR-C — not here.)*
**Acceptance Criteria / tests:**
- [ ] `tests/contexts/topology/domain/test_machine.py` updated; every variant covered; exhaustiveness test (every member ∈ the 5 shops).
- [ ] No old name (`press/weld/paint/inspect/pack`) remains in `sdf_api` (grep AC).
- [ ] Domain purity gates unaffected.
- [ ] Glossary wording matches the enum verbatim.

#### W1-ALEMBIC — Alembic multi-schema migration foundation
**Depends on:** **W1-SPIKE** (machine-placement/CAGG outcome), Ch0 (ADR-0030). **Parallel with:** W1-CONTRACTS/SCAFFOLD/CI/EDGE/MK-PY *after* the spike resolves.
**Commit:** `feat(api): introduce Alembic multi-schema migrations + public tenancy/identity tables`
**Scaffolding (paths + purpose):**
- `apps/api-python/alembic.ini`, `migrations/env.py` (search_path-aware; target `public` or a tenant schema), `migrations/versions/`.
- Baseline migration capturing the **per-tenant** object set per the **W1-SPIKE outcome** (hypertable + CAGG; CAGG references `public.machine` schema-qualified, or the chosen fallback). `public` baseline: `public.tenant` (slug, schema_name, region, tz, locale, created_at), `public.app_user` (id, credential hash), `public.membership(user_id, tenant_id, role)` with `(user_id, tenant_id)` unique + role-constrained + FKs; plus shared `public.machine`/`line`/`factory` per ADR-0003.
- **`sdf_default` cutover (MAJOR-7, no "or"):** decide and implement per ADR-0030 — recommended: retire `sdf_default`; KR/US/IN are the only tenants (created via onboarding); `001`(extensions) + the `public` baseline remain as bootstrap; `002`–`005` per-tenant/seed raw SQL is superseded by Alembic + W4-SEED.
- **Seed machine-name rename (MAJOR-C):** the `005_seed.sql` (or its Alembic successor) machine rows (`press/weld/paint/...`, column **`type`**, with `sparkplug_node_id` embedding `<type>`) are renamed to the 5-shop set in lockstep with W1-MK-PY/W1-EDGE.
**Acceptance Criteria / tests (integration, in CI per W1-CI):**
- [ ] `alembic upgrade head` against an empty tenant schema (testcontainers Timescale) reproduces the SPIKE-decided per-tenant object set (verified via `timescaledb_information` views).
- [ ] `upgrade head` twice = no-op (idempotent); mid-sequence failure + re-run converges.
- [ ] `public` tables created with the stated constraints; `downgrade` defined for the public baseline.
- [ ] `sdf_default` disposition implemented exactly as ADR-0030 states (no leftover ambiguous raw-init).
- [ ] Seed machine rows use the 5-shop names; `sparkplug_node_id` `<type>` segments match the simulator (cross-language parity).

### Wave 2 — Bounded contexts & routing (parallel)

#### W2-ID — Identity BC (domain + ports + adapters + application)
**Depends on:** W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD. **Parallel with:** W2-TEN/ING/FORMAL.
**Commit(s):** `feat(api): identity domain (can/Allowed/Denied)`; `feat(api): identity adapters (PyJWT, argon2, Pg user/membership repo)`; `feat(api): identity application (authenticate/authorize)`.
**Scaffolding:**
- `contexts/identity/domain/` — `User`, `Role` (operator | tenant-admin | [integration-engineer]), `Permission`, pure `can(action, role) -> Allowed | Denied`. Frozen dataclasses; no crypto/datetime.now.
- `contexts/identity/ports/` — `user_reader.py`, `membership_reader.py`, `token_port.py` (issue/verify Protocol), `password_hasher.py`, `unit_of_work.py`.
- `contexts/identity/adapters/` — `PostgresUserRepo`, `PostgresMembershipRepo` (ORM-contained; return domain/primitives), `PyJwtTokenAdapter` (alg allow-list; mandatory claims incl. active tenant; **injected signing key**), `Argon2PasswordHasher` (cost params per ADR-0028). Pydantic only at `adapters/http/`.
- `contexts/identity/application/` — `authenticate` (credentials → token w/ active tenant + role), `authorize_tenant_access` (requested tenant ✕ memberships).
- `tests/contexts/identity/fakes.py` — `IdentityInMemoryDataset`, `FakeUnitOfWork`, fake token/hasher honoring real-adapter rules.
**Acceptance Criteria / tests:**
- [ ] **Domain (pure, zero mocks):** `can()` per (role × action) → exact `Allowed`/`Denied`; operator-mutating → `Denied`. Property test over the action space.
- [ ] **JWT adapter (security negative set):** tampered signature, `alg:none`, expired (`exp` past via `FixedClock`), missing `sub`/active-tenant, cross-tenant claim → all rejected with named failures. Signing key is injected (test passes a fixture key; no hardcoded secret).
- [ ] **Password:** argon2 verifies correct, rejects wrong; hashing only in adapter (domain has no argon2 import — gate green).
- [ ] **Application (in-memory dataset):** `authenticate` returns token carrying `{sub, active tenant, that tenant's role}`; `authorize_tenant_access` denies a non-member tenant; asserts on dataset/returned variant, not call patterns (ADR-0024).
- [ ] **Membership:** per-(user,tenant) role independently settable (operator in KR, tenant-admin in US — both resolve).
- [ ] `bc-independence`: `identity` imports no other BC domain.

#### W2-TEN — Tenancy BC + onboarding use case + `POST /tenants`
**Depends on:** W1-CONTRACTS, W1-ALEMBIC, W1-SCAFFOLD, **W1-SPIKE**. **Parallel with:** W2-ID.
**Commit(s):** `feat(api): tenancy domain (Tenant, SchemaName VO)`; `feat(api): tenancy onboarding adapter (schema+migrate+hypertable+CAGG)`; `feat(api): POST /tenants application + wiring`.
**Scaffolding:**
- `contexts/tenancy/domain/` — `Tenant` (slug, schema-name VO, region/tz/locale); `SchemaName` VO (safe identifier; reject injection as a sum-type `Rejected`, not raise); onboarding outcome `Onboarded | Rejected(reason) | AlreadyExists`.
- `contexts/tenancy/ports/` — `tenant_registry.py`, `schema_provisioner.py` (create schema + Alembic over search_path + hypertable + CAGG), `unit_of_work.py`.
- `contexts/tenancy/adapters/` — `PostgresTenantRegistry`, `AlembicSchemaProvisioner` (wraps W1-ALEMBIC runner; **idempotent steps**; uses connection-scoped search_path).
- `contexts/tenancy/application/` — `onboard_tenant` orchestrating the **idempotent, rerunnable** sequence (multi-step DDL reality per ADR-0030 — *not* one transaction).
**Acceptance Criteria / tests:**
- [ ] **Domain (pure):** `SchemaName` rejects unsafe identifiers (`Rejected`, not raise); valid slug → `Onboarded`-eligible; property test over slug inputs.
- [ ] **Integration (testcontainers, in CI):** `POST /tenants` for `kr` creates schema `kr`, runs `upgrade head`, creates hypertable + CAGG (per SPIKE outcome), registers `public.tenant`; verified via `timescaledb_information`.
- [ ] **Idempotency (pre-mortem #1):** second call → `AlreadyExists`, no error; fault injected after `CREATE SCHEMA` before CAGG, then re-run, converges.
- [ ] **Isolation:** onboarding `us` does not alter `kr`'s objects.
- [ ] `bc-independence`: `tenancy` imports no other BC domain.
- [ ] **DoD note:** the tenant-admin **403/2xx authz** check is **NOT** part of this task (it depends on W3-RBAC). The endpoint here onboards correctly; authz is asserted in W3-RBAC. *(MAJOR-4)*

#### W2-ING — Ingest per-tenant `search_path` routing
**Depends on:** W1-ALEMBIC (schema convention + `public.tenant`), W1-SCAFFOLD (pool-safety mechanism). **Parallel with:** W2-ID/TEN/FORMAL.
**Commit:** `feat(ingest): route telemetry per-tenant via connection-scoped search_path`
**Scaffolding:**
- `ingest/adapters/writer.py` + `line_state_writer.py` — set `search_path` to the resolved tenant schema **per connection-scoped operation** (no leak); remove the single-public-schema write path.
- `adapters/resolver.py` — extend `MachineResolver` to resolve tenant slug → schema via the registry; cache per tenant.
- Unresolved tenant → structured log + drop/park (never `public`).
**Acceptance Criteria / tests (integration, in CI):**
- [ ] A `machine.telemetry` record for `kr` is written into schema `kr`, **absent** from `us` and `public`.
- [ ] **No-leak:** interleaved writes for `kr` then `us` on a reused pooled connection land in the correct schemas respectively (shares the W1-SCAFFOLD mechanism).
- [ ] Unresolvable tenant → no public write; structured log/metric emitted.
- [ ] Normalization/domain (`domain/record.py`, `line_activity.py`) unchanged (pure).
- [ ] Per-tenant ingest counter exposed.

#### W2-FORMAL — monitoring/topology formalization + **tenant-aware readers & WS poller**
**Depends on:** W1-SCAFFOLD. **Parallel with:** other W2.
**Commit:** `refactor(api): formalize monitoring/topology; tenant-scope readers and WS poller`
**Scaffolding (paths + purpose):**
- Add `topology/ports/` + `topology/adapters/` if Phase 2 needs per-tenant topology reads.
- Make the Pg readers (`monitoring/adapters/db.py` — currently unqualified `_OEE_QUERY`/`PgLineStateReader`) tenant-aware via the connection-scoped `search_path` (W1-SCAFFOLD), not by assuming `public`.
- **WS line-state poller (BLOCKER-3):** `app.py:_poll_line_state` (lines ~107–135) currently runs a *global, unqualified* `SELECT DISTINCT ON (line_id) … FROM line_state` and fans out to **all** WS subscribers. This task **owns** making it tenant-aware: either a per-tenant poll loop or a tenant-tagged broadcast filtered by each subscriber's active-tenant claim.
- Expose cross-BC OEE needs via `monitoring/ports/oee.py` reader contracts (not by reaching into adapters).
**Acceptance Criteria / tests (integration, in CI):**
- [ ] Monitoring line-state / OEE reads scoped to the caller's active tenant (same line id in `kr` vs `us` returns the respective tenant's data).
- [ ] **WS isolation:** a subscriber whose active tenant is `kr` receives **only** `kr` line-state frames, never `us`/`in` frames.
- [ ] `bc-independence` + `adapters-no-upward` green.
- [ ] UC-001/UC-002 behavior preserved for the active tenant (regression: existing monitoring tests still green, adjusted **only** for the tenant parameter, **not weakened** — testing-integrity rule).

### Wave 3 — Cross-BC & enforcement (parallel)

#### W3-RBAC — Tenant-context seam + authentication & authorization
**Depends on:** W2-ID, W2-TEN, W2-FORMAL. **Parallel with:** W3-OEE.
**Commit(s):** `feat(api): request-scoped tenant context (token→session)`; `feat(api): JWT auth dependency + RBAC enforcement`.
**Scaffolding (paths + purpose):**
- **Token→request→DB-session seam (MAJOR-6):** a FastAPI dependency decodes the bearer token, validates it (via the identity port), and establishes a **request-scoped tenant context** (e.g., `contextvar`/`request.state`) that the composition root reads to scope the DB session's `search_path` for that request. This is the connective tissue of the multi-tenant request path; it lives at the composition/boundary (touches the pool/session escape hatch — A3) and reuses the W1-SCAFFOLD connection-scoping mechanism.
- RBAC enforcement: authorize the requested/active tenant against memberships; operator = read-only (every mutating endpoint requires a non-operator role). Sum-type → `HTTPException` translation at the boundary only.
**Acceptance Criteria / tests (integration, in CI):**
- [ ] Missing/invalid token on a protected route → 401; valid token, non-member tenant → 403.
- [ ] **operator read-only:** every mutating endpoint returns **403** for an operator token (parametrized over the full mutating-endpoint list — explicit scope-doc AC).
- [ ] **`POST /tenants` requires tenant-admin** (operator → 403; tenant-admin → 2xx). *(This is the authz AC moved out of W2-TEN — MAJOR-4.)*
- [ ] Tenant re-scoping: switching active tenant re-scopes reads; a token scoped to `kr` cannot read `us` data (request-context seam verified end-to-end).
- [ ] `/healthz`, `/readyz` remain unauthenticated.

#### W3-OEE — Cross-BC enterprise-OEE use case
**Depends on:** W2-ID (membership), W2-TEN (tenant schemas), W2-FORMAL (OEE reader port), W1-CONTRACTS (DTO). **Parallel with:** W3-RBAC.
**Commit:** `feat(api): cross-tenant enterprise-OEE use case (member-scoped average)`
**Scaffolding (paths + purpose):**
- `src/sdf_api/use_cases/enterprise_oee.py` — cross-BC use case importing `identity` (membership) + the OEE reader **port**; **the averaging logic is pure** (computes the average over a `list[per-tenant OEE]` returned by the port).
- The **cross-schema `UNION ALL` SQL** lives in a dedicated reader **adapter** behind a port (composition-wired); per the SPIKE outcome it either UNION-ALLs per-tenant CAGGs or queries the fallback structure. The port returns `list[per-tenant OEE]`, keeping the BC boundary clean (MAJOR-9).
**Acceptance Criteria / tests:**
- [ ] **Use-case test (per-BC in-memory datasets, never shared):** caller with memberships {KR, US} → enterprise OEE = average over KR+US supplied values; IN excluded. Pure averaging asserted on the returned read model.
- [ ] **Integration (in CI):** with KR/US/IN seeded, the endpoint returns the member-scoped average; the **cross-schema UNION-ALL SQL is integration-tested only** (not via fakes).
- [ ] No new role (membership-driven authz) — verify against ADR-0032.
- [ ] `use-cases-no-domain-or-adapters` + `bc-independence` green (imports *ports*, not other BCs' domain/adapters).

### Wave 4 — Dogfood demo data

#### W4-SEED — Create KR/US/IN via dogfooding + per-tenant scenarios
**Depends on:** W2-TEN (onboarding), W2-ING (routing), W1-EDGE (scenarios), W3-RBAC (tenant-admin gate).
**Commit(s):** `feat: seed KR/US/IN tenants via POST /tenants`; `feat(edge): per-tenant simulator scenarios (distinct OEE stories)`.
**Scaffolding:**
- A bootstrap script (not raw SQL) calling `POST /tenants` for kr/us/in as a tenant-admin, then seeding factory/line/machine topology + persona accounts + memberships across the three tenants.
- Three `SimulatorScenario` configs: common full auto line (stamping→…→inspection) everywhere; differentiate by operational scenario (cycle-time/failure/quality/alarm), product/scale (line/station counts), shift/tz/locale. **No "one process per factory."**
- Persona accounts (operator, tenant-admin) with memberships spanning KR/US/IN (addendum §3.3/§5).
**Acceptance Criteria / tests:**
- [ ] A fresh stack + seed yields exactly 3 tenant schemas, each via `POST /tenants` (not hand-built); rerun is idempotent.
- [ ] Each tenant runs the full 5-shop line; the three scenarios produce **distinguishable** steady-state OEE (asserted to differ beyond noise — distinct stories).
- [ ] One operator + one tenant-admin account hold memberships across KR/US/IN; enterprise-OEE for that operator spans all three.
- [ ] **Domain-reasonableness review** (`architect`/human pass): seeded takt/failure/OEE values are plausible for an automotive line (ISO 22400 sane ranges).

### Wave 5 — Deploy

#### W5-DEPLOY — Backend public deploy (no FE)
**Depends on:** W4-SEED. **Last wave.**
**Commit(s):** `docs(adr): deploy platform decision`; `feat(deploy): docker-compose.prod.yml + Cloudflare Tunnel + JWT secret + always-on simulators`; `feat(ops): retention + UptimeRobot monitor`.
**Scaffolding (paths + purpose):**
- **Mid-phase ADR (platform):** Hetzner CX32 vs Oracle Free — decision + rationale + the conditional multi-arch/ARM build branch (only if Oracle).
- `docker-compose.prod.yml` **at repo root** (matching the existing `docker-compose.yml`; MINOR-F) — prod profile: timescale, broker, ingest, api, **N per-tenant simulators (kr/us/in)**, bridge, Cloudflare Tunnel sidecar. **Remove the nonexistent dashboard build target** (`docker-compose.yml:101-102`; no FE in Plan A).
- **JWT signing-key custody (BLOCKER-A):** the signing secret is provided as an injected secret (env/mounted file), never committed; documented in the compose/ops notes and ADR-0028.
- `restart: unless-stopped` on simulators (always-on); 7-day TimescaleDB retention policy (demo); Cloudflare Tunnel config; UptimeRobot monitor on the API health endpoint + down-alert.
- **Rollback note (MAJOR-D):** documented rollback for a failed Tunnel/compose cutover and the disposition of a tenant onboarded with a broken schema in prod.
**Acceptance Criteria / tests:**
- [ ] `docker compose -f docker-compose.prod.yml config` validates; no nonexistent build target.
- [ ] Backend API reachable over HTTPS (valid cert) via Cloudflare Tunnel (smoke evidence captured).
- [ ] JWT signing key is sourced from an injected secret; grep AC: no secret literal committed in compose/env files.
- [ ] Per-tenant simulators run with `restart: unless-stopped`; after a simulated kill they recover (always-on).
- [ ] 7-day retention policy present + verified (policy-existence or fast-forward test).
- [ ] UptimeRobot monitor on API health + down-alert path exists (config/screenshot evidence).
- [ ] Platform ADR + rollback note committed before the platform-specific compose/build lands.

### Phase-end — Promote / living-doc

#### P-PROMOTE — Status changes & resolutions (phase end)
**Depends on:** all implementation waves.
**Commit:** `docs: phase-2a status notes + known-unknowns resolutions`
**Acceptance Criteria:**
- [ ] UC-004/005/006 rows annotated **backend-verified**; full `status: implemented` **deferred to Plan B** (coverage gate requires an existing `related_e2e` file → Plan B). Do not flip to `implemented` now.
- [ ] KNOWN-UNKNOWNS: platform decision resolved (→ platform ADR); cross-schema CAGG resolved (→ W1-SPIKE/ADR-0030); demo data-signal tuning updated.
- [ ] `uv run scripts/check-use-case-coverage.py` green.

---

## 6. Expanded Test Plan (deliberate mode)

| Tier | Coverage | Where (runs in) | Gate |
|---|---|---|---|
| **Unit / domain (pure, zero mocks)** | `can()` per role×action; `SchemaName`/onboarding sum types; `MachineKind` exhaustiveness; JWT-claim domain rules; DomainEventDispatcher fail-fast | `tests/contexts/*/domain/`, `tests/shared_kernel/` — **CI unit job** | pytest; import-linter domain-purity; AST A1/A2 |
| **Use-case (per-BC in-memory dataset)** | authenticate/authorize; onboard_tenant; enterprise-OEE pure averaging | `tests/contexts/*/application/`, `tests/use_cases/` — **CI unit job** | `use-cases-no-domain-or-adapters`; one dataset per BC |
| **Integration (testcontainers Postgres+Timescale)** | onboarding + idempotency; **search_path no-leak**; ingest per-tenant routing isolation; tenant-scoped reads + **WS isolation**; enterprise-OEE UNION ALL; RBAC 401/403 matrix | `tests/integration/` — **CI integration job (W1-CI) — NOT local-only** | testcontainers only here |
| **Security (negative)** | tampered/`alg:none`/expired/missing-claim/cross-tenant tokens; argon2 wrong-password; **signing-key not committed**; operator-mutating-endpoint 403 matrix; `SchemaName` injection rejection | identity adapter + API integration — **CI** | `security-reviewer` phase-end pass |
| **Contract** | spectral lint; codegen drift; **`oasdiff breaking` (now blocking, expected GREEN — additive)**; machine_telemetry unchanged | `packages/contracts` `make verify` + CI | contract-first §3 |
| **Architecture/fitness** | extended import-linter (new BCs, use_cases); Konsist K1/K2; AST A1–A3 | `tests/architecture/`, Konsist — **CI** | no opt-outs |
| **Observability** | per-tenant ingest counter; unresolved-tenant alert/log; API health; UptimeRobot; always-on simulator restart | ingest + deploy | W2-ING + W5-DEPLOY ACs |
| **De-risking probe** | cross-schema CAGG feasibility (throwaway) | W1-SPIKE (discarded after) | ADR-0030 records outcome |
| **E2E (Gherkin)** | UC-004/005/006 acceptance scenarios authored in Ch0 | **deferred to Plan B** (FE) | Plan B coverage gate |

---

## 7. Global Acceptance Criteria (mirrors scope doc §"Acceptance Criteria (Plan A)")

- [ ] 3 tenant schemas (KR/US/IN) created **by dogfooding `POST /tenants`** via an **idempotent, rerunnable** sequence (schema→migrate→hypertable→CAGG; *not* one DB transaction — DDL autocommit per ADR-0030).
- [ ] Ingest routes telemetry into the correct tenant schema via **connection-scoped** `search_path` (no pool leak).
- [ ] `tenancy`/`identity` BCs formalized; monitoring/topology explicit (incl. tenant-aware WS poller); cross-BC `use_cases/` + `DomainEventDispatcher` wired; fitness gates extended & green.
- [ ] Hand-rolled JWT (issue/verify, injected signing key) + argon2; pure `identity` `can()`; zero auth library.
- [ ] `public.app_user` + `public.membership(user_id,tenant_id,role)`; per-(user,tenant) role; persona accounts seeded across KR/US/IN.
- [ ] operator read-only (every mutating endpoint 403); `POST /tenants` requires tenant-admin.
- [ ] Cross-tenant enterprise-OEE endpoint returns the member-scoped UNION-ALL average.
- [ ] `MachineKind` = 5-shop; enum + simulator + **seed** + GLOSSARY/DOMAIN-NOTES updated; Kafka contract unchanged; codegen drift green.
- [ ] N per-tenant simulators (kr/us/in) run; bridge derives tenant from `group_id`; each encodes a distinct operational scenario.
- [ ] All new REST surfaces contract-first + **additive** (oasdiff blocking, green); no hand-written request/response models.
- [ ] Backend deploy: prod compose (root) + Cloudflare Tunnel; HTTPS reachable; **JWT secret injected, not committed**; always-on simulators; 7-day retention; UptimeRobot + alert; rollback note.
- [ ] CI green incl. the **integration job**: mypy strict, ruff, import-linter (new contracts), AST, Konsist/detekt/ktlint, contract drift, all test tiers.
- [ ] Chapter 0 batch landed first (ADR-0000).

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation | Owner task |
|---|---|---|---|---|
| Cross-schema CAGG can't reference `public.machine` / bleeds across tenants | Med | High | **W1-SPIKE** before baseline; fallback enumerated; ADR-0030 | W1-SPIKE, W1-ALEMBIC |
| `search_path` leaks across pooled connections (silent cross-tenant R/W) | Med | High | Connection-scoped `SET LOCAL`/pool reset; **no-leak integration AC in CI** | W1-SCAFFOLD, W2-ING/FORMAL |
| WS poller broadcasts all tenants to all subscribers | Med | High | Tenant-aware poller; WS isolation AC | W2-FORMAL |
| Half-applied onboarding (DDL autocommit) | Med | High | Idempotent/rerunnable steps; fault-injection test; ADR-0030; rollback note | W2-TEN, W1-ALEMBIC |
| Hand-rolled JWT forgery | Med | High | Alg allow-list, mandatory claims, negative test set, `security-reviewer` | W2-ID, W3-RBAC |
| JWT signing-key leaked/committed on public deploy | Med | High | Injected secret, never committed; ADR-0028; grep AC | W2-ID, W5-DEPLOY |
| Isolation tests run only locally, not in CI | Med | High | **W1-CI** integration job (Postgres+Timescale) | W1-CI |
| Existing-route tenant scoping breaks the blocking oasdiff gate | Low-Med | Med | Tenant via **JWT claim** (additive), not param | W1-CONTRACTS |
| Seed machine-name rename orphaned between tasks | Low | Med | Explicitly owned by W1-ALEMBIC; column is `type` | W1-ALEMBIC |
| `sdf_default` cutover ambiguity | Low | Med | ADR-0030 decides disposition (no "or") | W1-ALEMBIC |
| Late contract mistake forces re-gen ripple | Low-Med | Med | Front-load contracts (W1); additive; oasdiff blocking | W1-CONTRACTS |
| Demo OEE stories indistinguishable / implausible | Med | Med | Distinct-OEE assertion + domain-reasonableness review | W4-SEED |
| Platform (Oracle ARM) needs multi-arch build | Med | Low-Med | Conditional multi-arch branch; mid-phase platform ADR | W5-DEPLOY |
| UC-003 numbering collision with Phase 2b | Low | Low | UC-003 reserved; Plan A = UC-004/005/006; noted in USE-CASES.md | C0-UC |

---

## 9. Verification Steps (phase-level)

1. `cd packages/contracts && make verify` → spectral + drift + **oasdiff (blocking, green)**.
2. `cd apps/api-python` → `uv run mypy --strict`, `uv run ruff check`, `uv run lint-imports` (extended contracts), `uv run pytest` (domain + application + architecture). **Integration tier runs in CI via the W1-CI job** (testcontainers Postgres+Timescale); locally `uv run pytest tests/integration` when Docker is available.
3. `cd apps/ingest-python` → `uv run pytest` incl. integration routing + no-leak tests (CI integration job).
4. `cd apps/ot-gateway-kotlin` → `./gradlew test ktlintCheck detekt` (bridge + simulator); Konsist green.
5. `uv run scripts/check-use-case-coverage.py` (repo root) → UC registry consistent.
6. Stand up `docker-compose.prod.yml` (root); dogfood-seed KR/US/IN; hit `/auth/login`, tenant-scoped reads, WS (verify single-tenant frames), `POST /tenants` (RBAC matrix), `/enterprise/oee`; confirm HTTPS via Tunnel + UptimeRobot; confirm JWT secret is injected (not in the repo).
7. `security-reviewer` pass on the auth subsystem + key custody; `code-reviewer` pass on the phase diff.
8. Confirm `.github/workflows/ci.yml` integration job ran the isolation/no-leak/onboarding tests green.
9. Confirm `git log --oneline` shows Chapter 0 first, then implementation waves, then promote/living-doc (ADR-0000 story shape).

---

## 10. ADR (consensus decision record for this plan)

- **Decision:** Execute Phase-2a as **Option A (refined) — backend-complete-then-deploy with BC-parallel waves and a Wave-1 de-risking spike**: Chapter 0 → Foundations (spike-gated Alembic + contracts/scaffold/CI/edge/MK in parallel) → BCs (identity ∥ tenancy ∥ ingest ∥ formalization) → cross-BC + enforcement → dogfood seed → deploy (mid-phase platform ADR).
- **Drivers:** (1) Plan B needs a frozen, contract-clean, **additively-evolved** API; (2) auth + onboarding + cross-schema aggregation are the highest-risk subsystems and warrant isolation + a front-loaded de-risking spike + CI integration coverage; (3) `bc-independence` enables real identity∥tenancy parallelism.
- **Alternatives considered:** B walking-skeleton (rejected as a *strategy* — contradicts the locked scope; ships an unfinished API Plan B would chase — but its *risk-retirement* value is **absorbed via W1-SPIKE**); C strict-sequential BCs (rejected — forfeits independence-guaranteed parallelism for no quality gain).
- **Why chosen:** only A satisfies all three drivers without violating the scope-doc lock; the spike imports B's one real virtue; the independence guarantee makes C strictly worse.
- **Consequences:** no end-to-end signal until W4 (accepted; mitigated by the spike + front-loaded contracts + per-wave CI gates); contract correctness + tenant-isolation correctness are load-bearing early (mitigated by W1-SPIKE, additive contracts, connection-scoped search_path with a CI no-leak test); the implementing session must respect wave ordering (esp. spike→Alembic, W2-TEN authz→W3) to keep DoD honest.
- **Follow-ups:** mid-phase platform ADR + (conditional) CAGG-pivot ADR; Plan B (FE + FE deploy) consumes the frozen API + Ch0 Gherkin ACs; Phase 2b remains deferred.

---

## 11. Changelog (consensus review)

Consensus loop: Planner draft → Architect (APPROVE-WITH-CHANGES, 3 blockers / 6 majors / 4 minors) → Critic (REVISE; confirmed all 13 + added 6) → this revision (iteration 2). Applied:

**Blockers**
- **B1 — cross-schema CAGG ↔ `public.machine`:** added **W1-SPIKE** (Wave-1 de-risking gate) + folded the public/per-tenant boundary + CAGG strategy into ADR-0030; build map + pre-mortem #4 + risk table updated. Synthesis: absorbs Option B's risk-retirement virtue.
- **B2 — `search_path` pool leakage:** W1-SCAFFOLD now owns connection-scoped `search_path` (SET LOCAL / pool reset) with a **no-leak integration AC**; pre-mortem #3 split into unresolvable-vs-leaked; risk row added.
- **B3 — WS poller cross-tenant broadcast:** W2-FORMAL explicitly owns `app.py:_poll_line_state` with a WS-isolation AC.
- **B-A — JWT signing-key custody:** ADR-0028 + W2-ID + W5-DEPLOY now specify injected secret (never committed) + argon2 cost params; pre-mortem #2 extended; risk row + grep AC added.
- **B-B — no CI integration job:** added **W1-CI** (Postgres+Timescale job) so isolation/no-leak/onboarding tests run in CI; test-plan "where" column + DoD updated.

**Majors**
- M4: W2-TEN's tenant-admin 403 AC moved to W3-RBAC (DoD honesty).
- M5: excised "single/one transactional sequence" in §1/§7; ADR-0030 carries a superseding note (ADR-0003 not edited in place).
- M6: token→request→DB-session tenant-context seam now owned by W3-RBAC.
- M7: `sdf_default` disposition + raw-init cutover decided in ADR-0030/W1-ALEMBIC (no "or").
- M8/E: active tenant via **JWT claim** (additive) → oasdiff stays green; cross-referenced.
- M9: enterprise-OEE reader home + pure-averaging-vs-integration-SQL split clarified (port returns `list[per-tenant OEE]`).
- M-C: seed machine-name rename explicitly owned by W1-ALEMBIC (column `type`).
- M-D: operational rollback notes added (W2-TEN onboarding failure, W5 deploy).

**Minors**
- m10: ADR-0029 notes the stale ADR-0009 `ports.py` reference (no in-place edit).
- m11: UC-003 reservation resolved pre-Ch0 (note in USE-CASES.md; no open question in frozen Ch0).
- m12/F: prod compose path = repo-root `docker-compose.prod.yml`.
- m13: MachineKind "~0 contract churn" confirmed accurate (no change).

**Iteration 2 — Critic re-review: APPROVED** (18/18 required changes confirmed resolved against live source; W1-SPIKE↔Ch0 coherence holds; deliberate-mode gates satisfied). Two non-blocking polish notes merged:
- W1-SPIKE discard now has an explicit verification AC (grep/CI assertion that the throwaway probe leaves no residue).
- Added a commit-order note in C0-ADR: confirm Phase-1 plan archival vs Phase-2 Ch0 commit ordering for a clean `git log` chapter boundary.

Non-defect open items left to the author's discretion: ADR-0033 bundles credential→role mapping + Cloudflare posture (the plan already permits merging closely-related decisions — split if preferred).
