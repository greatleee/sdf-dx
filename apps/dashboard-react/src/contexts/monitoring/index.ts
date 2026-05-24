/**
 * Public API of the monitoring bounded context — the entry point UI and the composition root
 * import from. Internal layer modules are reached only through here (or `ports/*` for types),
 * enforced by `import/no-internal-modules`.
 */
export { useLineState } from "./application/use-line-state";
export type { UseLineStateResult } from "./application/use-line-state";
export { useLineOee } from "./application/use-line-oee";
export type { UseLineOeeResult } from "./application/use-line-oee";
export { useSelectedLineId, DEFAULT_LINE_ID } from "./application/selected-line";
export { MonitoringAdaptersProvider, useMonitoringAdapters } from "./application/adapters-context";
export { createMonitoringAdapters } from "./adapters/factory";
export type { MonitoringAdapters } from "./ports/monitoring-adapters";
export type { LineState, LineStateSnapshot } from "./domain/line-state";
export type { OeeReading, OeeWindow } from "./domain/oee";
