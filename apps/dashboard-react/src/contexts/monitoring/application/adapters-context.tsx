import { createContext, useContext } from "react";
import type { ReactElement, ReactNode } from "react";

import type { MonitoringAdapters } from "../ports/monitoring-adapters";

/**
 * Dependency-injection seam for the monitoring ports. The composition root (`src/app` /
 * `main.tsx`) wires the real adapters; tests wire in-memory fakes. Application hooks read the
 * adapters from here, so they never import an adapter directly (§1/§4).
 */
const MonitoringAdaptersContext = createContext<MonitoringAdapters | null>(null);

export function MonitoringAdaptersProvider({
  adapters,
  children,
}: {
  adapters: MonitoringAdapters;
  children: ReactNode;
}): ReactElement {
  return (
    <MonitoringAdaptersContext.Provider value={adapters}>
      {children}
    </MonitoringAdaptersContext.Provider>
  );
}

export function useMonitoringAdapters(): MonitoringAdapters {
  const adapters = useContext(MonitoringAdaptersContext);
  if (adapters === null) {
    throw new Error("useMonitoringAdapters must be used within a <MonitoringAdaptersProvider>");
  }
  return adapters;
}
