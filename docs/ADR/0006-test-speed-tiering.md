# ADR-0006: Test speed tiering

- **Status:** accepted
- **Date:** 2026-05-23
- **Phase:** 1

## Context

A test suite has two jobs that pull in opposite directions: give the author a sub-second feedback loop while editing, and give the merge gate enough realism to trust a green build. One uniform tier cannot do both. If everything runs against testcontainers, the local edit loop stalls at tens of seconds and the author stops running it; if nothing runs against real infrastructure, the suite is green while the real Postgres rejects the query.

Spec §2.4 already sketches the resolution as a table: domain tests always-on and sub-second, application tests on in-memory fakes, integration on testcontainers (opt-in locally, always-on in CI), E2E on a fake stack locally and the real stack in CI. What that table does not do is name the *policy* — which corpus runs when, and why each boundary sits where it does — at ADR status. The mechanism pieces are already owned elsewhere:

- The pure-domain purity that makes a zero-dependency, zero-mock tier *possible at all* is decided in [ADR-0004](0004-functional-core-imperative-shell.md). Without structural domain purity there is no tier that runs with neither IO nor fakes.
- The concrete fake design that the application tier runs on — per-BC `tests/contexts/<bc>/fakes.py`, `InMemoryDataset` shared state, `FakeUnitOfWork` with observable `committed` / `rolled_back` flags, mirrored DB-side constraints, and the "assert on state, never on calls" discipline — is owned in full by [ADR-0024](0024-fakes-with-in-memory-dataset.md).
- The pytest `integration` marker, the import contracts, and the `make ci` invocation that runs the heavy tiers are part of the contract set in [ADR-0023](0023-importlinter-contract-set.md).

This ADR therefore owns only the tiering policy and its rationale. It does not restate fake internals (ADR-0024), the purity rule (ADR-0004), or the CI gate plumbing (ADR-0023).

## Decision

Adopt a four-tier test pyramid, distinguished by *speed* and *dependency weight*. Each tier names where its tests live, what they may depend on, and when they run.

### D-1 — Tier 1: domain (`backend/tests/contexts/*/domain/`)

Pure-function tests over the functional core. **Zero mocks, zero stubs, zero fakes** — concrete values constructed inline and passed directly. Always-on locally and in CI, sub-second for the whole corpus. This tier exists only because of the domain purity rule in ADR-0004; property-based tests (Hypothesis) live here. No marker required.

### D-2 — Tier 2: application / use-case (`backend/tests/contexts/*/application/`)

Use-case tests that drive a use case against in-memory fakes: `FakeUnitOfWork` wrapping a per-BC `InMemoryDataset`, with `FixedClock` for the clock port. Still sub-second; no IO, no containers. The fake mechanism is ADR-0024's; this tier is the policy statement that use cases are exercised here and not against real infrastructure. Default-on locally and in CI. No marker required (or `@pytest.mark.unit`).

### D-3 — Tier 3: integration (`backend/tests/contexts/*/adapters/.../integration/`)

Adapter tests against real infrastructure via testcontainers (a throwaway Postgres, etc.). These verify the things fakes cannot: real SQL, real `GENERATED ALWAYS AS … STORED` columns, real `CHECK` constraints. Marked `@pytest.mark.integration`. **Opt-in locally** (run with `--integration`, off by default to keep the edit loop fast); **always-on in CI** via `make ci`. The marker and CI invocation are ADR-0023's.

### D-4 — Tier 4: E2E (`apps/dashboard-react/tests/e2e/`)

Full-stack browser tests (Playwright) exercising a use case end to end. Two execution profiles selected by adapter swap:

- **Local — fake stack.** The React dev server injects MSW, or the backend runs in `SDF_MODE=fake` (app-factory wires fakes instead of real adapters). Run via Playwright `--project=fake`. Fast, no infrastructure.
- **CI — real stack.** Real Postgres + Kafka + the Kotlin edge gateway. Backend in `SDF_MODE=real`. Run via Playwright `--project=real`.

The single switch is `SDF_MODE=fake|real` at the FastAPI app factory, mirrored by the Playwright project selection. The 1:1 use-case↔E2E-spec mapping and the coverage gate that enforces it are owned by [ADR-0007](0007-e2e-as-qa-coverage-gate.md); this ADR places E2E as the top tier of the pyramid.

The boundary rule across all four: a test runs at the lowest tier that can express its assertion. A behavior provable with concrete domain values does not move up to a fake; a behavior provable with a fake does not move up to a container.

## Consequences

### Positive
- Local feedback loop is dominated by Tiers 1 and 2 (sub-second), so authors keep running tests while editing.
- CI runs all four tiers, so the merge gate exercises real SQL, real constraints, and the real cross-service path.
- The `SDF_MODE` swap means the *same* E2E specs assert against fakes locally and the real stack in CI — one spec, two realism levels, no divergence in the assertions.
- The policy makes "which tier does this test belong in" a mechanical decision (lowest tier that expresses the assertion), reducing reviewer debate.

### Negative / Trade-offs
- Four tiers is more structure than a single `tests/` flat layout. The cost is the upfront convention; the payoff is the speed/realism split.
- Integration tests being opt-in locally means an author can land a change that passes Tiers 1–2 locally but fails Tier 3 in CI. This is acceptable: CI is the gate, and `--integration` is one flag away when touching adapters.
- The local fake stack and the CI real stack can diverge in behavior. Tier 3 (integration against real infra) is the seam that catches this before E2E; ADR-0024's mirrored-constraint discipline narrows the gap further.

## Migration Path

Forward: tiers are directory + marker conventions; no migration needed beyond placing new tests in the right directory. The `SDF_MODE` swap and Playwright projects land with the first E2E spec.

If the local feedback loop (Tiers 1 + 2) ever drifts past roughly five seconds, split the corpora further — by BC, or by splitting a slow application-tier file — rather than moving tests up a tier or relaxing the always-on rule. The always-on property of Tiers 1–2 is the value being protected.

Reversal (collapsing tiers) would re-merge the speed and realism jobs into one corpus and reintroduce the original dilemma. It is a category-level decision that would interact with ADR-0004 (the purity rule the bottom tier depends on).

## Sources

- Gary Bernhardt, "Boundaries" (Ruby Conf 2012) — the fast pure core / slow shell split underlying the tier ordering. https://www.destroyallsoftware.com/talks/boundaries
- Martin Fowler, "TestPyramid" — fewer slow high-level tests, many fast low-level tests. https://martinfowler.com/bliki/TestPyramid.html
- pytest — custom markers and `-m` selection (the `integration` marker). https://docs.pytest.org/en/stable/example/markers.html
- Playwright — projects and `--project` selection (the `fake` / `real` profiles). https://playwright.dev/docs/test-projects
- Testcontainers — disposable real infrastructure for the integration tier. https://testcontainers.com/
- Internal: `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §2.4; [ADR-0024](0024-fakes-with-in-memory-dataset.md) (fake mechanism — Tier 2); [ADR-0023](0023-importlinter-contract-set.md) (marker + `make ci` — Tier 3); [ADR-0004](0004-functional-core-imperative-shell.md) (domain purity — Tier 1).
