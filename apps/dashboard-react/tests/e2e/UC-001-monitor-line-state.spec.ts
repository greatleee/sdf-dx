import { expect, test } from "@playwright/test";

import { dashboardHomeUrl } from "./_helpers";

/**
 * UC-001 — Operator monitors single Line state.
 * Covers the FIRST Gherkin scenario only ("Dashboard shows current state on first
 * load"). The other two scenarios (live WS propagation; polling fallback when the
 * WS dies) need orchestration not wired in Phase 1 — see docs/KNOWN-UNKNOWNS.md
 * "UC-001 live-propagation / WS-fallback scenarios".
 *
 * Selectors are stable `data-testid` / ARIA roles only (frontend-rules §9) — never
 * text or class names. In `fake` mode the Line state resolves to RUNNING (MSW), but
 * the assertion accepts any valid Line state so the same spec holds against `real`.
 *
 * `dashboardHomeUrl()` honors `E2E_LINE_ID` so `real` mode can target the seeded
 * `production_line.id` (random per stack-up); `fake` mode leaves it unset and the
 * nil-UUID fallback path is exercised unchanged. See `./_helpers.ts`.
 */
test.describe("UC-001 — Operator monitors single Line state", () => {
  test("Dashboard shows current Line state on first load", async ({ page }) => {
    await page.goto(dashboardHomeUrl());

    await expect(page.getByRole("heading", { name: "SDF Manufacturing DX" })).toBeVisible();

    await expect(page.getByTestId("line-state-value")).toHaveText(
      /^(RUNNING|IDLE|DOWN|CHANGEOVER)$/,
      { timeout: 5_000 },
    );
  });
});
