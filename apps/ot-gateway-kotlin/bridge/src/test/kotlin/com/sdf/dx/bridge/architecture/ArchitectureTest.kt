package com.sdf.dx.bridge.architecture

import com.lemonappdev.konsist.api.Konsist
import com.lemonappdev.konsist.api.architecture.KoArchitectureCreator.assertArchitecture
import com.lemonappdev.konsist.api.architecture.Layer
import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Enforces the ADR-0023 Kotlin architecture contracts (domain isolation / K1) for the
 * bridge module's functional core. The throwaway plan sample omitted the K1
 * system-read check; both checks are mandatory here.
 */
public class ArchitectureTest {
    private val domainFiles =
        Konsist
            .scopeFromModule("bridge", "main")
            .files
            .filter { it.packagee?.name?.contains(".domain") == true }

    @Test
    public fun `domain does not import adapters or messaging frameworks`() {
        assertTrue(domainFiles.isNotEmpty(), "expected at least one domain file to verify")

        val forbiddenImportPrefixes =
            listOf(
                "com.sdf.dx.bridge.adapters",
                "org.apache.kafka",
                "org.springframework.kafka",
                "org.eclipse.paho",
                "org.eclipse.tahu",
                "com.fasterxml.jackson",
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

    @Test
    public fun `K3 - layer dependency direction (adapters may depend on domain, not vice versa)`() {
        // ADR-0023 K3 (adapters-no-upward). With only `domain` and `adapters` present today this
        // primarily encodes "adapters → domain only": `domain.dependsOnNothing()` forbids the
        // domain from importing the adapter package, and `adapters.dependsOn(domain)` declares the
        // one allowed direction. Written with `assertArchitecture` so it stays correct as the
        // `ports` / `application` layers are introduced — add them as `Layer`s and the same
        // direction holds without rewriting the check.
        Konsist
            .scopeFromModule("bridge", "main")
            .assertArchitecture {
                val domain = Layer("Domain", "com.sdf.dx.bridge.domain..")
                val adapters = Layer("Adapters", "com.sdf.dx.bridge.adapters..")

                domain.dependsOnNothing()
                adapters.dependsOn(domain)
            }
    }
}
