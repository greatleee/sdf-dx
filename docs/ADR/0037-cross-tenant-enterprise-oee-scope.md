# ADR-0037: Cross-tenant enterprise-OEE scope

- **Status:** accepted
- **Date:** 2026-05-25
- **Phase:** 2

## Context

ADR-0003 §Consequences noted that cross-tenant analytical queries ("OEE across all plants") require `UNION ALL` across schemas rather than a `GROUP BY tenant_id`, and deferred a "Phase 3+ cross-tenant aggregator" — a general analytics layer (multi-KPI, filters, ad-hoc dimensions). Phase 2 (Plan A) needs exactly one cross-tenant number: an `EnterpriseOEE` read model, the membership-scoped average OEE over the tenants a caller belongs to. The design spec §13.2 places this in Phase 2; ADR-0003/spec §5.2 place general cross-tenant analytics in Phase 3+. This ADR resolves that surface tension by separating the two.

There is no shared `tenant_id` column to group on — per ADR-0035 every `Factory`/`ProductionLine`/`Machine` and OEE CAGG lives inside its tenant schema, so any cross-tenant read must `UNION ALL` per-schema results. The question is scope, layering, and authorization, not whether to build a general analytics engine (we are not).

## Decision

Ship a **thin** cross-tenant `EnterpriseOEE` query as a single cross-BC use case in `src/sdf_api/use_cases/`. It reads each member tenant's per-tenant OEE CAGG — each now a schema-local join (ADR-0035) — through an OEE reader **port**; the reader **adapter** performs the `UNION ALL` over the caller's member tenants' schemas and returns a `list[per-tenant OEE]`. Averaging across that list is **pure** domain/use-case logic, asserted on the read model with per-BC in-memory datasets (never a shared dataset across BCs). The Plan-A metric is the **unweighted arithmetic mean** of the *contributing* member tenants — a member tenant whose CAGG has no rows yet (warming up) is excluded from the mean, not counted as zero (UC-006 alternative flow). A **volume-weighted** enterprise OEE (by line or production count) is deliberately deferred: it would change the read model the reader port returns — each per-tenant row would have to carry its weight — not merely the averaging logic, and the thin demo metric does not need it.

Authorization is **membership-driven, with no new role.** The caller's `public.membership` rows determine which tenants are in scope; a tenant the caller does not belong to is excluded from the `UNION ALL`. Both `operator` and `tenant-admin` (ADR-0033) can read it — it is a read, and `operator` is read-only. No `EnterpriseOEE`-specific role is introduced.

This ADR **reframes ADR-0003's "Phase 3+ cross-tenant aggregator" note as the *general* analytics layer** (multi-KPI, filters — still Phase 3+, out of Plan A scope). This thin enterprise-OEE is the Plan-A slice of that future surface, not its replacement. **This ADR does NOT supersede ADR-0003's core** (schema-per-tenant, RLS rejection) and supersedes no ADR-0003 clause; it only narrows the *scope* of the deferred-aggregator note.

## Consequences

### Positive

- One small, demonstrable cross-tenant metric ships in Plan A without committing to a general analytics engine.
- Membership-driven scoping means authorization is data, not a role proliferation — adding a tenant to a caller's memberships changes the aggregate with no code change.
- The `UNION ALL` runs over ADR-0035 local-join CAGGs, so the cross-tenant query composes per-tenant reads that are each already isolation-correct.
- Pure averaging keeps the cross-BC use case testable with in-memory datasets; the cross-schema SQL is exercised only in integration tests.

### Negative / Trade-offs

- `UNION ALL` cost scales linearly with a caller's member-tenant count; acceptable at 2–dozens of tenants (ADR-0003 scale context), not a general OLAP path.
- A genuinely general analytics layer (arbitrary KPIs, filters, time-range pivots) is explicitly *not* delivered and remains Phase 3+ — this endpoint must not accrete query parameters that turn it into one.
- The cross-BC use case imports both `identity` (membership) and an OEE reader port; it lives in `use_cases/` (not in any single BC's `application/`) to preserve `bc-independence`.
- The unweighted mean shifts as tenants warm up (a 3-member caller sees the mean of 2, then of 3 once the third tenant produces its first CAGG row) and weights a low-volume and an ultra-high-volume plant equally. A volume-weighted figure is the truer enterprise number, but is out of the thin-demo scope and deferred (see Decision); this is an accepted demo simplification, recorded so it is not mistaken for an oversight.

## Migration Path

If a general cross-tenant analytics layer is later needed (Phase 3+), this endpoint is not extended in place — a new surface (and ADR) introduces the general aggregator, and `EnterpriseOEE` either remains as a named convenience metric or is reimplemented on top of it. Reverting this decision (dropping cross-tenant OEE from Plan A) costs only the one use case + reader adapter + endpoint.

## Sources

- ADR-0003 (schema-per-tenant — "Phase 3+ cross-tenant aggregator" note reframed as the general analytics layer; core NOT superseded).
- ADR-0035 (multi-schema persistence — per-tenant local-join OEE CAGGs that this query UNION-ALLs).
- ADR-0034 (bounded-context formalization — cross-BC use case lives in top-level `use_cases/`, preserving `bc-independence`).
- ADR-0033 (identity & auth — `operator`/`tenant-admin` roles; membership model; no new role added here).
- Internal — scope doc `docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md` (thin enterprise-OEE constraint; §13.2 vs §5.2 reconciliation); plan `docs/plans/2026-05-24-phase-2-plan-a-backend-multitenancy.md` §1/§4/§5 W3-OEE.
