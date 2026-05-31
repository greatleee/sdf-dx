package com.sdf.dx.bridge.adapters

import com.sdf.dx.bridge.domain.NormalizedRecord
import org.eclipse.paho.mqttv5.client.MqttClient
import org.eclipse.paho.mqttv5.client.MqttConnectionOptions
import org.eclipse.paho.mqttv5.client.persist.MemoryPersistence
import org.eclipse.tahu.message.SparkplugBPayloadEncoder
import org.eclipse.tahu.message.model.Metric.MetricBuilder
import org.eclipse.tahu.message.model.MetricDataType
import org.eclipse.tahu.message.model.SparkplugBPayload.SparkplugBPayloadBuilder
import org.junit.jupiter.api.Tag
import org.junit.jupiter.api.Test
import org.testcontainers.containers.GenericContainer
import org.testcontainers.containers.wait.strategy.Wait
import org.testcontainers.images.builder.Transferable
import java.util.Date
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/**
 * Docker-backed regression test for the Paho mqttv5 1.2.5 `subscribe` StackOverflow.
 *
 * On the OLD code, `MqttSubscriber.start()` used the per-subscription
 * `subscribe(filter, qos, listener)` overload, which is recursively self-calling in
 * Paho mqttv5 1.2.5 (`MqttClient.subscribe:525`) and throws `StackOverflowError` on
 * first use — so [subscriber starts without StackOverflow and receives an NDATA record]
 * would fail before any assertion. The fix registers a single [org.eclipse.paho.mqttv5.client.MqttCallback]
 * via `setCallback` and uses the non-recursing `subscribe(filters[], qos[])` overload.
 *
 * OPT-IN: tagged `integration`, EXCLUDED from the default `:bridge:test` task (which CI
 * runs Docker-free). Run explicitly — Docker must be available — with:
 *   ./gradlew :bridge:integrationTest
 */
@Tag("integration")
public class MqttSubscriberIntegrationTest {
    @Test
    public fun `subscriber starts without StackOverflow and receives an NDATA record`() {
        broker().use { container ->
            container.start()
            val brokerUrl = "tcp://${container.host}:${container.getMappedPort(MQTT_PORT)}"

            val received = AtomicReference<NormalizedRecord?>(null)
            val latch = CountDownLatch(1)
            val subscriber =
                MqttSubscriber(brokerUrl, TENANT) { record ->
                    received.compareAndSet(null, record)
                    latch.countDown()
                }

            try {
                // On the old subscribe overload this line throws StackOverflowError.
                subscriber.start()

                publishNdata(brokerUrl)

                assertTrue(
                    latch.await(RECEIVE_TIMEOUT_SECONDS, TimeUnit.SECONDS),
                    "MqttSubscriber did not deliver a NormalizedRecord within $RECEIVE_TIMEOUT_SECONDS s",
                )
                val record = received.get()
                assertNotNull(record, "expected a NormalizedRecord from the published NDATA")
                assertEquals(TENANT, record.tenantId)
                assertEquals(EDGE_NODE_ID, record.lineId, "lineId is the edge_node_id (ADR-0011 D-2)")
                assertEquals("press", record.machineKey)
                assertEquals("cycle_count", record.metric)
                assertEquals(EXPECTED_CYCLE_COUNT.toDouble(), record.value)
            } finally {
                subscriber.close()
            }
        }
    }

    /**
     * Publishes one Sparkplug B NDATA carrying `press/cycle_count` to the node-level
     * topic, mirroring how the simulator's `SparkplugPublisher` encodes metrics with
     * Eclipse Tahu (tahu-core). A short connect window lets the subscriber's broker-side
     * subscription settle before the message is delivered.
     */
    private fun publishNdata(brokerUrl: String) {
        val encoder = SparkplugBPayloadEncoder()
        val publisher = MqttClient(brokerUrl, "sdf-it-publisher", MemoryPersistence())
        val options = MqttConnectionOptions()
        options.isCleanStart = true
        publisher.connect(options)
        try {
            val payload =
                SparkplugBPayloadBuilder()
                    .setTimestamp(Date())
                    .setSeq(SEQ)
                    .addMetric(
                        MetricBuilder("press/cycle_count", MetricDataType.Int64, EXPECTED_CYCLE_COUNT)
                            .createMetric(),
                    ).createPayload()
            // Retransmit a few times: QoS-1 publishes can race the broker-side subscription
            // registration on a freshly-started container.
            repeat(PUBLISH_ATTEMPTS) {
                publisher.publish(NDATA_TOPIC, encoder.getBytes(payload, false), QOS_AT_LEAST_ONCE, false)
                Thread.sleep(PUBLISH_GAP_MILLIS)
            }
        } finally {
            if (publisher.isConnected) {
                publisher.disconnect()
            }
            publisher.close()
        }
    }

    private fun broker(): GenericContainer<*> =
        GenericContainer(MOSQUITTO_IMAGE)
            .withExposedPorts(MQTT_PORT)
            // mosquitto 2.x denies anonymous clients by default; an explicit listener +
            // allow_anonymous config opens the 1883 listener for the test.
            .withCopyToContainer(
                Transferable.of("listener $MQTT_PORT\nallow_anonymous true\n"),
                "/mosquitto/config/mosquitto.conf",
            ).waitingFor(Wait.forListeningPort())

    private companion object {
        private const val MOSQUITTO_IMAGE = "eclipse-mosquitto:2.0"
        private const val MQTT_PORT = 1883
        private const val TENANT = "sdf_default"
        private const val EDGE_NODE_ID = "line-x"
        private const val NDATA_TOPIC = "spBv1.0/sdf_default/NDATA/line-x"
        private const val QOS_AT_LEAST_ONCE = 1
        private const val SEQ = 0L
        private const val EXPECTED_CYCLE_COUNT = 42L
        private const val RECEIVE_TIMEOUT_SECONDS = 15L
        private const val PUBLISH_ATTEMPTS = 5
        private const val PUBLISH_GAP_MILLIS = 300L
    }
}
