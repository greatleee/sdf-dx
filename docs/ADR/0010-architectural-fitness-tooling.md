# ADR-0010: Architectural fitness via tooling

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

This project's headline thesis (spec §1.1) is "AI-native senior … with *formal LLM drift containment*". The architecture decisions that carry that thesis — Functional Core / Imperative Shell (ADR-0004), errors-as-values (ADR-0016), system-read injection (ADR-0017 / ADR-0021), Pydantic-at-boundary (ADR-0018), ORM containment (ADR-0019), per-feature ports (ADR-0022) — only hold if a tool, not a reviewer, enforces them. LLM-generated code reaches for IO in domain, exceptions in core, `datetime.now()` inside a pure function, and `import pydantic` deep in a module, *every time the prompt is loose*. Human review catches the obvious case and misses the subtle one at the rate LLM output is produced.

Three forces shape this decision:

1. **The repo is polyglot** (ADR-0001: Python + TypeScript + Kotlin). Each language has its own mature fitness-function toolchain. A single cross-language matrix — drift category × language → tool — is the only way to keep the *same* architectural rule enforced uniformly across three stacks rather than three divergent rule sets.
2. **Feedback cost must match failure cost.** A formatter is milliseconds; a full strict type-check plus import-contract analysis is seconds-to-minutes. Running everything on every keystroke is intolerable; running nothing until CI is too late. The execution surface splits into a fast local layer and a thorough CI layer.
3. **The concrete enforcement list already has an owner.** ADR-0023 enumerates the seven Python `import-linter` contracts, the three custom AST checks (A1–A3), and the three Konsist tests (K1–K3). This ADR must *not* restate or renumber them — that would create exactly the drift this whole apparatus exists to prevent. This ADR owns the umbrella decision (*architecture is enforced by automated fitness functions*), the cross-language matrix, and the local-vs-CI execution split.

The term "fitness function" is Ford / Parsons / Kua (*Building Evolutionary Architectures*): an objective, automated check that a candidate architecture meets a structural characteristic. Import contracts, type strictness, and complexity limits are all fitness functions in that sense.

## Decision

Architecture is enforced by **automated fitness functions across all three languages, run at two execution layers.** No architectural rule in this repo relies on reviewer vigilance alone; each maps to a tool that fails the build.

### D-1. Cross-language fitness matrix

Each drift category is covered in every language by a named tool. This is the umbrella surface; the *exact contract enumeration* for the layer-boundary and BC-boundary row (Python) lives in ADR-0023, not here.

| Drift category | Python | TypeScript | Kotlin |
|---|---|---|---|
| Layer boundary (domain ↛ adapters) & BC boundary | `import-linter` (contract set per **ADR-0023**) | `eslint-plugin-boundaries` | Konsist (tests per **ADR-0023**) |
| Private / internal-API leak | `ruff` `PLC2701` (private import) + `PLE0604` | `import/no-internal-modules` + `@internal` JSDoc | `internal` keyword + `-Xexplicit-api=strict` |
| Type safety | `mypy --strict` (`disallow-any-*`) | `tsc --strict --noUncheckedIndexedAccess` + `no-explicit-any` | Kotlin compiler + `detekt` |
| Complexity | `ruff` `C901` / `PLR*` | `eslint` `complexity` | `detekt` `CyclomaticComplexMethod` |
| Unused code | `ruff` `F401` / `F841` | `ts-prune` + `no-unused-vars` | `detekt` `UnusedImports` |
| Async drift | `ruff` `B` (bugbear) / `ASYNC` | `no-floating-promises` | `detekt` coroutine rules |
| Codegen drift | CI `git diff --exit-code` gate | CI `git diff --exit-code` gate | CI `git diff --exit-code` gate |
| Format | `ruff format` | `prettier` | `ktlint` |
| Latent bugs | `ruff` `B` / `S` (bandit-derived) | `typescript-eslint` recommended | `detekt` |

The codegen-drift row is the contract-first SoT guard from ADR-0005 §D-3 (the `make all` + `git diff` gate); it appears here only as the cross-language fitness category it belongs to.

### D-2. Two execution layers

- **LOCAL (pre-commit hook): millisecond linters / formatters only** — `ruff` (lint + format), `eslint`, `ktlint`, `detekt`. These are fast enough to run on every commit without breaking flow. Slower whole-program analyses (`mypy`, `tsc`, Konsist) surface *interactively in the IDE via the language server* during editing, but are **not** in the pre-commit hook.
- **CI (`make ci`): the full surface** — strict `mypy` + strict `tsc`, `import-linter` contracts, Konsist tests, the codegen-drift gate, the custom AST checks, and all test tiers. CI is the authoritative gate; a green pre-commit does not imply a green CI.

This split is the same one ADR-0023 §"CI gate behavior" states from the contract side; this ADR generalizes it to every category in the matrix.

### D-3. Extra gate for AI-generated PRs

A PR carrying the AI-generated label triggers one additional gate beyond the matrix: it fails if (a) the PR introduces a load-bearing decision with **no ADR citation**, or (b) an **infrastructure import appears inside a domain module** that the standard contracts somehow did not already block. This is a belt-and-suspenders check aimed squarely at the drift modes ADR-0004 / ADR-0017 / ADR-0018 describe as LLM-instinctive.

### D-4. Deference — the concrete enforcement list is owned by ADR-0023

The **seven** Python `import-linter` contracts, the **three** custom AST checks, and the **three** Konsist tests (K1–K3) are enumerated, named, and numbered **only** in ADR-0023. This ADR references that enumeration as the single source of truth and deliberately does not reproduce it; any reader needing the exact contract names goes to ADR-0023. The clock / UUID / system-read AST checks (A1–A2) trace their *rationale* to ADR-0017 and ADR-0021; the ports-layout expectations that the boundary contracts assume trace to ADR-0022. On any apparent conflict between this matrix and ADR-0023's list, **ADR-0023 wins.**

## Consequences

### Positive
- One umbrella decision plus one matrix make the *whole* enforcement story legible on a single page, across three languages, without duplicating the contract list that ADR-0023 owns.
- The local-vs-CI split keeps commit-time feedback in milliseconds while CI stays authoritative — fast inner loop, strict outer loop.
- The AI-PR extra gate makes the project's central thesis (formal LLM drift containment) a mechanical reality on the exact PRs most at risk.
- Cross-language parity is explicit: a reviewer can see at a glance that "unused code" or "type safety" is covered in Kotlin and TypeScript, not just Python.

### Negative / Trade-offs
- The matrix is a maintenance surface of its own. When a tool is added, retired, or renamed in any language, this table must be updated — and kept consistent with ADR-0023 for the rows it shares.
- Two layers mean a class of failures (strict-type, import-contract) is invisible locally in the pre-commit hook and only caught in CI. Mitigation: IDE language-server surfacing of `mypy` / `tsc` / Konsist during editing, so the developer sees them before pushing.
- The AI-PR gate depends on a label being applied honestly. A mislabeled PR skips the extra gate (though the standard matrix still runs).

## Migration Path

Forward: rules are **tightened over time, never silently relaxed.** Adding a stricter `ruff`/`detekt` rule or a new contract category is an ordinary PR. **Any relaxation** — disabling a rule, widening an `Any` allowance, dropping a category — requires a PR whose description carries the rationale, and (for a contract owned by ADR-0023) an ADR update there first. The standing rule from the rules file §12 holds: *fix the code, not the contract.*

Reversal (abandoning tooling-enforced fitness) is a category-level decision that would undermine ADR-0004's purity guarantee and ADR-0023's enforcement layer simultaneously; it would supersede both.

## Sources

- Neal Ford, Rebecca Parsons, Patrick Kua, *Building Evolutionary Architectures* (O'Reilly, 2nd ed. 2022) — "fitness functions" — https://www.thoughtworks.com/insights/books/building-evolutionary-architectures
- `import-linter` — https://import-linter.readthedocs.io/en/stable/
- `ruff` (lint + format, rule families B/S/C901/PLR/PLC/PLE/F) — https://docs.astral.sh/ruff/rules/
- `mypy` strict mode — https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict
- `eslint-plugin-boundaries` — https://github.com/javierbrea/eslint-plugin-boundaries
- `ts-prune` — https://github.com/nadeesha/ts-prune
- `typescript-eslint` (`no-floating-promises`, `no-explicit-any`) — https://typescript-eslint.io/rules/
- `detekt` — https://detekt.dev/
- `ktlint` — https://pinterest.github.io/ktlint/
- Konsist — https://docs.konsist.lemonappdev.com/
- Kotlin explicit API mode (`-Xexplicit-api=strict`) — https://kotlinlang.org/docs/whatsnew14.html#explicit-api-mode-for-library-authors
- Internal: `docs/ADR/0023-importlinter-contract-set.md` (authoritative contract / AST / Konsist enumeration — this ADR defers there), `docs/ADR/0017-system-reads-injection.md`, `docs/ADR/0021-clockport-protocol-standardized.md`, `docs/ADR/0022-ports-as-folder-file-per-feature.md`, `docs/ADR/0005-contract-first-llm-drift.md` §D-3 (codegen-drift gate); design spec §6 (`docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`).
