FROM gradle:8.5-jdk17 AS builder
WORKDIR /workspace/services/terra-ops
COPY services/terra-ops/build.gradle services/terra-ops/settings.gradle ./
COPY services/terra-ops/src ./src
COPY docs/contracts /workspace/docs/contracts
RUN gradle build --no-daemon -x test

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=builder /workspace/services/terra-ops/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
