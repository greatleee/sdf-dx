# ADR-0032: Lint hardening — suppression discipline, complexity caps, K3 activation & edit-time hooks

- **Status:** accepted
- **Date:** 2026-05-24
- **Phase:** 1
- **Extends:** ADR-0023 (the import/Konsist/AST contract set — single source of truth for CI gates)

## Context

ADR-0023 established the architectural enforcement layer (import-linter contracts, Konsist tests, AST checks) as the single source of truth for CI gates, on the principle that *a rule survives review pressure only when a tool enforces it mechanically*. That layer is strong on **structural** purity (who may import whom) but leaves four gaps that matter specifically for a codebase authored by an LLM across many independent sessions:

1. **No suppression discipline.** An LLM in session *N+1* has no episodic memory of session *N*'s intent. Told "make CI green", it reaches for `# type: ignore` / `# noqa` / `@Suppress` because that is the locally cheapest path — it does not weigh the architectural cost. import-linter/Konsist/AST checks are strong *precisely because they have no inline-suppress mechanism*; ruff, mypy and detekt did not yet share that property. This is the single highest-leverage anti-drift category and we had none of it.
2. **Cyclomatic complexity was implicit.** ruff selected `C90` (mccabe) with no explicit `max-complexity` (silent default 10) and the `PLR09xx` thresholds at defaults; Kotlin had an explicit `CyclomaticComplexMethod: 12`. The ceiling was neither visible in one place nor aligned across the two languages. LLMs grow functions by accretion (add a branch rather than refactor); the cap must be explicit and reviewable.
3. **Konsist K3 (adapters-no-upward) was deferred.** ADR-0023 listed K3 "for parity ... enabled when Kotlin code lands at Phase 1 Task 4 [via] a Kotlin-specific ADR". Kotlin `adapters/` now exists (bridge, simulator), so K3 activates here.
4. **A formatter conflict and no edit-time feedback.** ktlint (default 140) and detekt (`MaxLineLength: 120`) disagreed on 120–140-char lines with no `.editorconfig` to reconcile them. And nothing formatted/linted code at authoring time — feedback arrived only at CI, the slowest possible loop for an LLM-driven workflow.

This ADR records the decision to close those gaps. It is the Kotlin-contract-set confirmation ADR-0023 anticipated, plus a Python suppression/complexity extension and an edit-time tooling layer. The rule "fix the code, never disable the contract" (rules §12) is unchanged and is the reason suppression discipline is enforced rather than suggested.

## Decision

The following additions extend the ADR-0023 gate set. As with ADR-0023, this list is the source; `pyproject.toml`, `detekt.yml`, `.editorconfig`, the rules files, and CI follow it.

### A. Suppression discipline (Python + Kotlin)

| Gate | Tool | Rule | Effect |
|---|---|---|---|
| Blanket-noqa ban | ruff | `PGH004` (via `PGH`) | `# noqa` without a code is rejected — no silent kill-switch |
| Stale-noqa detection | ruff | `RUF100` (via `RUF`) | a `# noqa` that suppresses nothing is an error (and auto-removed) |
| Typed-ignore requirement | mypy | `enable_error_code = ["ignore-without-code"]` | forces `# type: ignore[code]`, so one ignore masks exactly one error |
| Stale-ignore detection | mypy | `warn_unused_ignores = true` | a `# type: ignore` that no longer suppresses anything is an error |
| Un-suppressible architecture rules | detekt | `ForbiddenSuppress` | `@Suppress` of `CyclomaticComplexMethod`, `LongMethod`, `ReturnCount`, `ForbiddenImport`, `ForbiddenMethodCall`, `MagicNumber`, `ThrowsCount` is rejected |
| TODO/FIXME ban | detekt | `ForbiddenComment` | `TODO:` / `FIXME:` / `STOPSHIP:` fail the build (LLMs shed scope via forgotten markers) |
| Domain suppression allowlist | custom script | `scripts/check-domain-no-suppress.py` | ruff has no dir-scoped suppression ban; this fails CI on any inline `# noqa` / `# type: ignore` under `*/src/**/domain/` or `**/shared_kernel/` — extending import-linter's no-inline-suppress property to ruff/mypy in the most drift-expensive layer |

Additionally, `ingest-python`'s mypy is brought to `api-python` *strictness* parity — `disallow_any_decorated` and `warn_return_any`, which `api-python` already set (orthogonal to the suppression flags above, folded in here as a consistency fix).

Known limitation (documented in `detekt.yml`): `ForbiddenSuppress` cannot forbid suppressing *itself* ([detekt#7038]); accepted, called out for reviewers.

### B. Cyclomatic complexity — made explicit and aligned

| Gate | Tool | Value |
|---|---|---|
| `max-complexity` | ruff mccabe | **12** (aligned with Kotlin `CyclomaticComplexMethod`) |
| `max-args` / `max-branches` / `max-returns` / `max-statements` | ruff pylint | 6 / 12 / 6 / 50 (explicit, generous; not tightened) |
| `NestedBlockDepth` / `LongParameterList` | detekt | 4 / func 6, ctor 7 (made explicit) |
| `ThrowsCount` | detekt (`style`) | 2 (explicit; pairs with `ReturnCount: 3`) |

### C. Private-member-leak (Python)

`SLF001` (flake8-self, via `SLF`) is added to catch `obj._private` attribute access across class boundaries — the form `PLC2701` (already active) does not cover (it catches only the *import* of a private name). `tests/**` carries an `SLF001` per-file-ignore (fakes legitimately poke internals, ADR-0024).

### D. Kotlin layer enforcement — K3 activated + lint-level defense-in-depth (Option 2)

- **K3 (adapters-no-upward)** is implemented in `bridge` and `simulator` via Konsist `assertArchitecture` (layer direction: `adapters` may depend on `domain`, `domain` depends on nothing internal). Written with the layered DSL so it stays correct as `ports`/`application` layers are introduced.
- **detekt `ForbiddenImport`** (scoped `includes: ['**/domain/**']`) is a *superset* of the two modules' Konsist K2 import bans — uniform across bridge + simulator and intentionally broader than the per-module tests (e.g. `org.springframework.**` vs the bridge test's narrower `org.springframework.kafka`): `org.apache.kafka.**`, `org.springframework.**`, `org.eclipse.paho.**`, `org.eclipse.tahu.**`, `com.fasterxml.jackson.**`. A cheap PSI-level check (no type resolution).
- **detekt `ForbiddenMethodCall`** (scoped to domain) mirrors Konsist K1 at lint level: bans `Instant.now`, `UUID.randomUUID`, `System.currentTimeMillis`, `System.nanoTime`, and `println`/`print`. Scoped to `**/domain/**` on purpose — adapters and composition roots legitimately read the system clock.

`ForbiddenMethodCall` resolves calls to fully-qualified names, which **requires detekt type resolution**. The plain `detekt` Gradle task runs without a Kotlin classpath, where the rule is a silent no-op; the type-resolution variants `detektMain` / `detektTest` are required. The CI Kotlin job therefore changes from `./gradlew ktlintCheck detekt test` to `./gradlew ktlintCheck detektMain detektTest test`.

### E. Formatter alignment (Kotlin)

`apps/ot-gateway-kotlin/.editorconfig` sets `max_line_length = 120` + `indent_size = 4`, reconciling ktlint with detekt's `MaxLineLength: 120`. `ktlint_code_style` is deliberately not set (would switch rulesets and force a mass reformat). Python formatting is unchanged (ruff format, line length 100, already consistent across both apps).

### F. Edit-time hooks — per-folder, self-only

A Claude Code `PostToolUse` hook (`.claude/hooks/lint-on-edit.sh`, registered in `.claude/settings.json` for `Edit|Write|MultiEdit`) formats and lints the single edited file, routing **only** to that file's own toolchain (editing an `api-python` file never invokes `ingest-python` or Kotlin tooling):

- **Python** (`apps/{api,ingest}-python/**.py`): `ruff format` + `ruff check --fix` via that app's `.venv`; remaining (non-auto-fixable) errors are returned to the agent via exit code 2.
- **Kotlin** (`apps/ot-gateway-kotlin/**.{kt,kts}`): format-only via standalone `ktlint -F` if present, else a one-line note and defer to pre-commit — `./gradlew` is never invoked at edit time (~15–20 s is too slow for a per-edit loop; full detekt/ktlint stays at pre-commit + CI).
- **Contracts** (`packages/contracts/openapi/*.{yaml,yml}`): best-effort `make lint` (spectral); `codegen/**` is never linted (build output).
- Missing toolchains degrade gracefully (exit 0) — a hook must never block an edit because a given worktree has not run `init.sh`.

This is an authoring-loop accelerator, **not** a gate. The authoritative gates remain the pre-commit hook (contracts) and CI.

## Consequences

### Positive
- Suppression discipline gives ruff/mypy/detekt the same "cannot be silenced inline" property that import-linter/Konsist/AST already have — the highest-leverage defense for a multi-session LLM-authored repo.
- Complexity ceiling is now explicit, reviewable in one place, and aligned across Python and Kotlin.
- K3 closes the last deferred ADR-0023 Kotlin contract; `ForbiddenImport`/`ForbiddenMethodCall` add lint-level defense-in-depth that runs faster than (and complements) the Konsist tests.
- Switching to type-resolution detekt is strictly more analysis — it immediately surfaced a latent `NoNameShadowing` bug in `BridgeApplication.kt`, now fixed.
- The formatter conflict is resolved; edit-time hooks move lint/format feedback from CI to authoring time without slowing the loop.

### Negative / Trade-offs
- **Two-place forbidden lists in Kotlin.** detekt `ForbiddenImport`/`ForbiddenMethodCall` overlap Konsist K1/K2 by design (defense-in-depth). A new forbidden API must be added in both detekt.yml and the Konsist tests — itself a small drift surface. Mitigation: the rules-file §12 update names both as a paired edit.
- **Type-resolution detekt is slower** than the plain task (full Kotlin classpath). Acceptable in CI; the reason the edit-time hook does not run detekt.
- **`warn_unused_ignores` / `RUF100` can false-positive** across multiple Python versions or with multi-code noqa lines. Single-version CI today, so low risk; scope per-module if cross-version CI is added.
- **More gates = more maintenance.** Each is one config line or one small file, and review-visible.

## Migration Path

Forward: additions live in `apps/*/pyproject.toml`, `apps/ot-gateway-kotlin/detekt.yml` + `.editorconfig`, the two Konsist `ArchitectureTest.kt` files, `scripts/check-domain-no-suppress.py`, `.github/workflows/ci.yml`, and `.claude/` (hook + settings). The rules files (`.claude/rules/backend-code-architecture.md` §12) follow this ADR.

If a suppression-discipline rule proves too noisy (false positives that force *legitimate* suppressions — which would ironically train the team to suppress), the response is to tune the rule's scope, not disable it; a material reversal supersedes this ADR. The edit-time hook is non-load-bearing and may be changed freely without an ADR (it is not a gate).

Reversal cost is mechanical (delete config lines, the script, the hook), but the suppression-discipline property is the point — reverting it reopens the drift surface this ADR closes.

## Sources

- [blanket-noqa (PGH004) | Ruff](https://docs.astral.sh/ruff/rules/blanket-noqa/)
- [unused-noqa (RUF100) | Ruff](https://docs.astral.sh/ruff/rules/unused-noqa/)
- [private-member-access (SLF001) | Ruff](https://docs.astral.sh/ruff/rules/private-member-access/)
- [mypy — `warn_unused_ignores`, `ignore-without-code`](https://mypy.readthedocs.io/en/stable/config_file.html)
- [detekt — ForbiddenComment / ForbiddenImport / ForbiddenMethodCall / ForbiddenSuppress (style rule set)](https://detekt.dev/docs/rules/style/)
- [detekt — Suppressing Issues](https://detekt.dev/docs/introduction/suppressing-rules/); [detekt#7038] — ForbiddenSuppress self-suppression limitation — https://github.com/detekt/detekt/issues/7038
- [Konsist — assertArchitecture / layered dependencies](https://docs.konsist.lemonappdev.com/)
- [Claude Code — Hooks (PostToolUse)](https://docs.anthropic.com/en/docs/claude-code/hooks)
- Internal: `docs/ADR/0023-importlinter-contract-set.md` (the gate set this extends), `docs/ADR/0017-system-reads-injection.md`, `docs/ADR/0019-orm-containment-in-adapters.md`, `docs/ADR/0024-fakes-with-in-memory-dataset.md`.
