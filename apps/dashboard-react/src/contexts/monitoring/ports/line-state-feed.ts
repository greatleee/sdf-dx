import type { LineStateSnapshot } from "../domain/line-state";

/** Callbacks a live Line-state feed invokes over its lifetime. */
export interface LineStateFeedHandlers {
  /** A mapped snapshot arrived. The feed carries every Line; consumers filter by `lineId`. */
  onSnapshot: (snapshot: LineStateSnapshot) => void;
  /** The transport connected (or reconnected). */
  onOpen?: () => void;
  /** The transport dropped; the adapter will attempt to reconnect. */
  onClose?: () => void;
}

/**
 * A live push feed of Line-state snapshots (WebSocket today).
 *
 * A port (§1). The adapter owns the socket, reconnection, and boundary parsing; the
 * application layer subscribes and writes mapped frames into the Query cache (§5).
 * `subscribe` returns an unsubscribe function that tears the transport down.
 */
export interface LineStateFeed {
  subscribe(handlers: LineStateFeedHandlers): () => void;
}
