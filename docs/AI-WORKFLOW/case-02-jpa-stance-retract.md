# Case 02 — JPA-stance retract: living arch doc drift detected via user pushback

| | |
|---|---|
| **Date** | 2026-05-30 |
| **Phase** | Phase 2 (Plan A in-flight; this case touches living docs only, no code change) |
| **Status** | Resolved |
| **Artifacts** | `docs/architecture/2026-05-23-code-architecture.md` §8.1 (in-place edit — Kotlin row rewritten from hard "no JPA" exclusion to deferred decision with JPA as working preference); `.claude/rules/backend-code-architecture.md` §6 DO (Kotlin line aligned with deferral); this case study. ADRs unchanged. |

> Second instance of the case-01 "Over-strict conventions corrected" pattern. The trigger was a user question ("ADR과 현 코드베이스 분석") that exposed two layered drifts in the living arch doc: (a) a Kotlin "no JPA — pollutes core / lazy-loading violates purity" rationale that should have been retracted when ADR-0019 relaxed the SQLAlchemy ban via containment, and (b) the fact that the Kotlin persistence stance was never ADR-frozen at all — case-01 §결정표 row 9 had explicitly deferred it. User's pushback closed both: "JPA도 adapter 안에서만 쓰니까 기능 활용 OK / UoW 안 쓰면 됨 / JPA가 사실상 업계 표준."

---

## Incident

Two distinct things tangled together:

1. **Living arch doc drifted from case-01's deferral.** case-01 §결정표 row 9 deferred all Kotlin persistence ADR work to "Phase 1 Task 4 (Kotlin gateway setup) when actual Kotlin code lands." But `docs/architecture/2026-05-23-code-architecture.md` §8.1 carried a *hard* Kotlin persistence stance — "no JPA (`@Entity`, `@Id` on domain types pollutes core; lazy-loading and change-tracking violate purity)" + "Allowed at adapters (Kotlin): Exposed or JOOQ." That stance was never ADR-frozen; it lived only in the living arch doc, inherited from pre-case-01 drafts. From an external read it looked like a frozen decision; from the case-01 audit trail it was a deferred decision dressed up as one.

2. **Inconsistent containment standard between Python and Kotlin.** ADR-0019 relaxed the original "ORM blanket ban at adapter" for Python by introducing the SQLAlchemy `_Order` containment pattern (private declarative classes, public surface returns domain types). The arch doc kept "no JPA pollutes core" for Kotlin without applying the same containment lens — even though `@Entity` on an adapter-internal `_LineEntity` (private, returns domain types only) is *type-symmetric* to `_Order`. The asymmetry was unexamined.

LLM (me) initial response to the user's first question reproduced this drift uncritically — relayed "Kotlin = Exposed/JOOQ, JPA forbidden" as established fact, citing arch doc L522 as authority without checking whether case-01 actually decided it or just inherited it from case-00.

User's pushback rounds:

- **Round 1 (premise check).** User recalled prior discussion about "ORM/JPA breaks domain isolation as too extreme." LLM read case-01 + ADR-0019, confirmed user's recollection (the original "Core/raw only" position was indeed relaxed for SQLAlchemy via ADR-0019), but still hedged on JPA — argued "JPA stays excluded but on different grounds (UoW conflict)" without checking whether Kotlin UoW was even decided yet.
- **Round 2 (JPA-specific).** User pushed three arguments: (a) adapter-only containment makes JPA's machinery harmless, (b) Kotlin can skip UoW since ADR-0020 is Python-only, (c) JPA is JVM industry standard. LLM evaluated each and conceded:
  - Containment argument — technically symmetric to `_Order`. The "JPA defaults are implicit" cost is real but addressable via Konsist rules.
  - UoW skip argument — ADR-0020 is Python-only. Kotlin UoW is undecided. "Skip UoW for Kotlin" isn't a divergence; it's just not deciding yet.
  - Industry-standard argument — true for JVM/Spring. For target viewer (현대차그룹 SDF, Korean Spring enterprise) JPA-on-FC/IS is a stronger portfolio signal than divergent Exposed/JOOQ.
- **Crucial meta-finding surfaced during Round 2 prep, not earlier.** The JPA exclusion is not in any ADR. case-01 §결정표 row 9 already said "deferred." Arch doc text was the only source. Reframed the question from "should we re-open a frozen decision?" to "should we have the arch doc honestly reflect a deferred decision?" — option set changed.

---

## Sequence

1. **User message 1** ("Python sqlalchemy, Kotlin JPA로 결정했는데 코드는 raw SQL"). LLM dispatched 3 parallel `Explore` agents (ADR doc / Python code / Kotlin code). Synthesis: claim partly wrong (Kotlin = Exposed/JOOQ per arch doc, not JPA; Phase 1 Kotlin has no DB at all), partly right (Python uses raw asyncpg, but it's a permitted choice per ADR-0019, not drift). Surfaced as critical correction. **Missed the deeper layer**: did not check whether the "Kotlin = Exposed/JOOQ" claim itself was ADR-backed.
2. **User message 2** ("이전에도 sqlalchemy랑 jpa 도메인 격리 안 된다 그랬다, 너무 극단적이라 논의했었다"). LLM read roadmap (all 3 docs) + case-01 in full + ADR-0019 Context + ADR-0018, confirmed: yes, ADR-0019 IS the record of that discussion, the "Core/raw only" first-pass position was relaxed to "ORM allowed in adapter under containment." Surfaced asymmetric treatment (SQLAlchemy relaxed, JPA not) but still defended the JPA exclusion on UoW-conflict grounds — a soft hedge, not a flip.
3. **User message 3** ("JPA도 adapter 안에서만 쓰니까 기능 OK, UoW 안 쓰면 됨, JPA 업계 표준"). LLM evaluated each argument as above, surfaced the meta-finding (JPA exclusion not ADR-frozen, case-01 deferred Kotlin scope), reframed as 3 options (soften arch doc / new ADR now / leave until code), recommended (a) — soften arch doc + rules file, defer ADR.
4. **User chose (a)** + asked for add-on case file.
5. LLM read arch doc §8.1 + rules file §6 directly, drafted exact before/after for both files, presented for one-turn confirmation per its own mid-stream commitment ("edit 들어가기 전에 정확한 문구를 한 turn 더 합의").
6. **User approved.** Edits applied as single commit (`93f7255`); this case study committed as second commit.

---

## Decisions ultimately made

| Decision | Where | Source |
|---|---|---|
| Kotlin adapter persistence: TBD, ADR at Phase 2 W1~W2 Kotlin BC code time | arch doc §8.1 (rewritten) + rules §6 DO Kotlin line | case-01 §결정표 row 9 (deferral re-honored) |
| JPA candidate under containment, marked current working preference | arch doc §8.1 + rules §6 DO | user Round 2 argument + ADR-0019 symmetry |
| "no JPA pollutes core / lazy-loading violates purity" framing retracted from arch doc | arch doc §8.1 (visible "retracted" word) | user Round 2 argument; case-01 transferable #5 "intentional divergence documented in body" pattern |
| `JPA @Entity/@Id on domain types` ban retained in rules §6 DON'T | unchanged | uncontested (domain leak vs. adapter use is the distinction) |
| No new ADR yet | — | case-01 transferable #6 "per-language scope honest" (no Kotlin DB code in repo) |

---

## LLM judgment exercises

- **Round 1 missed the deeper "is this ADR-backed?" question.** LLM checked "what do the ADRs say" but didn't check "is what the arch doc says actually ADR-backed." Result: relayed the arch doc text as if frozen, when it was actually a deferred-decision text that drifted. The case-01 §guardrails ❌ "Pre-execution check that arch doc was already over-strict" item literally predicted this failure mode; LLM did not query it.
- **Round 2 hedge before concede.** When user pushed JPA, LLM's first response defended the exclusion on "UoW conflict" grounds — without checking whether Kotlin UoW was even decided. The defense was structurally similar to the first-pass over-strict position case-01 corrected. Required a second push from user to dislodge.
- **Concession came from evidence-flip, not push-fatigue.** Two specific findings flipped the position: (1) Kotlin UoW is undecided per ADR-0020 scope, (2) JPA exclusion is in arch doc only, not ADR. Both are checkable facts. The "JPA breaks isolation" argument failed the containment-symmetry test once SQLAlchemy precedent was applied consistently.
- **Pre-edit confirmation honored.** LLM committed mid-stream to "edit 들어가기 전에 정확한 문구를 한 turn 더 합의." Surfaced exact before/after diff for both files before touching them.
- **Portfolio framing surfaced as decision input.** Re-weighted the JPA choice through `project_onepager_framing` + `project_viewer_attention_model` memories — "industry-standard tool + visible discipline" reads stronger to target viewer than divergent Exposed/JOOQ. The architectural argument and the portfolio argument converged on the same answer; the portfolio angle would have been *decisive* if they had diverged.
- **Living-doc vs ADR-immutability distinction honored.** Edits went in-place on arch doc + rules (both living per case-01 §6 + memory `feedback_rules_file_dodont_only`). No ADR edited. New Kotlin persistence ADR deferred to first-Kotlin-BC-code time (case-01 transferable #6 "per-language scope honest").

---

## Guardrails — what fired, what didn't

| Guardrail | Result |
|---|---|
| Project memory `feedback_lazy_reasoning_audit` ("이미 있는 인프라/아티팩트 쓰자" → 멈춤) | ❌ did not fire round-1. LLM relayed arch doc as authoritative without auditing whether the arch doc text was itself ADR-backed. case-01 had already flagged this exact failure mode. |
| Project memory `feedback_deliberate_discussion` (option comparison via table/preview) | ✅ fired Round 2 ending. 3-option table (soften / new ADR / leave) surfaced before asking for choice. |
| Project memory `project_doc_immutability` (전략/ADR/AI-WORKFLOW supersede-only) | ✅ fired. arch doc + rules are explicitly living (case-01 §6); ADR not touched; new Kotlin ADR deferred to code-with-decision time. |
| Project memory `project_onepager_framing` + `project_viewer_attention_model` (portfolio reweighting) | ✅ fired during JPA-vs-Exposed reasoning. The "익숙한 스택 + visible 규율" argument came from these memories and was decisive in characterizing the trade-off. |
| User's CLAUDE.md "user is often wrong, suspiciously pleased to be corrected" | ✅ partial — LLM did correct the user's "Kotlin = JPA decided" premise round 1. ❌ failed to apply the same skepticism to its own claim ("Kotlin = Exposed/JOOQ") which was itself an unchecked relay of drifted arch doc text. |
| case-01 §guardrails ❌ "reference-impl drift check" improvement candidate | ❌ still missing. Same failure recurred 5+ days later. No automated check yet. |
| Pre-edit "한 turn 더 합의" mid-stream commitment | ✅ honored. Before/after diff surfaced before any edit. |

---

## Transferable patterns

1. **"Is this ADR-backed?" check before relaying arch doc text as authority.** When citing the living arch doc, query: was this paragraph *decided* via ADR, or did it inherit from an earlier draft and quietly survive? Anything in arch doc that conflicts with a case-01 결정표 "deferred" row is suspect. Concretely: when arch doc and case decision-rows touch the same topic, the case row wins on whether the decision exists; arch doc loses if it has more than the case row decided.
2. **Apply consistency tests to own claims, not just user claims.** When a rule applies to library X but is dropped for library Y on the same grounds, check whether Y's reasons survive applying X's relaxation pattern. Here: SQLAlchemy ORM containment relaxed → does JPA containment relaxation follow by the same logic? Yes. Inconsistency is the smell.
3. **Concede via evidence-flip, not via push-fatigue.** When user pushes back, the decision to flip should be tied to specific new facts (Kotlin UoW undecided, JPA exclusion not in ADR), not to "user disagreed multiple times." If push-fatigue is the only driver, hold the position and explain why. The honest version of "you're right" cites the fact that flipped it.
4. **Portfolio-reweighting as a first-class decision input.** For this codebase the viewer is concrete (Korean Spring enterprise, code-and-git-log reader per `project_viewer_attention_model`). When two architectural choices are technically close, viewer-recognition is decisive. Bake into reasoning surface, not afterthought paragraph.
5. **"Retract" word in living-doc edits.** When reversing a stance in a living doc (vs. supersede-only ADR), keep the retraction visible in the new text so future-me / future-AI traces the reversal instead of re-litigating. Symmetric to case-01 transferable #5 ("Intentional divergence documented in the ADR body") but for living docs: the retraction is the body annotation.
6. **Deferral re-honored, not first-stated.** When the deferral was already case-01 decision-table material and the arch doc drifted off it, the edit's job is to *re-honor* the deferral, not to *introduce* it. Frame edit commit message accordingly so the audit trail is "drift corrected" not "new deferral."

---

## Outcome

2 commits on `worktree-outside-2`:

```
93f7255 docs(architecture): Kotlin persistence — retract "JPA pollutes core" framing, defer choice to Phase 2 W1~W2 ADR
<this commit> docs(workflow): case-02 — JPA-stance retract via user pushback (second instance of case-01 over-strict pattern)
```

0 code files affected (Phase 1 Kotlin has no DB persistence). 0 ADRs touched. arch doc §8.1 + rules §6 DO Kotlin line in-place edited. New Kotlin persistence ADR scheduled for Phase 2 W1~W2 with first-Kotlin-BC code.

The case-01 ❌ guardrail "Pre-execution check that arch doc was already over-strict" remains unsatisfied — this case is its second instance. **Improvement candidate (carried forward)**: a session-start or rule-edit hook that compares living arch doc claims against case-01/case-02 decision-row "deferred" statuses and flags drift. Until that exists, transferable pattern #1 ("Is this ADR-backed?") is the manual mitigation.

---

**End of Case 02.**
