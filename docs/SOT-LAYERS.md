# Documentation SoT Layers

How this repo treats documents as sources of truth, and what's throwaway scaffolding. The intent is to keep durable docs *cheap to maintain* (they don't drift with code) while letting tactical docs (implementation plans) stay disposable.

---

## Why this project needs an explicit policy

In a typical product codebase, the deliverable *is* the running system. Documents that describe implementation eventually fall out of sync with code, so most teams end up with **functional spec as durable SoT (rarely-changing user behavior)** and **code as SoT for everything else**. Implementation plans are scaffolding.

This portfolio is different in one important way: **part of the deliverable is the documents themselves.** Interviewers read ADRs, KNOWN-UNKNOWNS, and AI-WORKFLOW case studies as primary evidence of engineering judgment. That widens the durable-SoT surface — but the same cost discipline still applies: a durable doc must be cheap to keep correct, or it isn't really SoT.

The trick is to split the durable surface into layers that each have a *natural reason not to drift*:
- decisions are frozen at decision time;
- AI-workflow incidents are frozen at incident time;
- functional surface only changes when user behavior changes;
- acceptance criteria only change when "done" is redefined.

Code is the only thing that changes constantly, and it stays the SoT for *current behavior*.

---

## The layers

| Layer | Change cadence | SoT? | Examples |
|---|---|---|---|
| **Strategy** (why / where) | Almost never | ✅ durable | `docs/roadmap/2026-05-22-sdf-manufacturing-dx-portfolio-design.md` §1, §10. Frozen snapshot at project start. |
| **Decisions (ADR)** | Once per decision, then frozen | ✅ snapshot at decision time | `docs/ADR/0001..NNNN`. Superseded ADRs are *added*, not edited. |
| **Engineering Conventions** | Convention evolution only — else frozen | ✅ durable (living guide) | `docs/architecture/...`. Code-level patterns (FC/IS adoption, DDD tactical mapping, error/clock/cross-BC rules). |
| **Functional surface** | Only when user-visible behavior changes | ✅ durable | `docs/spec/` (ACTORS, GLOSSARY, USE-CASES, per-UC files), `docs/DOMAIN-NOTES.md`, `docs/KNOWN-UNKNOWNS.md`, `README.md`, `docs/walkthrough-script.md` |
| **Acceptance Criteria (AC)** | Only when the definition of "done" for a phase changes | ✅ durable | design spec §13.1–13.5 (Phase 1..5 AC). Acts as the project's roadmap-spec. |
| **AI workflow cases** | Once per incident, then frozen | ✅ snapshot | `docs/AI-WORKFLOW/case-NN.md` |
| **Implementation plan** | One per phase, archived after execution | ❌ scaffold | `docs/plans/...` |
| **Code** | Continuously | ✅ "how it currently behaves" | the repo |

### What "SoT" means per layer

- *Strategy* — the answer to "what is this portfolio trying to prove?" If strategy changes, write a new spec, don't edit in place.
- *Decisions* — the answer to "why did we choose X over Y?" An ADR is authoritative about *the moment its decision was made*. If you reverse it, write a new ADR that supersedes the old one; don't edit history.
- *Engineering Conventions* — the answer to "what code-level patterns must all code in this repo follow?" A living guide for architecture rules (FC/IS, error handling, injection, cross-BC). Sits between ADRs (which record *why* a pattern was chosen, point-in-time) and code (which is the implementation). Edited only when a convention actually evolves.
- *Functional surface* — the answer to "what does the system do, from the outside?" This is the classic functional-spec role. Updated only when actual external behavior changes.
- *Acceptance Criteria* — the answer to "what must be true to call this phase done?" Functions as the checklist you diff against the repo + docs to see what's left. AC items can be runtime behaviors *or* engineering artifacts (e.g., "ADR 1, 2, 3, 4 written").
- *AI workflow cases* — the answer to "what did the LLM get right/wrong, and how did the guardrails fire?" Written immediately after the incident — cannot be reconstructed later.
- *Code* — the answer to "how does it currently work?" This is the only doc that's continuously updated, because it *is* the artifact.

---

## Mapping to traditional web-dev workflow

The author's prior habit (general web development) was: keep functional spec as the durable roadmap-shaped SoT; treat implementation plans as throwaway; let code be SoT for current behavior. That habit transfers directly — only the *names* and *scope* of the durable layer change:

| General web project | Equivalent in this project | Location |
|---|---|---|
| Functional spec (the roadmap) | Phase Acceptance Criteria | design spec §13.1–13.5 |
| Functional spec — runtime-behavior subset | `USE-CASES.md` + per-UC files | `docs/spec/USE-CASES.md`, `docs/spec/use-cases/` |
| Functional spec — actor catalog | `ACTORS.md` | `docs/spec/ACTORS.md` |
| Functional spec — ubiquitous language | `GLOSSARY.md` | `docs/spec/GLOSSARY.md` |
| Functional spec — explicit *negative* space | `KNOWN-UNKNOWNS.md` | `docs/KNOWN-UNKNOWNS.md` |
| Implementation plan (throwaway) | Phase plan | `docs/plans/...` |
| Decision rationale | ADRs | `docs/ADR/` |
| (Tacit team knowledge / wiki) | Engineering Conventions (explicit doc) | `docs/architecture/` |
| Strategy / context | Design spec (other than §13) | `docs/roadmap/...` |

In short: in this project's vocabulary, **"functional spec as durable SoT" expands to "(Strategy + ADRs + Functional surface + AC) as durable SoT"**. AC plays the roadmap role; USE-CASES plays the user-behavior subset role.

---

## Operational rules

### What stays SoT — never edit destructively
- **Strategy doc**: frozen at project start. If strategy shifts mid-flight, write a new spec under `docs/roadmap/` and let it supersede the old one. Do not edit in place.
- **ADRs**: never edit accepted ADRs. New decision → new ADR that lists the old as superseded.
- **Engineering Conventions**: edit only when a convention actually evolves (e.g., adopting a new pattern, deprecating one). Each substantive change should reference (or trigger) an ADR that records *why*. The convention doc says *how*; the ADR says *why we chose this how*. Code following an existing convention is not a reason to edit the doc.
- **AI-WORKFLOW cases**: never edit after the incident; correct typos only.
- **AC**: edit only when the definition of "done" for that phase changes (rare). Treat each AC checkbox as a contract.

### What's scaffolding — disposable
- **Phase plans**: written before each phase, executed once, then moved to `docs/plans/archive/` after the phase tag lands. Never updated to reflect drifted code — if reality diverged, write an ADR explaining why, leave the plan as a record of what we originally tried.

### What's continuously SoT
- **Code** — including `README.md` quickstart (since it's a thin shell around `docker compose up`).
- **Functional surface docs** — only updated when externally observable behavior actually changes; that's a real edit, not drift maintenance.

### What signals "this should become an ADR"
If you find yourself wanting to update an old doc to reflect a new choice, that usually means a new ADR is needed instead. Don't backfill the strategy doc; supersede.

---

## Per-phase workflow

1. **Before starting a phase**
   - Confirm the phase's AC exists in design spec §13.N. If anything is missing or unclear, edit AC *first* (this is the only durable doc you edit at this step).
   - Write the phase's implementation plan under `docs/plans/YYYY-MM-DD-phase-N-<slug>.md`. This is scaffold and treated as such.
   - If the phase depends on yet-undecided choices, write those ADRs *before* coding (load-bearing decisions deserve to be settled cold, not under deadline pressure).
   - The phase's first commits are the **Chapter 0 batch** (static spec + load-bearing ADRs + initial `DOMAIN-NOTES.md` / `KNOWN-UNKNOWNS.md`) — must land before any implementation commit. See [ADR-0000](ADR/0000-phase-iteration-chapter-0.md) for the structural rule and the rationale (commit-log shape, LLM drift prevention, AI-WORKFLOW authenticity).

2. **During the phase**
   - Treat AC as the SoT for "what's left." Don't add features that aren't in AC; if you discover one is needed, edit AC explicitly.
   - When a non-trivial decision lands in code, write the ADR *immediately* — the rationale rots within days.
   - When an AI-collaboration incident happens (LLM hallucination caught, surprising guardrail save, novel prompting pattern), write the AI-WORKFLOW case the same day.
   - The phase plan may go stale during the phase; that's fine — don't update it.

3. **At phase end**
   - Verify every AC checkbox passes (run the gates; don't self-certify).
   - Tag the commit (`phase-N`).
   - Move the phase plan to `docs/plans/archive/`.
   - Update `README.md` "Phase status" line.
   - Update USE-CASES / KNOWN-UNKNOWNS only if observable behavior changed.

---

## Quick test: "where does this belong?"

When unsure where to put a piece of information, ask:

- "Will this still be true a year from now?" → durable layer. Identify which.
- "Does this describe *a decision* I made?" → ADR.
- "Does this describe *how all code in this repo should be written*?" → Engineering Conventions (`docs/architecture/`).
- "Does this describe *what the user sees*?" → USE-CASES or DOMAIN-NOTES.
- "Does this describe *what I explicitly chose not to do*?" → KNOWN-UNKNOWNS.
- "Does this describe *how to build something*?" → Phase plan (scaffold).
- "Does this describe *what must be true to call a phase done*?" → AC.
- "Does this describe *how the code currently works*?" → code (or, occasionally, a brief comment in code).

If two layers look plausible, prefer the more *frozen* one. Durability is cheap because it doesn't get touched.
