# ADR-0033: Identity & authentication model — hand-rolled JWT + argon2id over a membership RBAC

- **Status:** accepted
- **Date:** 2026-05-25
- **Phase:** 2

## Context

Phase 2 makes the platform multi-tenant: three real-plant tenants (`kr`/Ulsan, `us`/HMGMA, `in`/Chennai), each an isolated Postgres schema. Telemetry and reads must be scoped to the caller's tenant, and write actions (notably `POST /tenants`) must be restricted. This is the first phase with authenticated, authorized access; Phase 1 had no auth at all.

Two forces shape the decision:

- **Portfolio honesty over framework convenience.** The repo's thesis is that one person modeled the domain and the security boundary deliberately. Reaching for a turnkey auth library (FastAPI-Users, Authlib, Keycloak) would hide exactly the judgment the portfolio is meant to prove — token claim design, password-hash cost tuning, the algorithm allow-list, the FC/IS split of crypto vs policy. Hand-rolling a *small, standards-grounded* auth surface is the higher-signal choice for this scope (a demo with two roles and a membership table, not a production IdP).
- **Additivity against a now-blocking contract gate.** Phase 2 promotes `oasdiff breaking` from advisory to blocking. Scoping every existing monitoring route by adding a `tenant` path/query parameter would be a breaking change across the whole API. Carrying the active tenant as a **JWT claim** keeps every existing route signature byte-identical — the auth context rides in the `Authorization` header, not the URL.

The design spec §13.2 lists three Phase-2 roles ("tenant admin / operator / viewer"). The scope doc and Plan A reconcile this down: there is no separate read-only persona in the data model — **"viewer" is operator with read-only permission**, which operator already is. A third "integration-engineer" (A-IE) role is *not* part of Plan A.

## Decision

Authentication is **hand-rolled** with **PyJWT** for token issue/verify and **argon2id** (via `argon2-cffi`) for password hashing — **no auth library or framework**. The model rests on a **Membership** many-to-many between users and tenants, with a **Role** assigned per `(user, tenant)` pair; the only roles are **operator** (read-only) and **tenant-admin**.

**Roles & permissions.**
- `public.membership(user_id, tenant_id, role)` — a user holds an independent Role in each Tenant they belong to (operator in `kr`, tenant-admin in `us` is legal). `(user_id, tenant_id)` is unique; `role` is constrained to the two-value set.
- **operator** = read-only: every mutating endpoint returns 403 for an operator token. The design-spec §13.2 "viewer" is **reconciled to operator read-only** — no separate viewer role, in the data model or in code.
- **tenant-admin** = operator's reads plus tenant-management writes; required for `POST /tenants`.
- **No integration-engineer (A-IE)** in Plan A.

**FC/IS split.**
- The `identity` **domain** is pure and synchronous: `User`, `Role`, `Permission` value objects and a pure `can(action, role) -> Allowed | Denied` sum-type function (error-as-value per ADR-0016). The domain imports no crypto, no `datetime.now`, no PyJWT, no argon2.
- **All crypto lives in adapters:** `PyJwtTokenAdapter` (sign/verify) and `Argon2PasswordHasher` (hash/verify) sit in `contexts/identity/adapters/`, behind `ports/token_port.py` and `ports/password_hasher.py`. The system clock reaches them as an injected `ClockPort` (ADR-0021); `exp`/`iat` are computed from it, never from `datetime.now()`.

**Token shape.**
- **Algorithm allow-list: HS256 only** for Plan A. The verifier passes an explicit single-element `algorithms=["HS256"]` allow-list to `jwt.decode`, so a token presenting `alg: none` (or any other algorithm, including an RS/HS confusion attempt) is rejected before signature checking. HS256 (symmetric HMAC-SHA-256) is chosen over EdDSA because issuer and verifier are the *same* single backend process — there is no third-party verifier that would justify asymmetric keys, and a symmetric secret is simpler to inject and rotate. If a future phase splits issuing from verifying (e.g., an external gateway), a superseding ADR moves to EdDSA (asymmetric) so the secret never leaves the issuer.
- **Mandatory claims**, all verified on every request: `sub` (user id), `iat` (issued-at), `exp` (expiry — short-lived; rejected when past, using the injected clock), and an **active-tenant claim** carrying the tenant the token is scoped to plus that tenant's Role. A token missing any mandatory claim is rejected with a named failure (not `None`, not a generic 401-from-exception). Tenant **switching** re-issues a token with a different active-tenant claim; the active tenant is *never* a route parameter.

**Signing-key custody.**
- The HS256 signing secret is an **injected secret** read from the environment or a mounted file at composition time (`composition.py`), **never committed** to the repo (a grep gate asserts no secret literal lands in version control — W5-DEPLOY). Rotation posture for Plan A: single active secret, rotated by redeploying with a new injected value, which invalidates outstanding tokens (acceptable given short `exp` and a demo-scale user set). Overlapping-key rotation (accept old + new during a window) is a documented future step, not built now.

**Out of Plan A (→ Phase 2b).** The publicly-exposed `admin_demo` credential, the landing persona-picker, and the admin UI are **not** part of Plan A. Plan A's tenant-admin is a backend role plus a dogfooding seed account only (see ADR-0038).

## Consequences

### Positive
- The auth surface is small, fully owned, and reads as deliberate engineering judgment — exactly the portfolio signal a turnkey library would erase.
- Pure `can()` is trivially unit-testable with zero mocks: every `(role × action)` pair asserts an exact `Allowed`/`Denied` variant; the operator-mutating case is a single property test.
- Crypto isolated in adapters means the security-negative test set (tampered signature, `alg: none`, expired via `FixedClock`, missing `sub`/active-tenant, cross-tenant claim) targets one file and runs against the real PyJWT path.
- Active-tenant-as-claim keeps every existing monitoring route signature unchanged → `oasdiff breaking` stays green even though the gate is now blocking.
- Per-`(user, tenant)` Role models the real world: one person can be an operator at one plant and a tenant-admin at another.

### Negative / Trade-offs
- Hand-rolled JWT means *we* own forgery and key-leak risk; mitigated by the algorithm allow-list, the mandatory-claim set, the negative test suite, and a `security-reviewer` gate — but the responsibility is ours, not a vendored library's.
- HS256's symmetric secret must be present wherever a token is verified; the moment verification moves off the issuing process, this ADR must be superseded (EdDSA) rather than stretched.
- A symmetric-secret rotation invalidates live tokens. Acceptable at demo scale; a production system would want overlapping keys or a JWKS endpoint — explicitly deferred.
- Two roles only is intentionally thin. A real plant has finer-grained permissions; modeling them now would be scope inflation against a two-role demo.

### Open questions
- **Exact argon2id cost parameters are not finally tuned.** The committed starting point follows the OWASP Password Storage Cheat Sheet's argon2id minimum: **m = 19456 KiB (19 MiB), t = 2, p = 1** as the floor, with an intent to raise the memory cost toward **m = 46–64 MiB** if the deploy VPS (Hetzner CX32, 8 GB) measures a per-hash latency comfortably under ~250 ms at a higher setting. Final values are tuned empirically on the target host in W2-ID/W5-DEPLOY and recorded there; the OWASP floor is the non-negotiable lower bound, never below `m=19 MiB, t=2, p=1`.
- Short-lived-token `exp` duration vs a refresh-token mechanism: Plan A ships short-lived access tokens with no refresh token; whether the demo needs refresh is left open and would be a follow-up if session length proves annoying in live use.

## Migration Path

Reversing or evolving this decision is local:
- **Adopt an auth library / external IdP.** The `ports/token_port.py` + `ports/password_hasher.py` boundary means a swap touches only the two adapters and `composition.py`; the pure `can()` policy and the membership model are unaffected.
- **Move to asymmetric signing (EdDSA).** Change `PyJwtTokenAdapter` to sign with a private key and verify with a public key; update the allow-list to `["EdDSA"]`. The claim set and route signatures do not change. Requires a superseding ADR.
- **Add roles beyond operator/tenant-admin (e.g., A-IE).** Extend the `Role` sum type and the `membership.role` constraint; `can()` gains cases and its exhaustiveness test forces every new `(role × action)` to be decided. No infrastructure change.

## Sources

- [OWASP Password Storage Cheat Sheet — argon2id parameters (m=19 MiB, t=2, p=1 minimum) — OWASP Foundation](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [RFC 7519 — JSON Web Token (JWT) — IETF, 2015](https://www.rfc-editor.org/rfc/rfc7519) — registered claims `sub`/`iat`/`exp`.
- [RFC 8725 — JSON Web Token Best Current Practices (algorithm allow-list; reject `alg:none`; HS/RS confusion) — IETF, 2020](https://www.rfc-editor.org/rfc/rfc8725)
- [RFC 9106 — Argon2 Memory-Hard Function for Password Hashing — IETF, 2021](https://www.rfc-editor.org/rfc/rfc9106) — argon2id variant rationale.
- Internal: `docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md` (Plan A scope, RBAC = operator + tenant-admin); `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §13.2 (Phase 2 AC, "viewer" reconciled to operator read-only); ADR-0016 (error-as-value), ADR-0021 (ClockPort), ADR-0022 (ports-as-folder), ADR-0024 (fakes); seeded-credential mapping in ADR-0038.
