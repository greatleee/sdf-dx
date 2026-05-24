import type { LineStateSnapshot } from "../domain/line-state";
import type { OeeReading } from "../domain/oee";
import type { LineStateFeed, LineStateFeedHandlers } from "../ports/line-state-feed";
import type { LineStateReader } from "../ports/line-state-reader";
import type { MonitoringAdapters } from "../ports/monitoring-adapters";
import type { OeeReader } from "../ports/oee-reader";

const DEFAULT_STATE: LineStateSnapshot = {
  lineId: "00000000-0000-0000-0000-000000000000",
  state: "RUNNING",
  since: "2026-05-22T00:00:00Z",
};

const DEFAULT_OEE: OeeReading = {
  lineId: "00000000-0000-0000-0000-000000000000",
  window: "5m",
  oee: 0.8,
  availability: 0.9,
  performance: 0.95,
  quality: 0.93,
  observedAt: "2026-05-22T00:00:00Z",
};

/** In-memory reader returning seeded values; no IO. Satisfies both read ports. */
class FakeMonitoringReader implements LineStateReader, OeeReader {
  constructor(
    private readonly state: LineStateSnapshot,
    private readonly oee: OeeReading,
  ) {}

  readLineState(): Promise<LineStateSnapshot> {
    return Promise.resolve(this.state);
  }

  readOee(): Promise<OeeReading> {
    return Promise.resolve(this.oee);
  }
}

/** Controllable in-memory feed: a test drives open/close/emit; production never constructs it. */
export class FakeLineStateFeed implements LineStateFeed {
  private handlers: LineStateFeedHandlers | null = null;

  subscribe(handlers: LineStateFeedHandlers): () => void {
    this.handlers = handlers;
    return () => {
      this.handlers = null;
    };
  }

  open(): void {
    this.handlers?.onOpen?.();
  }

  close(): void {
    this.handlers?.onClose?.();
  }

  emit(snapshot: LineStateSnapshot): void {
    this.handlers?.onSnapshot(snapshot);
  }
}

export interface FakeMonitoringAdapters extends MonitoringAdapters {
  feed: FakeLineStateFeed;
}

/** A working in-memory MonitoringAdapters for application-layer tests (fakes, not mocks, §9). */
export function createFakeMonitoringAdapters(seed?: {
  state?: LineStateSnapshot;
  oee?: OeeReading;
}): FakeMonitoringAdapters {
  const feed = new FakeLineStateFeed();
  const reader = new FakeMonitoringReader(seed?.state ?? DEFAULT_STATE, seed?.oee ?? DEFAULT_OEE);
  return { lineStateReader: reader, oeeReader: reader, lineStateFeed: feed, feed };
}
