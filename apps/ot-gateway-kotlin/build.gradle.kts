plugins {
    // Kotlin is pinned to detekt 1.23.7's supported compiler (2.0.10). detekt aborts when
    // its analyzer's compiled Kotlin version differs from the one on its classpath, and on
    // Spring-managed modules a Kotlin-BOM platform alignment overrides any per-config force.
    // Keeping the toolchain Kotlin == detekt's Kotlin is the only skew-free pairing; bump
    // both together (e.g. Kotlin 2.0.21 + detekt 1.23.8) if a newer Kotlin is needed.
    kotlin("jvm") version "2.0.10" apply false
    id("io.gitlab.arturbosch.detekt") version "1.23.7" apply false
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1" apply false
    id("org.springframework.boot") version "3.3.4" apply false
    id("io.spring.dependency-management") version "1.1.6" apply false
    // Coverage. Kover instruments JVM bytecode, so it is insensitive to the detekt/Kotlin
    // skew that pins the compiler above. Applied to the root for cross-module aggregation
    // (see the `kover(project(...))` dependencies at the foot of this file).
    id("org.jetbrains.kotlinx.kover") version "0.8.3"
}

allprojects {
    group = "com.sdf.dx"
    version = "0.1.0"
    repositories { mavenCentral() }
}

subprojects {
    apply(plugin = "io.gitlab.arturbosch.detekt")
    apply(plugin = "org.jlleitschuh.gradle.ktlint")
    apply(plugin = "org.jetbrains.kotlin.jvm")
    apply(plugin = "org.jetbrains.kotlinx.kover")

    extensions.configure<io.gitlab.arturbosch.detekt.extensions.DetektExtension> {
        buildUponDefaultConfig = true
        allRules = false
        config.setFrom(rootProject.files("detekt.yml"))
    }

    tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_21)
            freeCompilerArgs.addAll("-Xjsr305=strict", "-Xexplicit-api=strict")
        }
    }
}

// Aggregate coverage across the modules that carry production code. `gateway` is an empty
// scaffold (no src/main) and is deliberately omitted so it cannot dilute the ratio.
// `./gradlew koverXmlReport` writes build/reports/kover/report.xml; `koverLog` prints the total.
dependencies {
    kover(project(":simulator"))
    kover(project(":bridge"))
}
