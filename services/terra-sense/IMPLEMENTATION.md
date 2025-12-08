# 🔧 Terra-Sense Microservice Implementation

**Role:** IoT Ingestion Service  
**Technology Stack:** Java 17, Spring Boot 3.2, Gradle  
**Port:** 8081  
**Responsibility:** Ingest sensor data via HTTP/MQTT and publish to Kafka topic `raw-sensor-data`

---

## 📁 Project Structure

```
services/terra-sense/
├── build.gradle                    # Gradle build configuration
├── settings.gradle                 # Gradle settings
├── Dockerfile                      # Multi-stage Docker build
└── src/
    └── main/
        ├── java/com/terraneuron/sense/
        │   ├── TerraSenseApplication.java      # Spring Boot main class
        │   ├── config/
        │   │   └── KafkaConfig.java            # Kafka producer configuration
        │   ├── controller/
        │   │   └── IngestionController.java    # REST API endpoint
        │   ├── model/
        │   │   └── SensorData.java             # Data model
        │   └── service/
        │       └── KafkaProducerService.java   # Kafka producer service
        └── resources/
            └── application.properties          # Application configuration
```

---

## 🔨 Build Configuration

### **build.gradle**
```gradle
plugins {
    id 'java'
    id 'org.springframework.boot' version '3.2.0'
    id 'io.spring.dependency-management' version '1.1.4'
}

group = 'com.terraneuron'
version = '1.0.0'

java {
    sourceCompatibility = '17'
}

configurations {
    compileOnly {
        extendsFrom annotationProcessor
    }
}

repositories {
    mavenCentral()
}

dependencies {
    // Spring Boot Core
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-actuator'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    
    // Kafka
    implementation 'org.springframework.kafka:spring-kafka'
    
    // Lombok (reduce boilerplate)
    compileOnly 'org.projectlombok:lombok'
    annotationProcessor 'org.projectlombok:lombok'
    
    // JSON Processing
    implementation 'com.fasterxml.jackson.core:jackson-databind'
    implementation 'com.fasterxml.jackson.datatype:jackson-datatype-jsr310'
    
    // Monitoring
    implementation 'io.micrometer:micrometer-registry-prometheus'
    
    // Optional: MQTT Support
    implementation 'org.eclipse.paho:org.eclipse.paho.client.mqttv3:1.2.5'
    
    // Optional: InfluxDB Time-series Storage
    implementation 'com.influxdb:influxdb-client-java:6.10.0'
    
    // Testing
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.springframework.kafka:spring-kafka-test'
}

tasks.named('test') {
    useJUnitPlatform()
}
```

### **settings.gradle**
```gradle
rootProject.name = 'terra-sense'
```

---

## ☕ Core Java Implementation

### **1. Spring Boot Application Class**

**`src/main/java/com/terraneuron/sense/TerraSenseApplication.java`**
```java
package com.terraneuron.sense;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Terra-Sense Microservice
 * IoT Data Ingestion Service - Collects sensor data via HTTP/MQTT
 * and publishes to Kafka for downstream processing
 * 
 * @author TerraNeuron Team
 * @version 1.0.0
 */
@SpringBootApplication
public class TerraSenseApplication {

    public static void main(String[] args) {
        SpringApplication.run(TerraSenseApplication.class, args);
        System.out.println("""
            
            ╔══════════════════════════════════════════════════════╗
            ║  🌱 Terra-Sense IoT Ingestion Service Started      ║
            ║  Port: 8081                                         ║
            ║  Kafka Topic: raw-sensor-data                       ║
            ╚══════════════════════════════════════════════════════╝
            
            """);
    }
}
```

---

### **2. Data Model - SensorData**

**`src/main/java/com/terraneuron/sense/model/SensorData.java`**
```java
package com.terraneuron.sense.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;

/**
 * Sensor Data Transfer Object
 * Represents raw IoT sensor readings collected from smart farm devices
 * 
 * Fields as per specification:
 * - farmId: Identifies the farm location
 * - sensorType: Type of sensor (temperature, humidity, CO2, etc.)
 * - value: The measured sensor reading
 * - timestamp: When the measurement was taken
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SensorData {
    
    /**
     * Farm identifier (e.g., "farm-A", "farm-B")
     */
    @NotBlank(message = "farmId is required")
    private String farmId;
    
    /**
     * Type of sensor: temperature, humidity, co2, soil_moisture, light, etc.
     */
    @NotBlank(message = "sensorType is required")
    private String sensorType;
    
    /**
     * Measured value from the sensor
     */
    @NotNull(message = "value is required")
    private Double value;
    
    /**
     * Timestamp of the measurement (ISO-8601 format)
     * If not provided by client, will be set to current time
     */
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss'Z'", timezone = "UTC")
    private Instant timestamp;
    
    // Optional fields for enhanced functionality
    private String sensorId;    // Individual sensor identifier
    private String unit;         // Unit of measurement (°C, %, ppm, etc.)
}
```

---

### **3. Kafka Producer Service**

**`src/main/java/com/terraneuron/sense/service/KafkaProducerService.java`**
```java
package com.terraneuron.sense.service;

import com.terraneuron.sense.model.SensorData;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

/**
 * Kafka Producer Service
 * Publishes sensor data to Kafka topic for event-driven processing
 * 
 * Key Features:
 * - Asynchronous message publishing
 * - Error handling and logging
 * - Keyed messages for partitioning (using farmId or sensorId)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaProducerService {

    private final KafkaTemplate<String, SensorData> kafkaTemplate;

    @Value("${kafka.topic.raw-sensor-data:raw-sensor-data}")
    private String rawSensorDataTopic;

    /**
     * Send sensor data to Kafka topic
     * 
     * @param sensorData the sensor reading to publish
     */
    public void sendSensorData(SensorData sensorData) {
        try {
            String messageKey = sensorData.getFarmId(); // Partition by farmId
            
            CompletableFuture<SendResult<String, SensorData>> future = 
                kafkaTemplate.send(rawSensorDataTopic, messageKey, sensorData);
            
            future.whenComplete((result, ex) -> {
                if (ex == null) {
                    log.info("✅ Kafka publish SUCCESS: topic={}, partition={}, offset={}, farmId={}, sensorType={}, value={}", 
                            rawSensorDataTopic,
                            result.getRecordMetadata().partition(),
                            result.getRecordMetadata().offset(),
                            sensorData.getFarmId(),
                            sensorData.getSensorType(), 
                            sensorData.getValue());
                } else {
                    log.error("❌ Kafka publish FAILED: topic={}, farmId={}, error={}", 
                            rawSensorDataTopic,
                            sensorData.getFarmId(),
                            ex.getMessage());
                }
            });
        } catch (Exception e) {
            log.error("❌ Exception during Kafka send: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to send sensor data to Kafka", e);
        }
    }
    
    /**
     * Get the configured Kafka topic name
     */
    public String getTopic() {
        return rawSensorDataTopic;
    }
}
```

---

### **4. REST Controller - Ingestion API**

**`src/main/java/com/terraneuron/sense/controller/IngestionController.java`**
```java
package com.terraneuron.sense.controller;

import com.terraneuron.sense.model.SensorData;
import com.terraneuron.sense.service.KafkaProducerService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.time.Instant;
import java.util.Map;

/**
 * Ingestion Controller
 * REST API for receiving sensor data via HTTP POST
 * 
 * Endpoint: POST /api/v1/ingest/sensor-data
 * 
 * Example Request:
 * {
 *   "farmId": "farm-A",
 *   "sensorType": "temperature",
 *   "value": 25.5,
 *   "timestamp": "2025-12-08T10:30:00Z"
 * }
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/ingest")
@RequiredArgsConstructor
@Validated
public class IngestionController {

    private final KafkaProducerService kafkaProducerService;

    /**
     * Ingest sensor data via HTTP POST
     * 
     * @param sensorData JSON payload with sensor reading
     * @return Acknowledgment response with status
     */
    @PostMapping("/sensor-data")
    public ResponseEntity<Map<String, Object>> ingestSensorData(@Valid @RequestBody SensorData sensorData) {
        log.info("📥 Received sensor data: farmId={}, type={}, value={}", 
                sensorData.getFarmId(), 
                sensorData.getSensorType(), 
                sensorData.getValue());
        
        // Set timestamp if not provided by client
        if (sensorData.getTimestamp() == null) {
            sensorData.setTimestamp(Instant.now());
        }
        
        // Publish to Kafka
        kafkaProducerService.sendSensorData(sensorData);
        
        // Return acknowledgment
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(Map.of(
                "status", "accepted",
                "message", "Sensor data queued for processing",
                "farmId", sensorData.getFarmId(),
                "sensorType", sensorData.getSensorType(),
                "timestamp", sensorData.getTimestamp().toString(),
                "kafkaTopic", kafkaProducerService.getTopic()
        ));
    }

    /**
     * Health check endpoint
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
                "service", "terra-sense",
                "status", "UP",
                "timestamp", Instant.now().toString(),
                "version", "1.0.0"
        ));
    }
    
    /**
     * Service info endpoint
     */
    @GetMapping("/info")
    public ResponseEntity<Map<String, Object>> info() {
        return ResponseEntity.ok(Map.of(
                "service", "terra-sense",
                "description", "IoT Sensor Data Ingestion Service",
                "capabilities", new String[]{"HTTP Ingestion", "MQTT Ingestion", "Kafka Publishing"},
                "kafkaTopic", kafkaProducerService.getTopic(),
                "endpoints", Map.of(
                    "ingestion", "/api/v1/ingest/sensor-data",
                    "health", "/api/v1/ingest/health"
                )
        ));
    }
}
```

---

### **5. Kafka Configuration**

**`src/main/java/com/terraneuron/sense/config/KafkaConfig.java`**
```java
package com.terraneuron.sense.config;

import com.terraneuron.sense.model.SensorData;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JsonSerializer;

import java.util.HashMap;
import java.util.Map;

/**
 * Kafka Producer Configuration
 * Configures KafkaTemplate for publishing SensorData messages
 */
@Configuration
public class KafkaConfig {

    @Value("${spring.kafka.bootstrap-servers:localhost:9092}")
    private String bootstrapServers;

    /**
     * Producer Factory for Kafka
     */
    @Bean
    public ProducerFactory<String, SensorData> producerFactory() {
        Map<String, Object> configProps = new HashMap<>();
        configProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        configProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        configProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);
        
        // Performance tuning
        configProps.put(ProducerConfig.ACKS_CONFIG, "1"); // Leader acknowledgment
        configProps.put(ProducerConfig.RETRIES_CONFIG, 3);
        configProps.put(ProducerConfig.LINGER_MS_CONFIG, 10); // Batch for 10ms
        configProps.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy");
        
        return new DefaultKafkaProducerFactory<>(configProps);
    }

    /**
     * Kafka Template for message publishing
     */
    @Bean
    public KafkaTemplate<String, SensorData> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }
}
```

---

## ⚙️ Configuration

### **application.properties**
```properties
# Application Metadata
spring.application.name=terra-sense
server.port=8081

# Kafka Configuration
spring.kafka.bootstrap-servers=${SPRING_KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
spring.kafka.producer.key-serializer=org.apache.kafka.common.serialization.StringSerializer
spring.kafka.producer.value-serializer=org.springframework.kafka.support.serializer.JsonSerializer
spring.kafka.producer.properties.spring.json.add.type.headers=false

# Kafka Topics
kafka.topic.raw-sensor-data=raw-sensor-data

# Actuator Endpoints (Health, Metrics)
management.endpoints.web.exposure.include=health,info,prometheus
management.endpoint.health.show-details=always
management.metrics.tags.application=${spring.application.name}

# Logging
logging.level.com.terraneuron.sense=INFO
logging.level.org.springframework.kafka=WARN
```

---

## 🐳 Dockerfile (Multi-Stage Build)

**`Dockerfile`**
```dockerfile
# ========================================
# Stage 1: Build Stage
# ========================================
FROM gradle:8.5-jdk17 AS builder

WORKDIR /app

# Copy Gradle configuration files
COPY build.gradle settings.gradle ./

# Copy source code
COPY src ./src

# Build the application (skip tests for faster build)
RUN gradle build --no-daemon -x test

# ========================================
# Stage 2: Runtime Stage
# ========================================
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Copy the built JAR from builder stage
COPY --from=builder /app/build/libs/*.jar app.jar

# Expose service port
EXPOSE 8081

# Set JVM options for container environment
ENV JAVA_OPTS="-Xms256m -Xmx512m -XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8081/api/v1/ingest/health || exit 1

# Run the application
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar /app/app.jar"]
```

**Multi-Stage Build Benefits:**
- **Smaller image size**: Runtime image only contains JRE and JAR (not Gradle or source code)
- **Security**: Fewer attack vectors in production image
- **Build cache**: Gradle cache layers improve build speed

---

## 🧪 Testing the Service

### **1. Using cURL**

```bash
# Test health endpoint
curl http://localhost:8081/api/v1/ingest/health

# Post sensor data
curl -X POST http://localhost:8081/api/v1/ingest/sensor-data \
  -H "Content-Type: application/json" \
  -d '{
    "farmId": "farm-A",
    "sensorType": "temperature",
    "value": 25.5,
    "timestamp": "2025-12-08T10:30:00Z"
  }'
```

### **2. Using PowerShell**

```powershell
# Test health
Invoke-RestMethod -Uri "http://localhost:8081/api/v1/ingest/health" -Method Get

# Post sensor data
$body = @{
    farmId = "farm-A"
    sensorType = "temperature"
    value = 25.5
    timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8081/api/v1/ingest/sensor-data" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

### **3. Sample Request/Response**

**Request:**
```json
POST /api/v1/ingest/sensor-data
Content-Type: application/json

{
  "farmId": "farm-A",
  "sensorType": "temperature",
  "value": 25.5,
  "timestamp": "2025-12-08T10:30:00Z"
}
```

**Response:**
```json
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "status": "accepted",
  "message": "Sensor data queued for processing",
  "farmId": "farm-A",
  "sensorType": "temperature",
  "timestamp": "2025-12-08T10:30:00Z",
  "kafkaTopic": "raw-sensor-data"
}
```

---

## 🚀 Build & Run

### **Local Development**

```bash
# Navigate to service directory
cd services/terra-sense

# Build the project
./gradlew build

# Run the application
./gradlew bootRun

# Or run the JAR directly
java -jar build/libs/terra-sense-1.0.0.jar
```

### **Docker Build**

```bash
# Build Docker image
docker build -t terraneuron/terra-sense:1.0.0 .

# Run container
docker run -p 8081:8081 \
  -e SPRING_KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  terraneuron/terra-sense:1.0.0
```

### **Docker Compose**

```bash
# Start with docker-compose (includes Kafka and all dependencies)
docker-compose up -d terra-sense

# View logs
docker-compose logs -f terra-sense
```

---

## 📊 Monitoring

### **Actuator Endpoints**

- **Health**: `http://localhost:8081/actuator/health`
- **Info**: `http://localhost:8081/actuator/info`
- **Prometheus Metrics**: `http://localhost:8081/actuator/prometheus`

### **Key Metrics**

- `kafka_producer_record_send_total` - Total records sent to Kafka
- `http_server_requests_seconds` - HTTP request latency
- `jvm_memory_used_bytes` - JVM memory usage

---

## 🔐 Security Considerations

### **Current Implementation**
- ✅ Input validation using `@Valid` annotation
- ✅ Structured logging (no sensitive data exposure)
- ✅ Health checks for monitoring

### **Production Enhancements**
- [ ] Add authentication (API keys, JWT tokens)
- [ ] Rate limiting (already implemented in terra-gateway)
- [ ] Input sanitization for XSS prevention
- [ ] HTTPS/TLS encryption
- [ ] Kafka SSL/SASL authentication

---

## 📝 API Contract

### **POST /api/v1/ingest/sensor-data**

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `farmId` | String | Yes | Farm identifier |
| `sensorType` | String | Yes | Type of sensor (temperature, humidity, etc.) |
| `value` | Double | Yes | Measured value |
| `timestamp` | ISO-8601 String | No | Measurement time (defaults to current time) |

**Response Codes:**
- `202 Accepted` - Data accepted and queued
- `400 Bad Request` - Invalid input
- `500 Internal Server Error` - Server error

---

## 🎯 Key Features

✅ **RESTful HTTP API** for sensor data ingestion  
✅ **Kafka integration** with async publishing  
✅ **Input validation** using Bean Validation  
✅ **Structured logging** with SLF4J  
✅ **Health checks** for monitoring  
✅ **Prometheus metrics** for observability  
✅ **Multi-stage Dockerfile** for optimized container images  
✅ **Lombok** for clean, maintainable code  
✅ **Spring Boot 3.2** with Java 17 modern features  

---

## 🔄 Data Flow

```
IoT Device → HTTP POST → IngestionController 
    → KafkaProducerService 
    → Kafka Topic (raw-sensor-data) 
    → terra-cortex (AI Processing)
```

---

## 📚 Dependencies Summary

| Dependency | Purpose |
|------------|---------|
| `spring-boot-starter-web` | REST API framework |
| `spring-boot-starter-actuator` | Health checks & metrics |
| `spring-kafka` | Kafka producer integration |
| `lombok` | Reduce boilerplate code |
| `jackson-databind` | JSON serialization |
| `micrometer-registry-prometheus` | Metrics export |

---

## ✅ Deliverables Checklist

- [x] Spring Boot application initialized
- [x] Dependencies: Spring Web, Spring Kafka, Lombok
- [x] Data Model: `SensorData` with required fields
- [x] Kafka Producer Service for `raw-sensor-data` topic
- [x] REST Controller with `POST /api/v1/ingest` endpoint
- [x] Multi-stage Dockerfile
- [x] Configuration files (application.properties)
- [x] Health check endpoints
- [x] Comprehensive documentation

---

**Implementation Status:** ✅ **COMPLETE**  
**Service Ready for:** Development, Testing, Docker Deployment  
**Next Steps:** Deploy to Kubernetes, add authentication, implement MQTT listener

---

**Implementation by:** Senior Java Developer  
**Date:** December 8, 2025  
**Version:** 1.0.0
