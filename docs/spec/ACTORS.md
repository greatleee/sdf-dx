# Actors

Catalog of who interacts with the SDF Manufacturing DX system, and how. Used as a base reference by every per-use-case spec under `use-cases/`.

## Conventions

- **Actor = role, not job title.** One person can play multiple actor roles (e.g., a senior platform engineer often also acts as integration engineer during a new plant rollout).
- **Three categories:**
  - *Primary domain actor* — has a goal the system fulfills. Almost always human.
  - *Secondary system actor* — external system the platform collaborates with to fulfill a primary actor's goal. Used to make polyglot/integration boundaries first-class.
  - *Meta actor* — interacts with the *portfolio repository*, not the running platform. Tracked separately so they don't muddy domain modeling.
- **Granularity rule for secondary system actors:** only entities behind a *process or network boundary* are listed. In-process libraries are not actors.
- **Phase column** = earliest phase in which the actor participates in any use case.
- **Real org titles column** is a hint, not authoritative — it grounds the abstract role in the kinds of people who actually play it inside manufacturing organizations.

## Primary domain actors

| ID | Role | Typical real-org titles | Phase | Interaction depth |
|---|---|---|---|---|
| A-OP | Operator | line operator, shift operator, MES operator | 1+ | UI (read + ack) |
| A-SV | Production supervisor | shift leader, plant production manager | 3+ | UI + alarm rule config |
| A-TA | Tenant admin | plant IT lead, MES admin | 2+ | Admin UI + REST |
| A-IE | Integration engineer | MES integration engineer, OT/IT bridging engineer | 2+ | Configuration only (no code) |
| A-PE | Platform engineer | **SDF Manufacturing DX team senior full-stack** (= the role this portfolio targets), smart-factory platform engineer, solutions engineer | 4+ | Code + contract + test |

## Secondary system actors

Listed only when crossing a process/network boundary. Each row implies a *port* between the host service and this actor.

| ID | System | Kind | Phase |
|---|---|---|---|
| S-SIM | Device simulator (Kotlin) | publisher (Sparkplug B) | 1+ |
| S-MQTT | HiveMQ broker | infra (MQTT) | 1+ |
| S-BR | Sparkplug→Kafka bridge (Kotlin) | normalizer | 1+ |
| S-KAFKA | Redpanda | infra (Kafka) | 1+ |
| S-ING | Python ingest service | consumer | 1+ |
| S-DB | TimescaleDB | store (relational + timeseries) | 1+ |
| S-API | Python API / BFF | BFF (REST + WS) | 1+ |
| S-UI | React dashboard | client | 1+ |
| S-PROM | Prometheus | metrics scraper | 3+ |
| S-OTEL | OpenTelemetry collector | trace exporter | 3+ |

## Meta actor

Tracked separately because their interaction target is the *portfolio repository*, not the running platform.

| ID | Role | Phase | Reads / interacts with |
|---|---|---|---|
| M-IV | Interviewer / hiring manager / tech lead reviewing the portfolio | 5 (live demo) + ongoing repo access | README, ADRs, USE-CASES, KNOWN-UNKNOWNS, AI-WORKFLOW case studies, walkthrough video |

## Usage rules

- Every per-UC file under `use-cases/` declares `primary_actor:` (exactly one) and `secondary_actors:` (zero or more) by these IDs.
- M-IV is referenced only by `walkthrough-script.md` and the README's narrative — not by use-case specs.
- When a new actor candidate appears (e.g., a new external partner system in Phase 3), add a row here *before* writing the first UC that references it.
- Actor evolution beyond initial phase introduction is recorded in the ADR that introduced the change (e.g., the ADR that adds Prometheus also activates S-PROM).

## Out-of-scope actors (intentionally not modeled)

- *Quality manager / Maintenance technician* — Phase 4 may add quality or maintenance BC; the user research to model these actors properly is out of scope until that phase lands.
- *ML/AI engineer* — model training/serving is explicitly out of scope (design spec §16 Non-Goals).
- *PLC* — not an actor in our model; the Kotlin simulator stands in for it. Real PLC integration is documented as KNOWN-UNKNOWN.
