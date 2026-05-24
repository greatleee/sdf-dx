# ADR-0028: Frontend Functional Core / Imperative Shell + generated-Zod boundary

- **Status:** accepted
- **Date:** 2026-05-24
- **Phase:** 1

## Context

The React dashboard (`apps/dashboard-react/`) is the first TypeScript surface in the repo, and Phase 1's Section F is about to build it. The backend already commits to Functional Core / Imperative Shell (ADR-0004), error-as-value (ADR-0016), the boundary-DTO-≠-domain split (ADR-0018), and contract-first codegen (ADR-0005). The question is whether the frontend earns the same discipline or stays a thin React app.

Two forces make this a load-bearing decision now, settled cold before code lands:

1. **React pulls logic into components.** Co-location of state, effects, and rendering is convenient for small widgets and corrosive at scale — business rules get smeared across components and become untestable without a browser. The Phase 1 plan's Section F sketch already shows the pull: hand-typed `interface`s, `(await r.json()) as LineStateSnapshot` casts at the network boundary, and an unused generated client. Left alone, the frontend would be *less* disciplined than the backend it talks to.
2. **The contract codegen emits TypeScript types only.** `openapi-typescript` produces compile-time types that erase at runtime, so the untrusted network boundary has no runtime guard. The backend validates its boundary with generated Pydantic; the frontend has no equivalent.

## Decision

The frontend adopts FC/IS with the backend's layer discipline, adapted to React: pure `domain/` (no React, no IO, no clock/uuid/random reads), `application/` (TanStack Query hooks and use cases), `ports/` + `adapters/` (IO), and a thin `ui/` shell — with `ports/` as a folder, file-per-feature (mirroring ADR-0022).

The network boundary is validated at runtime by **generated Zod schemas**: `packages/contracts/` gains a target that emits Zod from `sdf-api.yaml` via the `@hey-api/openapi-ts` zod plugin, *alongside* the existing `openapi-typescript` types, committed under `codegen/` and protected by the same drift gate. The generated Zod is the **boundary/contract schema** — the frontend analog of the generated Pydantic boundary DTO (ADR-0018 / ADR-0005 D-2). Adapters parse untrusted responses through it, then project to a **separate frontend domain type** (plain TypeScript, no Zod) via a pure mapper, mirroring ADR-0018's "validation library at the boundary only; the domain is plain data reached by explicit conversion." `ui/` imports domain types only, never the generated schema.

## Consequences

### Positive
- **FE/BE symmetry.** One FC/IS mental model and one boundary-≠-domain split (ADR-0018) across the stack; a reviewer reads a single architecture, not two.
- **Runtime guard at the untrusted seam.** Types alone erase; generated Zod parses what the wire actually carries. It participates in the contract drift gate, so the boundary schema cannot silently diverge from the spec — the only boundary schema *not* under the gate would be a hand-written mirror, which this avoids.
- **Logic leaves components.** Domain rules are pure functions, testable in milliseconds without a browser; components shrink to a shell.

### Negative / Trade-offs
- Adds a second OpenAPI generator and a `zod` runtime dependency to the dashboard. `@hey-api/openapi-ts` 0.97.x is ESM-only and its zod plugin defaults to Zod v4 — pinned and invoked via the Makefile.
- Each concept has two shapes on the frontend too (generated contract Zod + frontend domain type) with a mapper between. Phase 1 mappers are near-identity (rename-only); the ceremony is paid up front for drift-catching and future divergence — the same trade the backend accepts under ADR-0018.
- The mapper is the only wire→domain transform without a runtime guard: a bug that produces a type-valid-but-wrong domain value (e.g. a field swap) is caught by the mandated mapper unit tests + adapter MSW tests (`frontend-code-architecture.md` §3 / §9), not at runtime. This is the deliberate FC/IS trade — mapper correctness is a test concern, not a type-guard concern. (A hand-written domain Zod would not catch a same-typed field swap either, and would be the one boundary schema outside the drift gate — so "no Zod in domain" is the ADR-0018 placement *and* an FE-specific call that post-mapper re-validation is redundant.)
- Supersedes the Phase 1 plan's Section F code samples (hand-typed interfaces, `as` casts, unused client). On conflict, `frontend-code-architecture.md` wins.

## Migration Path

Reverting to a types-only boundary = drop the Zod target and dependency and let adapters trust the `openapi-typescript` shapes; cheap mechanically, forfeits the runtime guard. Swapping the generator (e.g. to `orval`'s zod mode) = change one Makefile target and regenerate; the consuming import surface and the parse-then-map adapter discipline stay identical. The TypeScript consumption/packaging of `codegen/` (mirroring ADR-0027's Python packaging) is wired in Section F and is orthogonal to this decision.

## Sources

- Internal: `docs/ADR/0004-functional-core-imperative-shell.md`, `docs/ADR/0005-contract-first-llm-drift.md` (D-2), `docs/ADR/0016-error-as-value.md`, `docs/ADR/0018-pydantic-at-boundary-only.md`, `docs/ADR/0007-e2e-as-qa-coverage-gate.md`, `docs/ADR/0022-ports-as-folder-file-per-feature.md`, `docs/ADR/0027-generated-contracts-as-installable-package.md`, `.claude/rules/contract-first.md` §2.
- [Hey API — `openapi-ts` Zod plugin (Hey API, 2026)](https://heyapi.dev/openapi-ts/plugins/zod) — OpenAPI 3.1, standalone named Zod schema exports, ESM-only, Zod v4 default.
- [openapi-typescript (OpenAPI-TS, 2026)](https://openapi-ts.dev/) — emits TypeScript types only, no runtime validators.
- Gary Bernhardt, "Boundaries" — Functional Core / Imperative Shell.
