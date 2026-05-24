import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type { LineStateSnapshot } from "../domain/line-state";
import { useMonitoringAdapters } from "./adapters-context";
import { monitoringKeys } from "./query-keys";

const POLL_INTERVAL_MS = 2_000;

export interface UseLineStateResult {
  snapshot: LineStateSnapshot | undefined;
  isPending: boolean;
  isError: boolean;
  /** True while the live feed is connected; false drives the polling fallback + UI badge. */
  live: boolean;
}

/**
 * Live Line state for one line. Seeds from the REST reader, then a single WebSocket
 * subscription writes each mapped frame into the SAME Query cache key via `setQueryData`
 * (ADR-0029). Polling runs only while the socket is down (`refetchInterval` gated on `live`),
 * so `setQueryData` and a background refetch never race (§5). Frames for other lines — the
 * feed carries every line — are ignored.
 */
export function useLineState(lineId: string): UseLineStateResult {
  const { lineStateReader, lineStateFeed } = useMonitoringAdapters();
  const queryClient = useQueryClient();
  const [live, setLive] = useState(false);

  const query = useQuery({
    queryKey: monitoringKeys.lineState(lineId),
    queryFn: () => lineStateReader.readLineState(lineId),
    staleTime: Infinity,
    refetchInterval: live ? false : POLL_INTERVAL_MS,
  });

  useEffect(() => {
    const unsubscribe = lineStateFeed.subscribe({
      onOpen: () => {
        setLive(true);
      },
      onClose: () => {
        setLive(false);
      },
      onSnapshot: (snapshot) => {
        if (snapshot.lineId !== lineId) return;
        queryClient.setQueryData(monitoringKeys.lineState(lineId), snapshot);
      },
    });
    return unsubscribe;
  }, [lineId, lineStateFeed, queryClient]);

  return {
    snapshot: query.data,
    isPending: query.isPending,
    isError: query.isError,
    live,
  };
}
