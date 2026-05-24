import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { HttpMonitoringReader } from "./http-monitoring-reader";

// Node's fetch needs an absolute URL; MSW matches on path, so any origin works.
const ORIGIN = "http://api.test";
const LINE = "11111111-1111-4111-8111-111111111111";

const server = setupServer();
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

describe("HttpMonitoringReader", () => {
  it("parses + maps a line-state response", async () => {
    server.use(
      http.get("*/api/v1/lines/:lineId/state", () =>
        HttpResponse.json({ lineId: LINE, state: "DOWN", since: "2026-05-22T00:00:00Z" }),
      ),
    );
    const reader = new HttpMonitoringReader(ORIGIN);
    await expect(reader.readLineState(LINE)).resolves.toEqual({
      lineId: LINE,
      state: "DOWN",
      since: "2026-05-22T00:00:00Z",
    });
  });

  it("throws on a non-2xx response (transport failure, §6)", async () => {
    server.use(
      http.get("*/api/v1/lines/:lineId/state", () => new HttpResponse(null, { status: 500 })),
    );
    const reader = new HttpMonitoringReader(ORIGIN);
    await expect(reader.readLineState(LINE)).rejects.toThrow(/HTTP 500/);
  });

  it("throws when the response violates the contract (boundary parse failure, §6)", async () => {
    server.use(
      http.get("*/api/v1/lines/:lineId/state", () =>
        HttpResponse.json({ lineId: LINE, state: "MELTING", since: "2026-05-22T00:00:00Z" }),
      ),
    );
    const reader = new HttpMonitoringReader(ORIGIN);
    await expect(reader.readLineState(LINE)).rejects.toThrow();
  });

  it("parses + maps an oee response", async () => {
    server.use(
      http.get("*/api/v1/lines/:lineId/oee", () =>
        HttpResponse.json({
          lineId: LINE,
          window: "5m",
          oee: 0.8,
          availability: 0.9,
          performance: 0.95,
          quality: 0.93,
          observedAt: "2026-05-22T00:00:00Z",
        }),
      ),
    );
    const reader = new HttpMonitoringReader(ORIGIN);
    await expect(reader.readOee(LINE, "5m")).resolves.toMatchObject({ oee: 0.8, window: "5m" });
  });
});
