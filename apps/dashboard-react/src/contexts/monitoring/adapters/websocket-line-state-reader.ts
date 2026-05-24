import { zLineStateSnapshot } from "@sdf/contracts/zod";

import type { LineStateSnapshot } from "../domain/line-state";
import type { LineStateFeed, LineStateFeedHandlers } from "../ports/line-state-feed";
import { lineStateSnapshotFromWire } from "./mappers";

const BASE_RECONNECT_MS = 1_000;
const MAX_RECONNECT_MS = 30_000;
const JITTER_RATIO = 0.25;

/**
 * WebSocket adapter for the live Line-state feed (`WebSocketLineStateReader`, §8).
 *
 * Owns the socket and reconnection (exponential backoff + jitter, §5). Each frame is parsed
 * through the generated Zod and mapped with the SAME mapper as the REST path, so the Query
 * cache only ever holds the domain type — never a raw wire frame (ADR-0029). A frame that
 * fails to parse is dropped, not thrown: a feed has no caller to reject to, and one bad frame
 * must not tear the stream down.
 *
 * No application-level heartbeat: the Phase-1 endpoint is send-only and pushes on change
 * (a healthy Line can be silent for minutes), so there is no honest heartbeat signal to act
 * on. Reconnect-on-drop is the load-bearing resilience; the heartbeat is deferred — see
 * `docs/KNOWN-UNKNOWNS.md`.
 */
export class WebSocketLineStateReader implements LineStateFeed {
  constructor(private readonly url: string = defaultWsUrl()) {}

  subscribe(handlers: LineStateFeedHandlers): () => void {
    const wsUrl = this.url;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    function connect(): void {
      const ws = new WebSocket(wsUrl);
      socket = ws;

      ws.addEventListener("open", () => {
        attempt = 0;
        handlers.onOpen?.();
      });

      ws.addEventListener("message", (event: MessageEvent<unknown>) => {
        const snapshot = toSnapshot(event.data);
        if (snapshot !== null) handlers.onSnapshot(snapshot);
      });

      ws.addEventListener("close", () => {
        handlers.onClose?.();
        if (stopped) return;
        const backoff = Math.min(BASE_RECONNECT_MS * 2 ** attempt, MAX_RECONNECT_MS);
        const delay = backoff + Math.random() * backoff * JITTER_RATIO;
        attempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      });

      // An error event is always followed by a close event; reconnection happens there.
      ws.addEventListener("error", () => {
        ws.close();
      });
    }

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }
}

/** Parse + map a raw frame; return null (drop) if it does not satisfy the contract. */
function toSnapshot(data: unknown): LineStateSnapshot | null {
  const json = typeof data === "string" ? safeJsonParse(data) : data;
  const result = zLineStateSnapshot.safeParse(json);
  return result.success ? lineStateSnapshotFromWire(result.data) : null;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function defaultWsUrl(): string {
  return `${window.location.origin.replace(/^http/, "ws")}/ws/line-state`;
}
