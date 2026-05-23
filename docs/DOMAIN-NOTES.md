# Domain Absorption Notes

Working notes from absorbing the manufacturing domain via standards docs + vendor manuals. Each section cites a primary source.

## ISA-95 — Enterprise/Control integration
- Five-level model (L0 physical → L4 ERP). This portfolio operates L0–L2 (sensors, control, MES-edge).
- Equipment hierarchy: Enterprise → Site → Area → Work Center → Work Unit. We model Factory → Line → Machine.
- Source: [ISA-95.00.01-2010, ANSI/ISA — Enterprise-Control System Integration](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa95).

## ISO 22400 — KPI definitions
- OEE = Availability × Performance × Quality.
- Availability = APT / PBT (Actual Production Time / Planned Busy Time).
- Performance = (Ideal Cycle Time × Produced Quantity) / APT.
- Quality = Good Quantity / Produced Quantity.
- All components ∈ [0, 1]; OEE inherits that range.
- Source: [ISO 22400-2:2014](https://www.iso.org/standard/56847.html).

## Sparkplug B — payload + topic spec
- Topic: `spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]`.
- Message types: NBIRTH, NDATA, NDEATH (node); DBIRTH, DDATA, DDEATH (device); NCMD, DCMD (commands); STATE (host).
- Sequence number rolls 0..255; gap detection prompts rebirth.
- Source: [Sparkplug Specification v3.0, Eclipse Foundation](https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification-3.0.0.pdf).

## OPC UA Companion Specifications
- Phase 4 candidate: OPC UA for Machinery (DI base + extensions).
- Source: [OPC Foundation — Companion Specifications](https://opcfoundation.org/developer-tools/documents).
