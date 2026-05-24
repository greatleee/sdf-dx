# ADR-0038: Seeded-credential → role mapping (Plan A) + Cloudflare single-stack edge

- **Status:** accepted
- **Date:** 2026-05-25
- **Phase:** 2

## Context

Plan A is backend-only, but it stands the backend up on a public, always-on VPS at the end of the phase (deployment addendum §3.3/§5). Two decisions follow from that and need recording in Chapter 0, before any seed or deploy code lands:

- **What credentials exist, and what roles they map to.** The deployment addendum (§3.3) decided there is *no* separate "guest"/"demo" domain role — a visitor instead *wears* an existing primary actor role (operator, then tenant-admin). The addendum sketches two public credentials over two phases: `op_demo` exposed at Phase-2 deploy (operator, read-only) and `admin_demo` at Phase-2b (tenant-admin, demo-namespace-isolated). Plan A must state precisely which of this lands now and which is deferred, so the seed script and README don't over-promise.
- **The edge / TLS / DNS posture.** The addendum (§5) names Cloudflare as the single stack for DNS + TLS + Tunnel + rate-limiting, chosen over self-hosting nginx + Let's Encrypt. Plan A's prod compose ships a `cloudflared` sidecar, so the posture needs an accepted decision to cross-reference.

Role *definitions* (operator read-only, tenant-admin, per-`(user, tenant)` Membership) are owned by ADR-0033; this ADR only maps **seeded credentials** onto those roles and fixes the edge posture.

## Decision

**Seeded-credential → role mapping (Plan A).** The Plan A seed creates backend accounts mapped to the two roles defined in ADR-0033:
- **operator** accounts (read-only) and **tenant-admin** accounts, each wired into `public.membership` with the appropriate Role per Tenant. One operator and one tenant-admin hold Memberships spanning all three tenants (`kr`/`us`/`in`) so the cross-tenant enterprise-OEE query has a real member-scoped caller (W4-SEED).
- A **dogfooding tenant-admin seed account exists** and is the credential used to dogfood `POST /tenants` — the three tenants are created *through the API as that tenant-admin*, not hand-built in SQL. This is the proof that the tenant-admin role and the onboarding endpoint actually work end-to-end.

**Public credential exposure is deferred.** The addendum's *public* demo credentials — `op_demo`/`admin_demo` surfaced on the README first screen for an unauthenticated interviewer to use — are **not** part of Plan A. Public `op_demo` exposure (addendum §3.3, Phase-2 deploy row) is a **Plan-B / README concern**: it is meaningful only once a frontend exists for a visitor to log into. `admin_demo`, the persona-picker, and the admin UI are Phase-2b (also deferred per ADR-0033). Plan A therefore seeds the *accounts and memberships* but exposes *no public credential*; the seed accounts are operational dogfooding fixtures, not advertised demo logins.

**Cloudflare single-stack edge (addendum §5).** Production runs behind **Cloudflare as a single stack** — DNS, SSL/TLS (Full strict), and a **Cloudflare Tunnel** (`cloudflared`) sidecar in `docker-compose.prod.yml` — chosen over self-hosted nginx + Let's Encrypt. The Tunnel means the origin opens **zero inbound ports**: the VPS firewall stays closed and the origin IP is never published; `cloudflared` dials out to Cloudflare's edge. Rate-limiting and Bot Fight Mode (free tier) sit at the edge. This keeps the abuse surface minimal, which compounds with operator-being-read-only (ADR-0033): an unauthenticated or operator visitor can mount no write, and the origin is unreachable except through Cloudflare.

## Consequences

### Positive
- Dogfooding `POST /tenants` as a real tenant-admin proves the auth model and onboarding flow in one move — the tenant set is *created by the system*, not seeded around it.
- Deferring public credential exposure to Plan B keeps Plan A honest: there is no frontend yet, so advertising a public login would promise a surface that does not exist.
- Cloudflare Tunnel with zero inbound ports plus operator-read-only gives a near-zero abuse surface for a public always-on demo with negligible operational overhead (free tier + a single sidecar).
- Single-stack Cloudflare avoids hand-rolling TLS renewal / reverse-proxy config — appropriate for a one-person demo, and the application code is untouched (FC/IS: deploy doesn't reach into the domain).

### Negative / Trade-offs
- Hard dependency on one vendor (Cloudflare) for DNS + TLS + ingress; an outage takes the public URL down. Acceptable for a demo (the addendum's fallback is a recorded video + local `docker compose`), but it is a single point of failure.
- Seeding tenant-admin and operator accounts that are *not* publicly exposed means the live demo, in Plan A alone, has no interactive login path — the "살아있는 데이터" signal in Plan A comes only from the always-on simulators; the interactive persona experience waits for Plan B/2b.
- A long-lived dogfooding tenant-admin seed credential exists in the seed path; it must be treated as a real secret (injected, not committed) exactly like the JWT signing key (ADR-0033), or it becomes a backdoor.

## Migration Path

- **Expose `op_demo` publicly (Plan B).** Add the README-surfaced credential and the frontend login; the backend account/membership already exists from Plan A's seed, so this is a frontend + docs change, no backend schema change.
- **Add `admin_demo` + persona-picker + admin UI (Phase 2b).** Layered on top of the existing tenant-admin role and seed account; requires the demo-namespace isolation (`tenant_demo_*`) and 1-hour reset cron described in the addendum — none of which Plan A builds.
- **Drop Cloudflare.** Replace the `cloudflared` sidecar with an nginx + Let's Encrypt reverse proxy and open the VPS firewall to 80/443; this is a compose + ops change only, and would warrant a superseding ADR if it became the standing posture.

## Sources

- Internal: `docs/roadmap/2026-05-23-public-live-demo-deployment-addendum.md` §3.3 (seeded-credential → role mapping; no separate guest role; `op_demo` Phase-2 / `admin_demo` Phase-2b) and §5 (ADR roadmap delta — Cloudflare single-stack; deploy platform deferred to mid-phase ADR), §4.2 (Cloudflare DNS/TLS/Tunnel/rate-limit posture).
- Internal: `docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md` (Plan A = backend + backend deploy; public credential exposure → Plan B; Phase 2b deferred).
- Cross-reference: **ADR-0033** (identity & auth model — defines operator / tenant-admin roles, per-`(user, tenant)` Membership, and the injected-secret custody posture this ADR's seed credential inherits).
- [Cloudflare Tunnel overview — Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) — outbound-only origin connection, no public inbound ports.
