import { expect, test } from "@playwright/test";

import { dashboardHomeUrl } from "./_helpers";

/**
 * UC-002 — Operator observes OEE refresh.
 * Covers the FIRST Gherkin scenario only ("OEE tiles render with percentages on
 * first load"). The second scenario ("values refresh at the polling cadence") is
 * deferred per UC-002 Open Questions — it depends on non-deterministic simulator
 * activity within the test window.
 *
 * Stable `data-testid` selectors only (frontend-rules §9). The four factor tiles
 * carry `oee-{oee,availability,performance,quality}`; each renders a percentage.
 *
 * `dashboardHomeUrl()` honors `E2E_LINE_ID` so `real` mode can target the seeded
 * `production_line.id` (random per stack-up); `fake` mode leaves it unset and the
 * nil-UUID path is exercised unchanged. See `./_helpers.ts`.
 */
const FACTOR_TESTIDS = ["oee-oee", "oee-availability", "oee-performance", "oee-quality"] as const;

test.describe("UC-002 — Operator observes OEE refresh", () => {
  test("OEE tiles render with percentages on first load", async ({ page }) => {
    await page.goto(dashboardHomeUrl());

    for (const testId of FACTOR_TESTIDS) {
      // The tile testid only renders once the reading is present, so toHaveText
      // (which waits for attach + content) also covers visibility — one assertion.
      await expect(page.getByTestId(testId)).toHaveText(/^\d+(\.\d+)?%$/, { timeout: 5_000 });
    }
  });
});
