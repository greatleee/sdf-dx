# ADR-0026: OEE per ISO 22400-2:2014 §6 — clause-citation correction (supersedes ADR-0012)

- **Status:** accepted
- **Date:** 2026-05-24
- **Phase:** 1
- **Supersedes:** ADR-0012

## Context

[ADR-0012](0012-oee-iso22400.md) fixed the OEE decision for the monitoring BC: OEE = Availability × Performance × Quality per ISO 22400-2:2014, with the Phase-1 simplifications (Availability ≈ 1.0, single 5-minute CAGG) and errors-as-values for degenerate inputs. Those formulas and decisions are sound and are carried forward here unchanged.

ADR-0012 carries one factual error: it cites **ISO 22400-2:2014 §5** as the clause that "defines OEE and its three component KPIs" (4 occurrences). That clause pointer is wrong. It matters because ADR-0012's own stated value is that "an interview reader can check the formula against the standard" — a citation that points at the wrong clause defeats exactly that property. ADR-0012 is also internally inconsistent: it states its formulas are kept "identical to the GLOSSARY," yet the GLOSSARY (`monitoring` → *OEE* / *A·P·Q*) and `DOMAIN-NOTES` both cite §6.

The discrepancy surfaced during Section D (domain functional core) implementation and was externally verified against the **published standard's Contents page** (see Sources):

- **Clause 5 — "Elements used in KPI description"** (pp. 5–11): the input time/quantity *elements* (time models for work units / production order / personnel; logistical and quality elements). These are the variables that populate KPI formulas — not the formulas themselves.
- **Clause 6 — "Description of KPIs"** (pp. 12–36): the KPI catalogue, including OEE and its Availability / Performance (Effectiveness) / Quality components, each with its formula expressed in clause-5 elements. **This is where OEE = A × P × Q is defined.**
- **Annex B (informative)**: an *alternative* loss-time-model OEE calculation (Nakajima-style). Our model uses the clause-6 normative A×P×Q form, not Annex B.

Per the project's supersede-only doc policy (an ADR is not edited in place beyond a status pointer), the correction lands as this superseding ADR rather than an in-place edit of ADR-0012.

## Decision

OEE follows **ISO 22400-2:2014 §6 ("Description of KPIs")** — the corrected clause. Every substantive decision of ADR-0012 is carried forward verbatim:

- **D-1.** `OEE = Availability × Performance × Quality`, with components defined exactly as in §6 and the GLOSSARY: `Availability = APT / PBT`; `Performance` (ISO *Effectiveness*) `= (Ideal Cycle Time × Produced Quantity) / APT`; `Quality = Good Quantity / Produced Quantity`. Availability and Quality ∈ [0, 1] by construction; Performance can exceed 1 when the ideal cycle time is loose, so OEE is only *nominally* [0, 1] (`KNOWN-UNKNOWNS.md`).
- **D-2.** Phase-1 simplification — the 5-minute continuous-aggregate bucket is treated as Planned Busy Time, with Actual Production Time approximated as the full bucket, so **Availability ≈ 1.0**. Logged in `KNOWN-UNKNOWNS.md`; retired in Phase 3.
- **D-3.** Only the 5-minute CAGG (`line_oee_5m`) exists in Phase 1; the 1-hour and shift-length windows are Phase 3.
- **D-4.** OEE is a pure domain function returning failures as values (ADR-0016): zero Produced Quantity / zero APT / zero PBT return a named `OeeUndefined` case rather than raising; corrupt inputs that violate by-construction preconditions (negative counts/times, good > produced, APT > PBT, non-finite floats) raise.

The **only change from ADR-0012 is the clause citation (§5 → §6)** plus the verification source recorded below. No formula, threshold, or runtime behavior changes. The implementation (`apps/api-python/src/sdf_api/contexts/monitoring/domain/oee.py`), the GLOSSARY, and `DOMAIN-NOTES` already cite §6 and need no change.

## Consequences

### Positive
- The citable anchor now points at the correct clause — the "verifiable against the standard" property ADR-0012 sought is actually true.
- ADR / GLOSSARY / DOMAIN-NOTES / code are consistent on §6.
- Decision history is preserved: ADR-0012 remains readable with a status pointer; the correction and its evidence are explicit and append-only.

### Negative / Trade-offs
- A full ADR for a one-clause citation fix is heavyweight; chosen over an in-place erratum to honor the supersede-only doc policy and keep the decision log append-only.
- Two ADRs now describe one decision (0012 superseded, 0026 active); a reader must follow the pointer.

## Migration Path
None for code (already §6). A new edition of ISO 22400-2 is in draft as of 2026-05; if its clause numbering changes again, supersede this ADR with the new edition's clause.

## Sources
- ISO 22400-2:2014, *Contents* — clause 5 "Elements used in KPI description", clause 6 "Description of KPIs", Annex B (informative) "Alternative OEE calculation based on loss time model". Published 1st edition, 2014-01-15. Verified from the official preview sample: https://standards.iteh.ai/catalog/standards/sist/8a9efc01-6c74-42a2-ad8f-ec19e84b48f0/iso-22400-2-2014
- ISO catalogue entry for ISO 22400-2:2014 — https://www.iso.org/standard/54497.html
- Internal: supersedes [ADR-0012](0012-oee-iso22400.md); related [ADR-0004](0004-functional-core-imperative-shell.md), [ADR-0016](0016-error-as-value.md); `docs/spec/GLOSSARY.md` (`monitoring` → *OEE* / *A·P·Q*), `docs/DOMAIN-NOTES.md` (§"ISO 22400 — KPI definitions"), `docs/KNOWN-UNKNOWNS.md`.
