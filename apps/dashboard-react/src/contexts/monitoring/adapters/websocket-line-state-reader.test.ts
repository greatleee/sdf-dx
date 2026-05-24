import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LineStateSnapshot } from "../domain/line-state";
import { WebSocketLineStateReader } from "./websocket-line-state-reader";

const LINE = "11111111-1111-4111-8111-111111111111";
const URL = "ws://test/ws/line-state";

/**
 * Minimal controllable WebSocket stand-in: records every instance and lets a test fire
 * open/message/close. Not a mock library — a fake the adapter drives, so assertions are on
 * observable outcomes (handler calls, instance count), never on call patterns.
 */
class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  readonly url: string;
  closed = false;
  private listeners: Record<string, ((event: unknown) => void)[]> = {};

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, cb: (event: unknown) => void): void {
    (this.listeners[type] ??= []).push(cb);
  }

  close(): void {
    this.closed = true;
    this.fire("close", {});
  }

  fire(type: string, event: unknown): void {
    for (const cb of this.listeners[type] ?? []) cb(event);
  }

  fireMessage(data: unknown): void {
    this.fire("message", { data });
  }
}

function validFrame(state: LineStateSnapshot["state"]): string {
  return JSON.stringify({ lineId: LINE, state, since: "2026-05-22T00:00:00Z" });
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("WebSocketLineStateReader", () => {
  it("reports open and maps a valid frame to a domain snapshot", () => {
    const snapshots: LineStateSnapshot[] = [];
    let opened = 0;
    const reader = new WebSocketLineStateReader(URL);
    reader.subscribe({
      onSnapshot: (s) => snapshots.push(s),
      onOpen: () => (opened += 1),
    });

    const socket = FakeWebSocket.instances[0];
    expect(socket).toBeDefined();
    socket?.fire("open", {});
    socket?.fireMessage(validFrame("DOWN"));

    expect(opened).toBe(1);
    expect(snapshots).toEqual([{ lineId: LINE, state: "DOWN", since: "2026-05-22T00:00:00Z" }]);
  });

  it("drops an unparseable frame instead of calling onSnapshot or throwing", () => {
    const snapshots: LineStateSnapshot[] = [];
    const reader = new WebSocketLineStateReader(URL);
    reader.subscribe({ onSnapshot: (s) => snapshots.push(s) });

    const socket = FakeWebSocket.instances[0];
    socket?.fireMessage("not json");
    socket?.fireMessage(JSON.stringify({ lineId: LINE, state: "MELTING", since: "x" }));

    expect(snapshots).toEqual([]);
  });

  it("reconnects after a drop (backoff), and unsubscribe stops further reconnects", async () => {
    vi.useFakeTimers();
    const reader = new WebSocketLineStateReader(URL);
    const unsubscribe = reader.subscribe({ onSnapshot: () => undefined });
    expect(FakeWebSocket.instances).toHaveLength(1);

    // Socket drops → adapter schedules a backoff reconnect (~1s + jitter).
    FakeWebSocket.instances[0]?.fire("close", {});
    await vi.advanceTimersByTimeAsync(2000);
    expect(FakeWebSocket.instances.length).toBeGreaterThanOrEqual(2);

    // After unsubscribe, a further drop must not schedule another connect.
    unsubscribe();
    const countAfterUnsub = FakeWebSocket.instances.length;
    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeWebSocket.instances).toHaveLength(countAfterUnsub);
  });
});
