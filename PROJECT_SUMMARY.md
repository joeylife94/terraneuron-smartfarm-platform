# 🌿 TerraNeuron Smart Farm Platform - Project Summary

**Generated for Senior Architect Code Review**  
**Date:** December 9, 2025  
**Historical Snapshot Updated:** January 2026 (Phase 2.A + Phase 3)  
**Architecture Pattern:** Microservices (MSA) with Event-Driven Architecture (EDA)  
**Current Evidence Status:** **Bounded software Proof — see `STATUS.md` for authoritative accepted D1/D2 evidence and non-claims**  
**Historical Phase Marker:** Phase 3 - CloudEvents + software safety guards + JWT security

> **Authority / truthfulness note (2026-09):** `STATUS.md` is the authoritative implementation/evidence boundary. This document originated as a December 2025–January 2026 architecture review and retains historical implementation notes and small local/synthetic test observations where useful. Those historical observations are **not** production validation, load/performance certification, physical-device validation, manufacturer validation, field-safety evidence, HA/DR evidence, or public-production readiness. Current accepted scope is the bounded D1 command-lifecycle software Proof plus the D2 Synthetic Farm Operations Pilot.

---

## 📋 Executive Summary

TerraNeuron is a production-oriented **event-driven microservices architecture prototype** for smart-farm IoT data management and AI-assisted analysis. The system follows neural network-inspired naming conventions, where three core microservices (terra-sense, terra-cortex, terra-ops) work together to collect, analyze, and manage software-reported agricultural sensor data.

### Key Highlights
- ✅ **4 microservices** (3 core + 1 API Gateway)
- ✅ **Event-driven architecture** with Apache Kafka
- ✅ **Polyglot persistence** (MySQL, InfluxDB, Redis, ChromaDB)
- ✅ **Observability stack components** (Prometheus + Grafana)
- ✅ **CI/CD workflows** (GitHub Actions)
- ✅ **Security layers** (API Gateway, rate limiting, authentication)
- ✅ **Comprehensive documentation** (README, CONTRIBUTING, DEPLOYMENT, TROUBLESHOOTING)
- ✅ **Historical local E2E sample retained for context** (December 2025; not a production/load claim)
- ✅ **Hybrid AI + RAG Architecture** (Local Edge + Cloud LLM + Knowledge Base)
- ✅ **HTML Test Reporter** (AI verification, performance fields, color-coded results)
- ✅ **CloudEvents v1.0 Standard** (Phase 2.A - Action Protocol Implementation)
- ✅ **Software safety validation layers** (Logical, Context, Permission, Device) - IMPLEMENTED; not physical-safety evidence
- ✅ **Distributed Tracing** (Mandatory trace_id propagation) - IMPLEMENTED
- ✅ **FarmOS-compatible model mapping** (Asset/Log/Plan unified model) - IMPLEMENTED within repository scope
- ✅ **JWT Authentication** (Phase 3 - Role-based Access Control)
- ✅ **Software audit logging** (event history for traceability)

---

## 🏗️ System Architecture

### High-Level Data Flow (software architecture)
```
IoT Sensors → HTTP POST → terra-sense → Kafka (raw-sensor-data) → terra-cortex (AI) → Kafka (processed-insights) → terra-ops → MySQL
                             ↓                                                                                             ↓
                         InfluxDB                                                                                    Dashboard API

📊 Historical December 2025 local/synthetic run observations (non-authoritative for current production readiness):
- HTTP Ingestion: 15/15 requests succeeded in that bounded run
- AI Detection: 1 configured threshold anomaly observed (Temperature 39.98°C > 30°C threshold)
- Data Persistence: 25 insights present in MySQL for that run
- E2E Latency: approximately 1-2 seconds in that environment
```

### Microservices Overview

| Service | Technology | Port | Responsibility |
|---------|-----------|------|----------------|
| **terra-gateway** | Java 17 + Spring Cloud Gateway | 8000 | API Gateway with Redis-based rate limiting |
| **terra-sense** | Java 17 + Spring Boot 3.2 | 8081 | IoT data ingestion (HTTP POST) → Kafka producer |
| **terra-cortex** | Python 3.10 + FastAPI (async) + OpenAI/Ollama + RAG | 8082 | 3-stage AI: Local Edge + Cloud LLM + Knowledge Base |
| **terra-ops** | Java 17 + Spring Boot 3.2 + JPA + Spring Security | 8083 (mapped from 8080) | Management & Dashboard API + Action Protocol + JWT Auth |

### Infrastructure Components

| Component | Version | Purpose |
|-----------|---------|---------|  
| **Apache Kafka** | 7.5 | Event streaming backbone |
| **Zookeeper** | 7.5 | Kafka coordination |
| **MySQL** | 8.0 | Relational data (farms, sensors, insights, alerts) |
| **InfluxDB** | 2.7 | Time-series sensor data |
| **Mosquitto** | Latest | MQTT broker for IoT devices |
| **Redis** | 7 | Rate limiting cache |
| **ChromaDB** | Latest | Vector database for RAG knowledge base |
| **Prometheus** | 2.48 | Metrics collection |
| **Grafana** | 10.2 | Visualization dashboards |

---

## 📁 Repository Structure

```
terraneuron-smartfarm-platform/
├── services/
│   ├── terra-gateway/           # API Gateway Service
│   │   ├── src/main/java/com/terraneuron/gateway/
│   │   ├── src/main/resources/application.yml
│   │   ├── build.gradle
│   │   └── Dockerfile
│   ├── terra-sense/             # IoT Ingestion Service
│   │   ├── src/main/java/com/terraneuron/sense/
│   │   │   ├── TerraSenseApplication.java
│   │   │   ├── controller/IngestionController.java
│   │   │   ├── model/SensorData.java
│   │   │   └── service/KafkaProducerService.java
│   │   ├── src/main/resources/application.yml
│   │   ├── build.gradle
│   │   └── Dockerfile
│   ├── terra-cortex/            # AI Analysis Service
│   │   ├── src/
│   │   │   ├── main.py          # FastAPI entry point
│   │   │   ├── ai_engine.py     # AnomalyDetector class
│   │   │   ├── kafka_service.py # Kafka consumer/producer
│   │   │   ├── models.py        # Pydantic models
│   │   │   └── config.py        # Settings management
│   │   ├── requirements.txt
│   │   └── Dockerfile
   └── terra-ops/               # Management & Dashboard Service
       ├── src/main/java/com/terraneuron/ops/
       │   ├── TerraOpsApplication.java
       │   ├── controller/DashboardController.java
       │   ├── entity/
       │   │   ├── Insight.java         # JPA entity (id, farmId, status, message, timestamp)
       │   │   └── Sensor.java          # Additional sensor entity
       │   ├── repository/
       │   │   ├── InsightRepository.java  # Spring Data JPA for insights
       │   │   └── SensorRepository.java   # Spring Data JPA for sensors
       │   ├── service/KafkaConsumerService.java
       │   └── dto/InsightDto.java      # Kafka message DTO
       ├── src/main/resources/application.properties
       ├── build.gradle
       ├── Dockerfile
       ├── IMPLEMENTATION.md    # Detailed implementation guide
       ├── README.md            # Service documentation
       └── QUICKREF.md          # Quick reference for developers
├── infra/
│   ├── prometheus/
│   │   └── prometheus.yml       # Scrape configurations
│   ├── grafana/
│   │   ├── dashboards/
│   │   └── provisioning/
│   └── mosquitto/
│       └── mosquitto.conf       # MQTT broker config
├── tools/
│   └── sensor-simulator.py      # Data generator (4 modes: normal/anomaly/mixed/stress)
├── tests/
│   ├── simulation.py            # E2E pipeline simulation/testing tool
│   ├── neural-flow-test.py      # End-to-end integration test
│   ├── README.md                # Complete testing guide
│   ├── QUICKSTART.md            # 5-minute quick start guide
│   └── IMPLEMENTATION_SUMMARY.md # Testing implementation details
├── .github/workflows/
│   ├── ci-cd.yml                # Build, test, Docker push
│   └── security-scan.yml        # Trivy vulnerability scanning
├── docs/
│   ├── DEPLOYMENT.md            # Deployment guide (local/cloud/K8s)
│   └── TROUBLESHOOTING.md       # Common issues and solutions
├── docker-compose.yml           # Complete orchestration (13 services)
├── README.md                    # Project documentation with Mermaid diagram
├── CONTRIBUTING.md              # Contribution guidelines
├── QUICKSTART.md                # Quick start guide
└── PROJECT_SUMMARY.md           # This file
```

---

## 🐳 Docker Compose Configuration

### Full Service Stack (13 Services)

**docker-compose.yml** orchestrates the entire system:

```yaml
services:
  # Infrastructure Layer
  - redis           # Rate limiting cache
  - zookeeper       # Kafka coordination
  - kafka           # Event streaming
  - mysql           # Relational database
  - influxdb        # Time-series database
  - mosquitto       # MQTT broker

  # Monitoring Layer
  - prometheus      # Metrics scraper
  - grafana         # Visualization
  - kafka-exporter  # Kafka metrics
  - mysql-exporter  # MySQL metrics

  # Application Layer
  - terra-gateway   # Port 8000 - API Gateway
  - terra-sense     # Port 8081 - IoT Ingestion
  - terra-cortex    # Port 8082 - AI Engine
  - terra-ops       # Port 8080 - Dashboard API
```

### Key Configuration Highlights

**Networking:**
- Bridge network `terra-network` for inter-service communication
- Port mappings for external access (8000, 8080-8082, 9090, 3000)

**Persistence:**
- Named volumes: `mysql_data`, `influxdb_data`, `grafana_data`, `kafka_data`, `zookeeper_data`
- Provides persistent local volumes across ordinary container restarts; this is not backup/DR evidence

**Health Checks:**
- Services include configured health/dependency checks where implemented
- These checks support local orchestration; they are not production availability/HA evidence

**Environment Configuration:**
- Centralized via `.env` file support
- Service discovery via Docker DNS (e.g., `kafka:9092`, `mysql:3306`)

---

## 🔧 Technology Stack Details

### Java Services (terra-gateway, terra-sense, terra-ops)

**build.gradle common dependencies:**
```gradle
- Spring Boot 3.2.0
- Java 17
- Spring Kafka
- Spring Boot Actuator
- Micrometer Prometheus Registry
- Lombok
- Jackson (JSON processing)
```

**terra-gateway specific:**
- Spring Cloud Gateway 2023.0.0
- Spring Data Redis Reactive (rate limiting)

**terra-sense specific:**
- Eclipse Paho MQTT Client 1.2.5
- InfluxDB Client 6.10.0

**terra-ops specific:**
- Spring Data JPA
- MySQL Connector
- SpringDoc OpenAPI 2.3.0 (Swagger UI)

### Python Service (terra-cortex)

**requirements.txt:**
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
aiokafka==0.8.1          # Async Kafka client
pydantic==2.5.3
python-dateutil==2.8.2
```

**Key Implementation Details:**
- **Async Architecture**: Uses `aiokafka` for non-blocking Kafka operations
- **MVP Logic**: Simple rule-based anomaly detection (temp > 30°C or humidity < 40% = ANOMALY)
- **Message Format**: Produces insights with `farmId`, `status`, `message`, `timestamp` to `processed-insights` topic

---

## 🔍 Core Implementation Details

### 1. terra-sense (IoT Ingestion)

**TerraSenseApplication.java:**
```java
@SpringBootApplication
public class TerraSenseApplication {
    public static void main(String[] args) {
        SpringApplication.run(TerraSenseApplication.class, args);
    }
}
```

**IngestionController.java:**
```java
@RestController
@RequestMapping("/api/v1/ingest")
public class IngestionController {
    private final KafkaProducerService kafkaProducerService;

    @PostMapping("/sensor-data")
    public ResponseEntity<?> ingestSensorData(@RequestBody SensorData sensorData) {
        if (sensorData.getTimestamp() == null) {
            sensorData.setTimestamp(Instant.now());
        }
        kafkaProducerService.sendSensorData(sensorData);
        return ResponseEntity.ok(Map.of("status", "accepted"));
    }
}
```

**Data Flow:**
1. Receives sensor data via HTTP POST or MQTT subscription
2. Validates and enriches data (timestamp, metadata)
3. Publishes to Kafka topic: `raw-sensor-data`
4. Writes time-series data to InfluxDB for historical analysis

---

### 2. terra-cortex (AI Analysis Engine)

**main.py (Async FastAPI + Kafka Consumer):**
```python
from fastapi import FastAPI
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

app = FastAPI(
    title="Terra-Cortex AI Engine",
    description="🧠 Anomaly Detection for Smart Farm IoT Data"
)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(kafka_consumer_loop())

async def kafka_consumer_loop():
    """Continuously consume from raw-sensor-data and produce to processed-insights"""
    consumer = AIOKafkaConsumer('raw-sensor-data', bootstrap_servers='kafka:9092')
    producer = AIOKafkaProducer(bootstrap_servers='kafka:9092')
    
    await consumer.start()
    await producer.start()
    
    async for message in consumer:
        sensor_data = json.loads(message.value.decode('utf-8'))
        insight = analyze_sensor_data(sensor_data)  # MVP logic
        await producer.send('processed-insights', json.dumps(insight).encode('utf-8'))
```

**logic.py - MVP Anomaly Detection:**
```python
def analyze_sensor_data(data: dict) -> dict:
    """Simple rule-based anomaly detection"""
    status = "NORMAL"
    message = "All parameters within normal range"
    
    if data.get('temperature', 0) > 30:
        status = "ANOMALY"
        message = f"Temperature exceeds threshold: {data['temperature']}°C > 30°C"
    elif data.get('humidity', 100) < 40:
        status = "ANOMALY"
        message = f"Humidity below threshold: {data['humidity']}% < 40%"
    
    return {
        "farmId": data.get('sensorId', 'unknown'),
        "status": status,
        "message": message,
        "timestamp": data.get('timestamp', datetime.utcnow().isoformat())
    }
```

**Processing Pipeline:**
1. **Async Kafka Consumer**: Listens to `raw-sensor-data` topic (non-blocking)
2. **MVP Analysis Logic**: Simple threshold-based detection (temp > 30°C or humidity < 40%)
3. **Insight Generation**: Creates structured insights with `farmId`, `status`, `message`, `timestamp`
4. **Async Kafka Producer**: Publishes to `processed-insights` topic
5. **Async Processing**: Non-blocking I/O is implemented; no current throughput/load claim is made here

---

### 3. terra-ops (Management & Dashboard Service)

**TerraOpsApplication.java:**
```java
@SpringBootApplication
public class TerraOpsApplication {
    public static void main(String[] args) {
        SpringApplication.run(TerraOpsApplication.class, args);
    }
}
```

**Insight.java (JPA Entity - Simplified Structure):**
```java
@Entity
@Table(name = "insights", indexes = {
    @Index(name = "idx_farm_id", columnList = "farm_id"),
    @Index(name = "idx_status", columnList = "status"),
    @Index(name = "idx_timestamp", columnList = "timestamp")
})
public class Insight {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "farm_id", nullable = false)
    private String farmId;        // Farm/Sensor identifier
    
    @Column(name = "status", nullable = false)
    private String status;         // "NORMAL" or "ANOMALY"
    
    @Column(name = "message", columnDefinition = "TEXT")
    private String message;        // Human-readable insight description
    
    @Column(name = "timestamp", nullable = false)
    private Instant timestamp;     // When the insight was detected
    
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;     // Database insertion timestamp
}
```

**KafkaConsumerService.java:**
```java
@Service
public class KafkaConsumerService {
    private final InsightRepository insightRepository;

    @KafkaListener(topics = "processed-insights", groupId = "terra-ops-group")
    public void consumeInsight(InsightDto insightDto) {
        log.info("📥 Kafka Received: farmId={}, status={}", 
                insightDto.getFarmId(), insightDto.getStatus());
        
        Insight insight = Insight.builder()
                .farmId(insightDto.getFarmId())
                .status(insightDto.getStatus())
                .message(insightDto.getMessage())
                .timestamp(insightDto.getTimestamp())
                .build();
        
        insightRepository.save(insight);
        log.info("✅ Insight saved: ID={}", insight.getId());
    }
}
```

**DashboardController.java:**
```java
@RestController
@RequestMapping("/api/v1")
public class DashboardController {
    private final InsightRepository insightRepository;

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        return ResponseEntity.ok(Map.of(
            "service", "terra-ops",
            "status", "healthy",
            "timestamp", Instant.now()
        ));
    }

    @GetMapping("/dashboard/insights")
    public ResponseEntity<List<Insight>> getDashboardInsights() {
        return ResponseEntity.ok(insightRepository.findAllByOrderByTimestampDesc());
    }

    @GetMapping("/insights/farm/{farmId}")
    public ResponseEntity<List<Insight>> getInsightsByFarm(@PathVariable String farmId) {
        return ResponseEntity.ok(insightRepository.findByFarmId(farmId));
    }

    @GetMapping("/insights/status/{status}")
    public ResponseEntity<List<Insight>> getInsightsByStatus(@PathVariable String status) {
        return ResponseEntity.ok(insightRepository.findByStatus(status));
    }

    @GetMapping("/dashboard/summary")
    public ResponseEntity<?> getDashboardSummary() {
        long totalInsights = insightRepository.count();
        long normalInsights = insightRepository.findByStatus("NORMAL").size();
        long anomalyInsights = insightRepository.findByStatus("ANOMALY").size();
        
        return ResponseEntity.ok(Map.of(
            "totalInsights", totalInsights,
            "normalInsights", normalInsights,
            "anomalyInsights", anomalyInsights,
            "timestamp", Instant.now()
        ));
    }
}
```

**Database Schema (MySQL - Simplified):**
```sql
CREATE TABLE insights (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,        -- 'NORMAL' or 'ANOMALY'
    message TEXT,
    timestamp TIMESTAMP(6) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    INDEX idx_farm_id (farm_id),
    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp)
);
```

**REST API Endpoints (Updated):**
- `GET /api/v1/health` - Service health check
- `GET /api/v1/dashboard/insights` - **Main dashboard endpoint** (all insights, sorted by timestamp desc)
- `GET /api/v1/insights` - All insights
- `GET /api/v1/insights/farm/{farmId}` - Filter insights by farm ID
- `GET /api/v1/insights/status/{status}` - Filter by status (NORMAL/ANOMALY)
- `GET /api/v1/dashboard/summary` - Dashboard statistics (total, normal, anomaly counts)

**Key Implementation Features:**
- ✅ **Simplified Entity Model**: Single `Insight` entity with 5 core fields (id, farmId, status, message, timestamp)
- ✅ **Kafka Consumer**: Listens to `processed-insights` topic with `@KafkaListener` annotation
- ✅ **Spring Data JPA**: Repository with custom query methods (`findByFarmId`, `findByStatus`, etc.)
- ✅ **Database Indexes**: Optimized for common queries (farm_id, status, timestamp)
- ✅ **Comprehensive Documentation**: IMPLEMENTATION.md, README.md, QUICKREF.md for developers

---

### 4. terra-gateway (API Gateway)

**Features:**
- Single entry point for all microservices (port 8000)
- Redis-based distributed rate limiting (10 requests/second per user)
- CORS configuration for frontend integration
- Request routing with path rewriting

**application.yml routing:**
```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: terra-sense
          uri: http://terra-sense:8081
          predicates:
            - Path=/sense/**
          filters:
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 10
                redis-rate-limiter.burstCapacity: 20
```

---

## 📊 Monitoring & Observability

### Prometheus Configuration

**prometheus.yml:**
```yaml
scrape_configs:
  - job_name: 'terra-sense'
    static_configs:
      - targets: ['terra-sense:8081']
    metrics_path: '/actuator/prometheus'
  
  - job_name: 'terra-cortex'
    static_configs:
      - targets: ['terra-cortex:8082']
    metrics_path: '/metrics'
  
  - job_name: 'terra-ops'
    static_configs:
      - targets: ['terra-ops:8080']
    metrics_path: '/actuator/prometheus'
  
  - job_name: 'kafka-exporter'
    static_configs:
      - targets: ['kafka-exporter:9308']
  
  - job_name: 'mysql-exporter'
    static_configs:
      - targets: ['mysql-exporter:9104']
```

### Grafana Dashboards

**Provisioned Dashboards:**
1. **TerraNeuron System Overview**
   - Service health status
   - Request rates and latencies
   - Error rates

2. **Kafka Metrics**
   - Topic lag
   - Producer/consumer throughput
   - Partition metrics

3. **MySQL Performance**
   - Query performance
   - Connection pool usage
   - Table statistics

**Access:** http://localhost:3000 (admin/admin)

---

## 🚀 CI/CD Pipeline

### GitHub Actions Workflows

**ci-cd.yml:**
```yaml
name: CI/CD Pipeline
on: [push, pull_request]
jobs:
  build-java:
    strategy:
      matrix:
        service: [terra-gateway, terra-sense, terra-ops]
    steps:
      - Checkout code
      - Setup JDK 17
      - Build with Gradle
      - Run tests
      - Build Docker image
      - Push to Docker Hub
  
  build-python:
    steps:
      - Checkout code
      - Setup Python 3.11
      - Install dependencies
      - Run pytest
      - Build Docker image
      - Push to Docker Hub
  
  e2e-test:
    needs: [build-java, build-python]
    steps:
      - docker-compose up -d
      - Run neural-flow-test.py
      - Collect logs
```

**security-scan.yml:**
```yaml
name: Security Scan
on: [push, pull_request]
jobs:
  trivy-scan:
    steps:
      - Scan Docker images for CVEs
      - Upload SARIF results to GitHub Security
```

---

## 🧪 Testing & Validation

### Pipeline Simulation Script

**tests/simulation.py** - bounded end-to-end simulation/testing tool:
- **435 lines** of Python code
- **3 data generation modes:**
  - `normal` - Generated sensor values within expected ranges
  - `anomaly` - Generated out-of-range values to exercise threshold detection
  - `mixed` - 80% normal + 20% anomaly generation mode
- **5 sensor types:** Temperature, Humidity, Soil Moisture, CO2, Light
- **Run statistics:** Success rate, status code distribution, timing fields
- **Color-coded output:** ✅ success, ❌ failure, ⏱️ timeout indicators
- **CLI interface:** Configurable count, interval, mode, URL, verbose output

**Usage Examples:**
```bash
# Basic test (10 requests, mixed mode)
python tests/simulation.py

# Anomaly detection test
python tests/simulation.py --mode anomaly --count 20

# Bounded higher-rate local run (not a production load test)
python tests/simulation.py --count 100 --interval 0.1

# Verbose output with full request/response
python tests/simulation.py --mode mixed --count 30 --verbose
```

**Complete Data Flow Verification:**
```
Simulation Script → terra-sense → Kafka (raw-sensor-data) → 
terra-cortex → Kafka (processed-insights) → terra-ops → MySQL
```

**Verification Commands:**
```bash
# 1. Check service logs
docker-compose logs -f terra-sense
docker-compose logs -f terra-cortex
docker-compose logs -f terra-ops

# 2. Query MySQL database
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 terra_db -e \
  "SELECT * FROM insights ORDER BY timestamp DESC LIMIT 10"

# 3. Query Dashboard API
curl http://localhost:8083/api/v1/dashboard/insights | jq
curl http://localhost:8083/api/v1/dashboard/summary | jq
```

### Historical Local Software Run (December 8, 2025)

> The following values are retained as a **historical bounded local/synthetic run record**. They do not establish production readiness, production data quality, performance/load capacity, physical-device behavior, field reliability, or statistical AI accuracy.

**Phase 3 database-persistence exercise** - a small end-to-end software pipeline run recorded these observations.

#### SQL Query Results

**1. Total Insights Count:**
```sql
SELECT COUNT(*) as total_insights FROM insights;
-- Historical run result: 25 insights
```

**2. Threshold Detection Observation:**
```sql
SELECT id, farm_id, status, message, timestamp 
FROM insights 
WHERE status = 'ANOMALY' 
ORDER BY timestamp DESC LIMIT 5;
```
| ID | Farm | Status | Message | Timestamp |
|----|------|--------|---------|-----------|
| 11 | farm-E | ANOMALY | 🚨 Temperature is too high: 39.98°C (threshold: 30°C) | 2025-12-08 12:37:27.755762 |

**Observed threshold case:** Terra-Cortex identified the single configured temperature-threshold example in this run. This is not an accuracy benchmark.

**3. Farm-ID Distribution in the Historical Run:**
```sql
SELECT farm_id, COUNT(*) as count, 
       SUM(CASE WHEN status='ANOMALY' THEN 1 ELSE 0 END) as anomalies 
FROM insights GROUP BY farm_id ORDER BY farm_id;
```
| Farm | Total | Anomalies | Status |
|------|-------|-----------|--------|
| farm-A | 8 | 0 | ✅ sample normal |
| farm-B | 4 | 0 | ✅ sample normal |
| farm-C | 6 | 0 | ✅ sample normal |
| farm-D | 3 | 0 | ✅ sample normal |
| farm-E | 4 | 1 | ⚠️ sample threshold event |

**Historical sample:** five farm IDs were represented in this run.

**4. Timeline Observation:**
```sql
SELECT DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i') as time_window, 
       COUNT(*) as insights_count, status 
FROM insights GROUP BY time_window, status ORDER BY time_window DESC;
```
| Time Window | Count | Status |
|-------------|-------|--------|
| 2025-12-08 12:37 | 14 | NORMAL |
| 2025-12-08 12:37 | 1 | ANOMALY |
| 2025-12-08 12:21 | 10 | NORMAL |

**Historical observation:** two simulation batches were present with timestamped records.

#### Historical Run Metrics (not production/performance validation)

| Metric | Historical observation | Scope |
|--------|------------------------|-------|
| **HTTP requests** | 15/15 succeeded in the final small run | bounded local sample only |
| **Data persistence** | 25/25 generated records observed | bounded local sample only |
| **Threshold detector** | 1/1 configured anomaly example detected | single case, not accuracy statistics |
| **E2E latency** | approximately 1-2 seconds | that environment/run only |
| **Farm IDs** | 5 represented | synthetic/local sample only |

### Legacy Testing Tools

**tools/sensor-simulator.py:**
- Original data generator with 4 modes
- Used for standalone Kafka message production

**tests/neural-flow-test.py:**
- Legacy end-to-end integration test
- Validates complete software data flow (IoT-shaped input → analysis → Dashboard)

---

## 🔐 Security Considerations

### Implemented Security Measures

1. **API Gateway Rate Limiting**
   - Redis-backed token bucket algorithm
   - Per-user request throttling (10 req/sec, burst 20)

2. **Network Isolation**
   - Internal Docker bridge network
   - Local composition/exposure rules as configured in repository

3. **Container Security**
   - Multi-stage Docker builds where configured
   - Non-root execution where implemented
   - Trivy vulnerability scanning workflow

4. **Dependency Management**
   - Security/dependency scanning workflows where configured

### Production Security Gaps / Separate Evidence Required

- [ ] Production TLS/SSL boundary and certificate lifecycle
- [ ] Production MQTT/Kafka authenticated identity and authorization boundary
- [ ] Encrypted production database connections as required by deployment
- [ ] Production secrets management and rotation
- [ ] Production audit/compliance requirements

These are separate from the accepted D1/D2 bounded software Proof.

---

## 📈 Performance Characteristics

### Historical Observed Sample (December 8, 2025 — not a throughput benchmark)

| Service | Historical sample | Observed result in that run | Scope |
|---------|-------------------|-----------------------------|-------|
| **terra-sense** | 15 req/15s | 15 HTTP requests succeeded | bounded local sample |
| **terra-cortex** | 15 msg/15s | configured threshold event observed | bounded local sample |
| **terra-ops** | 15 msg/15s | generated records persisted | bounded local sample |
| **End-to-End** | small pipeline run | approximately 1-2 second latency | environment-specific observation |

### Historical Capacity-Planning Estimates (not validated/current claims)

Earlier planning notes used the following rough numbers. They are retained only as historical design context and **must not be interpreted as measured capacity or promised throughput**.

| Service | Historical planning input | Historical rough estimate |
|---------|---------------------------|---------------------------|
| **terra-sense** | 1000 sensors × 1 msg/min | ~17 msg/sec input arithmetic; scalability not validated |
| **terra-cortex** | AI processing | ~50 msg/sec was an unvalidated planning estimate |
| **terra-ops** | Dashboard queries | ~100 req/sec was an unvalidated planning estimate |

### Scalability Patterns (architectural options, not validated capacity)

1. **Horizontal Scaling (Kafka Partitioning)**
   - Kafka partitions/consumer groups are architectural options; production scale behavior is not established here

2. **Database Optimization**
   - Retention policies/read replicas are deployment options, not accepted production evidence

3. **Caching Layer**
   - Redis caching/cache-aside are architectural options where useful; production capacity is not claimed

---

## 🛠️ Development Guidelines

### Local Development Setup

1. **Start infrastructure only:**
   ```bash
   docker-compose up -d redis zookeeper kafka mysql influxdb mosquitto
   ```

2. **Run services locally:**
   ```bash
   # Terminal 1 - terra-sense
   cd services/terra-sense && ./gradlew bootRun
   
   # Terminal 2 - terra-cortex
   cd services/terra-cortex && uvicorn src.main:app --reload
   
   # Terminal 3 - terra-ops
   cd services/terra-ops && ./gradlew bootRun
   ```

3. **Verify connectivity:**
   ```bash
   curl http://localhost:8081/api/v1/ingest/health
   curl http://localhost:8082/health
   curl http://localhost:8083/api/v1/health
   ```

### Branch Strategy

- `main` - accepted integration branch; current evidence boundary is defined by `STATUS.md`
- `develop` - Integration branch (where used)
- `feature/*` - New features
- `hotfix/*` - Critical bug fixes

### Commit Convention

```
feat: Add temperature anomaly detection
fix: Resolve Kafka consumer offset issue
docs: Update API documentation
refactor: Simplify KafkaProducerService
test: Add integration tests for terra-cortex
```

---

## 📚 Documentation Inventory

| Document | Purpose | Location |
|----------|---------|----------|
| **STATUS.md** | Authoritative current implementation/evidence boundary | Root |
| **README.md** | Project overview, quick start, architecture | Root |
| **CONTRIBUTING.md** | Contribution guidelines, coding standards | Root |
| **QUICKSTART.md** | Fast setup guide with curl examples | Root |
| **docs/DEPLOYMENT.md** | Deployment instructions/reference | docs/ |
| **docs/TROUBLESHOOTING.md** | Common issues and solutions | docs/ |
| **PROJECT_SUMMARY.md** | Historical technical review reconciled to current truth boundary | Root |
| **services/terra-sense/IMPLEMENTATION.md** | terra-sense detailed implementation guide | services/terra-sense/ |
| **services/terra-sense/README.md** | terra-sense service documentation | services/terra-sense/ |
| **services/terra-sense/QUICKREF.md** | terra-sense quick reference | services/terra-sense/ |
| **services/terra-cortex/IMPLEMENTATION.md** | terra-cortex detailed implementation guide | services/terra-cortex/ |
| **services/terra-cortex/README.md** | terra-cortex service documentation | services/terra-cortex/ |
| **services/terra-cortex/QUICKREF.md** | terra-cortex quick reference | services/terra-cortex/ |
| **services/terra-ops/IMPLEMENTATION.md** | terra-ops detailed implementation guide | services/terra-ops/ |
| **services/terra-ops/README.md** | terra-ops service documentation | services/terra-ops/ |
| **services/terra-ops/QUICKREF.md** | terra-ops quick reference | services/terra-ops/ |
| **tests/README.md** | Complete testing guide with examples | tests/ |
| **tests/QUICKSTART.md** | 5-minute quick start for testing | tests/ |
| **tests/IMPLEMENTATION_SUMMARY.md** | Simulation script implementation details | tests/ |

---

## 🔮 Historical Roadmap Snapshot & Current Boundary

The phase list below originated in the 2025–2026 planning document. It is retained as historical context, **not** as a current authorization to implement production/physical scope. Current progression authority is `STATUS.md` plus explicitly human-approved destinations.

### Phase 1: Historical State (December 8, 2025)
- [x] Core microservices architecture (terra-sense, terra-cortex, terra-ops)
- [x] Kafka event streaming (raw-sensor-data → processed-insights topics)
- [x] MVP AI anomaly detection (rule-based: temp > 30°C or humidity < 40%)
- [x] Docker Compose orchestration
- [x] Monitoring components with Prometheus + Grafana
- [x] Service documentation
- [x] Simplified data model
- [x] Simulation testing tool
- [x] Historical small E2E pipeline run recorded
- [x] Single configured threshold anomaly example observed
- [x] Five synthetic/local farm IDs represented in historical run

### Historical Phase 2: Production Readiness Ideas (not accepted current evidence)
- [ ] Kubernetes deployment manifests (Helm charts)
- [ ] Advanced ML models (LSTM, Transformer-based time-series)
- [ ] Authentication & authorization evolution
- [ ] API versioning strategy
- [ ] Load testing & performance benchmarking

### Historical Phase 3: Feature Expansion Ideas (not authorized by this document)
- [ ] Mobile app integration (Flutter/React Native)
- [ ] Real-time WebSocket dashboard updates
- [ ] Automated farm irrigation control (requires separate physical-trust/safety review)
- [ ] Multi-tenancy support (farm owner isolation)
- [ ] Advanced analytics (yield prediction, crop health scoring)

### Historical Phase 4: Enterprise Ideas (not accepted current evidence)
- [ ] Multi-region deployment
- [ ] Data lake integration
- [ ] Machine learning model registry
- [ ] A/B testing framework
- [ ] Compliance/audit program work

---

## 🎯 Code Review Checklist (historical implementation checklist)

### Architecture & Design
- [x] Microservice boundaries implemented
- [x] Event-driven communication via Kafka implemented
- [x] Multiple persistence technologies present
- [x] API Gateway pattern present

### Code Quality
- [x] Java Spring Boot service patterns present
- [x] Python FastAPI async patterns present
- [x] Error handling/logging implemented in reviewed paths
- [x] Lombok used in Java code where applicable

### Operational Components
- [x] Docker build definitions present
- [x] Health endpoints/checks present in bounded paths
- [x] Prometheus metrics endpoints/configuration present
- [x] Docker Compose dependencies present

### Testing
- [x] Simulation tool present
- [x] End-to-end integration tests present
- [x] Data simulator present
- [x] Testing documentation present
- [x] Configurable higher-rate local simulation is possible; this is not production load certification
- [x] Historical database persistence exercise recorded
- [x] Historical 15/15 request sample recorded
- [x] Single configured threshold detection example recorded; not an AI accuracy claim
- [ ] Broader unit/coverage targets remain separate engineering work

### Security
- [x] API Gateway rate limiting implemented in bounded scope
- [x] Container security scanning workflow present
- [ ] Production TLS/identity/secret lifecycle requires separate evidence

### Documentation
- [x] README with architecture overview
- [x] API documentation where configured
- [x] Deployment reference
- [x] Troubleshooting guide
- [x] Contributing guidelines
- [x] Service-level documentation

---

## 📞 Project Metadata

**Repository:** terraneuron-smartfarm-platform  
**Historical snapshot size:** 60+ files / ~4500+ LOC at the time of the original summary; current repository may differ  
**Docker Images in historical composition:** 4 custom services + infrastructure components  
**Testing Tool:** simulation script retained as a bounded software test utility  
**Historical E2E Sample Date:** December 8, 2025  
**Historical Sample:** 25 generated/local insights with a 15-request final sample; not production validation  
**Current Evidence Authority:** `STATUS.md`  
**License:** (To be determined)

---

## 🤝 Contributors & Maintainers

**Core Team:**
- Project Lead: (To be assigned)
- Backend Engineer (Java): (To be assigned)
- AI/ML Engineer (Python): (To be assigned)
- DevOps Engineer: (To be assigned)

---

## 📝 Conclusion

TerraNeuron demonstrates a **bounded, production-oriented event-driven smart-farm software architecture prototype** with accepted software Proof slices recorded in `STATUS.md`. The authoritative accepted destinations are D1 (bounded command-lifecycle software Proof) and D2 (Synthetic Farm Operations Pilot).

### Current accepted strengths
- persisted plan/command identity and transactional outbox behavior under the accepted D1 boundary;
- bounded Kafka/MQTT software integration with a repository-owned synthetic device actor;
- explicit human approval and software safety-gate behavior under the implemented policy boundary;
- correlated synthetic ACK/feedback, terminal-state ordering/idempotency, bounded retry/recovery, and audit timeline evidence;
- reproducible software handoff and one coherent D2 operator/demo scenario with evidence artifact.

### Historical December 2025 observations retained for context
- a 15-request local/synthetic sample completed successfully in that run;
- 25 generated/local insight records were present in MySQL for that run;
- one configured temperature threshold example was detected;
- five farm IDs were represented;
- approximately 1-2 second E2E latency was observed in that environment.

These observations are **not** statistical reliability/accuracy evidence, production load evidence, real-world deployment evidence, or physical-device evidence.

### Explicit current non-claims
TerraNeuron does **not** currently claim production MQTT client identity/auth/TLS, production PKI/provisioning/secret lifecycle, production HA/DR/load guarantees, real manufacturer/device semantics, physical actuator truth, physical safety/interlocks/emergency stop behavior, unattended autonomous control, field readiness, or certification. Synthetic/device-reported software state must not be equated with physical equipment state.

**Overall Assessment:** the repository has strong bounded software Proof and buyer-demonstrable synthetic workflow evidence, but it must remain described as a software Proof/prototype unless later destinations establish additional trust with their own executable evidence. Historical small-run metrics must not be promoted into production or performance claims.

---

## 📜 Document History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| v1.0.0 | Dec 9, 2025 | Initial project summary with E2E run results | TerraNeuron Team |
| v2.0.0 | Dec 2025 | Added RAG/Hybrid AI architecture documentation | TerraNeuron Team |
| v2.1.0 | Jan 2026 | Phase 2.A (CloudEvents, Safety) + Phase 3 (JWT Auth) implementation snapshot | TerraNeuron Team |
| P0 reconciliation | Sep 2026 | Qualified historical claims against authoritative bounded-proof status | TerraNeuron progression |

---

## 🆕 Phase 2.A & Phase 3 Implementation Snapshot (January 2026)

> Historical implementation snapshot only. Terms such as “safety” and “security” below refer to implemented software logic/configuration, not physical safety, production security certification, or field validation.

### Phase 2.A: Action Loop Foundation ✅

**CloudEvents v1.0 Standard Implementation:**
- Event naming: `terra.<service>.<category>.<action>`
- Mandatory fields: `specversion`, `type`, `source`, `id`, `time`, `data`
- New Python models in `cloudevents_models.py`

**4-Layer Software Safety Validation System:**
```
┌─────────────────────────────────────────────┐
│ Layer 1: Logical Validation                 │
│   - Parameter bounds, action compatibility  │
├─────────────────────────────────────────────┤
│ Layer 2: Context Validation                 │
│   - Software-reported farm state checks     │
├─────────────────────────────────────────────┤
│ Layer 3: Permission Validation              │
│   - Human approval status, authority level  │
├─────────────────────────────────────────────┤
│ Layer 4: Device State Validation            │
│   - Software-reported device state/capability│
└─────────────────────────────────────────────┘
```

**Audit Logging (software event history):**
- FarmOS Log type: activity
- Event types: PLAN_CREATED, PLAN_VALIDATED, PLAN_APPROVED, PLAN_REJECTED, COMMAND_EXECUTED

### Phase 3: Security Implementation Snapshot ✅

**JWT Authentication:**
- Access tokens: 24 hours expiry (HS256)
- Refresh tokens: 7 days expiry
- BCrypt password hashing

**Role-Based Access Control (RBAC):**
| Role | Capabilities |
|------|-------------|
| ADMIN | Full system access, user management |
| OPERATOR | Action approval/rejection, dashboard access |
| VIEWER | Read-only dashboard access |

**Default Test Users:**
- `admin` / `admin123` (ROLE_ADMIN)
- `operator` / `operator123` (ROLE_OPERATOR)
- `viewer` / `viewer123` (ROLE_VIEWER)

These are local/test credentials documented for historical repository context and are not production credential/provisioning evidence.

---

**End of Technical Summary**  
*For current evidence scope and limitations, read `STATUS.md` first.*