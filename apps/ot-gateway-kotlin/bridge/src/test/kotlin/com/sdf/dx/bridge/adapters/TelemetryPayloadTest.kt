package com.sdf.dx.bridge.adapters

import com.sdf.dx.bridge.domain.NormalizedRecord
import java.time.Instant
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Contract-conformance unit test guarding [telemetryPayload] against drift from the
 * Kafka payload SoT `packages/contracts/kafka-payloads/machine_telemetry.schema.json`
 * (required fields + `additionalProperties: false`). No broker / docker needed.
 */
public class TelemetryPayloadTest {
    private val schemaKeys =
        setOf(
            "tenantId",
            "lineId",
            "machineKey",
            "metric",
            "value",
            "observedAt",
            "sparkplugSeq",
        )

    private val metricEnum =
        setOf("cycle_count", "good_count", "scrap_count", "state", "cycle_time_ms")

    private val record =
        NormalizedRecord(
            tenantId = "sdf_default",
            lineId = "line-a",
            machineKey = "press",
            metric = "cycle_count",
            value = 42.0,
            observedAtEpochMillis = 1_700_000_000_000L,
            sparkplugSeq = 7,
        )

    @Test
    public fun `payload key set matches the contract exactly`() {
        val payload = telemetryPayload(record)

        assertEquals(
            schemaKeys,
            payload.keys,
            "payload keys must equal the schema required set (additionalProperties:false)",
        )
    }

    @Test
    public fun `observedAt parses as ISO-8601`() {
        val payload = telemetryPayload(record)

        val observedAt = payload["observedAt"] as String
        // throws on a non-ISO-8601 string; reaching the assert means it parsed.
        val parsed = Instant.parse(observedAt)
        assertEquals(record.observedAtEpochMillis, parsed.toEpochMilli())
    }

    @Test
    public fun `sparkplugSeq is within the 0 to 255 contract bound`() {
        val payload = telemetryPayload(record)

        val seq = payload["sparkplugSeq"] as Int
        assertTrue(seq in 0..255, "sparkplugSeq must be in 0..255, was $seq")
    }

    @Test
    public fun `metric is one of the contract enum values`() {
        val payload = telemetryPayload(record)

        val metric = payload["metric"] as String
        assertTrue(metric in metricEnum, "metric '$metric' must be one of the schema enum values")
    }
}
