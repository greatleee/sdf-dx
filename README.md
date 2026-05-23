# SDF Manufacturing DX — Portfolio Project

End-to-end vertical slice of a Smart-Factory Data Fabric: Sparkplug B over MQTT → Kafka → TimescaleDB → FastAPI → React. Demonstrates AI-augmented senior full-stack engineering with explicit drift containment (contract-first, functional core, architecture-as-tests).

> **Phase 1 status:** in progress. See `docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md`.

## Quick start
```bash
docker compose up
```

## Documentation
- Design spec: `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md`
- ADRs: `docs/ADR/`
- Use cases: `docs/spec/USE-CASES.md` (registry); per-UC specs under `docs/spec/use-cases/`
- Known limits: `docs/KNOWN-UNKNOWNS.md`
- Domain absorption notes: `docs/DOMAIN-NOTES.md`
- AI workflow case studies: `docs/AI-WORKFLOW/`

## Development

### Git hooks — keep codegen in sync with schemas
Generated code under `packages/contracts/codegen/` is kept in lockstep with its
source schemas by a pre-commit hook (the local mirror of the `contracts` CI
gate). Enable it once per clone:
```bash
git config core.hooksPath .githooks
```
When a `packages/contracts/` schema (`*.proto`, OpenAPI `*.yaml`, Kafka
`*.schema.json`) is staged, the hook lints the spec, regenerates all codegen, and
stages the result — so codegen lands in the same commit as the schema and drift
never reaches CI. Requires `protoc`, `uv`, `pnpm`, `node` on PATH. Commits that
don't touch a schema are unaffected.

