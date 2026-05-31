package com.sdf.dx.bridge.adapters

import com.sdf.dx.bridge.domain.NormalizedRecord
import com.sdf.dx.bridge.domain.Normalizer
import com.sdf.dx.bridge.domain.NormalizerMetric
import org.eclipse.paho.mqttv5.client.IMqttToken
import org.eclipse.paho.mqttv5.client.MqttCallback
import org.eclipse.paho.mqttv5.client.MqttClient
import org.eclipse.paho.mqttv5.client.MqttConnectionOptions
import org.eclipse.paho.mqttv5.client.MqttDisconnectResponse
import org.eclipse.paho.mqttv5.client.persist.MemoryPersistence
import org.eclipse.paho.mqttv5.common.MqttException
import org.eclipse.paho.mqttv5.common.MqttMessage
import org.eclipse.paho.mqttv5.common.packet.MqttProperties
import org.eclipse.tahu.message.SparkplugBPayloadDecoder
import org.eclipse.tahu.message.model.SparkplugBPayload
import org.eclipse.tahu.model.MetricDataTypeMap
import org.slf4j.LoggerFactory
import java.io.IOException

/**
 * Imperative shell subscribing to node-level Sparkplug B messages over MQTT v5 and
 * forwarding each normalized record to [onRecord].
 *
 * Subscribes to the node-level data/birth filters `spBv1.0/+/NDATA/+` and
 * `spBv1.0/+/NBIRTH/+` (ADR-0011 D-1/D-3); the Device topic level is unused (D-2).
 * The `edge_node_id` is topic segment 3 (`= line slug = line_id`, D-2). Decoding uses
 * the Eclipse Tahu high-level payload model; metric value coercion and compound-name
 * splitting are the pure [Normalizer]'s job — this adapter only adapts tahu types to
 * [NormalizerMetric] and reads the message arrival clock (a system read permitted in
 * an adapter, ADR-0023 K1 / backend-code-architecture §2).
 */
public class MqttSubscriber(
    mqttUrl: String,
    private val defaultTenant: String,
    private val onRecord: (NormalizedRecord) -> Unit,
) {
    private val log = LoggerFactory.getLogger(MqttSubscriber::class.java)
    private val client = MqttClient(mqttUrl, "sdf-bridge-${System.nanoTime()}", MemoryPersistence())
    private val decoder = SparkplugBPayloadDecoder()

    /**
     * Connects and subscribes to the node-level NDATA and NBIRTH filters at QoS 1.
     *
     * Messages are delivered through a single [MqttCallback] registered with [MqttClient.setCallback]
     * rather than the per-subscription `subscribe(filter, qos, listener)` overload: that overload is
     * recursively self-calling in Paho mqttv5 1.2.5 (`MqttClient.subscribe:525`) and throws
     * `StackOverflowError` on first use, which previously killed the bridge at startup.
     */
    public fun start() {
        val options = MqttConnectionOptions()
        options.isCleanStart = true
        client.setCallback(
            object : MqttCallback {
                // TooGenericExceptionCaught: intentional — this is the Paho receive-thread
                // boundary. Any unchecked RuntimeException escaping onMessage() or
                // KafkaBridgeProducer.emit() would silently kill Paho's receive thread;
                // catching Exception here ensures every failure is logged-and-dropped rather
                // than silently swallowed. Jackson's JsonProcessingException (IOException)
                // was the original motivation; the broader catch covers all unchecked paths.
                @Suppress("TooGenericExceptionCaught")
                override fun messageArrived(
                    topic: String,
                    message: MqttMessage,
                ) {
                    try {
                        onMessage(topic, message)
                    } catch (ex: Exception) {
                        log.warn("dropping message on topic '{}' due to emit failure", topic, ex)
                    }
                }

                override fun connectComplete(
                    reconnect: Boolean,
                    serverURI: String?,
                ) = log.info("MQTT connect complete reconnect={} uri={}", reconnect, serverURI)

                override fun disconnected(disconnectResponse: MqttDisconnectResponse?): Unit =
                    log.warn("MQTT disconnected: {}", disconnectResponse?.reasonString)

                override fun mqttErrorOccurred(exception: MqttException?): Unit =
                    log.warn("MQTT error occurred", exception)

                override fun deliveryComplete(token: IMqttToken?): Unit =
                    log.trace("delivery complete (subscriber publishes nothing): {}", token)

                override fun authPacketArrived(
                    reasonCode: Int,
                    properties: MqttProperties?,
                ): Unit = log.trace("auth packet arrived reasonCode={}", reasonCode)
            },
        )
        client.connect(options)
        client.subscribe(
            arrayOf(NDATA_FILTER, NBIRTH_FILTER),
            intArrayOf(QOS_AT_LEAST_ONCE, QOS_AT_LEAST_ONCE),
        )
        log.info("MQTT subscriber connected, filters=[{}, {}]", NDATA_FILTER, NBIRTH_FILTER)
    }

    /** Disconnects and releases the client. */
    public fun close() {
        if (client.isConnected) {
            client.disconnect()
        }
        client.close()
    }

    private fun onMessage(
        topic: String,
        message: MqttMessage,
    ) {
        val segments = topic.split("/")
        if (segments.size < TOPIC_SEGMENT_COUNT) {
            return
        }
        val messageType = segments[MESSAGE_TYPE_INDEX]
        if (messageType != "NDATA" && messageType != "NBIRTH") {
            return
        }
        val edgeNodeId = segments[EDGE_NODE_INDEX]
        val payload = decode(message.payload) ?: return
        val metrics = toNormalizerMetrics(payload)
        val seq = (payload.seq ?: 0L).toInt()
        Normalizer.fromSparkplug(defaultTenant, edgeNodeId, metrics, seq).forEach(onRecord)
    }

    private fun decode(bytes: ByteArray): SparkplugBPayload? =
        try {
            decoder.buildFromByteArray(bytes, MetricDataTypeMap())
        } catch (ex: IOException) {
            // Malformed/partial bytes fail protobuf parsing (InvalidProtocolBufferException
            // is an IOException). Drop the message rather than kill the subscriber callback.
            log.warn("dropping undecodable Sparkplug payload", ex)
            null
        }

    private fun toNormalizerMetrics(payload: SparkplugBPayload): List<NormalizerMetric> =
        payload.metrics.mapNotNull { metric ->
            val name = metric.name ?: return@mapNotNull null
            val value = metric.value ?: return@mapNotNull null
            val timestampMs = metric.timestamp?.time ?: System.currentTimeMillis()
            NormalizerMetric(name, value, timestampMs)
        }

    private companion object {
        private const val NDATA_FILTER: String = "spBv1.0/+/NDATA/+"
        private const val NBIRTH_FILTER: String = "spBv1.0/+/NBIRTH/+"
        private const val QOS_AT_LEAST_ONCE: Int = 1
        private const val TOPIC_SEGMENT_COUNT: Int = 4
        private const val MESSAGE_TYPE_INDEX: Int = 2
        private const val EDGE_NODE_INDEX: Int = 3
    }
}
