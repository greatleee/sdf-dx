package com.sdf.dx.simulator.domain

/**
 * Pure deterministic idle schedule for the simulated production line.
 *
 * [isStopped] is a pure predicate over **simulated elapsed time** — tick-driven, where
 * one tick = `TICK_INTERVAL_MS` (1 s). The caller accumulates ticks as
 * `simulatedMs += TICK_INTERVAL_MS` each loop iteration; this is NOT wall-clock time.
 * Keeping the schedule tick-driven is essential: idle windows must be aligned to
 * production cycles, not real elapsed time (ADR-0023 K1 — no clock reads in domain).
 *
 * Schedule: the line runs for the first [FIRST_STOP_OFFSET_MS] simulated ms, then
 * enters a [STOP_DURATION_MS] idle window every [PERIOD_MS]. Steady-state running
 * window = `PERIOD_MS − STOP_DURATION_MS` = 48 s; ~80% uptime (the first period,
 * 30 s run + 12 s idle, differs from the steady-state rhythm).
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
     * Returns `true` iff the line should be stopped (idle) at [simulatedMs] simulated
     * elapsed time (tick-driven; one tick = `TICK_INTERVAL_MS`; not wall-clock).
     *
     * Pure predicate — no side effects, no system reads.
     */
    public fun isStopped(simulatedMs: Long): Boolean {
        if (simulatedMs < FIRST_STOP_OFFSET_MS) return false
        val phaseMs = (simulatedMs - FIRST_STOP_OFFSET_MS) % PERIOD_MS
        return phaseMs < STOP_DURATION_MS
    }
}
