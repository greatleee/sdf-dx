import { describe, expect, it } from "vitest";

import { zLineStateSnapshot, zOeeReading } from "@sdf/contracts/zod";
import { lineStateSnapshotFromWire, oeeReadingFromWire } from "./mappers";

const LINE = "11111111-1111-4111-8111-111111111111";

describe("lineStateSnapshotFromWire", () => {
  it("maps a contract-valid frame to the domain snapshot", () => {
    const wire = zLineStateSnapshot.parse({
      lineId: LINE,
      state: "RUNNING",
      since: "2026-05-22T00:00:00Z",
    });
    expect(lineStateSnapshotFromWire(wire)).toEqual({
      lineId: LINE,
      state: "RUNNING",
      since: "2026-05-22T00:00:00Z",
    });
  });
});

describe("oeeReadingFromWire", () => {
  it("maps a contract-valid reading to the domain reading", () => {
    const wire = zOeeReading.parse({
      lineId: LINE,
      window: "5m",
      oee: 0.8,
      availability: 0.9,
      performance: 0.95,
      quality: 0.93,
      observedAt: "2026-05-22T00:00:00Z",
    });
    expect(oeeReadingFromWire(wire)).toEqual({
      lineId: LINE,
      window: "5m",
      oee: 0.8,
      availability: 0.9,
      performance: 0.95,
      quality: 0.93,
      observedAt: "2026-05-22T00:00:00Z",
    });
  });
});
