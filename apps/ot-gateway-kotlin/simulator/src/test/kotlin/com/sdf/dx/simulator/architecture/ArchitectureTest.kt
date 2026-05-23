package com.sdf.dx.simulator.architecture

import com.lemonappdev.konsist.api.Konsist
import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Enforces the ADR-0023 Kotlin architecture contracts (K1 / domain isolation) for the
 * simulator module's functional core. The throwaway plan sample omitted the K1
 * system-read check; both checks are mandatory here.
 */
public class ArchitectureTest {
    private val domainFiles =
        Konsist
            .scopeFromModule("simulator", "main")
            .files
            .filter { it.packagee?.name?.contains(".domain") == true }

    @Test
    public fun `domain does not import adapters or messaging frameworks`() {
        assertTrue(domainFiles.isNotEmpty(), "expected at least one domain file to verify")

        val forbiddenImportPrefixes =
            listOf(
                "com.sdf.dx.simulator.adapters",
                "org.eclipse.paho",
                "org.eclipse.tahu",
            )

        domainFiles.forEach { file ->
            file.imports.forEach { import ->
                forbiddenImportPrefixes.forEach { forbidden ->
                    assertTrue(
                        !import.name.startsWith(forbidden),
                        "domain file ${file.name} must not import '$forbidden' (found '${import.name}')",
                    )
                }
            }
        }
    }

    @Test
    public fun `K1 - domain does not read the system clock, uuid, or nanotime`() {
        assertTrue(domainFiles.isNotEmpty(), "expected at least one domain file to verify")

        val forbiddenCallSites =
            listOf(
                "System.currentTimeMillis(",
                "System.nanoTime(",
                "Instant.now(",
                "UUID.randomUUID(",
            )

        domainFiles.forEach { file ->
            forbiddenCallSites.forEach { callSite ->
                assertTrue(
                    !file.text.contains(callSite),
                    "domain file ${file.name} must not contain system read '$callSite' (ADR-0023 K1)",
                )
            }
        }
    }
}
