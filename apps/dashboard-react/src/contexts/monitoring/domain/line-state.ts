/**
 * Monitoring domain — Line state types.
 *
 * Pure TypeScript: no React, no IO, no Zod (boundary-only, §2/§3). These mirror the
 * backend monitoring domain and the ubiquitous language in `docs/spec/GLOSSARY.md`
 * ("Line state", ISA-95 L2). The wire/boundary schema (generated Zod) is separate and
 * lives only in `adapters/`; the mapper there produces these plain types.
 */

/** Closed set of operational states for a Line (GLOSSARY: "Line state"). */
export type LineState = "RUNNING" | "IDLE" | "DOWN" | "CHANGEOVER";

/**
 * The current Line state with the instant it was entered.
 *
 * `since` is an ISO-8601 timestamp kept as a string in the domain — formatting it for a
 * locale is a UI concern (and needs the system clock/timezone the domain must not read).
 */
export interface LineStateSnapshot {
  lineId: string;
  state: LineState;
  since: string;
}
