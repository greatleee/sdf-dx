# ADR-0002: TimescaleDB over InfluxDB

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

Design spec §5.1 states the storage decision: PostgreSQL + TimescaleDB as a single store for both relational and time-series data. This ADR records the explicit trade-off against InfluxDB, which is the time-series market leader by a significant margin.

**Market position, stated plainly.** DB-Engines time-series category ranking (Q4-2025 snapshot): InfluxDB 20.86, TimescaleDB 5.62. InfluxDB leads by roughly 3.7×. Industrial adoption reflects this: PTC ThingWorx and Siemens WinCC OA both document InfluxDB as a supported historian backend. Choosing TimescaleDB over InfluxDB is a deliberate bet against the market leader, and the rationale must be specific enough to be falsifiable.

**Forces:**

1. **SQL legibility.** TimescaleDB is a Postgres extension; every query is standard SQL. An interviewer, a new teammate, or an AI assistant can read `SELECT time_bucket('1 hour', time), avg(value) FROM machine_telemetry WHERE ...` without learning a DSL. InfluxDB's query surface has gone through three generations: InfluxQL (v1), Flux (v2), and SQL-ish (v3/IOx) — with Flux now deprecated as InfluxData migrates to the IOx engine. The query-language instability is a concrete operational risk.

2. **Single Postgres instance.** TimescaleDB co-locates relational data (`factory`, `production_line`, `machine`, `alarm`) and time-series data (`machine_telemetry`, `line_state`, continuous aggregates) in one process. One connection pool, one backup target, one migration tool (Alembic), one set of RLS/search_path primitives. Running InfluxDB alongside Postgres doubles the infra surface — problematic for a live demo where failure is public.

3. **InfluxDB version migration churn.** InfluxDB v1 → v2 broke the Flux adoption; v2 → v3 (IOx rewrite) deprecated Flux entirely. A portfolio project built against InfluxDB v2 today risks query-layer obsolescence before the portfolio is even presented. TimescaleDB's extension model on top of stable Postgres carries no equivalent discontinuity risk.

4. **Continuous Aggregate × RLS incompatibility.** TimescaleDB's Continuous Aggregates (CAGGs) do not support Row-Level Security — they run as the superuser at refresh time and ignore RLS policies (GitHub timescaledb issue #5787). This incompatibility is directly relevant to the tenancy decision (ADR-0003): schema-per-tenant sidesteps it entirely, while an RLS-based tenancy model would be blocked by it. Choosing TimescaleDB made schema-per-tenant the correct tenancy design; the two decisions reinforce each other.

5. **Hiring-market signal.** "Postgres + time-series extension" demonstrates dual competence on a widely-known base. InfluxDB fluency signals vertical specialization; TimescaleDB fluency signals Postgres depth plus the ability to extend it.

6. **Live-demo reliability.** Fewer moving parts means fewer failure modes during a live interview walkthrough. One Postgres container is simpler than Postgres + InfluxDB.

## Decision

Use TimescaleDB (Postgres extension) as the single store for both relational and time-series data. InfluxDB is not used at any phase.

Time-series tables (`machine_telemetry`, `line_state`) are Postgres tables converted to TimescaleDB hypertables via `SELECT create_hypertable(...)`. Pre-aggregated KPI views (`line_oee_5m`, `line_oee_1h`, `line_oee_shift`) are TimescaleDB Continuous Aggregates. The tenant isolation model (schema-per-tenant, ADR-0003) places hypertables and CAGGs inside per-tenant schemas.

## Consequences

### Positive

- Standard SQL throughout — no DSL to learn, no query-language version to track.
- Single Postgres instance eliminates a second infra dependency from local dev, CI, and live demo.
- InfluxDB v1→v2→v3 / FluxQL-deprecation / IOx-rewrite migration risk is entirely avoided.
- Continuous Aggregates are available without the RLS incompatibility becoming a blocker (see ADR-0003).
- Alembic handles both schema migrations (relational) and hypertable setup in one tool.
- Portfolio signal: demonstrates Postgres extension model understanding, not just "used a time-series DB."

### Negative / Trade-offs

- TimescaleDB is a Postgres extension, not a native time-series engine. At very high ingest rates (millions of data points/second) a native columnar time-series engine (InfluxDB IOx, ClickHouse) will outperform it. Phase 1 simulated load does not approach this ceiling.
- `create_hypertable` and CAGG DDL are non-standard SQL — Alembic migrations that use them need raw `op.execute()` calls, which are opaque to the auto-generate diff.
- InfluxDB's industrial ecosystem integrations (PTC ThingWorx, Siemens WinCC OA) are not available for TimescaleDB. This is acceptable: we are not integrating with those platforms.
- DB-Engines ranking gap (3.7×) means InfluxDB has a deeper community and more third-party tooling. At the scale of this project, that gap is not felt.
- Calibrated bet (per ADR-0000 §Calibration): if a future phase requires columnar scan performance at scale, re-evaluate ClickHouse or Citus. This ADR's rationale does not apply at >100-tenant or >1M rows/second load.

## Migration Path

At either of these triggers, re-evaluate ClickHouse or Citus (Postgres distributed):

1. **>100 tenants** — per-tenant schema count approaches Postgres connection-pool limits and CAGG refresh scheduling becomes complex.
2. **Heavy analytical scan load** — full-history aggregation queries exceed acceptable latency on a single Postgres node.

Exit cost: Alembic migration scripts + hypertable DDL must be rewritten for the target engine; Python adapter layer for time-series inserts and CAGG-equivalent queries must be replaced. Relational data (factory, line, machine, alarm) can stay in Postgres; only the hypertable tier migrates. Estimated effort: 1–2 weeks for adapter + migration rewrite, not counting data migration time.

## Sources

- [DB-Engines — Time Series DBMS ranking](https://db-engines.com/en/ranking/time+series+dbms)
- [InfluxData — InfluxDB 3.0 and the future of Flux](https://www.influxdata.com/blog/the-future-of-flux/)
- [TimescaleDB — Continuous Aggregates documentation](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/)
- [GitHub timescaledb issue #5787 — Continuous Aggregates incompatible with Row-Level Security](https://github.com/timescale/timescaledb/issues/5787)
- Internal — design spec §5.1, §5.3 (`docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`); ADR-0003 (schema-per-tenant isolation).
