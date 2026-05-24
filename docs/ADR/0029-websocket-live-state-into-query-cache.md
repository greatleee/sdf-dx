# ADR-0029: Live Line state over WebSocket reconciled into the TanStack Query cache

- **Status:** accepted
- **Date:** 2026-05-24
- **Phase:** 1

## Context

UC-001 requires the operator to watch live *Line state* update without manual action; UC-002 reads *OEE* over a plain REST poll (single channel, no socket). *Line state* therefore has two channels for one observable: an initial REST snapshot and a live WebSocket frame stream (the API pushes *Line state* in Section E, Task 20).

The Phase 1 plan's Section F sketch opened `new WebSocket` *inside* the dashboard component, kept a parallel `useQuery` snapshot, and merged them with `liveState ?? snapshot` in the component body. That places IO and orchestration in the shell — two sources of truth reconciled by hand in the most refactor-fragile layer — which FC/IS (ADR-0004) and the frontend conventions (ADR-0028) forbid. A single, testable pattern for "snapshot seeds, frames update" is needed before the dashboard is built.

## Decision

Live *Line state* is reconciled into a **single TanStack Query cache entry**, keyed by identity (`['lineState', lineId]`) and shared verbatim by the REST hook and the WebSocket writer. The WebSocket lives behind a `ports/` + `adapters/` boundary; each frame is parsed through the generated Zod for the shared `LineStateSnapshot` component schema and run through the **same pure mapper as the REST response** (ADR-0028), so the value written to the cache is the *domain* type — identical in shape to what the REST query seeded, never the raw wire frame. An `application/` hook subscribes **once**, mounted high in the tree, and writes each mapped frame into that cache key via `queryClient.setQueryData`. Because each frame carries the **full** *Line state* shape, the hook pushes rather than invalidating-and-refetching, which would force a needless REST round-trip per live update. The WS-fed query sets `staleTime: Infinity`, and `refetchInterval` polling is enabled **only while the socket is down**, so the two channels are mutually exclusive *while connected*. The one allowed overlap is reconnect: the hook then `invalidateQueries` (a REST refetch) while frames may resume — benign because both channels carry the identical `LineStateSnapshot` shape and last-write-wins. Reconnection uses exponential backoff with jitter and an application-level heartbeat. `useSyncExternalStore` is **not** used: the Query cache already provides tearing-safe reads, and a raw socket exposes no stable snapshot to read. The component reads one hook (`useLineState`) and contains no socket and no merge. *OEE* remains a plain interval-polled query.

## Consequences

### Positive
- One source of truth (the cache); the component is a thin shell, and both IO and orchestration sit in the layers FC/IS assigns them to, testable with an in-memory fake adapter.
- Push-on-full-frame avoids a REST round-trip per live update, and the mutually-exclusive polling fallback degrades gracefully when the socket drops — without the stale-overwrite race that `setQueryData` + an active `refetchInterval` would invite.

### Negative / Trade-offs
- Reconnection, backoff, and heartbeat are hand-rolled (no WS library) — a small amount of lifecycle code we own and test.
- `setQueryData` merging is less forgiving than invalidation if a frame ever becomes a partial delta rather than a full shape; that scenario has a documented escape (below).
- Cache-as-single-source-of-truth assumes the server delivers the *terminal* frame: the Section E broadcaster drops frames for slow consumers (bounded queue), and the heartbeat detects a dead socket, not a dropped frame — so a dropped last frame leaves the cached state stale until the next change or a disconnect. Mitigation (periodic reconcile or a bounded `staleTime`) is deferred (`KNOWN-UNKNOWNS.md`).
- The live frame is not yet a first-class contract schema: OpenAPI 3.1 has no WebSocket message type and the API currently broadcasts an untyped value, so Section F must make the frame conform to and be validated against the shared `LineStateSnapshot` component before the generated Zod can guard it (`KNOWN-UNKNOWNS.md`).

## Migration Path

If frames become high-frequency partial deltas, switch the *Line state* key from `setQueryData` to `invalidateQueries` (or a delta-merge updater function) — the `ports`/`adapters`/`application` boundary is unchanged. Streaming additional entities later = one adapter and one hook each, the same shape. Replacing the hand-rolled socket with a library would be contained to the adapter.

## Sources

- Internal: `docs/ADR/0004-functional-core-imperative-shell.md`, `docs/ADR/0028-frontend-fc-is-and-generated-zod-boundary.md`, `docs/spec/use-cases/UC-001-monitor-line-state.md`, `docs/spec/use-cases/UC-002-observe-oee.md`.
- [Using WebSockets with React Query — Dominik Dorfmeister "TkDodo" (TanStack Query maintainer), 2021](https://tkdodo.eu/blog/using-web-sockets-with-react-query) — invalidate-vs-`setQueryData`, subscribe once at the root.
- [TanStack Query v5 — `QueryClient.setQueryData` reference (TanStack, 2026)](https://tanstack.com/query/v5/docs/reference/QueryClient).
- [`setQueryData` ⇄ background-refetch race — TanStack Query discussion #7180 (2024)](https://github.com/TanStack/query/discussions/7180).
- [React — `useSyncExternalStore` (react.dev, 2026)](https://react.dev/reference/react/useSyncExternalStore) — intended for non-React external stores; built-in state preferred otherwise.
