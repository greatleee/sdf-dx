# Code Review Guide

> **Purpose**: Runtime review guide loaded into CodeRabbit on every PR. Applies to the entire repository tree (root scope). Area-specific rules belong in `<area>/CODE_REVIEW_GUIDE.md` (registered via the same glob in `.coderabbit.yaml`).
>
> **Authority**: This file is the *review-time* SOT. Canonical specifications live in `docs/spec/**`, decisions in `docs/ADR/**`, plans in `docs/plans/**`. When this guide conflicts with them, the canonical sources win — fix this file.
>
> **Edit policy**: This file is a digest, not an immutable SOT. In-place edits OK. Keep it tight.

## Review Principles

- Push back on weak reasoning. Don't validate work just because it compiles.
- Priority order: correctness > security > consistency with spec/ADR > maintainability > style.
- Flag missing test coverage on new behavior; flag tests that assert implementation rather than contract.
- Surface hidden assumptions explicitly (what must be true for this code to be correct?).

## Phase 1 Context — single factory vertical slice

_To be filled in as Phase 1 spec stabilizes. Canonical sources in `docs/spec/**`._

### Use cases in scope
- _TBD — see `docs/spec/USE-CASES.md`_

### Actors
- _TBD — see `docs/spec/ACTORS.md`_

### Key glossary terms
- _TBD — see `docs/spec/GLOSSARY.md`_

### Out of scope (Phase 1)
- Multi-factory orchestration
- Public-facing deployment (Phase 2)
- _add as encountered_

## TypeScript / React SPA (default stack)

- Explicit return types on exported functions; no `any` at module boundaries.
- No `console.*` in production code paths. Debug behind a dev-only flag.
- Hooks rules respected; no derived state stored in `useState` (use `useMemo` or compute on render).
- Prefer typed boundaries over runtime parsing — if both, validate at the boundary (Zod or equivalent) and trust types after.

## Security baseline

- No secrets, tokens, or API keys in source. `gitleaks` is the safety net, not the gate — flag suspicious patterns even if it doesn't fire.
- Validate user input at every boundary (API, form, URL params, query strings).
- No raw HTML injection from user input. Use framework-provided escaping; flag any `dangerouslySetInnerHTML` or equivalent.

## Tests

- Behavior tests > implementation tests. Test public contracts, not internals.
- New feature → at least one test for the happy path.
- Bug fix → regression test that fails before the fix.
- Flaky tests (timing, randomness, network without stub) get flagged for hardening or quarantine.

## What to skip

- Style nits already covered by ESLint/Prettier in CI (CodeRabbit's tool linters are disabled in `.coderabbit.yaml` for exactly this reason).
- Naming bikeshedding unless naming is genuinely misleading.
- Refactors unrelated to the PR's purpose — note in a follow-up issue, don't block the PR.

## Doc/ADR/plan PRs

- ADR PRs: verify `supersede` semantics if replacing prior ADR (new file, old file marked superseded — no in-place edit).
- Plan PRs: check that scope, success criteria, and out-of-scope are explicit.
- Spec changes go through their own SOT process — not coded against directly.
