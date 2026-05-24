import type { MonitoringAdapters } from "../ports/monitoring-adapters";
import { HttpMonitoringReader } from "./http-monitoring-reader";
import { WebSocketLineStateReader } from "./websocket-line-state-reader";

/**
 * Wire the real (HTTP + WebSocket) monitoring adapters. The composition root calls this for
 * production/dev; tests inject in-memory fakes instead (see `testing/fakes.ts`). A single
 * `HttpMonitoringReader` satisfies both read ports.
 */
export function createMonitoringAdapters(): MonitoringAdapters {
  const httpReader = new HttpMonitoringReader();
  return {
    lineStateReader: httpReader,
    oeeReader: httpReader,
    lineStateFeed: new WebSocketLineStateReader(),
  };
}
