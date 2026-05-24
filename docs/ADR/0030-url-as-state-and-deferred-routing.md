# ADR-0030: URL as source of truth for shareable view state + the three-way state split (router & store deferred)

- **Status:** accepted
- **Date:** 2026-05-24
- **Phase:** 1

## Context

The React dashboard is the repo's first SPA. ADR-0028 placed the network boundary (generated Zod → mapper → domain type) and ADR-0029 placed server + live state in the TanStack Query cache. Neither addressed three adjacent questions that a SPA forces: where *shareable/navigable* view state lives, where *client-global UI* state lives, and whether Phase 1 needs a router or a state store.

Phase 1 as scoped is a **single hardcoded line, one view, one time window** (plan Section F, line 4325: "single hardcoded line — Phase 2 introduces a line picker + tenant"; `KNOWN-UNKNOWNS.md`: only the 5-minute OEE aggregate exists). So there is **no navigable state today** — the only URL is `/`, already shareable trivially. A router over one route would be capability built for a presumptive feature (YAGNI), and a client store would have nothing legitimate to hold once server/live state lives in the Query cache (ADR-0029).

But leaving the question implicit has a real cost, and it is *not* the cost of installing a router later. The documented failure mode (e.g. Granular Engineering's retrofit case) is **state misallocation**: state that should be a URL search param gets stashed in component state or a store during the single-view phase, then has to be untangled when the second destination arrives. The cheap, durable defence is to decide the *principle* now and defer the *library*.

## Decision

**The URL (path + search params) is the single source of truth for shareable, bookmarkable, refresh-surviving view state** — which `Line`, selected time window, active view, filters. Such state never lives in component state or a client store. This extends ADR-0028/0029 into a **three-way state split**:

| State | Owner |
|---|---|
| Server / live data (`LineState`, `OEE`) | TanStack Query cache (ADR-0028/0029) — never duplicated into a store |
| Shareable / navigable view state | the URL |
| Ephemeral, non-shareable UI state | component-local `useState`; React Context only for low-frequency config (theme/locale) |
| Cross-tree, non-server, non-URL global UI state | a client store — **only when that need is real** |

**Data loading derives the query key from URL params inside `application/` hooks** (keeps `useQuery` in `application/`, testable with fakes per ADR-0028 / ADR-0024). A thin *non-blocking* route loader calling an `application/`-defined `queryOptions` factory is permitted later as composition-root orchestration; the blocking `useSuspenseQuery` + loader pattern is deferred.

**Libraries are named but deferred to first real use:**
- **Router → TanStack Router**, landing with the Phase 2 multi-`Line` picker. Chosen over the more widely-known React Router v7 because React Router in *library mode* (the CSR-SPA path) still exposes raw `URLSearchParams` — its typed-search-param RFCs are Stage-0 with no ship date — whereas TanStack Router gives fully type-safe path + search params with no plugin (serving the §10 "no `any`, no cast at the boundary" rule), has first-class TanStack Query v5 integration, and its `validateSearch` consumes our **generated contract Zod** (ADR-0028) so the contract guards URL params too. The cost is a smaller hiring pool than React Router.
- **Client store → Zustand v5**, landing only if a genuinely cross-tree, non-server, non-URL UI need appears (unlikely in Phase 1–2). It must never hold server/live data — that is the Query cache's job (ADR-0029).

**Phase 1 writes no router, no store, and no navigation port.** A port/adapter with zero callers would itself be the speculative scaffolding YAGNI warns against; the durable artifact is this principle. The router and store follow the existing per-feature `ports/` + `adapters/` pattern (ADR-0022) the moment navigation / global-UI state becomes real.

## Consequences

### Positive
- **Prevents state misallocation now** — the real cost of deferral — without paying for a router in a single-screen app.
- **Shareable URLs are designed-in:** the Phase 2 multi-`Line` picker becomes a wiring task, not a retrofit.
- **One mental model continues:** server/live → cache (0028/0029), shareable → URL, ephemeral → local. The reader learns it once.
- **Type-safety continues across the seam:** TanStack Router's `validateSearch` reuses the generated Zod, so URL params are validated by the same contract as the REST boundary.

### Negative / Trade-offs
- **Names a router before installing it** — a soft commitment, revisitable at Phase 2. The principle below it (URL = SoT, hook-derived query key) is library-agnostic, so a later swap costs only adapter/route wiring.
- **"URL is SoT" needs discipline while there is nothing to navigate.** The temptation is to keep the single `lineId` as a constant or `useState`; the rule says it is a URL param *in shape*, realized when the picker lands.
- **The loader-vs-hook data-loading detail is unexercised until Phase 2.** We commit the hook-first direction; the non-blocking-loader nuance is unproven until a second destination exists.

## Migration Path

- **Phase 2 (multi-`Line`):** wire TanStack Router; add `lineId` as a typed path/search param validated by the generated Zod; hooks read it into the query key. Adapters and domain unchanged.
- **First real global-UI need:** add a Zustand v5 store under `application/` (or `app/`), read via selectors in `ui/`; it never holds server/live state.
- **If TanStack Router proves wrong at Phase 2** (team familiarity, or SSR via TanStack Start): swap to React Router / nuqs — only the adapter and route wiring change, because the principle is library-agnostic.

## Sources

- Internal: `docs/ADR/0004-functional-core-imperative-shell.md`, `docs/ADR/0028-frontend-fc-is-and-generated-zod-boundary.md`, `docs/ADR/0029-websocket-live-state-into-query-cache.md`, `docs/ADR/0022-ports-as-folder-file-per-feature.md`, `docs/ADR/0024-fakes-with-in-memory-dataset.md`, `docs/KNOWN-UNKNOWNS.md`, Phase 1 plan §Section F.
- [Search Params Are State — Tanner Linsley, TanStack blog (Jun 2025)](https://tanstack.com/blog/search-params-are-state) — URL search params as first-class shareable state.
- [TkDodo — React Query as a State Manager](https://tkdodo.eu/blog/react-query-as-a-state-manager) & [Effective React Query Keys](https://tkdodo.eu/blog/effective-react-query-keys) — keep server state in the cache; derive query keys from URL params.
- [TanStack Router — Search Params guide](https://tanstack.com/router/latest/docs/guide/search-params) & [TanStack Query integration](https://tanstack.com/router/latest/docs/integrations/query) — typed `validateSearch`, loader→cache.
- [TanStack Query v5 — Does this replace client state managers?](https://tanstack.com/query/v5/docs/framework/react/guides/does-this-replace-client-state) — remaining client state is "usually very tiny".
- [Martin Fowler — Yagni](https://martinfowler.com/bliki/Yagni.html) — defer capability for a presumptive feature; never defer evolvability effort.
- [Announcing Zustand v5 — pmnd.rs](https://pmnd.rs/blog/announcing-zustand-v5/) — React 18+, native `useSyncExternalStore`, default lightweight store.
