# ADR-0007: E2E as QA + use-case coverage gate

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

A use case is only "done" when a user can actually do it through the running system. A green unit suite proves the pieces work; it does not prove the assembled product does the thing the spec promised. The conventional answer — a separate, hand-curated QA test plan maintained out of band — drifts: use cases get added without a matching test, tests get written for behaviors no use case describes, and nobody notices until a demo fails.

Spec §2.5 fixes the relationship: every use case maps to *exactly one* E2E spec, the acceptance criteria are expressed as code (BDD-style), and a CI gate fails the build when the use-case count and the spec count diverge. The registry that anchors this mapping is `docs/spec/USE-CASES.md`, with one authoritative per-UC file under `docs/spec/use-cases/UC-NNN-*.md` (front-matter + body).

The gate already exists as `scripts/check-use-case-coverage.py`. This ADR records the *decision* that E2E is the QA layer and that coverage divergence blocks merge — and describes precisely what the script enforces, so the gate is visible at ADR status rather than only as a script. It does not redefine the tier policy (that is [ADR-0006](0006-test-speed-tiering.md)) or the lower tiers' fakes (that is [ADR-0024](0024-fakes-with-in-memory-dataset.md)).

## Decision

### D-1 — One use case ⇄ one E2E spec; the Gherkin AC is the test contract

Each use case maps 1:1 to exactly one E2E spec. The use case's acceptance criteria — written as Gherkin-style Given/When/Then in the per-UC file — *are* the E2E test contract: the E2E spec encodes those scenarios, nothing more and nothing less. Acceptance criteria are not duplicated in a separate QA document; the per-UC file is the single source, and the E2E spec is its executable form.

E2E sits at the top of the test pyramid, above the integration tier. Tier policy and the `SDF_MODE=fake|real` execution profiles are owned by [ADR-0006](0006-test-speed-tiering.md); the tiers below E2E (domain, application, integration) and the in-memory fakes the application tier uses are owned by [ADR-0024](0024-fakes-with-in-memory-dataset.md). A use case that spans two bounded contexts is exercised end to end through its top-level cross-BC use case in `src/sdf_api/use_cases/`; the cross-BC interaction mechanics it relies on (top-level use cases + in-process `DomainEventDispatcher`, with BCs kept independent) are owned by [ADR-0009](0009-inter-context-communication.md).

### D-2 — A coverage gate blocks merge on any registry ↔ file ↔ E2E divergence

`scripts/check-use-case-coverage.py` is the gate. It runs via `uv run scripts/check-use-case-coverage.py`, wired into both pre-commit and CI, and exits non-zero (failing the build) on any of the following — derived from what the script actually checks:

1. **Well-formed front-matter.** Every `docs/spec/use-cases/UC-*.md` file must open with a YAML front-matter block carrying an `id`.
2. **`id` ⇄ filename match.** The front-matter `id` must match the filename — `UC-001` requires the file to start with `UC-001-`.
3. **Registry → file (set diff).** Every `UC-NNN` row in the registry (`docs/spec/USE-CASES.md`) must have a matching per-UC file.
4. **File → registry (set diff).** Every per-UC file's `id` must appear as a row in the registry. (Checks 3 and 4 together are a bidirectional set difference: neither side may carry an entry the other lacks.)
5. **Implemented ⇒ E2E exists.** Any UC with `status: implemented` must declare a `related_e2e` path, and that path must exist on disk.

The script also rejects duplicate ids across files. A `draft` UC is *not* required to have an E2E spec yet — only `implemented` UCs are, which is what lets a UC be specced in Chapter 0 before its E2E lands. On success it prints a single `OK:` line with the count of consistent use cases.

The effect: a use case cannot be marked `implemented` without an on-disk E2E spec, and the registry, the per-UC files, and the E2E mapping cannot silently drift apart.

## Consequences

### Positive
- Use-case coverage is mechanical, not curated — the build is red the moment a UC and its E2E spec diverge, so QA coverage cannot rot unnoticed.
- The acceptance criteria live once (per-UC file) and are executed once (E2E spec); there is no second QA document to keep in sync.
- `git log` shows coverage staying intact across the phase — a portfolio-visible signal that "every feature has a test" is enforced, not asserted.
- The `draft` → `implemented` lifecycle gives a clean Chapter-0-spec-then-implement ordering: spec the UC now, satisfy the E2E-exists check only when the feature actually lands.

### Negative / Trade-offs
- E2E specs are the slowest, most brittle tests; pinning one to every use case means E2E maintenance scales linearly with use-case count. The tier policy (ADR-0006) keeps them off the local fast loop via the fake profile, which mitigates the cost.
- The gate enforces *existence and mapping*, not test *quality* — a 1:1-mapped E2E spec can still under-test its acceptance criteria. Review covers that gap; the gate cannot.
- A status flip to `implemented` is now coupled to E2E delivery. This is intended (it is the point of the gate) but means the promote step lands at phase end, not at spec time.

## Migration Path

Forward: the gate is already wired. New use cases follow the registry's "How to add a new UC" flow (copy the template, fill front-matter, add the registry row, keep `status: draft` until the E2E spec is wired, then flip to `implemented`).

When the use-case count grows large (roughly 50+), split the coverage report by bounded context so a failure points at the owning BC rather than scanning one flat list. This is a change to the script's reporting, not to the 1:1 contract.

Reversal (dropping the gate) would return use-case coverage to manual curation and reintroduce silent drift. It is a deletion of the script + pre-commit/CI wiring, but it removes the enforcement that the QA story depends on.

## Sources

- Internal: `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2.5 (every use case → exactly one E2E spec; CI fails on count mismatch).
- `scripts/check-use-case-coverage.py` — the gate this ADR records (front-matter `id`, id⇄filename, bidirectional registry/file set diff, implemented⇒related_e2e-on-disk).
- `docs/spec/USE-CASES.md` — the registry the gate enforces, with the UC lifecycle (`draft` → `implemented` → `retired`).
- [ADR-0006](0006-test-speed-tiering.md) (tier policy + `SDF_MODE` profiles for E2E), [ADR-0024](0024-fakes-with-in-memory-dataset.md) (tiers below E2E), [ADR-0009](0009-inter-context-communication.md) (cross-BC use case exercised end to end).
- Cucumber / Gherkin — Given/When/Then acceptance criteria as executable specification. https://cucumber.io/docs/gherkin/reference/
- Playwright — end-to-end browser test runner. https://playwright.dev/docs/intro
