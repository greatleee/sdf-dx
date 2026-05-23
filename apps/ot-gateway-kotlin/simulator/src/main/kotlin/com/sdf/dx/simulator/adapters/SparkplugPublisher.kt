package com.sdf.dx.simulator.adapters

import com.sdf.dx.simulator.domain.LineModel
import org.eclipse.paho.mqttv5.client.MqttClient
import org.eclipse.paho.mqttv5.client.MqttConnectionOptions
import org.eclipse.paho.mqttv5.client.persist.MemoryPersistence
import org.eclipse.paho.mqttv5.common.MqttMessage
import org.eclipse.tahu.message.SparkplugBPayloadEncoder
import org.eclipse.tahu.message.model.Metric.MetricBuilder
import org.eclipse.tahu.message.model.MetricDataType
import org.eclipse.tahu.message.model.SparkplugBPayload
import org.eclipse.tahu.message.model.SparkplugBPayload.SparkplugBPayloadBuilder
import org.slf4j.LoggerFactory
import java.util.Date

/**
 * Imperative shell publishing Sparkplug B node-level messages for one Edge Node
 * (one Line) over MQTT v5, using the Eclipse Tahu high-level payload model and the
 * Paho client.
 *
 * Topic shape per ADR-0011 D-1/D-2: `spBv1.0/<group>/<NBIRTH|NDATA|NDEATH>/<edge>`.
 * The Device topic level is unused; Machines are addressed by compound metric names
 * (`<machineId>/cycle_count`, etc.).
 *
 * Sequence handling per ADR-0011 D-4: [seq] is an 8-bit `0..255` counter that wraps
 * (NBIRTH = 0, advanced after each message); [bdSeq] is a separate `0..255` counter
 * incremented once per MQTT session and carried in NBIRTH and the Last-Will NDEATH so
 * a stale death can be correlated to its originating session.
 */
public class SparkplugPublisher(
    mqttUrl: String,
    private val groupId: String,
    private val edgeNodeId: String,
) {
    private val log = LoggerFactory.getLogger(SparkplugPublisher::class.java)
    private val client = MqttClient(mqttUrl, "sdf-sim-$edgeNodeId", MemoryPersistence())
    private val encoder = SparkplugBPayloadEncoder()

    private var seq: Long = 0L
    private var bdSeq: Long = 0L

    private val birthTopic = "spBv1.0/$groupId/NBIRTH/$edgeNodeId"
    private val dataTopic = "spBv1.0/$groupId/NDATA/$edgeNodeId"
    private val deathTopic = "spBv1.0/$groupId/NDEATH/$edgeNodeId"

    /**
     * Connects with the NDEATH payload (carrying the current [bdSeq]) registered as a
     * retained Last-Will, then publishes NBIRTH (seq reset to 0) defining the full
     * metric set for the given [machineIds] (ADR-0011 D-3/D-4).
     */
    public fun publishBirth(machineIds: List<String>) {
        bdSeq = nextWrapping(bdSeq)
        seq = 0L

        val options = MqttConnectionOptions()
        options.isCleanStart = true
        options.keepAliveInterval = KEEP_ALIVE_SECONDS
        options.setWill(deathTopic, deathMessage())
        client.connect(options)

        val builder = SparkplugBPayloadBuilder().setTimestamp(Date()).setSeq(seq)
        builder.addMetric(MetricBuilder("bdSeq", MetricDataType.Int64, bdSeq).createMetric())
        machineIds.forEach { machineId ->
            builder.addMetric(metric("$machineId/cycle_count", 0L))
            builder.addMetric(metric("$machineId/good_count", 0L))
            builder.addMetric(metric("$machineId/scrap_count", 0L))
        }
        publish(birthTopic, builder.createPayload())
        seq = nextWrapping(seq)
        log.info("NBIRTH published edge={} bdSeq={} machines={}", edgeNodeId, bdSeq, machineIds)
    }

    /**
     * Publishes one NDATA carrying the current counter metrics for [model], using the
     * current [seq], then advances [seq] (ADR-0011 D-4).
     */
    public fun publishData(model: LineModel) {
        val payload =
            SparkplugBPayloadBuilder()
                .setTimestamp(Date())
                .setSeq(seq)
                .addMetric(metric("${model.machineId}/cycle_count", model.cycleCount))
                .addMetric(metric("${model.machineId}/good_count", model.goodCount))
                .addMetric(metric("${model.machineId}/scrap_count", model.scrapCount))
                .createPayload()
        publish(dataTopic, payload)
        seq = nextWrapping(seq)
    }

    /** Disconnects gracefully. The retained Will NDEATH covers ungraceful loss. */
    public fun close() {
        if (client.isConnected) {
            client.disconnect()
        }
        client.close()
    }

    private fun metric(
        name: String,
        value: Long,
    ) = MetricBuilder(name, MetricDataType.Int64, value).createMetric()

    private fun deathMessage(): MqttMessage {
        val payload =
            SparkplugBPayloadBuilder()
                .setTimestamp(Date())
                .addMetric(MetricBuilder("bdSeq", MetricDataType.Int64, bdSeq).createMetric())
                .createPayload()
        val message = MqttMessage(encoder.getBytes(payload, false))
        message.qos = QOS_AT_LEAST_ONCE
        message.isRetained = true
        return message
    }

    private fun publish(
        topic: String,
        payload: SparkplugBPayload,
    ) {
        client.publish(topic, encoder.getBytes(payload, false), QOS_AT_LEAST_ONCE, false)
    }

    private companion object {
        private const val QOS_AT_LEAST_ONCE: Int = 1
        private const val KEEP_ALIVE_SECONDS: Int = 30
        private const val SEQ_MODULUS: Long = 256L

        private fun nextWrapping(current: Long): Long = (current + 1L) % SEQ_MODULUS
    }
}
