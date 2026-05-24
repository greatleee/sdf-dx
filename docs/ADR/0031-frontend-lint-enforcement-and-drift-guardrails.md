# ADR-0031: Frontend lint enforcement set + LLM-drift guardrails

- **Status:** accepted
- **Date:** 2026-05-24
- **Phase:** 1

## Context

ADR-0028 puts the frontend on the same Functional Core / Imperative Shell footing as the backend: `domain/` is pure and synchronous — no React, no IO, no Zod, no clock/uuid/random reads (rules §2) — failures are discriminated-union values switched on exhaustively (rules §6/§10), and dependencies flow `ui → application → ports → domain` with adapters wired only at the composition root (rules §1). ADR-0029/0030 layer the live-cache and state-residence rules on top.

On the backend these rules survive review pressure only because **ADR-0023 enforces them mechanically** — `import-linter` contracts for the import graph plus custom AST checks (A1/A2) for call-site reads of the clock/uuid that `import-linter` can't express. The frontend, until now, had only the Phase-1 plan's Task 22 starter config: a two-row `eslint-plugin-boundaries` matrix and three `@typescript-eslint` rules. That left the FE enforcement surface materially weaker than the rules it was meant to guard:

1. **No FE analog of AST checks A1/A2.** Nothing stopped `Date.now()`, `new Date()`, `Math.random()`, `crypto.randomUUID()`, or browser-IO globals (`fetch` / `window` / `document` / `localStorage`) from appearing inside `domain/` or `shared/` — the exact clock/uuid/random *injection* discipline (rules §2) the backend guards with A1/A2.
2. **The boundary matrix under-specified §1's direction.** `ui → adapters` was allowed (a leak — §1/§7); `shared/` was unconstrained although §2 holds it to domain-grade purity; and `ports/` was not a registered element, so `domain → ports` was invisible.
3. **No exhaustiveness guard** on discriminated-union `switch` (§6/§10), **no cycle guard**, and **no complexity cap** — the backend pins cyclomatic complexity via ruff `C90`/mccabe (default 10).
4. **No formatter at all.** Python has `ruff format`, Kotlin has `ktlint`; the FE had nothing, so formatting churn would muddy diffs and obscure the contract-vs-domain seam.

This ADR is the FE sibling of ADR-0023: it makes the frontend enforcement set a decision of record, single-sourced here. The rules file §11 and arch doc §7 follow it (they restate the do/don't and the *why*, but the list lives here).

## Decision

The frontend enforcement set is the source of truth below. Changes land here first; `eslint.config.js`, the rules file §11, and arch doc §7 follow.

**ESLint flat config** (`apps/dashboard-react/eslint.config.js`):

| # | Rule | Scope | Enforces / forbids | Maps to |
|---|---|---|---|---|
| B1 | `boundaries/element-types` | all `src` (elements: `domain` / `application` / `ports` / `adapters` / `ui` / `shared`) | `domain ↛ {adapters, application, ui, ports}`; `shared ↛ {adapters, application, ui, ports, domain}`; `ui ↛ adapters`; `application ↛ {adapters, ui}` | rules §1, §7; FE analog of import-linter #4/#6/#7 |
| B2 | `@typescript-eslint/switch-exhaustiveness-check` | `src` | a discriminated-union `switch` must cover every case (no silent miss when `LineState` grows) | rules §6/§10 |
| B3 | `import/no-cycle` | `src` | no circular module deps (`boundaries` cannot see cycles) | rules §1/§11 |
| B4 | `complexity: ["error", 10]` | `src` | cyclomatic complexity ≤ 10 | parity with backend ruff `C90` (mccabe default 10) |
| B5 | `no-restricted-syntax` | `domain/` + `shared/` | bans `Date.now()`, `new Date()` (no-arg), `Math.random()`, `crypto.randomUUID()`, and `await` (domain is synchronous) | FE analog of AST A1/A2; rules §2 |
| B6 | `no-restricted-globals` | `domain/` + `shared/` | bans `fetch`, `WebSocket`, `localStorage`, `sessionStorage`, `window`, `document`, `navigator` | rules §2 |
| B7 | `@typescript-eslint/no-restricted-imports` | `domain/` + `shared/` | bans `zod`, `react`, `react-dom`, `@tanstack/react-query`, and the router/form/store libs (`react-router-dom`, `@tanstack/react-router`, `react-hook-form`, `zustand`) | rules §2/§3/§12 |
| B8 | `@typescript-eslint/no-restricted-imports` (pattern) | `application/` | bans `*/adapters/*` imports (belt-and-suspenders with B1) | rules §1/§4 |
| — | `no-explicit-any`, `no-floating-promises`, `consistent-type-imports`, + `strictTypeChecked` | `src` | carried from plan Task 22 | rules §10 |

Each guard was **fixture-tested at authoring** — a deliberately-violating file was linted and the expected error captured before the fixture was deleted — so the set is known to fire, not merely to be present.

**Formatter.** Prettier owns formatting (`printWidth: 100`, for parity with the backend's ruff `line-length = 100`; otherwise Prettier 3 defaults). `eslint-config-prettier` is the **last** flat-config block, switching off ESLint's stylistic rules so the two never fight. We deliberately do **not** use `eslint-plugin-prettier` — running Prettier as a lint rule is slower and noisier, against current Prettier guidance. `format` / `format:check` scripts; `format:check` is the gate.

**Earliest-feedback layer (Claude Code hook).** A `.claude/settings.json` `PostToolUse` hook runs Prettier (`--write`) then ESLint on any `apps/dashboard-react/**/*.{ts,tsx}` file an agent edits, so LLM-introduced drift is caught **at edit time** — before the human, before git, before CI. It *complements*, and does not replace, the CI gate (rules §11) and the eventual git pre-commit (plan Task 28). A Claude Code hook is chosen over a git hook here on purpose: in-session feedback during agentic coding is where drift in this repo originates; the git-hook / CI layers remain the authority for human commits.

## Consequences

### Positive
- The frontend now has the FE analog of the backend's AST checks (B5/B6) and a boundary matrix that expresses the full §1 dependency direction (B1) — the two largest gaps closed.
- Single source for the FE enforcement set; the rules file §11 and arch doc §7 cite this ADR rather than re-deriving the list.
- Drift is caught at three depths — agent edit (Claude hook), CI lint (this set), and the contract drift gate (ADR-0028) — with the cheapest layer firing first.
- The set is proven (fixture-tested), not aspirational.

### Negative / Trade-offs
- B5–B8 partly duplicate intent the `boundaries` matrix already covers. Kept deliberately: they fire on a *different signal* — package name / call-site (B5–B8) versus element topology (B1) — the same belt-and-suspenders stance ADR-0023 contracts #6/#7 accept.
- `no-restricted-syntax` selectors are string-coupled to the ESLint AST shape; a parser change needs a review pass. Low cost, paid rarely.
- The Claude hook only fires for **agent** edits inside a Claude Code session; human hand-edits fall back to CI / pre-commit. Acceptable — the hook targets the LLM-drift origin specifically, and is not the authority.
- Several rules are **not lint-enforceable** at reasonable cost and are left to code review + test placement, stated honestly: `new WebSocket` inside a component (§5), business logic written inline in a JSX body (§7), and adapter role-prefix naming (§8). A custom plugin would cost more than the drift it prevents.
- `ts-prune` (in devDeps from the scaffold) is archived and its own README redirects to **knip**; swapping it is a recommended follow-up, not part of this ADR.

## Migration Path

Forward: each rule is a block in `eslint.config.js`; the formatter is `.prettierrc.json` + `eslint-config-prettier`; the hook is a `.claude/settings.json` entry. Reversal is mechanical (delete the blocks / the hook entry).

If a guard proves too strict — false positives that mask a genuine refactor — the response is to **refine the selector or supersede this ADR**, never to add an inline `eslint-disable`, per rules §11 ("fix the direction, not the gate"). This mirrors ADR-0023's "fix the code, not the contract".

## Sources

- typescript-eslint — `switch-exhaustiveness-check` — https://typescript-eslint.io/rules/switch-exhaustiveness-check
- typescript-eslint — `no-restricted-imports` — https://typescript-eslint.io/rules/no-restricted-imports
- ESLint — `no-restricted-syntax` / `no-restricted-globals` — https://eslint.org/docs/latest/rules/no-restricted-syntax
- `eslint-plugin-boundaries` (element-types) — https://github.com/javierbrea/eslint-plugin-boundaries
- Prettier — "Integrating with linters" (why `eslint-config-prettier`, not `eslint-plugin-prettier`) — https://prettier.io/docs/integrating-with-linters
- Claude Code hooks — https://docs.claude.com/en/docs/claude-code/hooks
- Internal: `docs/ADR/0023-import-contract-set.md` (backend enforcement), `docs/ADR/0028-frontend-fc-is-and-generated-zod-boundary.md`, `docs/architecture/2026-05-24-frontend-architecture.md` §7, `.claude/rules/frontend-code-architecture.md` §1/§2/§6/§10/§11.
