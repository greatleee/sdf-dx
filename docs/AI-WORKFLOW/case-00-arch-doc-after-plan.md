# Case 00 — Architecture conventions retroactively defined after the plan

| | |
|---|---|
| **Date** | 2026-05-23 |
| **Phase** | Pre-Phase 1 (design) |
| **Status** | Resolved |
| **Artifacts** | `docs/architecture/2026-05-23-code-architecture.md`, `docs/ADR/0004` / `0009` / `0016` / `0017` / `0018`, `docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md` (header-patched), `docs/SOT-LAYERS.md` (Engineering Conventions layer added) |

> This case study is a meta-incident: it documents the design process for the architecture itself, not a Phase-N implementation incident. Written immediately per `docs/SOT-LAYERS.md` AI-workflow rule.

---

## Incident

The Phase 1 implementation plan (`docs/plans/2026-05-22-phase-1-single-factory-vertical-slice.md`, ~5000 lines with full code samples) was written **before** code-level architecture conventions were nailed down. When the team (LLM + me) sat down to formalize the architecture doc, three categories of plan code samples turned out to violate the architecture rules we were defining:

1. Core functions used `raise X` for expected failures (e.g., `apply_event` raising `InvalidTransition`). The architecture doc settled on sum-type return values (ADR-0016).
2. Several places called `datetime.now(timezone.utc)` directly inside what would become the domain layer. The architecture doc forbade this (ADR-0017).
3. Spec §3.1 mentioned Pydantic for the ISA-95 model "표현력 강함," which read naturally as "use Pydantic in domain." The architecture doc constrained Pydantic to boundary use only (ADR-0018), aligned with cosmic-python.

`docs/SOT-LAYERS.md` §"What's scaffolding — disposable" explicitly forbids editing phase plans to reflect drifted code: *"Never updated to reflect drifted code — if reality diverged, write an ADR explaining why, leave the plan as a record of what we originally tried."* So the question wasn't "rewrite the plan" — it was "how do we make the plan executable when its body is wrong?"

---

## Sequence

1. User asked to write the backend architecture doc, framing it as: FC/IS main, DDD tactical pattern selectively, ports/events for BC, plus other workflow-specific items.
2. I pushed back lightly on the framing — FC/IS and DDD tactical sit at different layers (code structure vs modeling vocabulary). Suggested mapping-style framing instead. Accepted.
3. The discussion surfaced six concrete gaps not yet decided: cross-BC use-case location, error idiom, clock injection, `shared_kernel` boundary, DDD-term usage policy, and plan handling.
4. **Lazy-reasoning slip**: I recommended using Kafka for cross-BC domain events because the telemetry pipeline already used it. User pushed back: "Kafka 없이 할 수 있는 방법은 없나요?" The pushback forced surfacing the in-process `DomainEventDispatcher` alternative, which on inspection was the better choice (zero new infra, telemetry-vs-domain-event abstraction layers stay separated, debuggability, simpler test path).
5. After deliberate option comparison (`AskUserQuestion` with folder-shape and code previews), three decisions landed: top-level `use_cases/` for cross-BC queries (Option B), sum-type errors with no external lib, new "Engineering Conventions" SoT layer.
6. Two more open questions surfaced during the skeleton: dispatcher failure policy (decided fail-fast) and Pydantic placement. User pushed back on the boundary-only Pydantic recommendation — "Python에서 pydantic이 거의 표준과 같은지 확인이 필요" — forcing me to articulate the cosmic-python rationale and the conceptual-blur cost. Agreed after pushback.
7. ADRs 0004 / 0009 / 0016 / 0017 / 0018 + a `template.md` written at the time of decision. SOT-LAYERS rule honored: "incidents cannot be reconstructed later."
8. Phase 1 plan's **header only** patched with a forward-reference: "load arch doc before each task; on conflict, arch doc wins" + enumeration of the four known conflict types. Plan body untouched.

---

## Decisions ultimately made (frozen in ADRs)

| Decision | Source | ADR |
|---|---|---|
| FC/IS load-bearing rule (domain = zero IO + zero validation lib) | working notes B1 + arch doc §1 | 0004 |
| Cross-BC sync queries → top-level `use_cases/` | working notes B3, "Option B" | 0009 |
| Cross-BC state propagation → in-process `DomainEventDispatcher`, fail-fast | working notes + open question O3 | 0009 |
| No Kafka for domain events (Kafka stays telemetry-only) | conversation after lazy-reasoning slip | 0009 |
| Errors as sum-type values, no external lib (`arrow-kt` / `returns` forbidden) | working notes B6 | 0016 |
| Clock / UUID / random injected from shell | working notes B5 | 0017 |
| Pydantic at boundary only; domain uses stdlib `@dataclass(frozen=True, slots=True)` | open question O4 | 0018 |

---

## LLM judgment exercises

- **Pushback on user framing**: surfaced that "FC/IS vs DDD tactical, drop conflicting parts" was wrong-shaped framing — they sit at different layers. Suggested mapping-style instead.
- **Self-pushback (lazy reasoning)**: retracted "use Kafka because it's there" after user prompt. Recognized that convenient existing infrastructure is not a design argument.
- **Convention precedent check**: validated Pydantic-at-boundary against cosmic-python (the closest reference architecture for FC/IS-flavored Python) rather than defaulting to "Pydantic is the Python standard."
- **SOT-LAYERS layer gap**: noticed the architecture doc didn't fit any existing layer. Proposed and added "Engineering Conventions" as an 8th layer in SOT-LAYERS.md rather than smuggling the doc into ADR or Strategy.
- **Plan handling**: rejected the "rewrite the plan" path even though it was the most natural-sounding shape. Honored SOT-LAYERS §74 and used a forward-reference pattern instead. Trade-off: minor sub-agent overhead at execution time vs. preserving plan-as-snapshot and not investing in scaffold.
- **Term usage policy**: explicitly decided to drop "Aggregate," "Repository," "Domain Service," "Factory" as code-level vocabulary because each carries DDD-classical implications that conflict with FC/IS (mutable methods, infra-coupled abstraction, etc.). Replaced with concrete-name conventions (`<Noun>Reader`/`Writer`, `apply_<event>`).

---

## Guardrails — what fired, what didn't

| Guardrail | Result |
|---|---|
| SOT-LAYERS §74 (plans-never-updated) | ✅ fired and honored. Without this rule, the obvious move would have been rewriting ~5000 lines of scaffold for a disposable doc. |
| User-driven lazy-reasoning challenge | ✅ caught the Kafka misroute. (Not a tool — direct user pushback. Captured in memory `feedback_lazy_reasoning_audit.md` for next time.) |
| User-driven precedent challenge (Pydantic) | ✅ caught the under-articulated boundary recommendation. Forced cosmic-python citation. |
| `import-linter` / Konsist drift rules (spec §6) | ✅ already specified pre-existing. Arch doc's §9 extends with new contracts (Pydantic forbidden in domain, system-read forbidden in domain) without breaking the existing matrix. |
| Pre-execution use-case-location lint | ❌ no tool surfaced the cross-BC use-case gap before this conversation. Plan had `application/` inside each BC with no answer for multi-BC use cases. Caught by manually reading the plan. **Improvement candidate**: a pre-execution lint that scans a plan for "use case spanning multiple BCs" patterns. |

---

## Transferable patterns

1. **Forward-reference pattern for plans**: when an authoritative doc lands after a plan, patch the plan's *header* (not body) with a reference + known-conflict enumeration. Honors SOT-LAYERS while making sub-agents conflict-aware. Cheap (header diff) + reversible.
2. **New SoT layer over smuggling**: if a durable doc doesn't fit existing SoT layers, propose a new layer in SOT-LAYERS.md rather than mis-categorizing. Cost: one row in a table + one bullet in 4 sections. Protects layer semantics for future docs.
3. **Lazy-reasoning audit**: when "we already have X" is doing heavy lifting in a recommendation, enumerate no-X alternatives explicitly. Encoded as user-feedback memory.
4. **Cosmic-python as Python precedent**: for Python FC/IS-shaped projects, validate against *cosmic-python* (Percival & Gregory) before defaulting to "Python ecosystem standard." Pydantic-in-domain is the most common slippage; the book explicitly separates Pydantic boundary use from stdlib domain types.
5. **Decision-time ADR write**: ADRs written *immediately when decisions land*, not deferred to a Phase 1 ADR-writing task. Honors SOT-LAYERS "rationale rots within days."
6. **Working-notes-then-decide**: capture working notes *before* committing to substantive decisions when the conversation contains many threads. Disposable doc, then archive after the durable doc lands.

---

## Outcome

5 commits on `worktree-be-code-arch-doc`, 0 broken existing artifacts:

```
21ef099 docs(plan): Phase 1 plan에 arch doc forward reference 추가 — body 무손상
d8b9458 docs(adr): 0004 / 0009 / 0016 / 0017 / 0018 + template — 결정 시점에 frozen snapshot
d52a7dc docs(architecture): code architecture body — §1~§9 채움
9617d26 docs(architecture): code architecture doc skeleton + 사전 논의 working notes
62a0098 docs(sot-layers): "Engineering Conventions" layer 추가
```

Phase 1 plan is now executable under known constraints; sub-agents will read the arch doc at task start and apply rules where the plan's code samples conflict. No spec / existing-ADR / AI-WORKFLOW supersession was needed — the existing artifacts remained valid; new artifacts filled gaps the originals didn't cover.

Working notes (`docs/plans/2026-05-23-arch-doc-discussion-notes.md`) archived to `docs/plans/archive/` after this case study was written.

---

**End of Case 00.**
