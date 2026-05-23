package com.sdf.dx.simulator.domain

import kotlin.random.Random

/**
 * Pure functional-core model of a single machine on a production line.
 *
 * Every transition is a pure function of the current state plus the injected
 * [rng]; the model performs no IO and reads no system clock, UUID, or randomness
 * source of its own (ADR-0023 K1 / backend-code-architecture §4). The composition
 * root injects a seeded [Random].
 *
 * Invariant: [cycleCount] == [goodCount] + [scrapCount] holds after every [tick].
 */
public data class LineModel(
    val machineId: String,
    val cycleCount: Long,
    val goodCount: Long,
    val scrapCount: Long,
    val scrapRate: Double,
    private val rng: Random,
) {
    /**
     * Advances production by `elapsedMs / CYCLE_TIME_MS` cycles. Each cycle draws
     * from [rng]: a draw below [scrapRate] is scrap, otherwise good. Returns an
     * updated copy with the new counts.
     *
     * Note: the injected [rng] is `kotlin.random.Random`, which is mutable; the
     * returned copy shares the same [rng] instance, so drawing here also advances
     * the receiver's RNG state. Callers drive the model forward by using only the
     * returned value and discarding the receiver (see the composition root).
     */
    public fun tick(elapsedMs: Long): LineModel {
        val cycles = elapsedMs / CYCLE_TIME_MS
        if (cycles <= 0L) {
            return this
        }
        var good = goodCount
        var scrap = scrapCount
        var remaining = cycles
        while (remaining > 0L) {
            if (rng.nextDouble() < scrapRate) {
                scrap += 1
            } else {
                good += 1
            }
            remaining -= 1L
        }
        return copy(
            cycleCount = cycleCount + cycles,
            goodCount = good,
            scrapCount = scrap,
        )
    }

    public companion object {
        private const val CYCLE_TIME_MS: Long = 1000L

        /**
         * Builds a fresh model. The default [seed] is a constant `0L`, never a
         * system read — the composition root injects a real per-machine seed
         * (ADR-0023 K1).
         */
        public fun initial(
            machineId: String,
            scrapRate: Double = 0.05,
            seed: Long = 0L,
        ): LineModel =
            LineModel(
                machineId = machineId,
                cycleCount = 0L,
                goodCount = 0L,
                scrapCount = 0L,
                scrapRate = scrapRate,
                rng = Random(seed),
            )
    }
}
