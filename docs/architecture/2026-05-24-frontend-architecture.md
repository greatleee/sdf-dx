# Frontend Code Architecture — Conventions

| | |
|---|---|
| **Date** | 2026-05-24 |
| **Status** | Draft — Phase 1 frontend conventions. |
| **Layer** | Engineering Conventions (see `docs/SOT-LAYERS.md`) |
| **Scope** | Frontend code-level conventions for the React/TypeScript dashboard (`apps/dashboard-react/`). Backend conventions: `docs/architecture/2026-05-23-code-architecture.md`. |
| **Audience** | Self (future me), LLM pair, portfolio reviewer reading code first. |
| **Related** | ADR-0028 (FC/IS + generated-Zod boundary), ADR-0029 (live WebSocket → Query cache). Parents: ADR-0004 / 0005 / 0016 / 0018 / 0007 / 0022. |

> **Editing rule**: living guide. Edit only when a convention actually evolves. Each substantive change references (or triggers) an ADR. The doc says *how*; the ADR says *why*. See `docs/SOT-LAYERS.md`, *Engineering Conventions* row. Operational do/don't lives in `.claude/rules/frontend-code-architecture.md`.

---

## TL;DR (rule cheatsheet)

1. **FC/IS, same as the backend** — pure `domain/`, IO at the shell. Business logic is plain TypeScript React can't reach.
2. **Layers**: `ui → application → ports/adapters → domain`, dependencies down only, enforced by `eslint-plugin-boundaries`.
3. **Domain is pure + synchronous** — no React, no IO, no `zod`, no clock/uuid/random reads. Inject those.
4. **Boundary = generated Zod.** Adapters parse untrusted responses through the generated contract schema, then map to a separate plain-TS domain type. Mirrors ADR-0018 (boundary type ≠ domain type).
5. **`ui/` never imports generated schemas** — domain types only.
6. **Server state = TanStack Query, in `application/` only.** Components call named hooks (`useLineState`).
7. **Live data**: WebSocket behind an adapter; one hook writes full-shape frames into the same Query cache key the REST snapshot seeds (ADR-0029). No socket in components.
8. **Failures**: transport → throw; domain outcome → discriminated-union value (ADR-0016). Never collapse the two.
9. **Ubiquitous language**: identifiers and UI copy match `GLOSSARY.md` verbatim; the Anti-glossary binds the screen too.
10. **Tests**: domain (no mocks) / application (fakes) / adapter (MSW) / E2E (Playwright, 1:1 UC↔spec). Assert on state, never on calls.

---

## §1. Why FC/IS on the frontend

The backend's case for Functional Core / Imperative Shell (ADR-0004) is not backend-specific — it is an argument about where business rules live, and it applies wherever rules and IO mix. React makes the mix tempting: state, effects, and rendering co-locate in one component file, which is convenient until a rule lives in three components slightly differently and one is wrong. The fix is the same as on the backend: give business logic a place React can't reach — a folder of pure `.ts` files with no React, no async, and no IO — so there is one copy of each rule, it has fast tests, and changing the UI never touches it.

Adopting the *same* architecture on both sides is itself the point: a reviewer reads one mental model across the stack, and an LLM session carries backend habits into frontend work without relearning.

## §2. Layers

```
ui/            React components — the thinnest shell.
application/   TanStack Query hooks, mutations, use cases.
ports/         Interfaces for external systems (folder, file-per-feature).
adapters/      Real implementations + in-memory fakes. Parse at the boundary.
domain/        Pure functions + plain-TS types. No React. No IO. No Zod.
```

Dependencies flow down only. `src/app/` is the **composition root** (wires real adapters or fakes into a provider, mounts the live-subscription hook) — it imports every layer and no layer imports it; it is not a layer in the dependency sense. `src/contexts/<bc>/` mirrors the backend's `contexts/<bc>/` split; Phase 1's bounded context is `monitoring`. `ports/` is a folder with one file per feature, mirroring ADR-0022, so the adapter discipline matches the backend's.

## §3. The boundary: generated Zod, and why the domain type is separate

Every response crosses two shapes: what the server *promises* over the wire (owned by the contract, `sdf-api.yaml`) and what the frontend *wants to reason about* (owned by the frontend). The backend already split these — generated Pydantic is the boundary DTO, the domain `@dataclass` is separate, and explicit conversion moves data across (ADR-0018, ADR-0005 D-2). The frontend mirrors that split exactly.

The wrinkle is that the contract codegen emits TypeScript **types** (`openapi-typescript`), which erase at runtime — so the untrusted network boundary has no runtime guard. We close that by generating **Zod** from the same spec (`@hey-api/openapi-ts` zod plugin), committed under `codegen/` and drift-gated like every other generated artifact. That generated Zod is the boundary/contract schema:

```
wire JSON ──parse(generatedZod)──▶ contract value ──pure mapper──▶ domain type (plain TS)
                  (in adapters/)                      (in adapters/)        (in domain/)
```

Two deliberate choices, both inherited from ADR-0018:

- **The domain type is separate and plain TypeScript — no Zod in `domain/`.** Zod is a validation library; the backend keeps validation libraries (Pydantic) at the boundary and lets the domain be plain data reached by explicit conversion. The frontend does the same: runtime validation happens once, at the seam; the mapper (the `to_domain` analog) narrows and renames in plain code and is unit-tested. A hand-written "domain Zod" would be a second validator the drift gate doesn't cover — exactly the thing generating from the spec avoids.
- **`ui/` imports domain types only.** A wire rename or a widened enum stops at the adapter; it never propagates into components that have no business knowing the wire shape.

Phase 1's mappers are near-identity (rename-only) because the dashboard's mental model and the wire shape nearly coincide. We keep the split anyway — the same "keep it even when trivial" stance the backend takes — so that drift is caught and the first genuinely-derived view (a composed or relabelled shape) has somewhere to live.

## §4. Live data into the Query cache

Server state — cached, refetched, invalidated data that lives on a backend — is TanStack Query's job, and it stays in `application/`; components call named hooks, not `useQuery` directly. The Phase 1 novelty is that *Line state* also arrives live over a WebSocket while *OEE* is polled over REST, so the frontend has two channels for one observable.

The reconciliation belongs in `application/`, not in a component, and it has one source of truth: the Query cache. A single hook subscribes to the socket (behind an adapter, each frame parsed through the generated Zod), and writes each full-shape frame into the same cache key the REST snapshot seeds, with `setQueryData`. Because frames carry the full shape, pushing beats invalidating-and-refetching, which would round-trip to REST on every update. The WS-fed query uses `staleTime: Infinity`, and `refetchInterval` polling turns on **only** when the socket drops — the two channels never run at once, which is what avoids the `setQueryData`-versus-background-refetch race. `useSyncExternalStore` is not needed: the cache already gives tearing-safe reads, and a raw socket has no stable snapshot to read. Full rationale and the reconnect/backoff detail are in ADR-0029.

The payoff is the same as elsewhere: the component reads one hook and contains neither a socket nor a `live ?? snapshot` merge, so it is a shell and the interesting logic is testable with a fake adapter.

## §5. Failure taxonomy

Two kinds of failure, kept apart. A **transport failure** — network down, 5xx, or a Zod parse failure — is not a domain outcome; the caller can only show an error and maybe retry, so adapters **throw** and TanStack Query's `error`/retry/error-boundary machinery handles it. A **domain outcome** — a business rule producing a specific tagged result on a 200 — is a **value**: adapters return a discriminated union (error-as-value, ADR-0016) and the component switches on it exhaustively. Throwing a domain outcome loses UI exhaustiveness; returning a transport failure breaks retry semantics. Phase 1 is read-mostly, so domain-outcome unions are rare — but the split is in place for the first write action.

## §6. Testing

The pyramid matches the backend's tiering (ADR-0006) and the E2E coverage gate (ADR-0007): many fast domain tests with no mocks; some application tests that inject in-memory **fakes** (working port implementations, not stubs) and assert on observable state, never on call patterns; a few adapter tests using MSW so the real parse-and-map path runs against controlled responses; and a small set of Playwright E2E flows, one per use case (1:1 UC↔spec), on stable selectors. Component unit tests are the exception, not the default — logic that wants one belongs in `domain/`, where the test is faster and survives refactoring.

## §7. Enforcement

Rules that aren't enforced get broken, especially under LLM-driven change. Two layers, mirroring the backend: **automatic** — `eslint-plugin-boundaries` fails the build on an upward import or a generated-schema import outside `adapters/`; `@typescript-eslint` strict rules ban `any`, floating promises, and inconsistent type imports; and the contract drift gate (`make all` + `git diff --exit-code codegen/`) keeps the generated Zod honest. **Documentary** — `.claude/rules/frontend-code-architecture.md` (auto-loaded) states the operational do/don't, and this doc explains the why. When a boundary check fails, the fix is to restructure to the correct direction, never to add an ignore entry or smuggle a runtime import behind `import type`.

## §8. Costs (honest accounting)

The same costs the backend pays. **Indirection**: a trivial read becomes a domain type, a port, an adapter, a mapper, a query hook, and a component — over-engineering for a one-off, worth it the moment the feature stops being trivial or needs a test. **Two shapes per concept** (generated contract Zod + domain type) with a mapper, near-identity in Phase 1. **A second generator + a `zod` dependency** in the contract pipeline. We accept these for the same reason as the backend: business logic smeared across components, tests that break on every refactor, and ungoverned LLM output cost more as the surface grows.

## §9. What this is not

It is not Clean/Hexagonal/DDD-by-the-book — it borrows FC/IS and ports/adapters and names things by concrete role. It is not anti-React: React renders, and the other layers make decisions and own IO. It is not final — when a convention stops serving the goals above, supersede the relevant ADR and revise this doc.
