# ADR-0003: Schema-per-tenant isolation

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1 (decision lands now); 2 (onboarding implemented)

## Context

Design spec §5.2–5.3 states the tenancy model: Postgres schema-per-tenant, each schema containing its own hypertables and Continuous Aggregates. This ADR records the explicit trade-off against Row-Level Security (RLS), which is the alternative most commonly recommended in the Postgres multi-tenancy literature.

**Phase 1 scope.** Phase 1 has exactly one implicit tenant, `sdf_default`. The schema-per-tenant structure is established at scaffold time; no tenant onboarding UI exists yet. Phase 2 adds `POST /tenants` that automates schema creation, Alembic migration, hypertable setup, and CAGG creation — and this onboarding flow is a live-demo scenario.

**Forces:**

1. **Industrial domain norms.** Industrial historians and SCADA platforms isolate by site, not by row policy. Inductive Automation Ignition uses per-project/per-site database schemas; AVEVA's PI historian is deployed per plant. When a manufacturing engineer asks "where is Korea plant data?", the answer "in the `tenant_korea` schema" is immediately legible. The answer "in the same table as India data, filtered by `tenant_id`" requires explanation.

2. **Scale context.** This system targets 2–dozens of factories, not 500+ SaaS tenants. The Citus/Crunchy Data guidance that favours RLS over schema-per-tenant is explicitly directed at >500 tenant contexts where per-schema migration time and connection-pool overhead become material. At 2–30 tenants, schema-per-tenant operational burden is comparable to RLS.

3. **TimescaleDB Continuous Aggregate × RLS incompatibility.** TimescaleDB CAGGs run as the superuser at refresh time and do not apply RLS policies (GitHub timescaledb issue #5787, documented in ADR-0002). An RLS-based tenancy model is therefore incompatible with the CAGG-based OEE pre-aggregation that is central to query performance in this system. Schema-per-tenant sidesteps this incompatibility entirely — each schema's CAGG runs in its own namespace without any RLS surface.

4. **Onboarding automation as demo asset.** `POST /tenants` → automatic schema creation + migration + hypertable + CAGG is a concrete, observable live-demo scenario (spec §5.2, scenario D). RLS onboarding — `INSERT INTO tenants` + `CREATE POLICY` — is less visually compelling and harder to narrate as a capability.

5. **Alembic multi-schema tooling.** Alembic supports dynamic `search_path` injection in `env.py`; the `alembic-multischema` pattern is established. Per-tenant migrations run `alembic upgrade head` with `search_path` set to the target schema — deterministic, auditable, rerunnable. RLS policy migration is also expressible in Alembic but is less decoupled (a policy change touches all tenants simultaneously).

**Connection routing.** Tenant resolution middleware extracts the tenant identifier (from JWT claim or subdomain) at request time and injects `SET search_path = tenant_{id}` via asyncpg before the first query. The FastAPI app factory wires this middleware in production; fake-mode uses `sdf_default`.

**Cross-BC interaction.** When the Phase 2 `tenancy` BC lands, its cross-BC interactions (e.g., tenant lifecycle events consumed by `monitoring`) follow ADR-0009's top-level use case + in-process domain event dispatcher pattern.

## Decision

Tenant isolation is Postgres schema-per-tenant. Each tenant schema (e.g., `tenant_korea`, `tenant_india`, `sdf_default`) contains its own hypertables (`machine_telemetry`, `line_state`) and Continuous Aggregates (`line_oee_5m`, `line_oee_1h`, `line_oee_shift`). Shared relational metadata (`factory`, `production_line`, `machine`) lives in the `public` schema and is referenced by all tenant schemas.

Phase 1 deploys with `sdf_default` created at migration time. Phase 2 implements `POST /tenants` that executes: schema creation → Alembic `upgrade head` with `search_path = tenant_{id}` → `create_hypertable` calls → CAGG creation — all in one transactional sequence. The GLOSSARY "Tenant" entry cites this ADR.

RLS is not used for tenant isolation at any phase unless the migration path trigger fires.

## Consequences

### Positive

- Tenant data is physically separated — a `search_path` misconfiguration leaks nothing across schemas, unlike an RLS policy bug that could expose cross-tenant rows.
- CAGG × RLS incompatibility (timescaledb issue #5787) is completely sidestepped.
- Industrial domain norms (per-site isolation) are mirrored naturally.
- Per-tenant migrations are independent: running `alembic upgrade head` for `tenant_korea` does not touch `tenant_india`.
- Onboarding automation (`POST /tenants`) is a concrete, demonstrable live-demo scenario.
- `psql -c '\dn'` in a live demo shows `tenant_korea | tenant_india | sdf_default` — immediately legible to any Postgres-familiar interviewer.

### Negative / Trade-offs

- Schema count scales linearly with tenant count. Postgres supports thousands of schemas without performance degradation at this scale, but each schema's CAGG refresh is a separate background job — scheduler overhead grows with tenant count.
- Cross-tenant analytical queries (e.g., "OEE across all plants") require `UNION ALL` across schemas, not a simple `GROUP BY tenant_id`. Phase 3+ will need an explicit cross-tenant aggregator.
- `alembic upgrade head` must be run per tenant schema on each deployment. A deployment pipeline must enumerate active tenants and iterate — operational complexity that a single-schema RLS model avoids.
- Connection pool partitioning: `search_path` is a session-level setting. With `asyncpg`, each connection must be acquired and `search_path` set before use, or tenant-specific connection pools must be maintained. Phase 1 uses per-request `SET search_path`; Phase 2 will evaluate connection-pool partitioning if contention appears.

## Migration Path

Switch to RLS or Citus (distributed Postgres) when EITHER:

1. **>100 tenants** — per-schema CAGG scheduler overhead and per-deployment migration iteration become material operational burdens.
2. **Per-tenant schema migration exceeds 30s p95** — blocking deployment windows become unacceptable.

At that point: consolidate hypertables into shared tables with a `tenant_id` column; introduce RLS policies (accepting the CAGG limitation by switching to materialised views or Citus distributed aggregates); update tenant-resolution middleware to pass `tenant_id` as a query parameter rather than `search_path`. Estimated effort: 1 week for schema consolidation + migration rewrite, not counting data migration time.

## Sources

- [Inductive Automation — Ignition multi-site architecture](https://inductiveautomation.com/ignition/multi-site)
- [AVEVA — PI Server historian per-plant deployment](https://www.aveva.com/en/products/pi-server/)
- [GitHub timescaledb issue #5787 — Continuous Aggregates incompatible with Row-Level Security](https://github.com/timescale/timescaledb/issues/5787)
- [Citus Data / Microsoft — Postgres multi-tenant: schema vs RLS](https://www.citusdata.com/blog/2018/01/22/update-on-distributed-joins/)
- Internal — design spec §5.2, §5.3 (`docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`); ADR-0002 (TimescaleDB over InfluxDB — issue #5787); ADR-0009 (inter-context communication — cross-BC interaction pattern for Phase 2 `tenancy` BC).
