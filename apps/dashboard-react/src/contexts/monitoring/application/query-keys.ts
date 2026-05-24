import type { OeeWindow } from "../domain/oee";

/**
 * Query keys for the monitoring bounded context, declared once and referenced by both reads
 * and the WebSocket cache writes (§4). `lineState` is the key the REST snapshot seeds and the
 * live feed overwrites via `setQueryData` (ADR-0029).
 */
export const monitoringKeys = {
  lineState: (lineId: string) => ["monitoring", "lineState", lineId] as const,
  lineOee: (lineId: string, window: OeeWindow) =>
    ["monitoring", "lineOee", lineId, window] as const,
};
