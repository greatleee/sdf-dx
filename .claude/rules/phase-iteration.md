# Rule: Phase iteration opens with Chapter 0

When planning, scaffolding, restructuring, or executing a Phase iteration in this repo: **the first commits of the phase MUST be the Chapter 0 batch.** No `feat(...)` or `chore: scaffold` commit lands until Chapter 0 is complete.

## Chapter 0 batch (at phase start, before any implementation commit)

**Append to project-lifetime registries** (already created; never re-write — only append rows / entries):
- `docs/spec/USE-CASES.md` — append rows for new UCs introduced this phase
- `docs/spec/ACTORS.md` — append new actor rows first appearing this phase
- `docs/spec/GLOSSARY.md` — append new terms first appearing this phase

**Create or extend per-phase artifacts**:
- `docs/spec/use-cases/UC-***.md` — one new file per UC introduced this phase
- `docs/ADR/****.md` — one ADR per **load-bearing decision known at planning time** (stack, persistence, contracts, layering, etc.)
- `docs/DOMAIN-NOTES.md` — this phase's initial domain study notes (extend the file if already exists)
- `docs/KNOWN-UNKNOWNS.md` — this phase's initial open questions (extend the file if already exists)

## Living docs (committed throughout the phase — NOT batched into Chapter 0)

- `docs/KNOWN-UNKNOWNS.md` additions / resolutions — at the moment they happen
- `docs/AI-WORKFLOW/case-NN.md` — during the incident, **not after**
- `docs/DOMAIN-NOTES.md` revisions — as understanding deepens
- New `docs/ADR/****.md` for decisions that *emerge mid-phase* — at decision time

## Plan-ordering check (apply when writing or reviewing any `docs/plans/YYYY-MM-DD-phase-N-*.md`)

Distinguish three task kinds when evaluating order:

- **Create** — a task that *first writes* a spec/ADR/UC file (or initializes a living doc). Must be in Chapter 0.
- **Promote / status-change** — a task that flips an existing file's status (e.g., UC `draft → implemented`) or wires it to E2E. Belongs at phase end, *not* in Chapter 0.
- **Living-doc update** — a task that adds an entry to a living doc (KNOWN-UNKNOWNS resolution, DOMAIN-NOTES revision, AI-WORKFLOW case) at the natural point of occurrence. Distributed throughout the plan, *not* batched into Chapter 0.

Then:

1. Every **Create** task must appear in Chapter 0, before any code / infra / scaffold task.
2. No code, infra, or scaffold task may appear before Chapter 0 is complete.
3. **Promote / status-change** tasks at phase end are correct — do not flag.
4. A single task that mixes **Create + Promote** (e.g., "write UC-002 spec + flip both UCs to implemented + add E2E") must be **split**: the Create portion to Chapter 0, the Promote portion remains at phase end.

## Why (short form)

- `git log --oneline` is the primary portfolio surface for this repo; commit *order* is the signal. Chapter 0 → implementation → revisions tells the right story.
- Chapter 0 acts as a frozen SoT for every later LLM session, reducing drift across sessions.
- AI-WORKFLOW cases are authentic only when written incident-time, not backfilled.

Full rationale & contents: [`docs/ADR/0000-phase-iteration-chapter-0.md`](../../docs/ADR/0000-phase-iteration-chapter-0.md)
Layer policy this complements: [`docs/SOT-LAYERS.md`](../../docs/SOT-LAYERS.md) §"Per-phase workflow"
