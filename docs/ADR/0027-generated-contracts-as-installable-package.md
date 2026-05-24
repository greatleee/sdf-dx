# ADR-0027: Generated contract DTOs consumed as an installable `sdf_contracts` package

- **Status:** accepted
- **Date:** 2026-05-24
- **Phase:** 1

## Context

Contract-first (ADR-0005) makes the schemas under `packages/contracts/` the source of truth and commits the generated Pydantic / TypeScript / protobuf code under `codegen/`. Section B left the *consumption* side open: `codegen/python/` was a bare tree of modules (`kafka/`, `openapi/`, `sparkplug/`) with no `__init__.py` and no packaging, importable only if `codegen/python` happened to be on `sys.path` (KNOWN-UNKNOWNS "Contract-codegen caveats"). Section E is the first time two Python services (`ingest-python`, `api-python`) must actually import those DTOs — the ingest consumer validates Kafka payloads against `MachineTelemetry`, and the API maps domain results to the generated OpenAPI response models. Contract-first §2 forbids hand-writing those boundary models, so the apps need a real, importable dependency, including inside their Docker images (whose per-app build context cannot reach `../../packages`).

## Decision

Package `packages/contracts/codegen/python/` as an installable distribution named `sdf-contracts` (import root `sdf_contracts`): the generated modules move under `sdf_contracts/{sparkplug,openapi,kafka}/`, and a hand-authored `pyproject.toml` + empty `__init__.py` / `py.typed` markers provide the packaging scaffold. The scaffold is *not* generated — `make all` only rewrites the four generated modules — so the drift gate (`git diff --exit-code codegen/`) stays green. Apps install it editable (`scripts/init.sh` runs `uv pip install -e packages/contracts/codegen/python` per venv) rather than declaring it as a `[project]` dependency, because `uv pip install` does not read `[tool.uv.sources]` and a declared PyPI lookup would fail. The Python service Docker images switch to a repo-root build context so the package is `COPY`-able and installed alongside the app.

## Consequences

### Positive
- Apps import generated DTOs by a clear namespaced path (`sdf_contracts.kafka.machine_telemetry`), satisfying contract-first §2 with no hand-written boundary models and no `sys.path` hacks.
- `py.typed` lets mypy use the generated types at call sites while treating the package as an external boundary (errors inside generated code are not reported against app strictness).
- The drift gate is unaffected: the generator owns only the four modules; the packaging scaffold is inert to `make all`.

### Negative / Trade-offs
- The package scaffold (`pyproject.toml`, `__init__.py`, `py.typed`) is hand-authored *inside* `codegen/`, slightly blurring the "codegen is pure build output" line (ADR-0005). Mitigated by keeping it inert to the generator and documenting it in the Makefile + `pyproject.toml`.
- Editable install (not a declared dependency) means the wiring lives in `scripts/init.sh` + the Dockerfiles, not in each app's `[project.dependencies]` — a monorepo-internal coupling that a fresh `pip install .` of an app alone would not satisfy.
- Repo-root Docker build context sends a larger context (mitigated by `.dockerignore`).

## Migration Path

Reversing to a non-packaged tree would mean deleting the scaffold and updating the Makefile output paths back — mechanical, but every consumer import (`sdf_contracts.…`) and the Dockerfiles/init script would have to change with it. A heavier future option (publishing `sdf-contracts` to a private index and declaring it as a real version-pinned dependency) is a forward move from here, not a reversal: the import surface stays identical.

## Sources

- Internal: `docs/ADR/0005-contract-first-llm-drift.md`, `docs/ADR/0018-pydantic-at-boundary-only.md`, `.claude/rules/contract-first.md` §2, `docs/KNOWN-UNKNOWNS.md` (Contract-codegen caveats).
- [uv — `pip` interface vs. project sources, Astral, 2026](https://docs.astral.sh/uv/)
- [Hatchling build configuration — PyPA/Hatch, 2026](https://hatch.pypa.io/latest/config/build/)
