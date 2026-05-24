import type { LineStateFeed } from "./line-state-feed";
import type { LineStateReader } from "./line-state-reader";
import type { OeeReader } from "./oee-reader";

/**
 * The set of monitoring ports the application layer depends on. The composition root supplies
 * an implementation — real HTTP/WebSocket adapters in production, in-memory fakes in tests —
 * through the adapters provider (§1/§4). Lives in `ports/` (not `application/`) so the adapter
 * factory can name it without importing upward into `application/`.
 */
export interface MonitoringAdapters {
  lineStateReader: LineStateReader;
  oeeReader: OeeReader;
  lineStateFeed: LineStateFeed;
}
