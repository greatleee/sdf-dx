---
id: UC-004
title: Tenant admin onboards a new tenant (backend)
status: draft
phase: 2
primary_actor: A-TA
secondary_actors:
  - S-API
  - S-DB
bounded_context: tenancy
related_adrs:
  - 0035
  - 0033
related_e2e: apps/dashboard-react/tests/e2e/UC-004-onboard-tenant.spec.ts
---

# UC-004 — Tenant admin onboards a new tenant (backend)

## Goal

A tenant admin can stand up a new tenant — an isolated Postgres schema with its full per-tenant object set (factory/line/machine tables, telemetry/state hypertables, and a per-tenant OEE CAGG) — by issuing one authenticated request, so a new plant can come online without hand-run SQL.

## Trigger

A-TA POSTs `/tenants` with a tenant slug and its plant attributes (region, timezone, locale).

## Preconditions

- A-TA is authenticated and holds the `tenant-admin` role on the active tenant carried in the request token (see UC-005; authorization itself is asserted there and in the RBAC enforcement task).
- The `public` registry tables (`tenant`, `app_user`, `membership`) exist.
- The Alembic migration head defines the per-tenant baseline object set.

## Main scenario (happy path)

1. A-TA POSTs `/tenants` to S-API with `{ slug, region, timezone, locale }`.
2. S-API validates the slug into a safe `SchemaName` value (rejecting unsafe identifiers as a domain outcome, not an exception).
3. S-API runs the idempotent provisioning sequence against S-DB over a connection-scoped `search_path`: `CREATE SCHEMA` → Alembic `upgrade head` → `create_hypertable` → per-tenant OEE CAGG + refresh policy. The sequence is **not** a single DB transaction — DDL autocommits (see ADR-0035), so each step is individually guarded and rerunnable.
4. S-API registers the new tenant row in `public.tenant`.
5. S-API returns the `TenantSummary` for the onboarded tenant.

## Alternative flows

- *Slug already onboarded* → S-API returns an `AlreadyExists` outcome; no schema is re-created and the call is a safe no-op.
- *Unsafe / malformed slug* → S-API returns a `Rejected(reason)` domain outcome translated to a 4xx at the HTTP boundary; no schema is created.
- *Provisioning interrupted mid-sequence* (e.g. fault after `CREATE SCHEMA`, before the CAGG) → a re-run of the same request converges to the complete object set (idempotent, rerunnable per ADR-0035).
- *Caller is not a tenant-admin* → S-API returns 403; no provisioning runs (enforcement asserted in the RBAC task; see UC-005).

## Commands & events (event-storming view)

| # | Actor | Command (intent) | Domain event(s) emitted |
|---|---|---|---|
| 1 | A-TA via REST | `OnboardTenant(slug, region, timezone, locale)` | `TenantOnboarded(slug, schemaName)` |
| 2 | S-API → S-DB | (provisioning DDL over `search_path`) | — |
| 3 | S-API → S-DB | (register `public.tenant` row) | — |

## Invariants

- The created schema name is a safe SQL identifier derived from the slug; an unsafe slug never reaches S-DB as DDL.
- Onboarding is idempotent: applying `OnboardTenant` for the same slug any number of times converges to exactly one schema with the full per-tenant object set, and emits `TenantOnboarded` at most once per slug.
- The new schema contains the full per-tenant baseline (factory/line/machine + telemetry/state hypertables + per-tenant OEE CAGG); `public` gains only the one `tenant` registry row and no domain tables.
- Onboarding tenant `B` never alters any object owned by an already-onboarded tenant `A`.

## Acceptance criteria (Gherkin)

```gherkin
Feature: Tenant admin onboards a new tenant (backend)

  Scenario: Onboarding a new tenant provisions its full schema
    Given A-TA is authenticated as a tenant-admin
    And no tenant with slug "us" exists
    When A-TA POSTs /tenants with slug "us" and its plant attributes
    Then the response is 201 with a TenantSummary for "us"
    And schema "us" exists with its telemetry hypertable and per-tenant OEE CAGG
    And a row for "us" exists in public.tenant

  Scenario: Re-onboarding an existing tenant is idempotent
    Given A-TA is authenticated as a tenant-admin
    And a tenant with slug "us" has already been onboarded
    When A-TA POSTs /tenants with slug "us" again
    Then the response signals AlreadyExists without re-creating the schema
    And schema "us" still holds exactly one copy of its baseline object set

  Scenario: A non-tenant-admin cannot onboard a tenant
    Given A-OP is authenticated as an operator (not a tenant-admin)
    When A-OP POSTs /tenants with slug "in"
    Then the response is 403
    And no schema "in" is created
```

## Out of scope for this UC

- *Authentication and RBAC enforcement mechanics* (token issue/verify, the operator-read-only 403 matrix) → UC-005.
- *Seeding a tenant's factory/line/machine topology and persona accounts* → the dogfood seed step, not this UC; this UC provisions an empty-but-complete schema.
- *Public visitor persona / admin UI / persona picker* → Phase 2b (deferred).
- *Choosing the deploy platform / standing the tenant up in production* → the deploy step.

## Open questions

- Operational disposition of a tenant left half-onboarded by a fault that no re-run can clear (e.g. a corrupt schema in production) is documented as a rollback note at the deploy step; the convergence guarantee here assumes a re-runnable fault, not a poisoned schema.
