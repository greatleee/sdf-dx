package com.sdf.dx.simulator.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

public class LineScheduleTest {
    // ── running windows ────────────────────────────────────────────────────

    @Test
    public fun `line is running at 0ms (before first stop)`() {
        assertFalse(LineSchedule.isStopped(0L))
    }

    @Test
    public fun `line is running just before the first stop offset`() {
        assertFalse(LineSchedule.isStopped(29_999L))
    }

    @Test
    public fun `line is running after the first idle window ends`() {
        assertFalse(LineSchedule.isStopped(42_000L))
    }

    @Test
    public fun `line is running before the second idle window`() {
        assertFalse(LineSchedule.isStopped(89_999L))
    }

    @Test
    public fun `line is running after the second idle window ends`() {
        assertFalse(LineSchedule.isStopped(102_000L))
    }

    // ── idle windows ───────────────────────────────────────────────────────

    @Test
    public fun `line is stopped at the first stop boundary`() {
        assertTrue(LineSchedule.isStopped(30_000L))
    }

    @Test
    public fun `line is stopped inside the first idle window`() {
        assertTrue(LineSchedule.isStopped(41_999L))
    }

    @Test
    public fun `line is stopped at the start of the second idle window`() {
        assertTrue(LineSchedule.isStopped(90_000L))
    }

    @Test
    public fun `line is stopped inside the second idle window`() {
        assertTrue(LineSchedule.isStopped(101_999L))
    }

    // ── boundary: negative input ───────────────────────────────────────────

    @Test
    public fun `negative simulated time is treated as running (before first stop)`() {
        assertFalse(LineSchedule.isStopped(-1L))
    }

    // ── LineModel.tick(0) invariant ────────────────────────────────────────

    @Test
    public fun `tick with 0 ms leaves cycleCount unchanged on an already-advanced model`() {
        val advanced = LineModel.initial("press").tick(1000L)
        assertEquals(1L, advanced.cycleCount)

        val ticked = advanced.tick(0L)
        assertEquals(1L, ticked.cycleCount)
    }
}
