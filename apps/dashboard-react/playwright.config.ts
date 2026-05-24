import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config. Two projects mirror the dual-adapter wiring (ADR-0028):
 *  - `fake`  — MSW serves the read API (`VITE_FAKE=1`), so the real HTTP adapter
 *    runs against controlled responses. The top-level `webServer` self-hosts the
 *    Vite dev server; it is gated on `VITE_FAKE` so it only starts for `e2e:fake`.
 *    This is the project the CI use-case gate runs (`pnpm e2e:fake`).
 *  - `real`  — runs against an externally-started stack (docker compose), no
 *    webServer. Reserved for the full-stack smoke (Section J).
 *
 * NOTE: `webServer` is a TOP-LEVEL key, not a per-project one — Playwright silently
 * ignores it if nested inside a project, which leaves the dev server unstarted.
 */
const fakeMode = process.env.VITE_FAKE === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  use: { baseURL: "http://localhost:5173", trace: "on-first-retry" },
  webServer: fakeMode
    ? {
        command: "pnpm dev:fake",
        url: "http://localhost:5173",
        timeout: 60_000,
        reuseExistingServer: !process.env.CI,
      }
    : undefined,
  projects: [
    {
      name: "fake",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "real",
      use: { ...devices["Desktop Chrome"] },
      // CI brings up docker compose externally before invoking this project.
    },
  ],
});
