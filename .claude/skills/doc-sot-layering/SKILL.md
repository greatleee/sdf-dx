---
name: doc-sot-layering
description: Use when adding, editing, moving, or restructuring any documentation under docs/spec/ (USE-CASES, ACTORS, GLOSSARY, per-UC files), docs/ADR/, docs/roadmap/, docs/plans/, docs/AI-WORKFLOW/, or docs/SOT-LAYERS.md — also covers use-case authoring, actor catalog changes, glossary updates, ADR drafting, phase plan edits, supersede-vs-edit decisions, and the use-case coverage gate.
---

# Documentation SoT Layering (this repo)

Documentation in this portfolio project is part of the *deliverable*, not just artifacts about it — interviewers read ADRs, glossary, and use-case specs as primary evidence of engineering judgment. That widens the durable SoT surface beyond a normal product codebase, but every durable layer has a built-in reason not to drift, and the implementation plan is the only intentional scaffold.

Use this skill any time you're about to touch `docs/`. The goal is to route each edit through the right policy *before* the file is opened.

## Why this exists

Two failure modes show up immediately if you don't classify the doc first:

1. *Plans masquerading as SoT* — sync cost balloons; plan and code diverge; plan becomes a fictional record.
2. *Strategy / ADRs edited destructively* — the *why* gets overwritten, and the portfolio loses its core "engineering judgment" evidence.

Both are pre-empted by consulting the layer table below before any edit.

## Layer table — consult before editing

| Layer | Location | Edit policy |
|---|---|---|
| Strategy | `docs/roadmap/` | **Never edit in place.** Write a new spec that supersedes. Surgical path-rename fixes are the only allowed in-place change. |
| Decisions (ADR) | `docs/ADR/` | **Never edit accepted ADRs.** New decision → new ADR, mark old as superseded. |
| Functional surface | `docs/spec/` (ACTORS, GLOSSARY, USE-CASES, use-cases/) + `docs/{DOMAIN-NOTES,KNOWN-UNKNOWNS}.md` | Edit only when externally observable behavior or vocabulary actually changes. |
| Acceptance Criteria | Design spec §13 in `docs/roadmap/...` | Edit only when the definition of "done" for a phase shifts. |
| AI workflow cases | `docs/AI-WORKFLOW/` | Frozen after incident; typo fixes only. |
| Implementation plan | `docs/plans/` | Scaffold — edit freely; archive after phase tag. |
| Code | `apps/`, `packages/`, `infra/`, `scripts/` | Continuously updated. |

The author's general-web instinct of "functional spec is the durable roadmap-SoT; impl plan is throwaway" transfers directly — only the *durable surface widens*. In this repo's vocabulary, that habit expands to "(Strategy + ADRs + Functional surface + AC) as durable SoT". AC plays the roadmap-spec role; USE-CASES plays the user-behavior subset.

## When this skill applies (recognition pattern)

- The user says: "add a use case", "update spec", "write an ADR", "edit a UC", "change actor catalog", "add a glossary term", "supersede", "문서 수정".
- You're about to touch anything under `docs/spec/`, `docs/ADR/`, `docs/roadmap/`, `docs/plans/`, `docs/AI-WORKFLOW/`, or `docs/SOT-LAYERS.md`.
- A path restructure or rename touches multiple durable docs at once.
- Anyone mentions: actor, glossary, ubiquitous language, bounded context, phase plan, AC, coverage gate.

## How to think about the edit

### 1. Classify before opening the file

Map the target file to a row in the layer table and apply that row's policy. Stop and re-route if it conflicts with the edit you were about to make.

### 2. Prefer supersede over edit for Strategy / ADRs

If the change captures a reversed decision or a strategic pivot, write a *new* ADR (or a new spec under `docs/roadmap/`) that supersedes the old one. Only mechanical path-rename fixes after a directory restructure may touch durable docs in place — and even then, leave frozen Strategy snapshots alone unless the user explicitly approves the fix.

### 3. Use-case spec conventions

Per-UC files live at `docs/spec/use-cases/UC-NNN-<slug>.md` and follow the hybrid template at `docs/spec/use-cases/_TEMPLATE.md`:

- **YAML frontmatter** (required): `id`, `title`, `status` (`draft` | `implemented` | `retired`), `phase`, `primary_actor` (exactly one ID from `ACTORS.md`), `secondary_actors` (list of IDs), `bounded_context`, `related_adrs`, `related_e2e`.
- **Body** (required, in order): Goal → Trigger → Preconditions → Main scenario → Alternative flows → Commands & events (event-storming table) → Invariants → Acceptance criteria (Gherkin) → Out of scope → Open questions.
- **Registry**: `docs/spec/USE-CASES.md` must have one row per per-UC file and vice versa.

After any UC change, run the coverage gate locally before committing:

```bash
uv run scripts/check-use-case-coverage.py
```

The gate verifies: frontmatter `id` ↔ filename match, registry rows ↔ per-UC files (bidirectional set diff), and (only for `status: implemented`) the `related_e2e` path exists on disk. It's also wired into pre-commit (Task 28 of the Phase 1 plan) and CI (Task 27).

### 4. Actor modeling rules

`docs/spec/ACTORS.md` has three categories:

- **Primary domain actors** (`A-XX`, human roles) — exactly one per UC's `primary_actor` field.
- **Secondary system actors** (`S-XX`, services / brokers / DBs) — listed only when the actor crosses a *process or network boundary*. In-process libraries are not actors. Direction matters: in a one-way data flow (Kotlin → Python in Phase 1), the downstream service is *not* an actor *of* the upstream service's UC.
- **Meta actor** (`M-IV` — Interviewer) — referenced only by `walkthrough-script.md` and the README narrative. Never by use-case specs.

Add a row to `ACTORS.md` *before* writing the first UC that references the new actor.

### 5. Ubiquitous language enforcement

Always check `docs/spec/GLOSSARY.md` for the term you're about to use in code or spec wording. The Anti-Glossary section ("don't say X — say Y") is the most effective LLM-drift defense in this repo, because synonym choice is where models slip first. New domain noun/verb → add the entry *before* merging the change that uses it.

### 6. No silent backfill

When a durable doc disagrees with current code, do **not** silently edit the durable doc to match. Instead, decide whether a new ADR should supersede, or whether `USE-CASES.md` needs a new UC. The only allowed in-place touch on durable docs is the mechanical path-rename fix after a directory restructure.

## Anti-patterns specific to this repo

- Editing `docs/plans/` to chase code drift — it's scaffold by design; chasing produces noise and a fake history.
- Editing `docs/roadmap/2026-05-22-...-design.md` to reflect a new decision — supersede with a new spec instead, or write an ADR. Surgical path-rename fixes are the only allowed in-place change there.
- Adding an actor inline in a UC file without updating `docs/spec/ACTORS.md` first.
- Using a synonym ("status", "rollup table", "real-time", "asset", "equipment") that the Anti-Glossary section flags — always consult `GLOSSARY.md` first.
- Treating `USE-CASES.md` as the *full* spec — it's only the index/registry; authoritative spec content lives in per-UC files.
- Running an older `scripts/check-use-case-coverage.sh` referenced in early plan drafts — the active gate is the Python script `check-use-case-coverage.py`, which actually parses YAML frontmatter. If you see the `.sh` referenced anywhere, that's a stale reference to update.

## Worked example

User: "Add a UC for the operator acknowledging an alarm."

Wrong path: open `docs/spec/USE-CASES.md` and add a paragraph describing the behavior.

Right path:

1. Confirm "Alarm" exists in `docs/spec/GLOSSARY.md` under `monitoring`. It does, but `status: proposed` — flag this in the UC's *Open questions* section.
2. Confirm `A-OP` exists in `docs/spec/ACTORS.md`. Yes.
3. Copy `docs/spec/use-cases/_TEMPLATE.md` to `docs/spec/use-cases/UC-003-acknowledge-alarm.md`. Fill frontmatter: `status: draft`, `primary_actor: A-OP`, `secondary_actors: [S-UI, S-API, S-DB]`, `bounded_context: monitoring`, `related_e2e: apps/dashboard-react/tests/e2e/UC-003-acknowledge-alarm.spec.ts`.
4. Write Goal / Trigger / Preconditions / Main scenario / Commands & events (e.g., `AcknowledgeAlarm(alarmId, by)` → `AlarmAcknowledged(alarmId, at, by)`) / Invariants / Gherkin AC / Out of scope / Open questions.
5. Add a row to `docs/spec/USE-CASES.md` pointing at the new file.
6. Run `uv run scripts/check-use-case-coverage.py` — expect `OK: N use case(s)...`.
7. Only after the corresponding E2E spec is written and passes, flip `status: implemented` in both the per-UC file and the registry row.
