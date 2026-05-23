# ADR-0000: Phase iteration opens with Chapter 0 (static spec & decisions before implementation)

* **Status**: Accepted
* **Date**: 2026-05-23
* **Supersedes**: none
* **Superseded by**: none

---

## Context

`docs/SOT-LAYERS.md` already states two policies that this ADR builds on:

- §"Per-phase workflow" §1: *"If the phase depends on yet-undecided choices, write those ADRs **before** coding (load-bearing decisions deserve to be settled cold, not under deadline pressure)."*
- §"Per-phase workflow" §2: *"When a non-trivial decision lands in code, write the ADR **immediately** — the rationale rots within days."*
- §"Per-phase workflow" §2: *"When an AI-collaboration incident happens..., write the AI-WORKFLOW case the same day."*

These rules are correct, but they describe the *cadence* of writing each artifact in isolation. They do not name the **structural unit** at the start of a Phase that bundles the load-bearing set into a single commit batch. As a result, the current Phase 1 plan (`docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md`) consolidates spec, ADR, and domain-notes work into **Section H — Documentation (Task 24–26)** at the end of the phase, after most implementation has landed. This violates both bullets above but the violation is easy to make because no single artifact in SOT-LAYERS names what is missing.

The cost of the current ordering, in this project specifically:

1. **Commit history shape is the primary portfolio surface.** Viewers (interviewers, recruiters, future maintainers) scroll `git log --oneline` and read the *order* of commits more than the body of any single doc. A phase whose log reads `feat(...) × 30 → docs(...) × 5` signals "built first, documented after." This contradicts the portfolio thesis ("AI-네이티브 senior가 낯선 도메인을 정직하게 탐독"). The thesis only survives if the log reads `docs(spec/ADR/...) × N → feat(...) × M → docs(...) × revisions`.

   *This rationale is a calibrated bet* (see Notes §"Calibration"). **Falsification criterion**: if Phase 1 and Phase 2 retrospectives surface *no* interviewer comment on commit ordering or doc cadence, downgrade this rationale and re-evaluate whether the Chapter 0 batch's upfront cost is justified.

2. **LLM drift across sessions.** Implementation sessions that start without a frozen Chapter 0 SoT must re-discover the spec from prior chat context each time. Drift accumulates between sessions. A Chapter 0 batch on disk gives every later session an unambiguous reference.

3. **AI-WORKFLOW case authenticity.** A case study written after the incident is a reconstruction, not a record. SOT-LAYERS line 95 already calls this out, but the Phase 1 plan still defers them — because no rule binds "incident-time writing" to a visible commit boundary.

A Phase is one iteration. Within an iteration, spec-first ordering is not waterfall — it is the normal opening of an iteration. The unit that has been missing is the **Chapter 0 commit batch**.

---

## Decision

Every Phase iteration opens with a discrete **Chapter 0 — Spec & Decisions** commit batch. The Phase's first implementation commit MUST come after Chapter 0 is complete.

### Chapter 0 contents

The repo's spec/ADR/domain documents fall into two categories. Both feed Chapter 0 commits, but with different cadence.

**Category A — Project-lifetime registries** (initial creation is a *one-time event* before Phase 1's Chapter 0; per-phase Chapter 0 only *appends* a delta, never re-writes):

| Path | Initial state (one-time, pre-Phase-1) | Per-phase Chapter 0 delta |
|---|---|---|
| `docs/spec/USE-CASES.md` | Registry created with conventions block (already exists) | Append rows for new UCs introduced this phase |
| `docs/spec/ACTORS.md` | Actor catalog created (already exists) | Append new actor rows first appearing this phase |
| `docs/spec/GLOSSARY.md` | Glossary created with Phase 1 BC scopes + reserved labels for future phases (already exists) | Append new terms first appearing this phase |
| `docs/spec/use-cases/_TEMPLATE.md` | Created once (already exists) | Touched only when the UC structure itself changes |

Their append-only conventions are enforced by the files themselves (`USE-CASES.md` line 7: *"never delete a row — set `status: retired` instead"*; `ACTORS.md` line 55: *"add a row before writing the first UC that references it"*). **Re-writing the whole of a Category A file in a per-phase Chapter 0 is a violation** of this ADR.

**Category B — Per-phase artifacts** (created or extended *at the start of each Phase*, before any implementation commit of that Phase):

| Path | What lands in Phase N's Chapter 0 |
|---|---|
| `docs/spec/use-cases/UC-***.md` | One new file per UC introduced this phase |
| `docs/ADR/****.md` | One ADR per load-bearing decision known at this phase's planning time |
| `docs/DOMAIN-NOTES.md` | This phase's initial domain study notes (extend the file if already exists) |
| `docs/KNOWN-UNKNOWNS.md` | This phase's initial open questions (extend the file if already exists) |

For Phase 1 specifically: `DOMAIN-NOTES.md` and `KNOWN-UNKNOWNS.md` do not yet exist; their initial contents land in Phase 1's Chapter 0.

### What counts as a "load-bearing decision" for Chapter 0

A decision is load-bearing — and therefore belongs in an ADR landed within Chapter 0 — if **any** of the following hold:

1. Two reasonable implementation paths exist *and* they would produce different code structure across ≥2 downstream tasks.
2. The decision constrains module boundaries, persistence shape, contract format, or cross-process protocol.
3. Reversing the decision would cost >1 day of focused work.

A decision is *not* load-bearing (so it can emerge mid-phase, per SOT-LAYERS §"Per-phase workflow" §2) if:

- It affects ≤1 task and reversal is local.
- It is a tactical choice *within* an already-decided architecture (e.g., a specific library choice within an already-decided protocol).

When in doubt, treat it as load-bearing and ADR it at Chapter 0. The cost of a redundant Chapter 0 ADR is small; the cost of post-hoc rationalization is the portfolio thesis (rationale 1 above).

### Living documents (committed throughout the phase — NOT in Chapter 0)

These continue to commit as their underlying events occur, per SOT-LAYERS §"Per-phase workflow" §2:

- `docs/KNOWN-UNKNOWNS.md` — additions and resolutions, at the moment they happen
- `docs/AI-WORKFLOW/case-NN.md` — written *during* the incident, not after
- `docs/DOMAIN-NOTES.md` — revisions when implementation reveals new understanding
- `docs/ADR/****.md` — new ADRs for decisions that *emerge mid-phase*, written immediately at decision time

### Phase plan ordering rule

A Phase plan (`docs/plans/YYYY-MM-DD-phase-N-*.md`) is **non-compliant** if any implementation task (`feat`, `chore: scaffold`, `infra`) appears in the task list ahead of the Chapter 0 tasks. Plans must be restructured before execution if this is found.

---

## Consequences

1. **Phase 1 plan (`docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md`) is partially non-compliant.** Task 5 (ADR-0001..0004) is already correctly positioned in Section A — no change needed there. The non-compliant portions:
   - **Task 24** is mixed (`Playwright E2E + UC-002 spec creation + status promotion to implemented`). The UC-002 spec *creation* must split out into Chapter 0; the E2E + `draft → implemented` status promotion correctly remains at phase end (those require the implementation + a passing E2E to be honest).
   - **Task 25** (ADRs 0005..0008, 0010..0012) is mis-positioned. The whole task moves to Chapter 0 — these are load-bearing decisions known at Phase 1 planning time.
   - **Task 26** is partially mis-positioned. The *initial* content of `KNOWN-UNKNOWNS.md` and `DOMAIN-NOTES.md` moves to Chapter 0; their *additions and revisions during the phase* stay inline at the point of occurrence (living docs). `docs/AI-WORKFLOW/case-01.md` must be written incident-time, not in Chapter 0 — the file may not even exist at phase start.

2. **Future Phases (2, 2b, 3, 4, 5) follow the same shape.** Each phase plan opens with its own Chapter 0.

3. **Spec/ADR revision commits during implementation are expected and visible.** A mid-phase commit like `docs(domain-notes): correct OEE idle-time exclusion after Hypothesis test (UC-002)` is *evidence of honest iteration*, not a failure of upfront planning. They are not to be hidden.

4. **Mild upfront cost at phase start.** Understanding Phase scope well enough at planning time to write spec + load-bearing ADRs before code is more work upfront than the previous "scaffold then doc" approach. This is accepted in exchange for (a) cleaner commit log, (b) LLM drift prevention, (c) AI-WORKFLOW authenticity.

5. **AI-WORKFLOW case files become a meaningful quality signal.** Because cases must be written incident-time, the *cadence* of case commits across the phase (interspersed with `feat`/`fix` commits) becomes itself a visible signal of LLM collaboration.

---

## Notes

- This ADR **tightens** `docs/SOT-LAYERS.md` §"Per-phase workflow" by naming the structural unit ("Chapter 0 commit batch") and forbidding the "documentation-at-end" anti-pattern. It does not contradict SOT-LAYERS; it gives the same policy an enforceable shape.
- **Chapter 0 prerequisites**: a Phase's Chapter 0 can begin only when (a) the Phase's AC is frozen in design spec §13.N and (b) a draft phase plan exists under `docs/plans/`. ADR-0000 itself is *idempotent* across phases — not re-decided per phase. The first *technical* ADR of a Phase's Chapter 0 depends only on the frozen AC.
- **Enforcement surface**: `.claude/rules/phase-iteration.md` — auto-loaded by Claude Code each session, mandates Chapter 0 ordering in any Phase plan work.
- **ADR-0000 by deliberate choice.** This methodology decision sits before all technical ADRs in the series. The first commit of the ADR sequence (`docs(adr): ADR-0000 ...`) is itself the first item of Phase 1's Chapter 0 batch — self-consistent.
- **Calibration that informed this ADR**: viewers of this portfolio (interviewers per the author's roleplay experience) read folder structure + commit history + code, not doc bodies. This shifts the "where does the signal live" weighting toward commit log shape and away from doc prose. The decision here is optimized accordingly.
