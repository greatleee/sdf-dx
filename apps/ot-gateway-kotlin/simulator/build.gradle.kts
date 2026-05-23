plugins {
    kotlin("jvm")
    application
}

application {
    mainClass.set("com.sdf.dx.simulator.MainKt")
}

dependencies {
    implementation("org.eclipse.tahu:tahu-core:1.0.10")
    implementation("org.eclipse.paho:org.eclipse.paho.mqttv5.client:1.2.5")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    implementation("ch.qos.logback:logback-classic:1.5.8")

    testImplementation(kotlin("test"))
    testImplementation("com.lemonappdev:konsist:0.17.3")
}

tasks.test { useJUnitPlatform() }
