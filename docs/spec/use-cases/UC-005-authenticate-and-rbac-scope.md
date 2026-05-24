---
id: UC-005
title: Operator authenticates and is RBAC-scoped (operator read-only)
status: draft
phase: 2
primary_actor: A-OP
secondary_actors:
  - S-API
  - S-DB
bounded_context: identity
related_adrs:
  - 0033
related_e2e: apps/dashboard-react/tests/e2e/UC-005-authenticate-and-rbac-scope.spec.ts
---

# UC-005 — Operator authenticates and is RBAC-scoped (operator read-only)

## Goal

An operator can log in with credentials, receive a token scoped to one of their member tenants, and read that tenant's data — while every write and every non-member tenant is refused — so access is governed by real membership-driven RBAC.

## Trigger

A-OP POSTs `/auth/login` with credentials.

## Preconditions

- A-OP has an `app_user` row with an argon2 credential hash.
- A-OP holds at least one `membership(user_id, tenant_id, role)` row, with `role = operator` on the tenant they will read.
- The tenant carried as the active tenant has been onboarded (see UC-004).

## Main scenario (happy path)

1. A-OP POSTs `/auth/login` to S-API with credentials.
2. S-API verifies the credential against the stored argon2 hash (in an adapter; the `identity` domain stays pure).
3. S-API issues a JWT whose claims include `sub`, the active tenant, and that tenant's role (`operator`) — signed with the injected signing key.
4. A-OP issues a tenant-scoped read (e.g. `GET /api/v1/lines/{lineId}/state`) bearing the token.
5. S-API decodes and validates the token, establishes the request-scoped tenant context, and the pure `can(action, role)` decision returns `Allowed` for a read.
6. S-API scopes the DB session's `search_path` to the active tenant and returns that tenant's Line state from S-DB.

## Alternative flows

- *Invalid credentials* → S-API returns 401; no token is issued.
- *Mutating request with an operator token* → `can(write, operator)` returns `Denied`; S-API returns 403, no write occurs.
- *Read against a tenant the caller is not a member of* → membership lookup yields no row; S-API returns 403.
- *Missing / tampered / expired token* (bad signature, `alg:none`, past `exp`, missing `sub` or active-tenant claim) → S-API returns 401.
- *Tenant switch* → A-OP requests a token re-issued with a different active-tenant claim; the new token re-scopes subsequent reads to that tenant (the prior token cannot read the new tenant).

## Commands & events (event-storming view)

| # | Actor | Command (intent) | Domain event(s) emitted |
|---|---|---|---|
| 1 | A-OP via REST | `Authenticate(credentials)` | — |
| 2 | S-API | `IssueToken(sub, activeTenant, role)` | — |
| 3 | A-OP via REST | `AuthorizeTenantAccess(token, action, tenant)` | — |
| 4 | S-API → S-DB | (tenant-scoped read) | — |

## Invariants

- A token is issued only when the credential verifies against the stored argon2 hash; a wrong password yields no token.
- Every issued token carries `sub`, an active tenant, and that tenant's role; a token missing any mandatory claim is rejected at verification.
- `can(write, operator)` is always `Denied`; an operator token can never cause a write.
- A read is authorized only when the caller holds a membership on the active tenant; a token's active tenant can never read a tenant the caller is not a member of.
- The role used for a request's authorization is the role on the *active* tenant claim, independent of the caller's role on any other tenant.

## Acceptance criteria (Gherkin)

```gherkin
Feature: Operator authenticates and is RBAC-scoped (operator read-only)

  Scenario: Valid login issues a tenant-scoped token
    Given A-OP has an operator membership on tenant "kr"
    When A-OP POSTs /auth/login with valid credentials for active tenant "kr"
    Then the response is 200 with a token carrying sub, active tenant "kr", and role "operator"

  Scenario: Operator reads data for a member tenant
    Given A-OP holds an operator token for member tenant "kr"
    When A-OP GETs the line state for a line in tenant "kr"
    Then the response is 200 with that tenant's line state

  Scenario: Operator is refused a mutating request
    Given A-OP holds an operator token for member tenant "kr"
    When A-OP issues a mutating request to any endpoint
    Then the response is 403 and no write occurs

  Scenario: Operator is refused a non-member tenant
    Given A-OP holds an operator token whose active tenant is "kr"
    And A-OP has no membership on tenant "us"
    When A-OP attempts to read data scoped to tenant "us"
    Then the response is 403
```

## Out of scope for this UC

- *Onboarding the tenant whose data is read* → UC-004.
- *Cross-tenant enterprise OEE over multiple member tenants at once* → UC-006.
- *Public visitor persona / persona picker / admin UI* → Phase 2b (deferred).
- *Token signing-key custody in production* → the deploy step (ADR-0033 records the posture).
- *The tenant-admin authorization gate on `POST /tenants`* → asserted in UC-004's third scenario and the RBAC enforcement task.

## Open questions

- Token lifetime / refresh posture (single short-lived token vs refresh flow) is left to ADR-0033 and the RBAC enforcement task; this UC asserts `exp` is mandatory and enforced, not its exact duration.
