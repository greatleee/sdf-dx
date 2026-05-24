# Frontend Code Architecture — Rules

Fast-scan condensation of `docs/architecture/2026-05-24-frontend-architecture.md` + ADRs 0004 / 0005 / 0007 / 0016 / 0018 / 0022 / 0028 / 0029 / 0030 / 0031. Covers the React/TypeScript dashboard under `apps/dashboard-react/`.

Rules-only, do/don't form; the arch doc carries the *why*. **On conflict between Phase 1 plan Section F code samples and these rules, these rules win** — ADR-0028 / ADR-0029 supersede the Section F sketch.

Architecture is **Functional Core / Imperative Shell**, the same as the backend.

Stack: React 18 + TypeScript strict + Vite + TanStack Query v5 + Tailwind + Recharts + react-i18next + Zod (boundary only) + MSW + Vitest + Playwright + pnpm. Versions pinned in `apps/dashboard-react/package.json`.

---

## §1. Layer placement

DO:
- Pure domain logic + domain types → `src/contexts/<bc>/domain/`.
- Port interfaces → `src/contexts/<bc>/ports/<noun>.ts` — folder, file-per-feature (mirror ADR-0022).
- IO / adapters (HTTP, WebSocket) + their in-memory fakes → `src/contexts/<bc>/adapters/`.
- BC-local use cases + TanStack Query hooks → `src/contexts/<bc>/application/`.
- Cross-cutting values (shared IDs, formatting) → `src/shared/`.
- React components → `src/ui/`.
- Composition / DI wiring (real adapters vs fakes, providers) → `src/app/` + `src/main.tsx`.

DON'T:
- Import from a higher layer. Dependencies flow down only: `ui → application → ports → domain` — `adapters` implement `ports` (and depend on `ports`/`domain`), wired in `app/`, **never imported by `application` or `ui`** (§11).
- Silence `eslint-plugin-boundaries`. Restructure to the correct direction instead.
- Put business rules anywhere above `domain/`.

BC scope for Phase 1 is `monitoring` (mirrors the backend `contexts/monitoring/`).

---

## §2. Domain purity — forbidden imports

MUST NOT import or call inside `src/contexts/*/domain/` or `src/shared/`:
- `react`, `@tanstack/react-query`, any form / router / state-store library.
- `fetch`, `WebSocket`, `localStorage`, `window`, `document`, or any browser API.
- `zod` — boundary only (`adapters/`); it is a validation library (ADR-0018; §3).
- `Date.now()`, `new Date()` (no-arg), `Math.random()`, `crypto.randomUUID()` — inject from the shell.

MUST in domain:
- Be pure and **synchronous** — no `Promise`, no `async`. Async orchestration lives in `application/`; `domain/` receives already-resolved values.
- Plain TypeScript `type` / `interface` for domain types; failures returned as discriminated-union **values** (§6), never thrown.

---

## §3. Boundary & dual-schema (generated Zod)

DO:
- Treat the **generated Zod** (emitted from `sdf-api.yaml`, committed under `packages/contracts/codegen/`, drift-gated) as the boundary schema — the FE analog of the generated Pydantic DTO (ADR-0028).
- In adapters: `Schema.parse(await res.json())` → pure mapper → frontend domain type. A parse failure is a transport failure (throw — §6).
- Keep the frontend domain type **separate** and plain TypeScript in `domain/`; the mapper is pure, lives in `adapters/`, and is unit-tested.
- Rename across the seam: wire `snake_case` → domain `camelCase` in the mapper.

DON'T:
- Import the generated Zod (or generated types) anywhere outside `adapters/`. `ui/` imports domain types only.
- `(await res.json()) as T` — never cast at the boundary; parse it.
- Put a Zod schema in `domain/`.
- Couple domain field names to wire field names.

---

## §4. Server state — TanStack Query

DO:
- Use `useQuery` / `useMutation` **only** inside `application/` named hooks (`useLineState`, `useLineOee`); components call the named hook.
- Declare query keys as constants in one place, referenced by both reads and invalidations.
- Read adapters from the injected provider (`useAdapters()`-style) so the composition root wires the real adapter or an in-memory fake.
- Mutations invalidate via `onSuccess`.

DON'T:
- Import `useQuery` in `ui/`.
- Inline string query keys at call sites.
- Add optimistic updates unless user-visible latency requires it.

---

## §5. WebSocket live updates

DO (ADR-0029):
- Put the WebSocket behind a `ports/` + `adapters/` boundary. Parse each frame through the generated Zod for the shared Line-state component, then run it through the **same pure mapper as the REST response** — the cache holds the domain type, **never the raw wire frame**.
- Subscribe **once** in an `application/` hook mounted high in the tree; write each mapped frame into the REST-seeded key `['lineState', lineId]` via `queryClient.setQueryData`.
- Set `staleTime: Infinity` on the WS-fed query; enable `refetchInterval` polling **only while the socket is down**.
- Reconnect with exponential backoff + jitter and an app-level heartbeat; keep the socket in a `ref`; clean up on unmount.

DON'T:
- Call `new WebSocket` in a component, or merge `live ?? snapshot` in a component.
- Run `setQueryData` and an active `refetchInterval` at the same time (stale-overwrite race).
- Use `useSyncExternalStore` for the socket.

---

## §6. Failure taxonomy

- **Transport failure** (network, 5xx, Zod parse fail) → adapters **throw**. TanStack Query's `error`, retry, and error boundary handle it.
- **Domain outcome** (a tagged business result on a 200) → return a discriminated union **value** (error-as-value, ADR-0016); the component switches exhaustively. Unions live in `domain/`.
- **Never collapse the two.**

---

## §7. UI rules

Components do only:
1. Read data via application-layer hooks.
2. Call mutation hooks / actions on user events.
3. Render JSX, optionally calling pure domain functions for derived values.

DON'T put business rules, `fetch`, `WebSocket`, `localStorage`, or direct API calls in components.

---

## §8. Naming & ubiquitous language

DO:
- Match `docs/spec/GLOSSARY.md` **verbatim** (modulo `camelCase`/`PascalCase`): `LineState` (states `RUNNING | IDLE | DOWN | CHANGEOVER`), `OEE`, `Availability` / `Performance` / `Quality`. BC folder `monitoring`.
- Role-prefix adapters: `HttpMonitoringReader`, `WebSocketLineStateReader`.
- Apply the Anti-glossary to UI copy **and** identifiers: say "live", never "real-time"; never "status" for *Line state*; never "smart factory" / "equipment" / "asset".

DON'T:
- Introduce a synonym the glossary flags, in code or on screen.

---

## §9. Testing

| Layer | Tool | Scale |
|---|---|---|
| Domain | Vitest, no mocks | Many, ms |
| Application | Vitest + fakes via provider | Some, ms |
| Adapter | Vitest + MSW | Few per adapter |
| E2E | Playwright | Few, key flows |

(Tiering ADR-0006; fakes-not-mocks ADR-0024; 1:1 UC↔E2E gate ADR-0007.)

DO:
- Domain tests: pass concrete values; assert on return values. No `vi.fn()` / `vi.mock()` / `vi.spyOn()` — if you need one, the function isn't pure.
- Application tests: inject in-memory **fakes** (working port implementations, not stubs); assert on observable state / query data, never on call patterns.
- Adapter tests: MSW, so the real parse + mapper path runs against controlled responses.
- E2E: Playwright, **1:1 use-case ↔ spec** (ADR-0007); stable selectors (`data-testid`, ARIA roles), never text/class names.

DON'T:
- Use MSW above the adapter layer — use fakes.
- Write component unit tests by default; logic that wants one belongs in `domain/`.

---

## §10. TypeScript

- `strict: true` + `noUncheckedIndexedAccess`. **No `any`** — use `unknown` and narrow through Zod at the boundary.
- No `as` casts to silence errors (only when you genuinely know more than the compiler and document why).
- Discriminated unions for results/commands with **exhaustive** switches.
- `consistent-type-imports`; never use `import type` to smuggle a runtime dependency past the boundary lint.

---

## §11. CI gates + enforcement set (ADR-0031)

Authoritative list + rationale: **ADR-0031** (FE analog of backend ADR-0023). This is the do/don't surface.

- **`eslint-plugin-boundaries`** element-types (elements `domain`/`application`/`ports`/`adapters`/`ui`/`shared`): `domain ↛ {adapters, application, ui, ports}`; `shared ↛ {adapters, application, ui, ports, domain}`; `ui ↛ adapters`; `application ↛ {adapters, ui}`. Generated schemas importable in `adapters` only.
- **Domain/shared purity guards** (FE analog of backend AST A1/A2; scoped to `domain/` + `shared/`): `no-restricted-syntax` bans `Date.now()` / `new Date()` / `Math.random()` / `crypto.randomUUID()` / `await`; `no-restricted-globals` bans `fetch` / `WebSocket` / `localStorage` / `window` / `document` / `navigator`; `@typescript-eslint/no-restricted-imports` bans `zod` / `react` / `@tanstack/react-query` / router·form·store libs. Inject clock/uuid/random; IO lives in `adapters/`.
- **`@typescript-eslint/switch-exhaustiveness-check`** (exhaustive union switches, §6/§10); **`import/no-cycle`**; **`complexity` ≤ 10** (parity with backend ruff `C90`/mccabe). Plus `no-explicit-any` / `no-floating-promises` / `consistent-type-imports` + `strictTypeChecked`.
- **Prettier** owns formatting (`printWidth 100`); `eslint-config-prettier` is the last config block — never `eslint-plugin-prettier`. `format:check` is the gate.
- **Claude Code hook** (`.claude/settings.json` PostToolUse): auto-runs Prettier + ESLint on `apps/dashboard-react/**/*.{ts,tsx}` an agent edits — earliest drift catch; complements (≠ replaces) CI + git pre-commit.
- Contract **drift gate** (`make all` + `git diff --exit-code codegen/`) covers the generated Zod (contract-first.md §3).

DON'T disable a boundary rule or add an inline `eslint-disable` to make code pass. Fix the direction (ADR-0031 migration path).

---

## §12. State placement & deferred infrastructure

Binds **now** (ADR-0030):
- **URL (search params) is the source of truth for shareable / navigable view state** — which `Line`, time window, filters. Never component state or a store, even the single Phase-1 `Line`.
- State residences: server / live data → Query cache (§4/§5, never copied into a store); shareable view state → URL; ephemeral UI state → `useState` / Context (low-frequency config only); cross-tree non-server non-URL UI state → a store, only when real.
- A form's Zod schema lives at the **form boundary** (`application/` / `adapters/`), **never** in `domain/` (§3).

Deferred — out of Phase 1; arch §10 + ADR-0030 give the placement:
- **Routing → TanStack Router** (lands with the Phase 2 multi-`Line` picker; data loading derives the query key from URL params inside `application/` hooks; blocking Suspense-loader deferred; no navigation port until something navigates).
- **Client store → Zustand v5** (only when a real cross-tree, non-server, non-URL need appears; never holds server/live data — that's the cache, ADR-0029).
- **Forms → React Hook Form** (first operator write-action); **optimistic mutations / command-as-data** (when a write action's latency warrants).

---

Full rationale: `docs/architecture/2026-05-24-frontend-architecture.md`. Decision records: ADR-0028 (FC/IS + generated-Zod boundary), ADR-0029 (live WebSocket → Query cache), ADR-0030 (URL-as-SoT + state split; router/store deferred), ADR-0031 (lint enforcement set + LLM-drift guardrails). Parents: ADR-0004 / 0005 / 0016 / 0018 / 0007 / 0022.
