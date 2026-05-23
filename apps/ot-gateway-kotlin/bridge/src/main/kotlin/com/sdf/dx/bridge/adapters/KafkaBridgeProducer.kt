package com.sdf.dx.bridge.adapters

import com.fasterxml.jackson.databind.ObjectMapper
import com.sdf.dx.bridge.domain.NormalizedRecord
import org.apache.kafka.clients.producer.KafkaProducer
import org.apache.kafka.clients.producer.ProducerConfig
import org.apache.kafka.clients.producer.ProducerRecord
import org.apache.kafka.common.serialization.StringSerializer
import java.time.Instant
import java.util.Properties

/**
 * Assembles the Kafka value payload for one [NormalizedRecord], conforming exactly to
 * `packages/contracts/kafka-payloads/machine_telemetry.schema.json` (required fields +
 * `additionalProperties: false`): the seven keys `tenantId`, `lineId`, `machineKey`,
 * `metric`, `value`, `observedAt`, `sparkplugSeq` and nothing else.
 *
 * `observedAt` is the ISO-8601 rendering of the record's epoch-millis timestamp; the
 * epoch→ISO conversion is a Kafka-boundary concern and lives here, never in the domain.
 * Kept `internal` and pure so the contract-conformance unit test can assert the key set
 * without a live broker.
 */
internal fun telemetryPayload(record: NormalizedRecord): LinkedHashMap<String, Any> =
    linkedMapOf(
        "tenantId" to record.tenantId,
        "lineId" to record.lineId,
        "machineKey" to record.machineKey,
        "metric" to record.metric,
        "value" to record.value,
        "observedAt" to Instant.ofEpochMilli(record.observedAtEpochMillis).toString(),
        "sparkplugSeq" to record.sparkplugSeq,
    )

/**
 * Imperative shell publishing normalized telemetry to Kafka. Wraps a Kafka
 * [KafkaProducer] configured for idempotent, fully-acked delivery and serializes the
 * contract payload from [telemetryPayload] with Jackson.
 *
 * Downstream topic naming per ADR-0011 D-5: `sdf.{tenant}.machine.{type}` with
 * `{type}` = `telemetry` (the `machine_telemetry` schema family). Jackson and Kafka
 * imports live here in the adapter, never in the domain (backend-code-architecture §2).
 */
public class KafkaBridgeProducer(bootstrap: String) {
    private val mapper = ObjectMapper()
    private val producer: KafkaProducer<String, String> =
        KafkaProducer(
            Properties().apply {
                put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrap)
                put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer::class.java.name)
                put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer::class.java.name)
                put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true)
                put(ProducerConfig.ACKS_CONFIG, "all")
            },
        )

    /**
     * Publishes one [record] to `sdf.<tenant>.machine.telemetry`, keyed by
     * `<lineId>/<machineKey>` so all metrics of one machine share a partition.
     */
    public fun emit(record: NormalizedRecord) {
        val topic = "sdf.${record.tenantId}.machine.telemetry"
        val key = "${record.lineId}/${record.machineKey}"
        val value = mapper.writeValueAsString(telemetryPayload(record))
        producer.send(ProducerRecord(topic, key, value))
    }

    /** Flushes and closes the underlying producer. */
    public fun close() {
        producer.close()
    }
}
