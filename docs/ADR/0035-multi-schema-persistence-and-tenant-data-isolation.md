# ADR-0035: Multi-schema persistence & tenant data isolation

- **Status:** accepted
- **Date:** 2026-05-25
- **Phase:** 2

## Context

ADR-0003 established schema-per-tenant isolation and rejected RLS (CAGGs run as superuser and ignore RLS policies — ADR-0002, timescaledb #5787). Phase 1 implemented that structure with raw init SQL (`001`–`005`) over a single `sdf_default` schema, with `factory`/`production_line`/`machine` placed in `public` as "shared relational metadata." Phase 2 (Plan A) turns schema-per-tenant from a one-schema scaffold into a live, dogfooded capability: `POST /tenants` onboards three real-plant tenants (`kr`/Ulsan, `us`/HMGMA, `in`/Chennai) by provisioning a schema each.

Two ADR-0003 clauses do not survive contact with that work, and this ADR records why.

**Metadata placement.** A `Machine` belongs to exactly one `ProductionLine`, which belongs to exactly one `Factory`, which belongs to exactly one `Tenant`. There is no `Machine` that is shared across tenants. It is tenant-owned data, not cross-cutting metadata. Placing it in `public` was a Phase-1 convenience that does not reflect the domain. The author's reason for moving it is **domain correctness, not ADR inertia** — "ADR-0003 isn't broken" is explicitly *not* the argument. The second-order consequence is decisive: with `machine` co-resident in the tenant schema, every per-tenant OEE CAGG (which must join telemetry → `machine` → `production_line` to attribute a signal to a line) becomes a **schema-local join**. Keeping `machine` in `public` would force every per-tenant CAGG to reach across schemas — the variant ADR-0002/#5787 makes most fragile.

**Migration tooling and atomicity.** Phase 1's raw `001`–`005` SQL cannot baseline an arbitrary freshly-created schema on demand. Onboarding needs a parameterized, rerunnable migration over a target `search_path`. Separately, ADR-0003 described onboarding as "all in one transactional sequence" — but `CREATE SCHEMA`, `create_hypertable`, and CAGG creation are DDL, and TimescaleDB DDL autocommits. A single rollback boundary across the whole sequence does not exist. The honest property is **idempotent rerunnability**, not atomicity.

## Decision

Alembic multi-schema migrations become the persistence **schema source of truth**, replacing raw `001`–`005` init SQL. A `search_path`-aware `env.py` runs `alembic upgrade head` against a target tenant schema; the raw extension bootstrap (`001`) and the public registry baseline remain as bootstrap, and `002`–`005` per-tenant/seed SQL is retired.

**Per-tenant data boundary.** `factory`, `production_line`, and `machine` move *into* each tenant schema, alongside `machine_telemetry`, `line_state`, and the OEE CAGGs (`line_oee_5m`, `line_oee_1h`, `line_oee_shift`). The `public` schema holds **only** the cross-cutting registry — `tenant`, `app_user`, `membership` — and **no domain tables**. `machine.sparkplug_node_id` uniqueness is therefore per-schema.

**This ADR explicitly supersedes the ADR-0003 §Decision clause** "Shared relational metadata (`factory`, `production_line`, `machine`) lives in the `public` schema and is referenced by all tenant schemas." ADR-0003's schema-per-tenant **core** and its **RLS rejection** remain fully valid and are not touched.

**Per-tenant CAGG = local join is the primary design.** Each per-tenant CAGG joins only schema-local tables; no cross-schema reach exists in the aggregation path. A **secondary fallback (A)** is documented but not adopted: denormalize `line_id` directly into `machine_telemetry` to eliminate the CAGG's join entirely. Fallback (A) is selected only if per-tenant local-join CAGGs prove hard to create/refresh on a freshly-onboarded schema at W1-SPIKE; the author decides post-spike, and any such pivot lands as its own mid-phase ADR.

**Connection-level `search_path` safety.** Tenant scoping is set per operation, never left resident on a pooled connection: either `SET LOCAL search_path` inside a per-operation transaction, or a pool acquire/reset hook that restores the default `search_path` on release. A reused pooled connection must never carry a prior tenant's `search_path` (no cross-tenant read/write leakage); a no-leak integration test asserts this in CI. Because `public` carries **no domain tables** (only the registry — see the per-tenant data boundary above), `public` riding on the `search_path` serves registry (`tenant`/`membership`) lookups only, never the aggregation join: a per-tenant CAGG resolves every joined table within the leading tenant schema, with no `public.machine` to fall through to. The schema-local-join guarantee therefore holds *by construction*, not by `search_path` discipline.

**Onboarding is an idempotent, rerunnable multi-step sequence, not a single DB transaction.** The sequence is: `CREATE SCHEMA` → `alembic upgrade head` over the target `search_path` → `create_hypertable` → CAGG (+ refresh policy) creation. DDL autocommits, so there is no whole-sequence rollback; each step is guarded to be safe to re-run, and a re-run after a mid-sequence fault converges to the same end state. This **narrows ADR-0003's "all in one transactional sequence" wording**: idempotent rerunnability replaces atomicity as the correctness property. A second onboarding of an existing tenant resolves to `AlreadyExists`, not a duplicate provision.

**`sdf_default` is retired.** It is not carried forward as a fourth tenant. `kr`/Ulsan is onboarded fresh through `POST /tenants` and inherits the Phase-1 Ulsan demo content.

## Consequences

### Positive

- Placement matches the domain: a tenant-owned `machine` lives with its tenant's data; the model reads correctly to a manufacturing engineer.
- Every per-tenant OEE CAGG is a clean schema-local join — the cross-schema-CAGG risk that ADR-0002/#5787 makes fragile is removed by construction, not merely mitigated.
- Alembic gives parameterized, auditable, rerunnable per-schema baselining — onboarding an arbitrary new schema on demand is now a first-class operation.
- Connection-scoped `search_path` plus a CI no-leak test makes pooled-connection isolation a tested property, not an assumption.
- `public` is a small, legible registry (three tables); `psql -c '\dt public.*'` shows no domain leakage.

### Negative / Trade-offs

- Onboarding has no single rollback. A fault mid-sequence leaves a partially-provisioned schema; correctness rests on rerunnable convergence + a documented failed-onboarding operational disposition, verified by a fault-injection integration test.
- Per-tenant `factory`/`production_line`/`machine` means topology is duplicated per schema; a genuinely cross-tenant query (enterprise OEE, ADR-0037) must `UNION ALL` per-schema reads rather than `GROUP BY` a shared table.
- `create_hypertable` and CAGG DDL stay opaque to Alembic autogenerate (raw `op.execute()`), as noted in ADR-0002 — migrations carry hand-written DDL.
- The metadata-placement and single-transaction-sequence clauses of an accepted ADR (0003) are superseded; ADR-0003's status is flagged "partially superseded" and a pointer added, but its core prose is untouched (supersede-don't-edit, per `docs/SOT-LAYERS.md`).

## Migration Path

Reverting the per-tenant boundary (moving `factory`/`production_line`/`machine` back to `public`) reintroduces cross-schema CAGG joins and the #5787 fragility — it would require either accepting that risk or adopting fallback (A) denormalization globally; cost ~ rewriting the per-tenant baseline migration + every CAGG definition. Reverting Alembic to raw SQL forfeits on-demand schema baselining and is not viable once `POST /tenants` ships. The broader schema-per-tenant → RLS/Citus exit remains governed by ADR-0003's migration triggers (>100 tenants, or per-tenant migration p95 > 30s), unchanged by this ADR.

## Sources

- ADR-0003 (schema-per-tenant isolation — metadata-placement & single-transaction-sequence clauses superseded here; core + RLS rejection retained).
- ADR-0002 (TimescaleDB over InfluxDB — CAGG × RLS incompatibility, timescaledb #5787).
- ADR-0020 (per-BC Unit of Work — DDL onboarding sits outside the UoW commit boundary; DDL autocommits).
- ADR-0037 (cross-tenant enterprise-OEE — consumes the per-tenant local-join CAGGs UNION-ALL'd).
- [TimescaleDB — Continuous Aggregates documentation](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/)
- [GitHub timescaledb issue #5787 — Continuous Aggregates incompatible with Row-Level Security](https://github.com/timescale/timescaledb/issues/5787)
- Internal — scope doc `docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md`; plan `docs/plans/2026-05-24-phase-2-plan-a-backend-multitenancy.md` §0/§1/§2/§4.
