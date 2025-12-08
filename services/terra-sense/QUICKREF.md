# 🎯 Terra-Sense Quick Reference

## Core Java Files

### 1️⃣ **SensorData.java** (Data Model)
```java
@Data
@Builder
public class SensorData {
    private String farmId;       // Required: Farm identifier
    private String sensorType;   // Required: temperature, humidity, co2, etc.
    private Double value;        // Required: Measured value
    private Instant timestamp;   // Auto-set if not provided
}
```

### 2️⃣ **KafkaProducerService.java** (Kafka Publisher)
```java
@Service
public class KafkaProducerService {
    public void sendSensorData(SensorData sensorData) {
        kafkaTemplate.send("raw-sensor-data", farmId, sensorData);
    }
}
```

### 3️⃣ **IngestionController.java** (REST API)
```java
@RestController
@RequestMapping("/api/v1/ingest")
public class IngestionController {
    
    @PostMapping("/sensor-data")
    public ResponseEntity<?> ingestSensorData(@RequestBody SensorData data) {
        kafkaProducerService.sendSensorData(data);
        return ResponseEntity.accepted().build();
    }
}
```

---

## 🧪 Test Commands

### Local Test
```bash
# Start service
cd services/terra-sense
./gradlew bootRun

# Test (in another terminal)
curl http://localhost:8081/api/v1/ingest/health
```

### Docker Test
```bash
# Build
docker build -t terra-sense .

# Run
docker run -p 8081:8081 -e SPRING_KAFKA_BOOTSTRAP_SERVERS=kafka:9092 terra-sense
```

### API Test
```bash
curl -X POST http://localhost:8081/api/v1/ingest/sensor-data \
  -H "Content-Type: application/json" \
  -d '{"farmId":"farm-A","sensorType":"temperature","value":25.5}'
```

---

## 📦 Dependencies (build.gradle)
```gradle
// Core Spring Boot
implementation 'org.springframework.boot:spring-boot-starter-web'
implementation 'org.springframework.boot:spring-boot-starter-actuator'

// Kafka
implementation 'org.springframework.kafka:spring-kafka'

// Lombok
compileOnly 'org.projectlombok:lombok'
annotationProcessor 'org.projectlombok:lombok'

// Metrics
implementation 'io.micrometer:micrometer-registry-prometheus'
```

---

## 🔧 Configuration (application.properties)
```properties
server.port=8081
spring.kafka.bootstrap-servers=localhost:9092
kafka.topic.raw-sensor-data=raw-sensor-data
```

---

## 🐳 Dockerfile
```dockerfile
FROM gradle:8.5-jdk17 AS builder
WORKDIR /app
COPY build.gradle settings.gradle ./
COPY src ./src
RUN gradle build --no-daemon -x test

FROM eclipse-temurin:17-jre-alpine
COPY --from=builder /app/build/libs/*.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 📊 Data Flow
```
IoT Device → HTTP POST → IngestionController 
    → KafkaProducerService 
    → Kafka (raw-sensor-data topic) 
    → terra-cortex
```

---

## ✅ All Files Present

- [x] `build.gradle` - Dependencies
- [x] `Dockerfile` - Multi-stage build
- [x] `TerraSenseApplication.java` - Main class
- [x] `SensorData.java` - Data model
- [x] `KafkaProducerService.java` - Kafka producer
- [x] `IngestionController.java` - REST API
- [x] `KafkaConfig.java` - Configuration
- [x] `application.properties` - Settings
- [x] `IMPLEMENTATION.md` - Full docs
- [x] `README.md` - Overview

**Status: ✅ COMPLETE**
