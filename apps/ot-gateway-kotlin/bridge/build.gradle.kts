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
    testImplementation("org.testcontainers:kafka:1.20.2")
    testImplementation("org.testcontainers:hivemq:1.20.2")
    testImplementation("org.testcontainers:junit-jupiter:1.20.2")
}

tasks.test { useJUnitPlatform() }

// The Spring Boot fat jar is the only runtime artifact; give it a stable, version-free
// name the Dockerfile can copy, and skip the plain library jar (nothing depends on it).
tasks.bootJar { archiveFileName.set("bridge.jar") }
tasks.jar { enabled = false }
