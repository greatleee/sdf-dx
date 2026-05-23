# ADR-0005: Contract-first inter-service schemas as single source of truth (with LLM drift containment)

* **Status**: Accepted
* **Date**: 2026-05-23
* **Supersedes**: none
* **Superseded by**: none
* **Phase**: 1

---

## Context

Design spec §2.3 already states the *policy*: every inter-service contract is a committed schema, codegen produces models/clients, change flows `spec → codegen → impl` (not the reverse), and CI fails on drift. ADR-0000 §"load-bearing decision" classifies "contract format" as one of the explicit triggers for an ADR at Chapter 0.

This ADR exists because §2.3's one-paragraph policy is **under-specified** in three ways that materially affect Phase 1 implementation:

1. **Which direction with FastAPI?** FastAPI's documented and idiomatic flow is *code-first*: write Pydantic models → FastAPI derives `/openapi.json`. The polyglot consumer set in this repo (Kotlin gateways, TypeScript frontend, Phase 2+ Kotlin REST services) cannot tolerate that direction — every non-Python consumer would regenerate against a possibly-stale exported snapshot, and FastAPI's auto-derived spec can include framework-specific shape leakage that downstream Kotlin/TS generators handle inconsistently (Microsoft ISE 2023; Bump.sh code-first analysis). §2.3 says "spec first" but does not commit to a tool or a discipline strong enough to resist FastAPI's natural pull.

2. **Which generator, and how much of it?** The Python ecosystem has at least two relevant tools by the same author: `datamodel-code-generator` (Pydantic model generation only) and `fastapi-code-generator` (full route-stub generation). The latter's documentation explicitly labels itself "in experimental phase." Choosing between them is load-bearing for Phase 1: model-only generation keeps route handlers as the human-authored layer where FastAPI's `response_model`, `Depends`, status codes, and validation live, and route handlers cannot tell that a model was generated rather than hand-written. Full-stub generation, by contrast, makes the route layer also a regeneration target — which on an experimental tool is unacceptable risk.

3. **What does "CI gate fails on drift" actually check?** A `git diff --exit-code codegen/` only catches "generated output diverged from committed output." It does *not* catch (a) a malformed or convention-breaking spec that *successfully* generates broken code, nor (b) a breaking change to the spec that lands undetected because all consumers happen to be in the same repo at the same time. Both gaps are the failure modes that contract-first promises to prevent; both require explicit tooling beyond a diff check.

The external-context research from 2026-05-23 (see Notes §Sources) supplied direct evidence on all three: Malt Engineering published a production case study doing exactly this (polyglot, FastAPI, OpenAPI as SoT) and lists the same disciplines as load-bearing; Pydantic's official documentation endorses `datamodel-code-generator` as the integration tool; OpenAPI Initiative's best-practices page names the OAD itself as the "first-class source file" that gates the build; the Spring/Kotlin ecosystem (Baeldung, openapi-generator's `kotlin-spring` + `delegatePattern=true`) treats contract-first as the default for polyglot scenarios.

---

## Decision

### D-1. OpenAPI 3.1 YAML is the single source of truth for the REST surface

`packages/contracts/openapi/sdf-api.yaml` is hand-authored. Pydantic v2 models (Python) and TypeScript types (frontend) are *outputs* of this file, never inputs to it. Phase 2+ Kotlin REST services consume the same file via `openapi-generator`'s `kotlin-spring` generator with `delegatePattern=true`. The polyglot consumer set is the load-bearing reason this direction is chosen despite FastAPI's natural code-first pull.

Sparkplug B Protobuf (Edge↔Bus) and JSON Schema (Kafka normalized payloads) follow the same direction with their own SoT files (`packages/contracts/sparkplug/*.proto`, `packages/contracts/kafka-payloads/*.schema.json`) and their own generators — design spec §2.3's policy applies uniformly across all three contract families.

### D-2. Python codegen scope: models only, via `datamodel-code-generator`

`datamodel-codegen --output-model-type pydantic_v2.BaseModel` generates Pydantic v2 models into `packages/contracts/codegen/python/`. FastAPI route handlers are hand-written and import these generated models directly. `fastapi-code-generator` (full route-stub generation) is **rejected for Phase 1** because its upstream documentation declares itself experimental. Re-evaluate if it stabilizes.

Custom Pydantic validators, business-logic methods, or BC-specific extensions live in `apps/api-python/src/sdf_api/contexts/<bc>/models.py` and *subclass* the generated models. Generated files in `packages/contracts/codegen/` are **never hand-edited** — they are regenerated on every CI run.

### D-3. Three CI gates on the OpenAPI spec, ordered by failure cost

The `make verify` target and `.github/workflows/contracts.yml` run three gates in order:

1. **Quality gate (blocking)** — `spectral lint --ruleset openapi/.spectral.yaml openapi/sdf-api.yaml`. A malformed or convention-breaking spec fails fast, *before* any codegen runs. Catches the "spec successfully generates broken code" failure mode that a drift check cannot.
2. **Drift gate (blocking)** — `make all` then `git diff --exit-code codegen/`. Generated artifacts must match what is committed. Catches the "committed codegen is stale relative to the SoT" failure mode.
3. **Breaking-change gate (advisory in Phase 1)** — `oasdiff breaking` between PR head and `main`. Emits a GitHub Actions warning when the OpenAPI spec introduces a breaking change but does **not** fail the build in Phase 1, because Phase 1 has zero external consumers. Phase 2 promotes this to blocking once the first external tenant exists.

### D-4. Living-doc clause: schema changes are not silent

A schema change to any contract file (`sdf-api.yaml`, any `.proto`, any `*.schema.json`) lands as its own commit with subject prefix `feat(contracts):` or `fix(contracts):`. Mid-phase additions to ADR-0005 (e.g., a new contract family added, or the breaking-change gate promoted to blocking) follow the living-doc cadence per ADR-0000 §"Living documents".

---

## Consequences

### Positive

1. **LLM hallucination surface is contracted.** Every endpoint signature, every payload field, every enum value referenced in code traces to a YAML/proto/JSON-Schema line a model cannot invent — `datamodel-codegen` and `openapi-typescript` will refuse to produce a `lineId: number` if the spec declares `format: uuid`. This is the §2.6 mechanism made concrete for the inter-service boundary.
2. **Polyglot consumers stay in sync by construction.** Phase 2+ Kotlin REST adoption is mechanical: `openapi-generator-gradle-plugin` + `kotlin-spring` + `delegatePattern=true` reads the same `sdf-api.yaml` already in use by Python and TypeScript. Compile-time delegate-interface mismatch becomes the regression signal.
3. **Three-tier failure ordering means fast feedback.** A malformed spec is rejected by spectral in seconds; a drift situation is rejected after one `make all` run; a breaking-change advisory surfaces on the PR without blocking iteration speed in Phase 1.
4. **Portfolio signal.** The commit log shape `feat(contracts): OpenAPI 3.1 + spectral lint + python/ts codegen` → `feat(api): use generated models` reads as "contract first, implementation second" — consistent with ADR-0000 §Consequences 1's commit-history-as-portfolio thesis.

### Negative / Trade-offs

1. **FastAPI's documented idioms point the other direction.** Tutorials, Stack Overflow answers, and Sebastián Ramírez's own commentary all assume code-first. Onboarding contributors will hit the friction of "wait, why aren't we just writing Pydantic models?" — mitigation: this ADR is the documented answer to that question.
2. **Raw OpenAPI 3.1 YAML authoring is verbose.** TypeSpec or Stoplight Studio would be a higher-level authoring layer. Phase 1 surface (4 endpoints) does not justify the extra tool; revisit if the surface exceeds ~30 endpoints.
3. **Generated-code subclassing pattern is a discipline, not a compiler check.** A future contributor could in principle hand-edit `codegen/python/sdf_openapi_models.py`. Mitigation: CI drift gate catches it (the regenerated output will differ); pre-commit hook can additionally `.gitattributes`-mark the directory as generated.
4. **Spectral and oasdiff add ~10–20s to CI.** Acceptable relative to the failure modes they prevent. The breaking-change gate's `fetch-depth: 0` adds a small clone cost.

### Migration path

- **If `fastapi-code-generator` exits experimental status (declared stable upstream)**: re-evaluate D-2 — full route generation could replace the hand-written FastAPI route layer. The change would be additive to this ADR or a superseding ADR-NNNN, not a destructive edit.
- **If the surface exceeds ~30 endpoints or schema authoring becomes the bottleneck**: introduce TypeSpec as the *upstream* authoring layer compiling to `sdf-api.yaml`. The contract-first direction is preserved; only the human-facing source format changes.
- **If a non-OpenAPI-expressible protocol is added (e.g., gRPC, GraphQL)**: add a new contract family under `packages/contracts/<family>/` with its own SoT file and generator chain. The three-gate pattern (quality → drift → advisory breaking-change) generalizes.
- **If contract-first proves wrong** — i.e., the polyglot benefit is consistently outweighed by FastAPI velocity loss — exit is via a new ADR that supersedes this one, inverts D-1 for the Python side, and accepts the Kotlin/TS divergence cost. Estimated cost: 2–3 days of generator removal + Pydantic-first refactor of `apps/api-python`. Not free, but not catastrophic.

---

## Notes

### Calibration

The polyglot-rationale weight in §Context is a **calibrated bet**: this repo's value as a portfolio asset depends on the Kotlin↔Python↔TS contract surface being visibly consistent across three languages. If Phase 1 retrospectives reveal that no viewer or interviewer comments on the cross-language contract consistency, downgrade D-1's "load-bearing" weight in Phase 2 planning. The drift containment value (§Positive 1) stands independently and is not subject to this calibration.

### Relationship to other ADRs

- **ADR-0000** (Chapter 0): this ADR is part of Phase 1's Chapter 0 batch — landed before any `feat(...)` commit per the phase-iteration rule.
- **ADR-0010** (architectural fitness tooling): the three CI gates in D-3 are the contract-layer analogue of import-linter / mypy / Konsist at the code layer. Both ADRs answer the same "what tooling catches drift?" question for different surfaces.
- **ADR-0011** (Sparkplug B namespace): the Sparkplug B Protobuf SoT under D-1 is upstream of ADR-0011's topic conventions — together they constitute the OT/Edge contract surface.

### Sources cited from external-context research (2026-05-23)

- [Pydantic — datamodel_code_generator official integration](https://docs.pydantic.dev/latest/integrations/datamodel_code_generator/)
- [Koxudaxi — fastapi-code-generator project page (experimental notice)](https://koxudaxi.github.io/fastapi-code-generator/)
- [Pydantic discussion #4789 — spec-first generation + custom validators (subclass pattern)](https://github.com/pydantic/pydantic/discussions/4789)
- [Malt Engineering — Design, Generate, Deploy: Contract-First API Strategy with FastAPI and OpenAPI](https://blog.malt.engineering/design-generate-deploy-our-contract-first-api-strategy-with-fastapi-and-openapi-15bb3e855dff)
- [OpenAPI Initiative — Best Practices ("OAD as first-class source file")](https://learn.openapis.org/best-practices.html)
- [Microsoft ISE Developer Blog — A Technical Journey into API Design-First](https://devblogs.microsoft.com/ise/design-api-first-with-typespec/)
- [Bump.sh — Code-First: How to Generate OpenAPI from Code (annotation staleness failure mode)](https://bump.sh/blog/code-first-openapi/)
- [Baeldung — API First Development with Spring Boot and OpenAPI 3.0](https://www.baeldung.com/spring-boot-openapi-api-first-development)
- [openapi-generator — kotlin-spring generator docs (delegatePattern)](https://openapi-generator.tech/docs/generators/kotlin-spring/)
- [Stoplight — Spectral OpenAPI rules](https://docs.stoplight.io/docs/spectral/4dec24461f3af-open-api-rules)
- [HackerNoon — Contract-First APIs: OpenAPI as Single Source of Truth (CI drift gate pattern)](https://hackernoon.com/contract-first-apis-how-openapi-becomes-your-single-source-of-truth)

### Original §2.3 fragment this ADR formalizes

> 모든 inter-service 통신은 *schema가 single source of truth*. OpenAPI 3.1 (FE↔BE), Sparkplug B Protobuf (Edge↔Bus), JSON Schema (Kafka payload), Phase 3에서 Avro 검토. 변경 순서: spec 먼저 → codegen → 구현. 거꾸로 가지 않음. CI gate: codegen drift 감지 시 fail. 결과: LLM이 endpoint 시그니처를 hallucinate 못 함.
>
> — `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2.3
