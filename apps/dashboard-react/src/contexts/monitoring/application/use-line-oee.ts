import { useQuery } from "@tanstack/react-query";

import type { OeeReading, OeeWindow } from "../domain/oee";
import { useMonitoringAdapters } from "./adapters-context";
import { monitoringKeys } from "./query-keys";

const OEE_REFRESH_MS = 5_000;

export interface UseLineOeeResult {
  reading: OeeReading | undefined;
  isPending: boolean;
  isError: boolean;
}

/**
 * OEE for one line over a window. REST-only with a periodic refresh — OEE is a rolled-up
 * aggregate (no live push channel), so a low-frequency `refetchInterval` is the right fit (§4).
 */
export function useLineOee(lineId: string, window: OeeWindow): UseLineOeeResult {
  const { oeeReader } = useMonitoringAdapters();
  const query = useQuery({
    queryKey: monitoringKeys.lineOee(lineId, window),
    queryFn: () => oeeReader.readOee(lineId, window),
    refetchInterval: OEE_REFRESH_MS,
  });
  return {
    reading: query.data,
    isPending: query.isPending,
    isError: query.isError,
  };
}
