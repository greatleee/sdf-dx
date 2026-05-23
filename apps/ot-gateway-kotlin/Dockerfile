# syntax=docker/dockerfile:1
# Multi-stage build for the Kotlin OT-gateway modules (simulator + bridge).
# Stage 1 (JDK) builds runnable artifacts; stage 2 (JRE) runs them — no Gradle at runtime.
# Both docker-compose services build from this single context and select their entrypoint
# via `command:` (simulator -> the application-plugin script, bridge -> the Spring Boot jar).

FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY . .
# Tests run in CI, not in the image build. installDist yields the simulator's
# self-contained distribution; bootJar yields the bridge's runnable fat jar.
RUN ./gradlew --no-daemon :simulator:installDist :bridge:bootJar -x test

FROM eclipse-temurin:21-jre AS runtime
WORKDIR /app
# simulator: application-plugin distribution (bin/<launch-script> + lib/<deps>)
COPY --from=build /src/simulator/build/install/simulator /app/simulator
# bridge: Spring Boot fat jar (stable name set in bridge/build.gradle.kts)
COPY --from=build /src/bridge/build/libs/bridge.jar /app/bridge.jar
# Default entrypoint is the bridge; docker-compose overrides `command:` per service:
#   simulator -> ["/app/simulator/bin/simulator"]
#   bridge    -> ["java","-jar","/app/bridge.jar"]
CMD ["java", "-jar", "/app/bridge.jar"]
