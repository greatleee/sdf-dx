# ADR-0005: Contract-first inter-service schemas as single source of truth (with LLM drift containment)

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

Design spec §2.3 already states the *policy*: every inter-service contract is a committed schema, codegen produces models/clients, change flows `spec → codegen → impl` (not the reverse), and CI fails on drift. ADR-0000 §"load-bearing decision" classifies "contract format" as an explicit trigger for an ADR at Chapter 0.

This ADR exists because §2.3's one-paragraph policy is **under-specified** in three ways that materially affect Phase 1 implementation:

1. **Which direction with FastAPI?** FastAPI's documented and idiomatic flow is *code-first*: write Pydantic models → FastAPI derives `/openapi.json`. The polyglot consumer set in this repo (Kotlin gateways, TypeScript frontend, Phase 2+ Kotlin REST services) cannot tolerate that direction — every non-Python consumer would regenerate against a possibly-stale exported snapshot, and FastAPI's auto-derived spec can leak framework-specific shape that downstream Kotlin/TS generators handle inconsistently (Microsoft ISE 2023; Bump.sh code-first analysis). §2.3 says "spec first" but does not commit to a tool or a discipline strong enough to resist FastAPI's natural pull.

2. **Which generator, and how much of it?** The Python ecosystem has two relevant tools by the same author: `datamodel-code-generator` (Pydantic model generation only) and `fastapi-code-generator` (full route-stub generation, self-labeled "experimental"). Model-only generation keeps route handlers as the human-authored layer where FastAPI's `response_model`, `Depends`, status codes, and validation live — and route handlers cannot tell that a model was generated rather than hand-written. Full-stub generation makes the route layer also a regeneration target, which on an experimental tool is unacceptable risk.

3. **What does "CI gate fails on drift" actually check?** A `git diff --exit-code codegen/` only catches "generated output diverged from committed output." It does *not* catch (a) a malformed or convention-breaking spec that *successfully* generates broken code, nor (b) a breaking change to the spec that lands undetected because all consumers happen to be in the same repo. Both are the failure modes contract-first promises to prevent; both need explicit tooling beyond a diff check.

External-context research (2026-05-23, sources below) supplied direct evidence on all three: Malt Engineering published a production case study doing exactly this (polyglot, FastAPI, OpenAPI as SoT); Pydantic's docs endorse `datamodel-code-generator`; the OpenAPI Initiative names the OAD itself as the "first-class source file" that gates the build; the Spring/Kotlin ecosystem treats contract-first (`kotlin-spring` + `delegatePattern=true`) as the polyglot default.

## Decision

### D-1. OpenAPI 3.1 YAML is the single source of truth for the REST surface

`packages/contracts/openapi/sdf-api.yaml` is hand-authored. Pydantic v2 models (Python) and TypeScript types (frontend) are *outputs* of this file, never inputs to it. Phase 2+ Kotlin REST services consume the same file via `openapi-generator`'s `kotlin-spring` generator with `delegatePattern=true`. The polyglot consumer set is the load-bearing reason this direction is chosen despite FastAPI's natural code-first pull.

Sparkplug B Protobuf (Edge↔Bus) and JSON Schema (Kafka normalized payloads) follow the same direction with their own SoT files and generators — §2.3's policy applies uniformly across all three contract families.

### D-2. Python codegen scope: boundary DTOs only, via `datamodel-code-generator`

`datamodel-codegen --output-model-type pydantic_v2.BaseModel` generates Pydantic v2 models into `packages/contracts/codegen/python/`. FastAPI route handlers are hand-written and import these generated models directly. `fastapi-code-generator` (full route-stub generation) is **rejected for Phase 1** because its upstream documentation declares itself experimental. Re-evaluate if it stabilizes.

The generated Pydantic models are **boundary DTOs** (HTTP request/response shapes) — consistent with ADR-0018 (Pydantic at boundary only). They are **not** domain types: the domain layer uses stdlib `@dataclass(frozen=True, slots=True)`, and data crosses the boundary via explicit `from_domain` / `to_domain` conversion (arch doc §4.4, §8.3). Generated files in `packages/contracts/codegen/` are **never hand-edited** — they are regenerated on every CI run. If a boundary DTO needs extra *input-shape* validation, subclass the generated DTO in the HTTP adapter layer; **domain invariants and business logic must never be attached to a DTO** (`@field_validator` for domain rules on a Pydantic DTO is an ADR-0018 anti-pattern — those live in core sum types and functions).

### D-3. Three CI gates on the OpenAPI spec, ordered by failure cost

The `make verify` target and `.github/workflows/contracts.yml` run three gates in order:

1. **Quality gate (blocking)** — `spectral lint --ruleset openapi/.spectral.yaml openapi/sdf-api.yaml`. A malformed or convention-breaking spec fails fast, *before* any codegen runs. Catches the "spec successfully generates broken code" failure mode that a drift check cannot.
2. **Drift gate (blocking)** — `make all` then `git diff --exit-code codegen/`. Generated artifacts must match what is committed. Catches the "committed codegen is stale relative to the SoT" failure mode.
3. **Breaking-change gate (advisory in Phase 1)** — `oasdiff breaking` between PR head and `main`. Emits a GitHub Actions warning when the spec introduces a breaking change but does **not** fail the build in Phase 1 (zero external consumers). Phase 2 promotes this to blocking once the first external tenant exists.

### D-4. Schema changes are not silent

A change to any contract file (`sdf-api.yaml`, any `.proto`, any `*.schema.json`) lands as its own commit with subject prefix `feat(contracts):` or `fix(contracts):`. Mid-phase additions to this ADR (a new contract family, or promoting the breaking-change gate to blocking) follow the living-doc cadence per ADR-0000 §"Living documents".

## Consequences

### Positive

- **LLM hallucination surface is contracted.** Every endpoint signature, payload field, and enum value referenced in code traces to a YAML/proto/JSON-Schema line a model cannot invent — `datamodel-codegen` and `openapi-typescript` refuse to emit `lineId: number` when the spec declares `format: uuid`. This is the §2.6 mechanism made concrete for the inter-service boundary.
- **Polyglot consumers stay in sync by construction.** Phase 2+ Kotlin REST adoption is mechanical: the same `sdf-api.yaml` feeds `openapi-generator-gradle-plugin` + `kotlin-spring` + `delegatePattern=true`; compile-time delegate-interface mismatch becomes the regression signal.
- **Three-tier failure ordering means fast feedback.** A malformed spec is rejected by spectral in seconds; drift after one `make all`; a breaking-change advisory surfaces on the PR without blocking Phase 1 iteration speed.
- **Boundary/domain separation is preserved.** Generated DTOs sit at the HTTP boundary; the domain stays stdlib-dataclass and Pydantic-free per ADR-0018 — contract-first codegen does not leak Pydantic into core.
- **Portfolio signal.** The commit log shape `feat(contracts): OpenAPI 3.1 + spectral lint + python/ts codegen` → `feat(api): use generated DTOs` reads as "contract first, implementation second" — consistent with ADR-0000 §Consequences 1.

### Negative / Trade-offs

- **FastAPI's documented idioms point the other direction.** Tutorials and most community material assume code-first. New contributors hit "why aren't we just writing Pydantic models?" — this ADR is the documented answer.
- **Raw OpenAPI 3.1 YAML authoring is verbose.** TypeSpec or Stoplight Studio would be a higher-level authoring layer; Phase 1 surface (4 endpoints) does not justify it. Revisit beyond ~30 endpoints.
- **The DTO-subclass / no-domain-logic rule is a discipline, not a compiler check.** A contributor could hand-edit `codegen/` or attach domain logic to a DTO. Mitigation: drift gate catches hand-edits; ADR-0018's import-linter contract + arch-doc anti-pattern catalogue guard the DTO-logic boundary.
- **Spectral + oasdiff add ~10–20s to CI** (plus `fetch-depth: 0` clone cost). Accepted relative to the failure modes prevented.
- **Calibrated bet (per ADR-0000 §Calibration).** The polyglot-rationale weight in D-1 assumes viewers value visible cross-language contract consistency. If Phase 1/2 retrospectives surface no such signal, downgrade D-1's "load-bearing" weight; the drift-containment value stands independently.

## Migration Path

- **If `fastapi-code-generator` exits experimental status:** re-evaluate D-2 — full route generation could replace the hand-written route layer, via an additive or superseding ADR.
- **If the surface exceeds ~30 endpoints or YAML authoring becomes the bottleneck:** introduce TypeSpec as the *upstream* authoring layer compiling to `sdf-api.yaml`. Contract-first direction is preserved; only the human-facing source format changes.
- **If a non-OpenAPI-expressible protocol is added (gRPC, GraphQL):** add a new contract family under `packages/contracts/<family>/` with its own SoT file and generator chain. The three-gate pattern generalizes.
- **If contract-first proves wrong** (polyglot benefit consistently outweighed by FastAPI velocity loss): exit via a new ADR that supersedes this one and inverts D-1 for the Python side, accepting Kotlin/TS divergence cost. Estimated ~2–3 days (generator removal + Pydantic-first refactor of `apps/api-python`). Not free, not catastrophic.

## Sources

- [Pydantic — datamodel_code_generator official integration](https://docs.pydantic.dev/latest/integrations/datamodel_code_generator/)
- [Koxudaxi — fastapi-code-generator project page (experimental notice)](https://koxudaxi.github.io/fastapi-code-generator/)
- [Pydantic discussion #4789 — spec-first generation + custom validators (subclass pattern)](https://github.com/pydantic/pydantic/discussions/4789)
- [Malt Engineering — Design, Generate, Deploy: Contract-First API Strategy with FastAPI and OpenAPI](https://blog.malt.engineering/design-generate-deploy-our-contract-first-api-strategy-with-fastapi-and-openapi-15bb3e855dff)
- [OpenAPI Initiative — Best Practices ("OAD as first-class source file")](https://learn.openapis.org/best-practices.html)
- [Microsoft ISE Developer Blog — A Technical Journey into API Design-First, 2023](https://devblogs.microsoft.com/ise/design-api-first-with-typespec/)
- [Bump.sh — Code-First: How to Generate OpenAPI from Code (annotation staleness failure mode)](https://bump.sh/blog/code-first-openapi/)
- [Baeldung — API First Development with Spring Boot and OpenAPI 3.0](https://www.baeldung.com/spring-boot-openapi-api-first-development)
- [openapi-generator — kotlin-spring generator docs (delegatePattern)](https://openapi-generator.tech/docs/generators/kotlin-spring/)
- [Stoplight — Spectral OpenAPI rules](https://docs.stoplight.io/docs/spectral/4dec24461f3af-open-api-rules)
- [HackerNoon — Contract-First APIs: OpenAPI as Single Source of Truth (CI drift gate pattern)](https://hackernoon.com/contract-first-apis-how-openapi-becomes-your-single-source-of-truth)
- Internal — design spec §2.3 (`docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`); ADR-0000 (Chapter 0 batch); ADR-0018 (Pydantic at boundary only); arch doc §4.4 + §8.3 (`docs/architecture/2026-05-23-code-architecture.md`); related but not-yet-written ADR-0010 (architectural fitness tooling) and ADR-0011 (Sparkplug B namespace).
