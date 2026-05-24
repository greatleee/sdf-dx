---
id: UC-006
title: Operator queries cross-tenant enterprise OEE
status: draft
phase: 2
primary_actor: A-OP
secondary_actors:
  - S-API
  - S-DB
bounded_context: monitoring
related_adrs:
  - 0037
  - 0033
related_e2e: apps/dashboard-react/tests/e2e/UC-006-query-enterprise-oee.spec.ts
---

# UC-006 — Operator queries cross-tenant enterprise OEE

## Goal

An operator with memberships across several tenants can read one `EnterpriseOEE` figure — the average OEE over exactly the tenants they belong to — so they can compare plant performance at a glance without per-tenant round trips.

## Trigger

A-OP GETs `/enterprise/oee` bearing a valid token.

## Preconditions

- A-OP is authenticated (see UC-005) and holds memberships on one or more tenants.
- Each member tenant has been onboarded (UC-004) and has at least one row in its per-tenant OEE CAGG.

> **Implementation note:** `EnterpriseOEE` is a cross-BC read model. The query is a **top-level cross-BC use case** under `src/sdf_api/use_cases/` (not inside any single BC's `application/`): it reads membership from the `identity` BC and per-tenant OEE through a `monitoring` reader port. The pure averaging logic lives in the use case; the cross-schema `UNION ALL` SQL lives in a reader adapter behind that port. `bounded_context: monitoring` here names the OEE read model's home context; the use case itself spans `identity` + `monitoring` (ADR-0037).

## Main scenario (happy path)

1. A-OP GETs `/enterprise/oee` to S-API.
2. S-API resolves the caller's member tenants from `public.membership` (identity BC).
3. S-API reads each member tenant's latest per-tenant OEE via a reader port; the adapter `UNION ALL`s over those tenants' OEE CAGGs in S-DB.
4. S-API computes the average OEE over the member tenants (pure logic in the cross-BC use case).
5. S-API returns the `EnterpriseOEE` payload (the member-scoped average) to A-OP.

## Alternative flows

- *Caller is a member of a single tenant* → the average is over that one tenant; the figure equals that tenant's OEE.
- *A member tenant has no CAGG rows yet* → that tenant contributes no row to the UNION ALL; the average is taken over the tenants that do have data (warming-up tenant excluded), and the response indicates the contributing set.
- *Caller has no memberships* → S-API returns 403 (no tenant in scope; nothing to average).
- *Missing / invalid token* → S-API returns 401 (see UC-005).

## Commands & events (event-storming view)

| # | Actor | Command (intent) | Domain event(s) emitted |
|---|---|---|---|
| 1 | A-OP via REST | `QueryEnterpriseOEE()` | — |
| 2 | S-API → S-DB | (membership lookup) | — |
| 3 | S-API → S-DB | (UNION ALL over member tenants' OEE CAGGs) | — |

## Invariants

- The average is computed over **exactly** the caller's member tenants — never a non-member tenant, and never every tenant in the system.
- Authorization is membership-driven; querying `EnterpriseOEE` introduces no new role (ADR-0037).
- `EnterpriseOEE ∈ [0, 1]` under the same Phase-1 calibration caveat as per-tenant OEE: `Availability` and `Quality` are bounded by construction, but `Performance` can exceed 1 with a loose ideal cycle time (see GLOSSARY and `KNOWN-UNKNOWNS.md`).
- The averaging is a pure function of the per-tenant OEE read model; the `UNION ALL` SQL never reaches above the reader adapter.

## Acceptance criteria (Gherkin)

```gherkin
Feature: Operator queries cross-tenant enterprise OEE

  Scenario: Enterprise OEE averages only the caller's member tenants
    Given A-OP holds memberships on tenants "kr" and "us"
    And A-OP has no membership on tenant "in"
    And each of "kr", "us", "in" has per-tenant OEE data
    When A-OP GETs /enterprise/oee
    Then the response is 200 with an EnterpriseOEE equal to the average of the "kr" and "us" OEE figures
    And the "in" tenant is excluded from the average

  Scenario: A non-member tenant never contributes
    Given A-OP holds a membership only on tenant "kr"
    When A-OP GETs /enterprise/oee
    Then the response is 200 with an EnterpriseOEE equal to the "kr" OEE figure
    And no other tenant's data is read
```

## Out of scope for this UC

- *General cross-tenant analytics* (multi-KPI, filters, time windows beyond the demo metric) → Phase 3+ (ADR-0003's general aggregator; ADR-0037 does not supersede that core).
- *The frontend enterprise-OEE view* → Plan B.
- *Per-tenant single-line OEE refresh on the dashboard* → UC-002.
- *Authentication / token issue mechanics* → UC-005.

## Open questions

- Whether the member-tenant average should be unweighted (mean of per-tenant OEE) or weighted (by line/production volume) is left to ADR-0037 and the cross-BC use-case task; this UC's Gherkin assumes the unweighted mean of the demo metric.
