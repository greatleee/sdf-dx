import type { OeeReading, OeeWindow } from "../domain/oee";

/**
 * Reads an OEE reading for a Line over a window.
 *
 * A port (§1); the HTTP adapter implements it. A transport failure rejects the promise (§6).
 */
export interface OeeReader {
  readOee(lineId: string, window: OeeWindow): Promise<OeeReading>;
}
