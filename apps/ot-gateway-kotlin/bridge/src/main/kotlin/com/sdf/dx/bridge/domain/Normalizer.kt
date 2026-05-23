package com.sdf.dx.bridge.domain

/**
 * One raw Sparkplug metric as decoded from a payload by the MQTT adapter, before
 * normalization. [name] is the compound metric name (`<machineKey>/<metric>`),
 * [value] is the tahu-decoded boxed value, [timestampMs] is epoch millis.
 *
 * This is an adapter→domain input record carrying only stdlib types; the tahu
 * `Metric` type never crosses into the functional core (backend-code-architecture §2).
 */
public data class NormalizerMetric(
    val name: String,
    val value: Any,
    val timestampMs: Long,
)

/**
 * One normalized telemetry record, the functional-core output that the Kafka
 * adapter serializes against `kafka-payloads/machine_telemetry.schema.json`.
 *
 * [lineId] is the edge-native line slug (`= Sparkplug edge_node_id`, ADR-0011 D-2)
 * and [machineKey] the compound-metric prefix (`press`, ...) — neither is a topology
 * UUID; the ingest service resolves both to DB ids downstream. [observedAtEpochMillis]
 * holds epoch millis; the adapter converts it to ISO-8601 at the Kafka boundary.
 */
public data class NormalizedRecord(
    val tenantId: String,
    val lineId: String,
    val machineKey: String,
    val metric: String,
    val value: Double,
    val observedAtEpochMillis: Long,
    val sparkplugSeq: Int,
)

/**
 * Pure functional core: maps a decoded Sparkplug node payload to normalized
 * telemetry records. No IO, no system reads, kotlin-stdlib imports only
 * (ADR-0023 K1 / backend-code-architecture §2).
 */
public object Normalizer {
    /**
     * Splits each compound metric name on `/` (limit 2) into `(machineKey, metric)`,
     * coerces the value to a [Double] (`Number` → [Number.toDouble], `Boolean` →
     * 1.0/0.0), and emits one [NormalizedRecord] per coercible compound metric.
     * Names without exactly two `/`-separated parts and values that are neither
     * [Number] nor [Boolean] are skipped. [lineId] is set to [edgeNodeId]
     * (ADR-0011 D-2: `edge_node_id == line_id`).
     */
    public fun fromSparkplug(
        tenantId: String,
        edgeNodeId: String,
        metrics: List<NormalizerMetric>,
        sparkplugSeq: Int,
    ): List<NormalizedRecord> =
        metrics.mapNotNull { metric ->
            val parts = metric.name.split("/", limit = 2)
            if (parts.size != 2) {
                return@mapNotNull null
            }
            val coerced = coerce(metric.value) ?: return@mapNotNull null
            NormalizedRecord(
                tenantId = tenantId,
                lineId = edgeNodeId,
                machineKey = parts[0],
                metric = parts[1],
                value = coerced,
                observedAtEpochMillis = metric.timestampMs,
                sparkplugSeq = sparkplugSeq,
            )
        }

    private fun coerce(value: Any): Double? =
        when (value) {
            is Number -> value.toDouble()
            is Boolean -> if (value) 1.0 else 0.0
            else -> null
        }
}
