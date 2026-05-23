# Contract-First Inter-Service Schemas — Rules

Fast-scan condensation of ADR-0005 (contract-first SoT + LLM drift containment). Covers the inter-service contract surface (OpenAPI 3.1, Sparkplug B Protobuf, JSON Schema) and its codegen pipeline under `packages/contracts/`.

ADR-0005 carries full rationale; this file is rules-only, do/don't form. The boundary-DTO-vs-domain split (generated Pydantic = boundary DTO, never domain type, no domain logic on a DTO) lives in `backend-code-architecture.md` §5 (ADR-0018) — **not duplicated here**.

---

## §1. Direction — the schema is the source of truth

DO:
- Edit the schema *first*, then regenerate. SoT files:
  - REST: `packages/contracts/openapi/sdf-api.yaml`
  - Edge↔Bus: `packages/contracts/sparkplug/*.proto`
  - Kafka payloads: `packages/contracts/kafka-payloads/*.schema.json`
- Regenerate via `make all` (or the per-target command) in `packages/contracts/` after any schema edit, and commit the regenerated output alongside.
- Treat `packages/contracts/codegen/**` as build output.

DON'T:
- Hand-edit anything under `packages/contracts/codegen/`. Change the schema and regenerate.
- Derive the OpenAPI spec from FastAPI code (code-first). FastAPI *consumes* the spec's generated models; it does not author the spec.
- Add a REST field / endpoint / enum in Python or TypeScript first — add it to `sdf-api.yaml`, regenerate, then wire it.

---

## §2. Generators — what runs, what's banned

DO:
- OpenAPI → Pydantic v2 **models only**: `datamodel-codegen --output-model-type pydantic_v2.BaseModel`.
- OpenAPI → TypeScript: `openapi-typescript`.
- JSON Schema → Pydantic v2: `datamodel-codegen --input-file-type jsonschema`.
- Sparkplug `.proto` → Python + Kotlin stubs via `protoc`.
- Phase 2+ Kotlin REST: `openapi-generator` `kotlin-spring` generator + `delegatePattern=true` — implement the generated delegate interface only.

DON'T:
- Use `fastapi-code-generator` (full route-stub generation) — upstream self-declares experimental; rejected for Phase 1. Re-evaluate only if it stabilizes (would need a new/superseding ADR).
- Hand-write a FastAPI request/response model — import the generated DTO.
- Edit a generated `kotlin-spring` controller or interface — implement the delegate.

---

## §3. CI gates — three, ordered by failure cost

`packages/contracts` `make verify` + `.github/workflows/contracts.yml` run, in order:
1. **Quality** (blocking) — `spectral lint --ruleset openapi/.spectral.yaml openapi/sdf-api.yaml`, *before* codegen. Catches a malformed/convention-breaking spec that would otherwise generate broken code.
2. **Drift** (blocking) — `make all` then `git diff --exit-code codegen/`. Generated artifacts must match what is committed.
3. **Breaking-change** (advisory in Phase 1, blocking in Phase 2) — `oasdiff breaking` vs `main`.

DON'T:
- Edit a spec and commit without running `make verify`.
- Disable a gate to make a PR pass — fix the spec, regenerate, recommit.
- Promote the oasdiff gate to blocking before Phase 2 (no external consumers yet).

---

## §4. Schema-change commit hygiene

DO:
- Land a contract-file change as its own commit: `feat(contracts):` (new surface) / `fix(contracts):` (correction).
- Commit the regenerated `codegen/` output in the *same* commit as the schema change (keeps the drift gate atomic and the contract-evolution log readable).

DON'T:
- Bundle a schema change with unrelated app code in one commit.

---

Full rationale: `docs/ADR/0005-contract-first-llm-drift.md`. Boundary-DTO/domain split: `backend-code-architecture.md` §5 + ADR-0018. Spec policy: design spec §2.3.
