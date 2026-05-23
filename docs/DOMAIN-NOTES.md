# Domain Absorption Notes

Working notes from absorbing the manufacturing domain via standards docs + vendor manuals. Each section cites a primary source.

## ISA-95 — Enterprise/Control integration
- Two **orthogonal** models — don't conflate them:
  - (a) *Functional levels*: L0 physical → L1 sensing/actuation → L2 supervisory control → L3 MES/MOM → L4 ERP. This portfolio operates at **L0–L2** (sensors, control, edge aggregation). Note **MES is L3**, above our scope — so we say "edge", not "MES-edge".
  - (b) *Role-based equipment hierarchy* (a separate axis from the levels): Enterprise → Site → Area → Work Center → Work Unit. We model Factory → Line → Machine onto Site → Production Line (a Work Center sub-type) → Work Unit.
- Simplification: Work Center / Work Unit are role-groupings; ISA-95 also defines concrete sub-types (Process Cell / Production Line / Production Unit / Work Cell) and lower engineered levels (Equipment Module / Control Module). Our 3-tier model is a deliberate teaching-level slice.
- Source: [ANSI/ISA-95.00.01-2010 (IEC 62264-1 Mod) — Enterprise-Control System Integration, Part 1: Models and Terminology](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa95). (A 2025 edition now exists; 2010 is the edition modeled here.)

## ISO 22400 — KPI definitions
- OEE = Availability × Performance × Quality. ISO 22400-2's normative names are Availability × *Effectiveness* × *Quality ratio*; we keep the Nakajima/TPM names *Performance* / *Quality* (aliases).
- Availability = APT / PBT (Actual Production Time / Planned Busy Time).
- Performance = (Ideal Cycle Time × Produced Quantity) / APT. (ISO term for "Ideal Cycle Time" is *planned run time per item, PRI*.)
- Quality = Good Quantity / Produced Quantity. (ISO *Quality ratio*; Good Quantity excludes rework.)
- Availability and Quality ∈ [0, 1] by construction; **Performance can exceed 1** if the ideal cycle time is set loose, so OEE is only nominally bounded — see `KNOWN-UNKNOWNS.md`.
- Source: [ISO 22400-2:2014, §6 "Description of KPIs"](https://www.iso.org/standard/56847.html). (KPI definitions live in clause 6; clause 5 is the input *elements*. 2014 is the current edition — a revision is only at draft (ISO/DIS 22400-2) as of 2026-05.)

## Sparkplug B — payload + topic spec
- Topic: `spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]` ("spBv1.0" stays literal even at spec v3.0 — it versions the payload encoding, not the spec).
- Message types: NBIRTH, NDATA, NDEATH (node); DBIRTH, DDATA, DDEATH (device); NCMD, DCMD (commands); STATE (host online/offline — a single message with a boolean field, not separate birth/death types).
- `seq` rolls 0..255 per message, **reset to 0 by each NBIRTH**; gap detection prompts rebirth (NCMD `Node Control/Rebirth`). Distinct from `bdSeq` (per-session birth/death counter).
- Source: [Sparkplug Specification v3.0, Eclipse Foundation](https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification-3.0.0.pdf).

## OPC UA Companion Specifications
- Phase 4 candidate: OPC UA for Machinery (OPC 40001-1, "Machinery Basic Building Blocks"). Downstream machinery specs normatively reference both OPC 40001-1 and OPC UA DI (OPC 10000-100) in parallel — better described as building *on* OPC 40001-1 + DI than as a pure "DI extension".
- Source: [OPC Foundation — OPC UA for Machinery](https://opcfoundation.org/markets-collaboration/opc-ua-for-machinery/).
