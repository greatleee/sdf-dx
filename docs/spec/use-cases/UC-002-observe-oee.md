---
id: UC-002
title: Operator observes OEE refresh
status: implemented
phase: 1
primary_actor: A-OP
secondary_actors:
  - S-UI
  - S-API
  - S-DB
bounded_context: monitoring
related_adrs:
  - 0012
related_e2e: apps/dashboard-react/tests/e2e/UC-002-observe-oee.spec.ts
---

# UC-002 — Operator observes OEE refresh

## Goal
An operator sees the production line's current 5-minute OEE (and its A/P/Q components) on the dashboard, refreshing without manual action, so they can spot performance degradation.

## Trigger
A-OP has the dashboard open.

## Preconditions
- The line referenced by `lineId` exists.
- At least one row exists in the `line_oee_5m` continuous aggregate (i.e., the simulator has been running long enough for the CAGG policy to have fired at least once).

## Main scenario (happy path)
1. S-UI calls `GET /api/v1/lines/{lineId}/oee?window=5m` on mount.
2. S-API queries the most recent row of `line_oee_5m` from S-DB and derives Availability / Performance / Quality / OEE via the Phase 1 approximation (see ADR-0012).
3. S-UI renders four tiles: OEE, Availability, Performance, Quality (percentages).
4. Every 5 seconds, S-UI refetches the same endpoint and updates tiles in place.

## Alternative flows
- *No CAGG rows yet*: S-API returns 404; S-UI shows a "warming up" placeholder.
- *S-API returns 5xx*: tiles retain their previous values; a stale indicator appears after >30 s without a refresh.

## Commands & events (event-storming view)

| # | Actor | Command (intent) | Domain event(s) emitted |
|---|---|---|---|
| 1 | A-OP via S-UI | `RequestLineOee(lineId, window=5m)` | — |
| 2 | S-API → S-DB | (read of `line_oee_5m`) | — |

## Invariants
- All four returned ratios lie in `[0, 1]` *under Phase 1 calibration*. Availability and Quality are bounded by construction; `Performance` (ISO 22400-2 *Effectiveness*) can exceed 1 if the ideal cycle time is set loose — see Open questions and `KNOWN-UNKNOWNS.md`.
- `OEE = Availability × Performance × Quality` within floating-point tolerance (`≤ 1e-9` absolute).
- Phase 1 simplification: `Availability` is approximated as `1.0` (CAGG bucket treated as planned-busy-time). See ADR-0012 and `KNOWN-UNKNOWNS.md`.

## Acceptance criteria (Gherkin)

```gherkin
Feature: Operator observes OEE refresh

  Scenario: OEE tiles render with percentages on first load
    Given the line "Line A" has had at least one continuous-aggregate refresh
    When A-OP opens the dashboard
    Then four tiles labeled "OEE", "Availability", "Performance", "Quality" are visible within 5 seconds
    And each tile shows a percentage value in the form "<n>.<n>%" where 0 ≤ n ≤ 100

  Scenario: OEE values refresh at the polling cadence
    Given A-OP has the dashboard open and the OEE tile shows some value V1
    When 5 seconds elapse with new telemetry arriving
    Then the OEE tile shows a value V2 (possibly equal to V1) without page reload
```

## Out of scope for this UC
- *1 h / shift OEE windows* — Phase 3.
- *Cross-line OEE rollup* — separate UC.
- *OEE alarms* (e.g., "OEE < 60% for 30 min") — Phase 3 supervisor UC.

## Open questions
- The "refresh at polling cadence" scenario depends on simulator activity within the test window; making it deterministic in CI requires either time-mocking or seeded simulator output. Resolve at E2E implementation time; second Gherkin scenario is currently *deferred* (covered only in `fake` mode where MSW returns fresh handlers).
- The `[0,1]` invariant assumes `Performance` ≤ 1, which is not guaranteed by ISO 22400-2 (*Effectiveness* can exceed 100% with a loose ideal cycle time). Holds under Phase 1 simulator calibration; revisit before sourcing real ideal-cycle-time data. Tracked in `KNOWN-UNKNOWNS.md`.
