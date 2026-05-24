import { zLineStateSnapshot, zOeeReading } from "@sdf/contracts/zod";

import type { LineStateSnapshot } from "../domain/line-state";
import type { OeeReading, OeeWindow } from "../domain/oee";
import type { LineStateReader } from "../ports/line-state-reader";
import type { OeeReader } from "../ports/oee-reader";
import { lineStateSnapshotFromWire, oeeReadingFromWire } from "./mappers";

/**
 * REST adapter for the monitoring read API (`HttpMonitoringReader`, role-prefixed per §8).
 *
 * Every response is parsed through the generated Zod (the boundary schema, ADR-0028) and
 * mapped to a domain type — never cast (§3). A non-2xx status or a parse failure is a
 * *transport* failure and throws (§6); TanStack Query turns it into `error` + retry.
 *
 * `baseUrl` defaults to "" so the browser resolves paths against the page origin (Vite proxies
 * `/api` to the API in dev); tests pass an absolute origin so Node's fetch can build the URL.
 */
export class HttpMonitoringReader implements LineStateReader, OeeReader {
  constructor(private readonly baseUrl: string = "") {}

  async readLineState(lineId: string): Promise<LineStateSnapshot> {
    const res = await fetch(`${this.baseUrl}/api/v1/lines/${encodeURIComponent(lineId)}/state`);
    if (!res.ok) throw new Error(`GET line state failed: HTTP ${String(res.status)}`);
    return lineStateSnapshotFromWire(zLineStateSnapshot.parse(await res.json()));
  }

  async readOee(lineId: string, window: OeeWindow): Promise<OeeReading> {
    const path = `/api/v1/lines/${encodeURIComponent(lineId)}/oee?window=${window}`;
    const res = await fetch(`${this.baseUrl}${path}`);
    if (!res.ok) throw new Error(`GET oee failed: HTTP ${String(res.status)}`);
    return oeeReadingFromWire(zOeeReading.parse(await res.json()));
  }
}
