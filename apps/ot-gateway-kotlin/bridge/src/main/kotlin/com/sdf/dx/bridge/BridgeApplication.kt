package com.sdf.dx.bridge

import com.sdf.dx.bridge.adapters.KafkaBridgeProducer
import com.sdf.dx.bridge.adapters.MqttSubscriber
import org.springframework.boot.CommandLineRunner
import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication
import org.springframework.context.annotation.Bean

/**
 * Composition root for the Sparkplug→Kafka bridge. Reads connection settings from the
 * environment, wires the pure [MqttSubscriber] → [KafkaBridgeProducer] pipeline, and
 * starts the subscription. `-Xexplicit-api=strict` requires `public open` on the Spring
 * bean class and method so the framework can subclass/proxy them.
 */
@SpringBootApplication
public open class BridgeApplication {
    /**
     * Wires the bridge pipeline: each normalized record from the [MqttSubscriber] is
     * emitted to Kafka by the [KafkaBridgeProducer]. Connection settings come from env
     * (`MQTT_URL`, `KAFKA_BOOTSTRAP`, `SDF_DEFAULT_TENANT`) with localhost defaults.
     */
    @Bean
    public open fun bridgeRunner(): CommandLineRunner =
        CommandLineRunner {
            val mqttUrl = System.getenv("MQTT_URL") ?: "tcp://localhost:1883"
            val kafkaBootstrap = System.getenv("KAFKA_BOOTSTRAP") ?: "localhost:9092"
            val tenant = System.getenv("SDF_DEFAULT_TENANT") ?: "sdf_default"

            val producer = KafkaBridgeProducer(kafkaBootstrap)
            val subscriber = MqttSubscriber(mqttUrl, tenant) { record -> producer.emit(record) }
            Runtime.getRuntime().addShutdownHook(
                Thread {
                    subscriber.close()
                    producer.close()
                },
            )
            subscriber.start()
        }
}

// Spring Boot's runApplication takes `vararg args`; spreading the entrypoint array is the
// framework idiom and the only way to forward CLI args — the detekt perf heuristic is moot here.
@Suppress("SpreadOperator")
public fun main(args: Array<String>) {
    runApplication<BridgeApplication>(*args)
}
