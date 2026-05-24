package com.sdf.dx.simulator.domain

/**
 * Pure deterministic idle schedule for the simulated production line.
 *
 * Given accumulated elapsed milliseconds since simulator start, [isStopped] returns
 * whether the line is currently in a synthetic idle window. No clock reads, no IO, no
 * RNG — the function is a pure predicate over the elapsed-time parameter (ADR-0023 K1).
 *
 * Schedule: the line runs for the first [FIRST_STOP_OFFSET_MS] ms, then enters a
 * [STOP_DURATION_MS] idle window every [PERIOD_MS]. Approximate uptime: ~80%.
 *
 *   0 ms ──────────── 30 000 ms : RUNNING
 *   30 000 ms ─────── 42 000 ms : IDLE  (first window)
 *   42 000 ms ─────── 90 000 ms : RUNNING
 *   90 000 ms ──────── 102 000 ms : IDLE  (second window)
 *   …
 *
 * **This is SYNTHETIC, deterministic idle injected for observability/demo purposes** so
 * that the downstream `line_state` path demonstrably transitions RUNNING↔IDLE. It does
 * not model real downtime or operator events. DOWN and CHANGEOVER are still never emitted
 * (consistent with [docs/KNOWN-UNKNOWNS.md] — line state is a Phase-1 heuristic).
 */
public object LineSchedule {
    /** Elapsed ms before the first idle window begins. */
    public const val FIRST_STOP_OFFSET_MS: Long = 30_000L

    /** Duration of each idle window in ms (~12 s of unchanged cycle_count publishes). */
    public const val STOP_DURATION_MS: Long = 12_000L

    /** Interval between the start of successive idle windows in ms. */
    public const val PERIOD_MS: Long = 60_000L

    /**
     * Returns `true` iff the line should be stopped (idle) at [elapsedMs] ms since start.
     *
     * Pure predicate — no side effects, no system reads.
     */
    public fun isStopped(elapsedMs: Long): Boolean {
        if (elapsedMs < FIRST_STOP_OFFSET_MS) return false
        val phaseMs = (elapsedMs - FIRST_STOP_OFFSET_MS) % PERIOD_MS
        return phaseMs < STOP_DURATION_MS
    }
}
