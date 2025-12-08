# Terra-Ops Quick Reference

## Service Info
- **Port**: 8083 (mapped from container 8080)
- **Stack**: Java 17 + Spring Boot 3.2 + MySQL + Kafka
- **Purpose**: Management & Dashboard microservice

---

## 🚀 Quick Start

```bash
# Start service
docker-compose up -d terra-ops

# Check logs
docker-compose logs -f terra-ops

# Health check
curl http://localhost:8083/api/v1/health
```

---

## 📡 REST API Endpoints

### Core Endpoints

```bash
# Health check
GET http://localhost:8083/api/v1/health

# Dashboard insights (sorted by timestamp desc)
GET http://localhost:8083/api/v1/dashboard/insights

# All insights
GET http://localhost:8083/api/v1/insights

# Filter by farm ID
GET http://localhost:8083/api/v1/insights/farm/{farmId}

# Filter by status (NORMAL or ANOMALY)
GET http://localhost:8083/api/v1/insights/status/{status}

# Dashboard summary statistics
GET http://localhost:8083/api/v1/dashboard/summary
```

### Example Responses

**GET /api/v1/dashboard/insights**
```json
[
  {
    "id": 1,
    "farmId": "sensor_temp_001",
    "status": "ANOMALY",
    "message": "Temperature exceeds threshold: 35.5°C > 30°C",
    "timestamp": "2025-01-23T10:30:45.123456Z",
    "createdAt": "2025-01-23T10:30:45.200000Z"
  }
]
```

**GET /api/v1/dashboard/summary**
```json
{
  "totalInsights": 150,
  "normalInsights": 120,
  "anomalyInsights": 30,
  "timestamp": "2025-01-23T10:45:00.000Z"
}
```

---

## 🐳 Docker Commands

```bash
# Build image
docker build -t terra-ops:1.0.0 ./services/terra-ops

# Run standalone
docker run -p 8083:8080 \
  -e SPRING_KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e SPRING_DATASOURCE_URL=jdbc:mysql://mysql:3306/terra_db \
  terra-ops:1.0.0

# With docker-compose
docker-compose up -d terra-ops
docker-compose logs -f terra-ops
docker-compose restart terra-ops
docker-compose stop terra-ops
```

---

## 🔧 Local Development

```bash
# Build
./gradlew build

# Run (default port 8080)
./gradlew bootRun

# Run with custom port
SERVER_PORT=8083 ./gradlew bootRun

# Test
./gradlew test

# Clean build
./gradlew clean build
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPRING_KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `SPRING_DATASOURCE_URL` | `jdbc:mysql://localhost:3306/terra_ops` | MySQL URL |
| `SPRING_DATASOURCE_USERNAME` | `terra` | DB user |
| `SPRING_DATASOURCE_PASSWORD` | `terra2025` | DB password |
| `SERVER_PORT` | `8080` | HTTP port |

---

## 📊 Kafka Integration

### Consumer Configuration
- **Topic**: `processed-insights`
- **Group ID**: `terra-ops-group`
- **Deserializer**: JSON (Spring Kafka JsonDeserializer)
- **Auto-offset**: Latest

### Expected Kafka Message Format
```json
{
  "farmId": "sensor_temp_001",
  "status": "ANOMALY",
  "message": "Temperature exceeds threshold: 35.5°C > 30°C",
  "timestamp": "2025-01-23T10:30:45.123456Z"
}
```

### Test Kafka Producer
```bash
docker exec -it kafka kafka-console-producer \
  --bootstrap-server localhost:9092 \
  --topic processed-insights

# Then paste JSON (one per line):
{"farmId":"sensor_temp_001","status":"ANOMALY","message":"Test anomaly","timestamp":"2025-01-23T10:30:45.123456Z"}
```

---

## 🗄️ Database Schema

```sql
CREATE TABLE insights (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    farm_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    message TEXT,
    timestamp TIMESTAMP(6) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    INDEX idx_farm_id (farm_id),
    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp)
);
```

### MySQL CLI Access
```bash
docker exec -it mysql mysql -u terra -pterra2025 terra_db

# Then run queries:
SELECT * FROM insights ORDER BY timestamp DESC LIMIT 10;
SELECT COUNT(*) FROM insights WHERE status = 'ANOMALY';
SELECT farm_id, COUNT(*) FROM insights GROUP BY farm_id;
```

---

## 📈 Monitoring

### Actuator Endpoints
```bash
# Health
curl http://localhost:8083/actuator/health

# Prometheus metrics
curl http://localhost:8083/actuator/prometheus

# Info
curl http://localhost:8083/actuator/info
```

### Swagger UI
```
http://localhost:8083/swagger-ui.html
```

### Log Levels
Edit `application.properties`:
```properties
logging.level.com.terraneuron.ops=DEBUG
logging.level.org.springframework.kafka=DEBUG
```

---

## 🐛 Troubleshooting

### No insights in database?
```bash
# Check Kafka consumer is running
docker logs terra-ops | grep "Kafka Received"

# Check MySQL connection
docker logs terra-ops | grep "HikariPool"

# Verify terra-cortex is producing
docker logs terra-cortex | grep "processed-insights"
```

### Consumer lag?
```bash
# Check consumer group status
docker exec -it kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group terra-ops-group
```

### Database connection refused?
```bash
# Check MySQL is running
docker ps | grep mysql

# Check network
docker network inspect terraneuron-smartfarm-platform_default

# Verify credentials
docker exec -it mysql mysql -u terra -pterra2025 terra_db
```

---

## 📁 Project Structure

```
terra-ops/
├── src/main/java/com/terraneuron/ops/
│   ├── TerraOpsApplication.java          # Main class
│   ├── entity/Insight.java                # JPA entity
│   ├── repository/InsightRepository.java  # JPA repo
│   ├── service/KafkaConsumerService.java  # Kafka logic
│   ├── controller/DashboardController.java # REST API
│   └── dto/InsightDto.java                # Kafka DTO
├── src/main/resources/application.properties
├── build.gradle
├── Dockerfile
├── IMPLEMENTATION.md
├── README.md
└── QUICKREF.md (this file)
```

---

## 🔑 Key Classes

### Insight Entity
```java
@Entity
public class Insight {
    @Id @GeneratedValue
    private Long id;
    private String farmId;    // Farm identifier
    private String status;     // NORMAL or ANOMALY
    private String message;    // Human-readable message
    private Instant timestamp; // Detection time
}
```

### Kafka Consumer
```java
@KafkaListener(topics = "processed-insights", groupId = "terra-ops-group")
public void consumeInsight(InsightDto dto) {
    Insight insight = map(dto);
    repository.save(insight);
}
```

### REST Controller
```java
@GetMapping("/api/v1/dashboard/insights")
public ResponseEntity<List<Insight>> getDashboardInsights() {
    return ResponseEntity.ok(repository.findAllByOrderByTimestampDesc());
}
```

---

## 🔗 Service Dependencies

```
terra-sense (IoT) → Kafka (raw-sensor-data)
                         ↓
                    terra-cortex (AI)
                         ↓
                    Kafka (processed-insights)
                         ↓
                    terra-ops (Dashboard) → MySQL
                         ↓
                    REST API (Frontend)
```

---

## ✅ Testing Checklist

- [ ] Service starts without errors
- [ ] Kafka consumer connects successfully
- [ ] MySQL connection established
- [ ] Health endpoint returns 200 OK
- [ ] Insights are saved to database
- [ ] REST APIs return correct data
- [ ] Swagger UI is accessible
- [ ] Actuator endpoints work

---

## 📚 Documentation

- **README.md**: Overview and setup guide
- **IMPLEMENTATION.md**: Detailed implementation details
- **QUICKREF.md**: This file (quick reference)
- **Swagger UI**: http://localhost:8083/swagger-ui.html

---

## 🆘 Common Commands

```bash
# Restart service
docker-compose restart terra-ops

# View real-time logs
docker-compose logs -f terra-ops

# Check Kafka topics
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list

# Test API
curl -s http://localhost:8083/api/v1/dashboard/insights | jq

# Check database
docker exec -it mysql mysql -u terra -pterra2025 -e "SELECT COUNT(*) FROM terra_db.insights"

# Build and restart
docker-compose build terra-ops && docker-compose up -d terra-ops
```

---

**For detailed information, see IMPLEMENTATION.md and README.md**
