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
