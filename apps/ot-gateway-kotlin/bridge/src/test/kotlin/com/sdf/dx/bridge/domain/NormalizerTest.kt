package com.sdf.dx.bridge.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

public class NormalizerTest {
    @Test
    public fun `splits compound metric names into machineKey and metric`() {
        val records =
            Normalizer.fromSparkplug(
                tenantId = "sdf_default",
                edgeNodeId = "line-a",
                metrics =
                    listOf(
                        NormalizerMetric("press/cycle_count", 42L, 1_000L),
                        NormalizerMetric("press/good_count", 40L, 1_000L),
                    ),
                sparkplugSeq = 7,
            )

        assertEquals(2, records.size)
        val first = records[0]
        assertEquals("sdf_default", first.tenantId)
        assertEquals("line-a", first.lineId)
        assertEquals("press", first.machineKey)
        assertEquals("cycle_count", first.metric)
        assertEquals(42.0, first.value)
        assertEquals(1_000L, first.observedAtEpochMillis)
        assertEquals(7, first.sparkplugSeq)
    }

    @Test
    public fun `drops non-compound metric names that lack a slash`() {
        val records =
            Normalizer.fromSparkplug(
                tenantId = "sdf_default",
                edgeNodeId = "line-a",
                metrics =
                    listOf(
                        NormalizerMetric("bdSeq", 3L, 1_000L),
                        NormalizerMetric("press/cycle_count", 42L, 1_000L),
                    ),
                sparkplugSeq = 1,
            )

        assertEquals(1, records.size)
        assertEquals("cycle_count", records[0].metric)
    }

    @Test
    public fun `coerces boolean values to one or zero and skips uncoercible values`() {
        val records =
            Normalizer.fromSparkplug(
                tenantId = "sdf_default",
                edgeNodeId = "line-a",
                metrics =
                    listOf(
                        NormalizerMetric("press/state", true, 1_000L),
                        NormalizerMetric("press/note", "running", 1_000L),
                    ),
                sparkplugSeq = 2,
            )

        assertEquals(1, records.size)
        assertEquals("state", records[0].metric)
        assertEquals(1.0, records[0].value)
        assertTrue(records.none { it.metric == "note" })
    }
}
