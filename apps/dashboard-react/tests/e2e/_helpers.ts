/**
 * Shared Playwright helpers for the UC specs. Kept intentionally tiny — no
 * test-framework features (no fixtures, no `test.extend`); just functions the
 * specs import.
 *
 * The dashboard reads its `Line` from `?lineId=<uuid>` (URL-as-SoT, ADR-0030)
 * and falls back to a nil-UUID when the param is missing
 * (`useSelectedLineId` in `src/contexts/monitoring/application/selected-line.ts`).
 * That fallback is fine under MSW (every request is intercepted regardless of
 * id), but it 404s against a real API whose seeded `production_line.id` is a
 * random `uuid_generate_v4()`. So in `real` mode CI discovers the seeded id
 * and exports it as `E2E_LINE_ID`; specs append it as a URL param. `fake` mode
 * leaves it unset, the param is omitted, and the nil-UUID path is preserved
 * (zero behaviour change for `pnpm e2e:fake`). FE production code is not
 * touched — the lineId mechanism stays in tests/CI per frontend-rules §9.
 */
export function dashboardHomeUrl(): string {
  const id = process.env.E2E_LINE_ID;
  return id ? `/?lineId=${id}` : "/";
}
