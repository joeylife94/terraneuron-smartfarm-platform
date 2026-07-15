FROM gradle:8.5-jdk17 AS builder
WORKDIR /workspace/services/terra-sense
COPY services/terra-sense/build.gradle services/terra-sense/settings.gradle ./
COPY services/terra-sense/src ./src
COPY docs/contracts /workspace/docs/contracts
RUN gradle build --no-daemon -x test

FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=builder /workspace/services/terra-sense/build/libs/*.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
