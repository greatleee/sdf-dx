---
id: UC-XXX
title: <Short, action-oriented title — verb + object>
status: draft           # draft | implemented | retired
phase: 1                # phase in which this UC is delivered
primary_actor: A-OP     # exactly one — ID from docs/spec/ACTORS.md
secondary_actors:       # zero or more — IDs from docs/spec/ACTORS.md
  - S-UI
  - S-API
bounded_context: monitoring   # tentative until extracted into the BC layout
related_adrs: []        # e.g., [0004, 0011]
related_e2e:            # path under apps/dashboard-react/tests/e2e/. Required for status >= implemented.
---

# UC-XXX — <title>

> Hybrid spec: narrative + event-storming (Commands → Events) + Gherkin AC.
> Reads as a contract for engineers; parses as structured input for LLM-assisted BC extraction and test scaffolding.

## Goal

One sentence stating what the *primary actor* wants to achieve. Should pass the "elevator-pitch from the actor's mouth" test.

## Trigger

What initiates this UC. Examples: "Operator opens the dashboard"; "Sparkplug NDEATH received"; "Cron at 00:00 KST"; "Tenant admin POSTs /tenants".

## Preconditions

Bulleted list of what must hold before the UC can start. State-of-the-world only, not implementation details.

- The line referenced by `lineId` exists in topology.
- The operator is authenticated (Phase 2+).

## Main scenario (happy path)

Plain-prose walkthrough. Use *actor IDs* (A-OP, S-API, …) where they enter the scene. Keep to 5–10 sentences.

> Example shape: "A-OP opens the dashboard. S-UI requests the latest line-state snapshot from S-API. S-API queries S-DB and returns the snapshot. S-UI also subscribes to live updates via WebSocket against S-API, which streams state changes as they happen."

## Alternative flows

Bulleted list of meaningfully different paths. One sentence each; spawn a separate UC if a path is large enough to warrant its own AC.

- *WebSocket connection drops* → S-UI falls back to REST polling every 2s; banner shown.
- *No state recorded for the line yet* → S-UI shows placeholder until the first event arrives.

## Commands & events (event-storming view)

Used by LLM-assisted BC extraction. Each row: who issues a *command* (intent) and what *domain events* are emitted as a result. Keep this aligned with the Main scenario.

| # | Actor | Command (intent) | Domain event(s) emitted |
|---|---|---|---|
| 1 | A-OP via S-UI | `RequestLineStateSnapshot(lineId)` | — |
| 2 | S-API → S-DB | (query, no command) | — |
| 3 | S-API | `SubscribeLineStateChanges()` | `LineStateChanged(lineId, newState, since)` |

Conventions:
- *Commands* are imperative, PascalCase, present tense (`RequestX`, `OpenY`).
- *Events* are past tense, PascalCase (`XCreated`, `YChanged`).
- A row with no command (pure read) is fine; mark the Command column `—`.

## Invariants

Properties that must hold throughout the UC. These become domain-test assertions and CI guardrails.

- Returned `state` is always one of `RUNNING | IDLE | DOWN | CHANGEOVER`.
- `since` is monotonically non-decreasing for a given `lineId` across consecutive snapshots.

## Acceptance criteria (Gherkin)

Each `Scenario` maps to one Playwright (or pytest-bdd) test. The E2E spec listed in front-matter implements *all* scenarios here.

```gherkin
Feature: <UC title>

  Scenario: <happy path — one assertion-worthy outcome>
    Given <state>
    When <action>
    Then <observable outcome with latency/scope bound>

  Scenario: <alt flow #1>
    Given ...
    When ...
    Then ...
```

Guidance:
- Bind observable outcomes to *time / scope*: "within 2s", "in the line panel", "without page reload".
- If a scenario can't be tested at the E2E layer (e.g., pure domain invariant), call it out and link to a unit/property test instead — do not put untestable claims here.

## Out of scope for this UC

Bullets clarifying boundaries. Especially: which sibling UC handles related-but-separate behavior. Prevents UC drift.

- Operator *acknowledges* an alarm → UC-XXX (separate).
- Cross-line aggregation → not in Phase 1.

## Open questions

Anything not yet decided. Should be empty by the time `status: implemented`. If a question survives implementation, it must become either an ADR or a KNOWN-UNKNOWN entry.

- Polling fallback cadence — 2s vs 5s. (Pending: review with A-OP simulation.)
