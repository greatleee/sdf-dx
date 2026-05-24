import type { zLineStateSnapshot, zOeeReading } from "@sdf/contracts/zod";

import type { LineStateSnapshot } from "../domain/line-state";
import type { OeeReading } from "../domain/oee";

/** Boundary shapes = the output of the generated Zod schemas (ADR-0028). Adapters parse the
 *  wire into these, then map to the domain types below. Kept separate from the domain (§3). */
type WireLineStateSnapshot = ReturnType<typeof zLineStateSnapshot.parse>;
type WireOeeReading = ReturnType<typeof zOeeReading.parse>;

/**
 * Map a boundary-parsed Line-state frame to the frontend domain type.
 *
 * The wire and domain shapes coincide today (the OpenAPI contract is already camelCase), but
 * the mapper still exists and is the single seam: it keeps the domain type independent of the
 * wire, so a future contract rename changes only this function (§3).
 */
export function lineStateSnapshotFromWire(wire: WireLineStateSnapshot): LineStateSnapshot {
  return { lineId: wire.lineId, state: wire.state, since: wire.since };
}

/** Map a boundary-parsed OEE reading to the frontend domain type. */
export function oeeReadingFromWire(wire: WireOeeReading): OeeReading {
  return {
    lineId: wire.lineId,
    window: wire.window,
    oee: wire.oee,
    availability: wire.availability,
    performance: wire.performance,
    quality: wire.quality,
    observedAt: wire.observedAt,
  };
}
