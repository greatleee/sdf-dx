import type { LineStateSnapshot } from "../domain/line-state";

/**
 * Reads the current Line state from a backing store.
 *
 * A port (interface over an external system, §1). The HTTP adapter implements it; the
 * application layer depends on this interface, never on the adapter. A transport failure
 * (network / non-2xx / boundary parse failure) rejects the promise (§6).
 */
export interface LineStateReader {
  readLineState(lineId: string): Promise<LineStateSnapshot>;
}
