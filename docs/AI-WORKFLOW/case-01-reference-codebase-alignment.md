# Case 01 — Over-strict conventions corrected via reference-impl verify + intentional divergence

| | |
|---|---|
| **Date** | 2026-05-23 (same day as case-00; this is the immediate follow-up) |
| **Phase** | Pre-Phase 1 (design) |
| **Status** | Resolved |
| **Artifacts** | `docs/ADR/0019` (ORM containment) / `0020` (UoW) / `0021` (ClockPort) / `0022` (Ports folder) / `0023` (importlinter set) / `0024` (Fakes with InMemoryDataset); `docs/architecture/2026-05-23-code-architecture.md` (TL;DR + §1.2 + §2 + §3.2 + §5 + §6 + §7 + §8 + §9 in-place edits); `.claude/rules/backend-code-architecture.md` (full rewrite, fast-scan form preserved); `docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md` (header conflicts (e)~(k) added, body untouched); `docs/plans/archive/2026-05-23-reference-codebase-alignment-plan.md` (disposable alignment plan, archived after execution); memory `reference-codebase` (cross-conversation pointer) |

> Second meta-incident on the same architecture work — case-00 wrote the conventions, this case corrects them against an external Python reference impl (`the reference codebase`). The corrections weren't bug-fixes; the original conventions were "defensible but stricter than the reference," and the user wanted reference alignment where it made sense.

---

## Incident

Case-00 landed arch doc + ADRs 0004 / 0009 / 0016 / 0017 / 0018. Several rules in that body were drawn from cosmic-python conventions and stricter readings of FC/IS, without checking what the team's actual Python reference impl (`the reference codebase`, an unrelated project in `the reference codebase/`) does. Three classes of over-strictness:

1. **ORM blanket ban at adapter** — case-00 §8.1 said "Forbidden in core: ORM. Allowed at adapter: SQLAlchemy Core / asyncpg raw." That ruled out the working pattern `the reference codebase` ships: SQLAlchemy 2.0 ORM *inside the adapter file* with private `_Base` / `_X` declarations and a public `*Repo` class that returns primitives. Domain still doesn't see ORM; the containment is at file boundary.
2. **Two-shape latitude for clock injection** — case-00 ADR-0017 allowed both `Callable[[], datetime]` and a `Clock` Protocol. `the reference codebase` uses `ClockPort` Protocol uniformly. Two shapes coexisting produced fork-by-author-preference once code started landing.
3. **Single-file ports + DDD-classical naming bans** — case-00 placed Port Protocols in single `contexts/<bc>/ports.py` and banned `*Repository` outright (intended to block DDD-classical Repository pattern). The reference impl uses `ports/<noun>.py` folders and `*Repo` suffix as general persistence vocabulary — and user pointed out "Repo는 DDD만의 용어가 아니라 범용적으로 사용되는 어휘" (Repo is general, not DDD-exclusive).

Also implied but not yet decided in case-00: Unit of Work pattern (who owns `commit()`?), per-BC fakes layout, importlinter contract for "adapters don't import upward."

User's framing: "the reference codebase은 어떻게 하나? 그쪽 패턴이 더 nuanced하면 정렬하자." The alignment scope was not assumed — it was decided per item.

---

## Sequence

1. **Disposable alignment plan written first** (`docs/plans/2026-05-23-reference-codebase-alignment-plan.md`). Header: `Temporary — disposable. /clear 후 cold-resume용.` §9 Resume guide + §10 placeholder for "verified findings + new questions." Plan declared verify-FIRST per project memory `feedback-lazy-reasoning-audit`. Plan committed before any other change so a /clear-survivor existed.
2. **Permission surface**: auto-mode classifier blocked the first attempt to `ls` the external repo (`(path removed)/...`) as "scope escalation." Did *not* work around — surfaced to user with three options (session-only read, persistent settings.json, user-paste). User chose session-only. Took 1 turn; no time lost relative to alternative of just trying to bypass.
3. **Verify FIRST** — 12 files read in batched parallel calls. composition.py first (gives wiring shape), then 1 domain file, 1 sum-type domain file, 2 ports files, 1 UoW protocol + adapter pair, 1 ORM adapter, 1 clock adapter, 1 fakes file, 1 use case file. Findings written into plan §10 inline as authoritative source (not just summarized in chat).
4. **Decisions surfaced as a sequence of `AskUserQuestion` batches**, ~4 questions per batch with `preview` for folder shapes / code snippets. Each batch closed a class of decision and constrained the next:
   - Batch 1: `contexts/` vs flat (multi-BC vs single-BC). User kept `contexts/`.
   - Batch 2: Pydantic-in-domain / Ports grouping / Use-case folder name / importlinter scope. User kept Pydantic-out-of-domain (intentional divergence), file-per-feature ports, `application/` folder, importlinter adopted.
   - Batch 3: `*Repo` suffix / sum-type tag literal / fakes layout. User allowed `*Repo` for both Port and Adapter, rejected tag-literal pattern, accepted per-BC fakes.
   - Batch 4: Kotlin scope. User proposed "Kotlin 전용 ADR" as an option not in my list. I surfaced the conditions for writing one (Kotlin reference impl needed OR defer to Phase 1 Task 4) and user chose to defer.
5. **6 new ADRs written + ADR-0018 preserved with divergence note**. Each ADR cites the reference impl file path. ADR-0020 took an additional internal decision (per-BC vs global UoW — chose per-BC, aligned with ADR-0009 inter-context independence) and surfaced it as part of the ADR Context, not silently.
6. **Doc-immutability check before editing arch doc** — surfaced project memory `project-doc-immutability` (which names "전략/ADR/AI-WORKFLOW" as supersede-only) and asked whether arch doc was in scope. User chose in-place editing for arch doc ("living doc, ADRs are the frozen snapshots"). Edits then proceeded in-place with each substantive change citing its ADR number.
7. **Rules file rewritten in fast-scan form** preserving Kotlin parallel constructs. User specifically asked "rules는 간결해야하기 때문에 do/dont or must/must not 형태로 압축" — followed strictly. Lines grew 191→238 (+25%) because new rule areas were added (UoW, Ports folder, Fakes, importlinter), but form held.
8. **Phase 1 plan header patched** — known conflicts (a)~(d) extended with (e)~(k). Body untouched per case-00's forward-reference pattern.
9. **Reference memory written + MEMORY.md index updated** so the cross-conversation pointer survives `/clear`.
10. **Alignment plan archived** to `docs/plans/archive/` after execution complete. Case-01 (this file) written immediately per SOT-LAYERS AI-workflow rule.

---

## Decisions ultimately made (frozen in ADRs)

| Decision | Source | ADR |
|---|---|---|
| SQLAlchemy 2.0 ORM allowed in adapter under containment (private `_Base`/`_X`, public `*Repo` returns primitives, no commit, no Port inheritance, `Computed` for GENERATED) | reference `adapters/postgres_orders.py` | 0019 |
| Unit of Work — `UnitOfWork` Protocol per BC (not global), `SqlAlchemyUnitOfWork` adapter, use case owns `commit()` via `async with self._uow_factory() as uow:`, `async_sessionmaker(expire_on_commit=False)` | reference `adapters/sqlalchemy_uow.py` + ADR-0009 inter-context | 0020 |
| Clock injection — `ClockPort` Protocol uniformly. `Callable[[], datetime]` retired. Location: `shared_kernel/ports/clock.py` (cross-cutting) | reference `adapters/system_clock.py` + plan §10 decision | 0021 |
| Ports as folder, file-per-feature (`contexts/<bc>/ports/<noun>.py`); cross-cutting Ports in `shared_kernel/ports/` | reference `ports/` layout + plan §10 decision | 0022 |
| importlinter contract set as single source — 7 Python contracts (existing 4 + new `adapters-no-upward`, `composition-only-imports-adapters`, `bc-independence` formalized) + 3 AST checks (A1/A2 existing + A3 new for `uow.session`) | reference `adapters-no-upward` + ADR-0019/0020 follow-ups | 0023 |
| Fakes — per-BC `tests/contexts/<bc>/fakes.py` + per-BC `InMemoryDataset`, working in-memory implementations, mirror DB-side constraints, assertion-on-state not assertion-on-call | reference `adapters/fakes.py` pattern + Fowler "Mocks Aren't Stubs" | 0024 |
| Pydantic stays at boundary only — `@dataclass(frozen=True, slots=True)` in domain. **Intentional divergence** from reference (which uses Pydantic-in-domain throughout) | user kept status quo at batch 2 | 0018 (preserved + divergence note added to body) |
| Sum-type discrimination via class type, no `tag: Literal[...]` field — **intentional divergence** from reference | user chose simpler line at batch 3 | (no ADR — rule §3 + plan §10.3 #3) |
| Kotlin scope — no Kotlin-specific ADRs in this round; defer to Phase 1 Task 4 (Kotlin gateway setup) when actual Kotlin code lands | user choice at batch 4 | (deferred) |

---

## LLM judgment exercises

- **Verify FIRST, written into plan**: the alignment plan opened with `§2 Verify FIRST (실행 전 반드시) — Lazy reasoning 재발 방지`. I cited the `feedback-lazy-reasoning-audit` memory explicitly in the opening verify message. The plan-as-self-audit pattern made the verify discipline visible to the user, not just internal.
- **Permission denial handled correctly**: classifier blocked external-repo access. I did not try to bypass (e.g., using `head` instead of `ls` after `ls` denied). Surfaced with three options. The denial itself was a guardrail working as intended.
- **Intentional divergence is a decision, not a default**: when the user kept Pydantic-out-of-domain despite the reference using Pydantic-in-domain, I added a "Intentional divergence from the reference codebase" paragraph to ADR-0018 body and the arch doc §8.3. The divergence is now traceable from any future "why don't we do what the reference codebase does?" question.
- **Per-BC UoW vs global UoW surfaced inside ADR-0020**: the reference is single-BC so the question doesn't appear there. For multi-BC sdf-dx, "where does UoW Protocol live" is a real decision. I made the call (per-BC, aligned with ADR-0009) and documented the rejected alternative in the ADR Context, not just the Decision.
- **Kotlin scope honest**: user proposed "Kotlin 전용 ADR" as a fourth option (not in my list). I surfaced the conditions — Kotlin reference impl needed OR defer — instead of writing Kotlin ADRs from inference. Phase 1 Task 4 (Kotlin gateway) will land Kotlin code; that is the right time to write Kotlin-specific decisions with code in hand.
- **Doc-immutability check before arch doc edit**: project memory says "전략/ADR/AI-WORKFLOW는 in-place 편집 금지." Arch doc is ambiguously in scope (it is a "convention" doc, not strategy or ADR). I surfaced this rather than assumed, and user explicitly cleared in-place editing for arch doc (living doc).
- **Decision-matrix surface before ADR drafting**: after all `AskUserQuestion` batches resolved, I posted the full decision matrix (11 rows) + ADR list (6 new + 1 preserved) for user confirmation before starting to write ADR-0019. No ADR draft was opened until the matrix was acknowledged.
- **Rules file form preserved under user instruction**: user said "rules는 간결해야하기 때문에 do/dont or must/must not 형태로 압축." I rewrote in form, added content where decisions changed, kept Kotlin parallel constructs because they were already-decided previous work. Did not let new content expand the form.

---

## Guardrails — what fired, what didn't

| Guardrail | Result |
|---|---|
| Project memory `feedback-lazy-reasoning-audit` | ✅ fired pre-emptively. Cited in plan §2 opening + in the verify-first message. Drove the 12-file read before any decision. |
| Project memory `feedback-deliberate-discussion` | ✅ fired. Four `AskUserQuestion` batches with `preview` for code/folder shapes, not natural-language descriptions. User changed his mind on the fly twice (e.g., Pydantic-in-domain rejection) — the preview pattern made the alternatives concrete enough to evaluate. |
| Project memory `project-doc-immutability` | ✅ fired. Asked whether arch doc was in scope before editing instead of assuming. |
| Auto-mode classifier external-repo block | ✅ fired and respected. No bypass attempt; surfaced choices to user. |
| SOT-LAYERS §74 (plans never updated to reflect drifted code) | ✅ fired and honored, twice. Phase 1 plan body untouched; only header conflicts list extended. The alignment plan was archived as-is post-execution, not edited to "match current state." |
| Decision-time ADR write (case-00 transferable pattern #5) | ✅ fired. All 6 ADRs written within the same conversation as the decisions, not deferred. |
| Forward-reference pattern (case-00 transferable pattern #1) | ✅ fired. Phase 1 plan header patched with (e)~(k) instead of body rewrite. |
| Pre-execution check that arch doc was already over-strict | ❌ no tool surfaced this. The over-strictness in case-00 was internal-reasoning-only — no automated comparison against the reference impl. **Improvement candidate**: a "reference-impl drift" check that compares written conventions against a designated reference repo and surfaces deltas. For Python-only this could be a structured prompt that walks named reference patterns + checks arch doc has not contradicted them. |
| Verify-FIRST as a *plan section*, not a casual habit | ✅ new pattern this round. The plan literally had `§2. Verify FIRST (실행 전 반드시) — Lazy reasoning 재발 방지` as a section title. Made the discipline survive `/clear` cold-resume. |

---

## Transferable patterns

1. **Disposable alignment plan as cold-resume scaffolding**. When a multi-commit doc-correction round starts, write the plan with `/clear`-survival in mind: `§9 Resume guide` + `§10 placeholder for verified findings (frozen source after verify)`. Plan committed *before* any other work; archived after execution. Distinct from case-00's case study (which is the post-mortem) — the plan is the pre-execution scaffolding.
2. **Verify FIRST as a plan section**. Don't just say "verify before deciding." Make `§2. Verify FIRST` a literal plan section with file paths + verify questions. The plan becomes a self-audit artifact, and `/clear` cold-resume picks up the discipline.
3. **Decision matrix before ADR drafting**. After `AskUserQuestion` batches resolve, post the full matrix (one row per decision) for user confirmation. ADRs only open after matrix acknowledged. Stops mid-draft direction changes from polluting ADR commit history.
4. **Reference memory pointer with re-verify reminder**. Memory entry includes the reference path + "verify by reading current files — patterns may evolve in that repo." Future sessions read the memory + re-verify, not just recite.
5. **Intentional divergence documented in the ADR body**. When not mirroring a referenced pattern, add a paragraph naming the reference + the reason for divergence. Makes future "why don't we do X like the reference?" questions cheap to answer.
6. **Per-language scope honest**. Don't write conventions for languages without code or reference impl. Defer to the conversation that lands the first file. Mark deferred areas explicitly in the plan/ADR set, so future-me sees the gap.
7. **Doc-immutability surfacing as an `AskUserQuestion` step**. When a memory rule is ambiguously in scope (does "ADR" cover the arch doc?), don't assume either way — surface to user with options including in-place / supersede / hybrid. The 30 seconds of friction beats either of: editing a frozen doc or duplicating an active doc.
8. **Rules-file form preservation under expansion**. When new content lands in a fast-scan rules file, expand in the existing do/don't shape, not in a more elaborate ADR-style shape. The rules file's value *is* the scannability — content that overflows it belongs in arch doc or ADR.

---

## Outcome

8 commits on `worktree-be-code-arch-doc`, 0 broken existing artifacts:

```
afadbcd docs(plan): the reference codebase alignment §10 — verify 결과 + 11개 결정 inline 박제
3bad7d0 docs(adr): 0019 ORM containment + 0020 Unit of Work — coupled 결정
d6f4a78 docs(adr): 0021 ClockPort 통일 + 0022 Ports folder + file-per-feature
b1738a3 docs(adr): 0023 importlinter contract set + 0024 fakes with InMemoryDataset
87258c1 docs(architecture): ADR-0019~0024 반영 — ORM containment + UoW + ClockPort + ports folder + lint + fakes
06f0871 docs(rules): ADR-0019~0024 반영 + Kotlin parallel 보존 — fast-scan do/dont 형태
6e54f88 docs(plan): Phase 1 plan header에 known conflicts (e)~(k) 추가 — body 무손상
(this commit) docs(workflow): case-01 + alignment plan archive
```

Plus 1 cross-conversation memory artifact (`reference-codebase`) and 1 MEMORY.md index entry.

Phase 1 plan is now executable under the expanded conflict list (a)~(k). Arch doc + rules file reflect the the reference codebase alignment where adopted (ORM containment, UoW, ClockPort, Ports folder, importlinter, Fakes) and the intentional divergence where not (Pydantic placement, sum-type tag field). ADR-0018 is preserved with a divergence note. No Kotlin-specific decisions were taken; that work waits for Phase 1 Task 4.

Working alignment plan archived to `docs/plans/archive/2026-05-23-reference-codebase-alignment-plan.md` immediately after this case study was written.

---

**End of Case 01.**
