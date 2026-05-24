plugins {
    kotlin("jvm")
    id("org.springframework.boot")
    id("io.spring.dependency-management")
}

dependencies {
    implementation("org.springframework.boot:spring-boot-starter")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("org.springframework.kafka:spring-kafka:3.2.4")
    implementation("org.eclipse.paho:org.eclipse.paho.mqttv5.client:1.2.5")
    implementation("org.eclipse.tahu:tahu-core:1.0.10")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")

    testImplementation(kotlin("test"))
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("com.lemonappdev:konsist:0.17.3")
    testImplementation("org.testcontainers:kafka:1.20.6")
    testImplementation("org.testcontainers:hivemq:1.20.6")
    testImplementation("org.testcontainers:junit-jupiter:1.20.6")
    // GenericContainer (core) drives the eclipse-mosquitto broker for the MqttSubscriber
    // integration test (MqttSubscriberIntegrationTest).
    testImplementation("org.testcontainers:testcontainers:1.20.6")
    // Spring Boot's test classpath pulls Apache HttpClient 4.x, which references
    // org.apache.commons.codec.Charsets — a class removed in commons-codec 1.16. Spring's
    // dependency management does not put commons-codec on this test classpath at all, so the
    // class is missing at runtime (NoClassDefFoundError during GenericContainer.start()). This
    // persists through TC 1.20.6 (docker-java 3.4.1). Pin the last version that ships
    // `Charsets` for the integration test runtime only.
    testRuntimeOnly("commons-codec:commons-codec:1.15")
}

// Integration tests (Docker/testcontainers) are OPT-IN, mirroring the Python side's
// `--integration` flag (apps/api-python/tests/conftest.py). The default `test` task — the
// one CI's `kotlin` job runs alongside ktlint/detekt — must stay Docker-free, so it
// EXCLUDES the `integration` JUnit5 tag. Run the integration tests explicitly with:
//   ./gradlew :bridge:integrationTest        (Docker must be running)
tasks.test { useJUnitPlatform { excludeTags("integration") } }

tasks.register<Test>("integrationTest") {
    description = "Runs Docker-backed integration tests tagged 'integration' (opt-in)."
    group = "verification"
    testClassesDirs = sourceSets.test.get().output.classesDirs
    classpath = sourceSets.test.get().runtimeClasspath
    useJUnitPlatform { includeTags("integration") }
    // Never up-to-date: a passing broker run should always be re-runnable on demand.
    outputs.upToDateWhen { false }
    // Modern Docker Engine (Desktop 4.73 / Engine 29.x) advertises MinAPIVersion 1.40 and
    // rejects the api.version=1.32 ping hardcoded in DockerClientProviderStrategy
    // (docker-java 3.4.1, present through at least TC 1.21.3; no TC bump removes it).
    // Pin a supported API version so the environment probe succeeds. Honour a
    // DOCKER_API_VERSION already in the environment; otherwise default to 1.41.
    systemProperty("api.version", System.getenv("DOCKER_API_VERSION") ?: "1.41")
}

// The Spring Boot fat jar is the only runtime artifact; give it a stable, version-free
// name the Dockerfile can copy, and skip the plain library jar (nothing depends on it).
tasks.bootJar { archiveFileName.set("bridge.jar") }
tasks.jar { enabled = false }
