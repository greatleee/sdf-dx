/**
 * Monitoring domain — OEE (Overall Equipment Effectiveness) types.
 *
 * Pure TypeScript (§2/§3). OEE = Availability × Performance × Quality (ISO 22400-2 §6,
 * GLOSSARY). The factors are nominally [0, 1]; `performance` can exceed 1 when the ideal
 * cycle time is set loose, so `oee` is only nominally bounded (see `docs/KNOWN-UNKNOWNS.md`).
 * OEE is computed on the backend; the dashboard only reads and renders it.
 */

/** OEE aggregation window over which the reading is computed. */
export type OeeWindow = "5m" | "1h" | "shift";

/** An OEE reading for a Line over a window, tagged with the instant it was observed. */
export interface OeeReading {
  lineId: string;
  window: OeeWindow;
  oee: number;
  availability: number;
  performance: number;
  quality: number;
  observedAt: string;
}
