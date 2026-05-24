// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { MonitoringAdaptersProvider, useLineState } from "@/contexts/monitoring";
import type { LineStateSnapshot } from "@/contexts/monitoring";
import { createFakeMonitoringAdapters } from "@/contexts/monitoring/testing/fakes";

afterEach(cleanup);

const LINE = "11111111-1111-4111-8111-111111111111";
const OTHER_LINE = "99999999-9999-4999-8999-999999999999";

function makeWrapper(adapters: ReturnType<typeof createFakeMonitoringAdapters>) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={queryClient}>
        <MonitoringAdaptersProvider adapters={adapters}>{children}</MonitoringAdaptersProvider>
      </QueryClientProvider>
    );
  };
}

describe("useLineState", () => {
  it("seeds the snapshot from the REST reader", async () => {
    const seed: LineStateSnapshot = { lineId: LINE, state: "IDLE", since: "2026-05-22T00:00:00Z" };
    const adapters = createFakeMonitoringAdapters({ state: seed });
    const { result } = renderHook(() => useLineState(LINE), { wrapper: makeWrapper(adapters) });

    await waitFor(() => {
      expect(result.current.snapshot).toEqual(seed);
    });
  });

  it("overwrites the cached snapshot with a live frame and marks the feed live", async () => {
    const seed: LineStateSnapshot = { lineId: LINE, state: "IDLE", since: "2026-05-22T00:00:00Z" };
    const adapters = createFakeMonitoringAdapters({ state: seed });
    const { result } = renderHook(() => useLineState(LINE), { wrapper: makeWrapper(adapters) });
    await waitFor(() => {
      expect(result.current.snapshot).toEqual(seed);
    });

    const frame: LineStateSnapshot = { lineId: LINE, state: "DOWN", since: "2026-05-22T00:05:00Z" };
    act(() => {
      adapters.feed.open();
      adapters.feed.emit(frame);
    });

    await waitFor(() => {
      expect(result.current.snapshot).toEqual(frame);
      expect(result.current.live).toBe(true);
    });
  });

  it("ignores live frames for other lines", async () => {
    const seed: LineStateSnapshot = {
      lineId: LINE,
      state: "RUNNING",
      since: "2026-05-22T00:00:00Z",
    };
    const adapters = createFakeMonitoringAdapters({ state: seed });
    const { result } = renderHook(() => useLineState(LINE), { wrapper: makeWrapper(adapters) });
    await waitFor(() => {
      expect(result.current.snapshot).toEqual(seed);
    });

    act(() => {
      adapters.feed.open();
      adapters.feed.emit({ lineId: OTHER_LINE, state: "DOWN", since: "2026-05-22T01:00:00Z" });
    });

    expect(result.current.snapshot).toEqual(seed);
  });
});
