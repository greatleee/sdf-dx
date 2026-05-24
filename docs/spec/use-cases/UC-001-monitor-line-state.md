---
id: UC-001
title: Operator monitors single line state
status: implemented
phase: 1
primary_actor: A-OP
secondary_actors:
  - S-UI
  - S-API
  - S-DB
bounded_context: monitoring
related_adrs:
  - 0004
related_e2e: apps/dashboard-react/tests/e2e/UC-001-monitor-line-state.spec.ts
---

# UC-001 — Operator monitors single line state

## Goal

An operator can see the current state of a production line on the dashboard, with live updates as the state changes, so they can react to stoppages without leaving the screen.

## Trigger

A-OP opens the dashboard URL.

## Preconditions

- The line referenced by `lineId` exists in `production_line`.
- Phase 1: a single implicit factory and a single line; no authentication.
- At least one `line_state` row has been written for the line (or the UI gracefully handles the "no state yet" case — see Alternative flows).

## Main scenario (happy path)

1. A-OP navigates to `/` on the dashboard.
2. S-UI fetches the current line-state snapshot from S-API via `GET /api/v1/lines/{lineId}/state`.
3. S-API queries S-DB for the most recent `line_state` row and returns `{ lineId, state, since }`.
4. S-UI renders the state pill (color + label + time-since).
5. In parallel, S-UI opens a WebSocket to S-API at `/ws/line-state`.
6. S-API subscribes the connection to its in-memory broadcaster.
7. When the underlying state changes (background poller detects a new row), S-API publishes `LineStateChanged` to all subscribers.
8. S-UI receives the payload and updates the pill in place without page reload.

## Alternative flows

- *WebSocket fails to connect or disconnects*: S-UI falls back to REST polling every 2 seconds. A small banner indicates "polling (WS reconnecting)".
- *No `line_state` row exists yet*: S-UI shows a "no state yet" placeholder until the first update arrives. No error.
- *S-API returns 5xx*: S-UI retains the last successfully rendered state and shows a stale indicator after >10 s without a refresh.

## Commands & events (event-storming view)

| # | Actor | Command (intent) | Domain event(s) emitted |
|---|---|---|---|
| 1 | A-OP via S-UI | `RequestLineStateSnapshot(lineId)` | — |
| 2 | S-API → S-DB | (read) | — |
| 3 | S-UI | `SubscribeLineStateChanges(lineId)` | — |
| 4 | (internal poller) | (read) | `LineStateChanged(lineId, newState, since, reason?)` |

## Invariants

- `state` is always one of `RUNNING | IDLE | DOWN | CHANGEOVER` (closed enum; enforced by DB CHECK constraint and Pydantic `Literal`).
- `since` is non-decreasing for a given `lineId` across consecutive snapshots — a snapshot never travels backward in time.
- A `LineStateChanged` event is emitted at most once per `(lineId, state, since)` triple — replays do not double-fire.

## Acceptance criteria (Gherkin)

```gherkin
Feature: Operator monitors single line state

  Scenario: Dashboard shows current state on first load
    Given the line "Line A" is currently in state "RUNNING"
    When A-OP opens the dashboard
    Then the state pill displays "RUNNING" within 2 seconds

  Scenario: Live state changes propagate over WebSocket
    Given A-OP has the dashboard open and the state pill shows "RUNNING"
    When the line transitions to "DOWN"
    Then the state pill updates to "DOWN" within 1 second without a page reload

  Scenario: Polling fallback engages when WebSocket dies
    Given A-OP has the dashboard open with a live WS connection
    When the WS connection is closed by the server
    Then a "polling (WS reconnecting)" indicator appears within 2 seconds
    And the state pill continues to reflect the latest state via REST polling
```

## Out of scope for this UC

- *Cross-line / factory-level state aggregation* — separate UC, not in Phase 1.
- *Operator acknowledges an alarm tied to a DOWN state* — separate UC.
- *Data-pipeline staleness detection* (S-SIM → S-MQTT → S-BR → S-KAFKA → S-ING → S-DB integrity) — separate UC; this UC trusts the data path.
- *Authentication / RBAC* — Phase 2+ (A-TA use cases).

## Open questions

- **[RESOLVED — Section E]** Authoritative source of `line_state` rows. Of the two options (A: a projection computed inside S-API and written back to `line_state`; B: a Kafka-side consumer that maintains `line_state` directly), Phase 1 implements **option B**: the ingest service derives a *coarse* line state from telemetry (`apps/ingest-python/src/sdf_ingest/domain/line_activity.py` — a machine whose `cycle_count` advanced is producing; the line is `RUNNING` if any machine is, else `IDLE`) and writes one row per transition. This keeps S-API read-only. `DOWN` / `CHANGEOVER` are not derivable from counts and are deliberately never emitted; the Phase-1 simulator injects a deterministic synthetic idle schedule (`LineSchedule`, Section G) so the path demonstrably transitions `RUNNING`↔`IDLE`. This is an honest Phase-1 heuristic, not modeled downtime — see `KNOWN-UNKNOWNS.md` ("OEE & line-state derivation"), which holds the Section-E living-doc record of this decision. Promoting that record to a standalone ADR, and adding a dedicated line-state producer (operator input / PLC state word), remain deferred follow-up work.
- Polling fallback cadence (2 s) is a guess — should be revisited against operator-perceived latency once the Phase 1 system is observable.
