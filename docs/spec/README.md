# Spec — Behavior Catalog

Spec-driven development artifacts. This folder is the durable source of truth for *what the system does, for whom, and what "done" means* — independent of how it's implemented today.

## What lives here

- `ACTORS.md` — catalog of actors (primary domain, secondary system, meta) referenced by every use case.
- `GLOSSARY.md` — Ubiquitous Language: domain vocabulary scoped per Bounded Context. Code identifiers and spec wording must match terms here verbatim.
- `USE-CASES.md` — registry/index of all use cases. One row per UC with status, actor, BC, phase, and pointers to the per-UC spec file and E2E test spec.
- `use-cases/_TEMPLATE.md` — the per-UC template (YAML front-matter + hybrid body: narrative + event-storming Commands→Events + Gherkin AC).
- `use-cases/UC-NNN-<slug>.md` — one file per use case, copied from the template.

## Relationship to other docs

- *Phase acceptance criteria* live in `docs/roadmap/<design-spec>.md` §13 and reference UC IDs from here.
- *Architectural decisions* in `docs/ADR/` may reference UC IDs to ground rationale.
- *AI workflow case studies* in `docs/AI-WORKFLOW/` may reference UC IDs as work context.
- *Implementation plans* in `docs/plans/` reference UC IDs as deliverables. Plans themselves are throwaway scaffolding (see `docs/SOT-LAYERS.md`).

## Editing policy

This folder is part of the durable *functional surface* layer (see `docs/SOT-LAYERS.md`).

- Add a UC: add a row to `USE-CASES.md` and create the per-UC file.
- Change observable behavior: edit the UC file; AC and E2E tests follow.
- Retire a UC: mark `status: retired` in both the registry row and per-UC file (do not delete — keeps history readable).
- Add an actor or BC: edit `ACTORS.md` *before* writing any UC that references it.

CI gates:
- Use-case coverage gate (`uv run scripts/check-use-case-coverage.py`) — parses YAML front-matter from each `use-cases/UC-*.md`, cross-checks against `USE-CASES.md` registry rows, and (for `status: implemented` UCs) verifies the `related_e2e` path exists on disk.
