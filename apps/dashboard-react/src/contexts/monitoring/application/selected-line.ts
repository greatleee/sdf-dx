const LINE_ID_PARAM = "lineId";

/** 8-4-4-4-12 hex UUID shape; permissive on version/variant so any contract-valid id passes. */
const UUID_SHAPE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Nil-UUID default Line, used until the URL supplies a real id. Phase 1 has a single line and
 * no picker; this keeps the dashboard rendering without a hardcoded production id (which is a
 * random `uuid_generate_v4()` in the seed, not known at build time).
 */
export const DEFAULT_LINE_ID = "00000000-0000-0000-0000-000000000000";

/**
 * The selected Line id, read from the URL search params — the source of truth for shareable
 * view state (ADR-0030). Phase 1 is read-only (no router yet, so this is not reactive to
 * navigation); a missing param falls back to {@link DEFAULT_LINE_ID}. Reads `window` here in
 * the shell, never in `domain/` (§2/§12).
 */
export function useSelectedLineId(): string {
  // `??` alone would let `?lineId=` (empty string) or arbitrary text flow into query keys and
  // adapter URLs — `get` returns "" (not null) for an empty param. Require a UUID-shaped value,
  // else fall back to the default (validate user input at the boundary).
  const raw = new URLSearchParams(window.location.search).get(LINE_ID_PARAM)?.trim();
  if (raw === undefined || !UUID_SHAPE.test(raw)) return DEFAULT_LINE_ID;
  return raw;
}
