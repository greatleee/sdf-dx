# Frontend Code Architecture — Rules

Fast-scan condensation of `docs/architecture/2026-05-24-frontend-architecture.md` + ADRs 0004 / 0005 / 0007 / 0016 / 0018 / 0022 / 0028 / 0029. Covers the React/TypeScript dashboard under `apps/dashboard-react/`.

Arch doc carries full rationale; this file is rules-only, do/don't form. **On conflict between Phase 1 plan Section F code samples and these rules, these rules win** — the Section F samples (hand-typed interfaces, `as` casts at the boundary, component-level WebSocket) are superseded by ADR-0028 / ADR-0029.

Architecture is **Functional Core / Imperative Shell**, the same as the backend: business logic is pure TypeScript, isolated from React, network, storage, and the clock.

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
- Import from a higher layer. Dependencies flow down only: `ui → application → ports/adapters → domain`.
- Silence `eslint-plugin-boundaries`. Restructure to the correct direction instead.
- Put business rules anywhere above `domain/`.

BC scope for Phase 1 is `monitoring` (mirrors the backend `contexts/monitoring/`).

---

## §2. Domain purity — forbidden imports

MUST NOT import or call inside `src/contexts/*/domain/` or `src/shared/`:
- `react`, `@tanstack/react-query`, any React Hook Form / router / state-store library.
- `fetch`, `WebSocket`, `localStorage`, `window`, `document`, or any browser API.
- `zod` — it is a validation library and belongs at the boundary (`adapters/`), mirroring ADR-0018's "no validation lib in domain".
- `Date.now()`, `new Date()` (no-arg), `Math.random()`, `crypto.randomUUID()` — inject these from the shell.

MUST in domain:
- Be pure and **synchronous** — no `Promise`, no `async`. Async orchestration (awaiting adapters, sequencing IO) lives in `application/`; `domain/` receives already-resolved values.
- Use plain TypeScript `type` / `interface` for domain types; failures returned as discriminated-union **values** (§6), never thrown.

---

## §3. Boundary & dual-schema (generated Zod)

DO:
- Treat the **generated Zod** (emitted from `sdf-api.yaml`, committed under `packages/contracts/codegen/`, drift-gated) as the contract/boundary schema — the FE analog of the generated Pydantic boundary DTO (ADR-0018 / ADR-0005, ADR-0028).
- In adapters: `Schema.parse(await res.json())` → pure mapper → frontend domain type. A parse failure is a transport failure (throw — §6).
- Keep the frontend domain type **separate** and plain TypeScript in `domain/`; the mapper is pure, lives in `adapters/`, and is unit-tested.
- Rename across the seam: wire `snake_case` → domain `camelCase` happens in the mapper.

DON'T:
- Import the generated Zod (or generated types) anywhere outside `adapters/`. `ui/` imports domain types only.
- `(await res.json()) as T` — never cast at the boundary; parse it.
- Put a Zod schema in `domain/` — runtime validation is boundary-only.
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
- Put the WebSocket behind a `ports/` + `adapters/` boundary; parse each frame through the generated Zod for the shared Line-state component schema and run it through the **same pure mapper as the REST response** — so what lands in the cache is the domain type, identical in shape to what the REST query seeded, **never the raw wire frame**.
- Subscribe **once** in an `application/` hook mounted high in the tree; write each mapped frame into the REST-seeded cache key — parameterized by identity, `['lineState', lineId]`, and shared verbatim by the REST hook and the WS writer — with `queryClient.setQueryData`.
- Set `staleTime: Infinity` on the WS-fed query; enable `refetchInterval` polling **only while the socket is down** (mutually exclusive *while connected*). Reconnect is the one allowed overlap — `invalidateQueries` runs a REST refetch while frames may resume; benign because both carry the identical shape (last-write-wins).
- Reconnect with exponential backoff + jitter and an app-level heartbeat; keep the socket in a `ref`; clean up on unmount.

DON'T:
- Call `new WebSocket` in a component, or merge `live ?? snapshot` in a component.
- Run `setQueryData` and an active `refetchInterval` at the same time (stale-overwrite race).
- Use `useSyncExternalStore` for the socket — the Query cache already gives tearing-safe reads.

---

## §6. Failure taxonomy

- **Transport failure** (network, 5xx, Zod parse fail) → adapters **throw**. TanStack Query's `error`, retry, and error boundary handle it.
- **Domain outcome** (a tagged business result on a 200) → return a discriminated union **value** (error-as-value, ADR-0016); the component switches exhaustively. Unions live in `domain/`.
- **Never collapse the two.** (Phase 1 is read-mostly, so domain-outcome unions are few — but the split holds for the first write action.)

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

Tier policy mirrors ADR-0006; fakes-not-mocks per ADR-0024; the 1:1 UC↔E2E gate is ADR-0007.

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

## §11. CI gates

- `eslint-plugin-boundaries` element-types: `domain` disallows `application`/`adapters`/`ui`; `application` disallows `adapters`/`ui`. Generated schemas importable in `adapters` only.
- `@typescript-eslint/no-explicit-any`, `no-floating-promises`, `consistent-type-imports` — error level.
- Contract **drift gate** (`make all` + `git diff --exit-code codegen/`) covers the generated Zod, same as the other generated artifacts (contract-first.md §3).

DON'T disable a boundary rule to make code pass. Fix the direction.

---

## Deferred (out of Phase 1 — land when the need arrives)

- **Forms** (React Hook Form) — arrive with the first operator write-action. Form input is an untrusted boundary like the network, so its Zod schema lives at the form boundary (`application/` / `adapters/`), **not** in `domain/` (§2/§3); cross-field rules beyond shape are pure domain functions called after parse.
- **Client routing / multi-view navigation** — arrives with a multi-`Line` picker and per-`Line` detail views.
- **Optimistic mutations** and **command-as-data** unions — arrive when a write action's latency or side-effect set warrants them.

Phase 1 is a read-mostly, single-`Line` dashboard; documenting these as deferred (not absent) marks the boundary deliberately.

---

Full rationale: `docs/architecture/2026-05-24-frontend-architecture.md`. Decision records: ADR-0028 (FC/IS + generated-Zod boundary), ADR-0029 (live WebSocket → Query cache). Parent decisions: ADR-0004 / 0005 / 0016 / 0018 / 0007 / 0022.
