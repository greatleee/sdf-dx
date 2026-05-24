# CLAUDE.md

* Important (critical)** : Your user is often wrong, and is suspiciously pleased to have their mistakes reasonably pointed out. Always think critically about the user's claims. Don't assume the user is correct just because they speak assertively — if their reasoning is weak or contradicts the facts, point it out immediately. For this user, accurate corrections are far more helpful than simple agreement.

## Project overview

Portfolio project for the 현대차그룹 SDF Manufacturing DX Senior Full-Stack role. Builds one *honest* end-to-end slice of a smart-factory data fabric: simulated equipment signals → live line state + OEE. Scope is deliberately bounded — data path only; equipment *control*, digital twin, and Catena-X are out (see `docs/KNOWN-UNKNOWNS.md`), and drawing that boundary is itself part of the deliverable. Standards-grounded, not faked: ISA-95, ISO 22400, OPC UA Companion Spec, Sparkplug B.

**Data path:** Kotlin edge (Sparkplug B / MQTT) → Kafka → Python ingest → TimescaleDB → FastAPI → React.

**Polyglot apps** (deps are per-worktree, never shared — see Development setup):
- `apps/ot-gateway-kotlin/` — Kotlin: `gateway/` (edge), `bridge/` (Sparkplug→Kafka), `simulator/` (device sim).
- `apps/ingest-python/` — Kafka consume → normalize → TimescaleDB.
- `apps/api-python/` — FastAPI domain service (line state machine, OEE / A·P·Q).
- `packages/contracts/` — OpenAPI / Sparkplug `.proto` / Kafka JSON Schema; the codegen source of truth.
- `infra/timescale/` + `docker compose up`.

**Load-bearing principles** (the rules below enforce these): Functional Core / Imperative Shell, contract-first inter-service schemas, architecture-as-tests (import-linter + Konsist + AST checks), error-as-value, injected clock/uuid/random.

Phase status: see `README.md`. Active phase plan: `docs/plans/`.

## Development setup

Per-worktree init (idempotent): `bash scripts/init.sh` — sets git hooks + installs each app's deps (`.venv`/`node_modules`/Gradle, not shared across worktrees).
Before working in any folder other than `docs/`, verify that area's deps are installed; if not, run the script first.

## Testing integrity (critical)

**Do not warp test code or production code to make tests pass.** This
is the most important rule.

- A failing test means **fix the production bug**, not the test
  assertion. Adjusting the expected value to match current (broken)
  behaviour is forbidden.
- Don't delete test cases, loosen assertions, or add `skip` / `xfail`
  to hide failures.
- Don't replace specific assertions with weaker ones (e.g.
  `assertTrue(True)`).
- Don't add test-only branches to production code (`if testing:`).
- Changing a test's intent requires explicit prior justification and
  approval.

Tests are the contract that verifies the code matches the spec. The
code follows the contract — never the other way around.

## Claude rules index

`.claude/rules/*.md` are auto-loaded as project instructions every session — fast-scan, do/don't condensations of the architecture doc + ADRs. Map of what each governs and when it binds:

| File | Governs | Applies when |
|---|---|---|
| `rules/backend-code-architecture.md` | Layer placement, domain purity, error-as-value, clock/UUID/random injection, ORM containment, ports, naming, tests, CI gates. On conflict, these rules win over Phase-1 plan code samples. | Writing any Python/Kotlin under `apps/*/src` (domain / application / adapters / composition). |
| `rules/frontend-code-architecture.md` | FC/IS layer placement, domain purity, generated-Zod boundary + dual-schema, TanStack Query + WebSocket-into-cache, failure taxonomy, UI rules, ubiquitous-language naming, tests, TS strict, CI boundary gates. On conflict, these rules win over Phase-1 plan Section F samples. | Writing any TypeScript/React under `apps/dashboard-react/src` (domain / application / ports / adapters / ui). |
| `rules/contract-first.md` | Schema-as-SoT direction, allowed generators, codegen drift gates, schema-change commit hygiene. | Touching anything under `packages/contracts/`. |
| `rules/phase-iteration.md` | Chapter 0 batch ordering; Create / Implementation / Promote / Living-doc task kinds. | Planning, scaffolding, or executing a phase; writing or reviewing a `docs/plans/` plan. |

Full rationale lives in the ADRs / `docs/architecture/` doc each rule file cites.

## Docs: spec, ADR & SoT layers

`docs/SOT-LAYERS.md` is the authority on which docs are source-of-truth and how to edit them (frozen vs. living; supersede-don't-edit). Quick map:

- `docs/spec/` — functional surface. `USE-CASES.md` (registry) + `use-cases/UC-*.md` (per-UC), `ACTORS.md`, `GLOSSARY.md` (ubiquitous language — **code identifiers and spec wording must match a glossary term verbatim**).
- `docs/ADR/NNNN-*.md` — decision records, frozen at decision time. Reverse a decision with a *new* ADR that supersedes the old; never edit an accepted ADR in place.
- `docs/architecture/` — engineering conventions (living guide; the `.claude/rules/` files condense this).
- `docs/roadmap/` — strategy / design spec (frozen at project start). `docs/plans/` — phase plans (disposable scaffold, archived after the phase tag lands).
- `docs/DOMAIN-NOTES.md`, `docs/KNOWN-UNKNOWNS.md`, `docs/AI-WORKFLOW/` — domain study notes, declared out-of-scope, and incident-time AI-collaboration cases.

When unsure where information belongs, use the "where does this belong?" test in `docs/SOT-LAYERS.md`.
