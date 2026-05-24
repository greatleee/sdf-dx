# Use Cases — Registry

Index of all use cases. **Authoritative content for each UC lives in `use-cases/UC-NNN-<slug>.md`** (YAML front-matter + hybrid body). This registry mirrors front-matter for at-a-glance browsing and the CI coverage gate.

## Conventions

- One row per UC. Add the row when creating the UC file; never delete a row — set `status: retired` instead.
- ID format: `UC-NNN` (three-digit, gap-tolerant, no reuse on retirement).
- Status lifecycle: `draft` → `implemented` → `retired`. Only `implemented` rows are expected to have a non-empty E2E test path.
- Run `uv run scripts/check-use-case-coverage.py` to verify:
  - every row here has a matching `use-cases/UC-NNN-*.md` file,
  - every `use-cases/UC-NNN-*.md` file has a row here,
  - every `implemented` row's `related_e2e` path exists.
- Bounded-context names are tentative until the BC extraction step. Names here must match the `bounded_context:` front-matter field.

## Index

| ID | Title | Status | Phase | Primary actor | BC | Spec file | E2E test |
|---|---|---|---|---|---|---|---|
| UC-001 | Operator monitors single line state | draft | 1 | A-OP | monitoring | [use-cases/UC-001-monitor-line-state.md](use-cases/UC-001-monitor-line-state.md) | apps/dashboard-react/tests/e2e/UC-001-monitor-line-state.spec.ts |
| UC-002 | Operator observes OEE refresh | draft | 1 | A-OP | monitoring | [use-cases/UC-002-observe-oee.md](use-cases/UC-002-observe-oee.md) | apps/dashboard-react/tests/e2e/UC-002-observe-oee.spec.ts |
| UC-004 | Tenant admin onboards a new tenant (backend) | draft | 2 | A-TA | tenancy | [use-cases/UC-004-onboard-tenant.md](use-cases/UC-004-onboard-tenant.md) | apps/dashboard-react/tests/e2e/UC-004-onboard-tenant.spec.ts — Plan B |
| UC-005 | Operator authenticates and is RBAC-scoped (operator read-only) | draft | 2 | A-OP | identity | [use-cases/UC-005-authenticate-and-rbac-scope.md](use-cases/UC-005-authenticate-and-rbac-scope.md) | apps/dashboard-react/tests/e2e/UC-005-authenticate-and-rbac-scope.spec.ts — Plan B |
| UC-006 | Operator queries cross-tenant enterprise OEE | draft | 2 | A-OP | monitoring | [use-cases/UC-006-query-enterprise-oee.md](use-cases/UC-006-query-enterprise-oee.md) | apps/dashboard-react/tests/e2e/UC-006-query-enterprise-oee.spec.ts — Plan B |

> **UC-003 is reserved for Phase 2b** (visitor-persona / admin-UI E2E, deferred per [`docs/roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md`](../roadmap/2026-05-24-phase-2-backend-multitenancy-scope.md)). The gap between UC-002 and UC-004 is intentional: Phase 2 Plan A (backend) takes UC-004/005/006, leaving UC-003 for the Phase 2b plan to claim. IDs are gap-tolerant and never reused.
>
> Phase 2 UCs are authored `draft` in Chapter 0; their `related_e2e` paths are **declared** here but the spec files are authored in Plan B, so the rows stay `draft` (only `implemented` rows require the E2E file to exist on disk — the coverage gate enforces this).

## How to add a new UC

1. Pick the next `UC-NNN` ID.
2. Copy `use-cases/_TEMPLATE.md` to `use-cases/UC-NNN-<short-slug>.md`.
3. Fill in front-matter and body. Keep `status: draft` until the Gherkin AC is wired to an E2E spec.
4. Add a row to the table above.
5. Run `uv run scripts/check-use-case-coverage.py` locally before committing.

## Retiring a UC

1. Edit the per-UC file front-matter: `status: retired` and append a short `## Retirement note` section in the body explaining why and pointing to the successor UC (if any).
2. Set the row in the table above to `status: retired`.
3. Leave the E2E test in place if it still passes — or remove and document in the retirement note.
