package com.sdf.dx.simulator.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

public class LineModelTest {
    @Test
    public fun `tick advances one cycle per CYCLE_TIME_MS`() {
        val advanced = LineModel.initial("press").tick(1000)

        assertEquals(1L, advanced.cycleCount)
    }

    @Test
    public fun `scrap count over 100 ticks lands near the configured scrap rate`() {
        var model = LineModel.initial("press", scrapRate = 0.5, seed = 42L)
        repeat(100) { model = model.tick(1000) }

        assertEquals(100L, model.cycleCount)
        assertTrue(
            model.scrapCount in 35L..65L,
            "expected scrap count in 35..65 for scrapRate=0.5 over 100 ticks, was ${model.scrapCount}",
        )
    }

    @Test
    public fun `cycle count always equals good plus scrap`() {
        var model = LineModel.initial("weld", scrapRate = 0.3, seed = 7L)
        repeat(50) { model = model.tick(1000) }

        assertEquals(model.cycleCount, model.goodCount + model.scrapCount)
    }
}
