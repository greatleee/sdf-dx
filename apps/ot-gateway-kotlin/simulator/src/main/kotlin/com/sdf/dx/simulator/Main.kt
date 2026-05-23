package com.sdf.dx.simulator

import com.sdf.dx.simulator.adapters.SparkplugPublisher
import com.sdf.dx.simulator.domain.LineModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.slf4j.LoggerFactory

private val log = LoggerFactory.getLogger("com.sdf.dx.simulator.Main")

/** Machine types per GLOSSARY `topology` / ADR-0011. */
private val MACHINE_TYPES: List<String> = listOf("press", "weld", "paint", "inspect", "pack")

private const val MQTT_URL_DEFAULT = "tcp://localhost:1883"
private const val GROUP_ID_DEFAULT = "sdf_default"
private const val LINE_ID_DEFAULT = "line-a"
private const val TICK_INTERVAL_MS = 1000L

/**
 * Composition root for the device simulator. Reads configuration from the
 * environment, wires the [SparkplugPublisher] adapter, and drives the pure
 * [LineModel] core in a 1s loop. System reads (the per-machine RNG seed) live
 * here, never in the domain (ADR-0023 K1).
 */
public fun main(): Unit =
    runBlocking {
        val mqttUrl = System.getenv("MQTT_URL") ?: MQTT_URL_DEFAULT
        val groupId = System.getenv("SDF_GROUP_ID") ?: GROUP_ID_DEFAULT
        val lineId = System.getenv("SDF_LINE_ID") ?: LINE_ID_DEFAULT

        var models =
            MACHINE_TYPES.mapIndexed { index, machineId ->
                LineModel.initial(machineId, seed = System.currentTimeMillis() + index)
            }

        val publisher = SparkplugPublisher(mqttUrl, groupId, lineId)
        Runtime.getRuntime().addShutdownHook(Thread { publisher.close() })

        publisher.publishBirth(MACHINE_TYPES)
        log.info("simulator started edge={} group={} mqtt={}", lineId, groupId, mqttUrl)

        while (true) {
            models =
                models.map { model ->
                    val ticked = model.tick(TICK_INTERVAL_MS)
                    publisher.publishData(ticked)
                    ticked
                }
            delay(TICK_INTERVAL_MS)
        }
    }
