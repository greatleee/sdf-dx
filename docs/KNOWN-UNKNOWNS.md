# Known Unknowns

This document is a working acknowledgement of what this portfolio **does not** claim to model accurately. We choose "domain reliability level B — standards alignment" and explicitly disclaim "level C — operational realism" (see design spec §1.3).

## Operational realism deliberately unmodeled
- Shift handover data consistency — assumed, not validated against any real plant.
- PLC-vendor-specific OPC UA quirks — simulator abstracts them.
- ICS network segmentation (Purdue model) — single docker network in Phase 1.
- Hot patch / maintenance window policy in 24/7 environments — out of scope.
- Multi-region data sovereignty (GDPR, India DPDP) — migration path only (§14 of spec).

## Intentionally unresolved (migration paths declared)
- TimescaleDB Continuous Aggregate × RLS incompatibility (Timescale issue #5787) — not relevant in Phase 1 (no RLS); flagged for Phase 2 schema-per-tenant decision (ADR-0003).
- Kafka exactly-once semantics — at-least-once + idempotent consumer is sufficient (ADR-0005 reasoning).
- 100+ tenant scaling — Phase 2 ends at 3 tenants by design; migration path to Citus/RLS in ADR-0003.

## Phase 1 limitations to be addressed later
- OEE Availability assumes bucket == planned-busy-time (Phase 3 introduces shift schedules).
- Only 5-minute OEE continuous aggregate is implemented (1h and shift in Phase 3).
- Single implicit tenant — multi-tenancy is Phase 2.
- No authn/authz — JWT lands in Phase 2.
- DLQ topic (`dlq.{tenant}`) not yet implemented — invalid records are logged and dropped (see ingest in Task 18). To be added before Phase 2.
