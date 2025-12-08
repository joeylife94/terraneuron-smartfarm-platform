# Terra-Ops Implementation Guide

## Overview
**Terra-Ops** is the Management & Dashboard microservice of the TerraNeuron Smart Farm platform. It consumes processed AI insights from Kafka, persists them to MySQL, and provides REST APIs for dashboard consumption.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Terra-Ops Service                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌──────────────────┐         │
│  │ Kafka Consumer  │         │ REST Controller  │         │
│  │ (processed-     │──────▶  │ /api/v1/         │         │
│  │  insights)      │         │  dashboard/      │         │
│  └────────┬────────┘         │  insights        │         │
│           │                   └──────────────────┘         │
│           │                            │                    │
│           ▼                            ▼                    │
│  ┌──────────────────────────────────────────────┐         │
│  │         InsightRepository (JPA)              │         │
│  └──────────────────┬───────────────────────────┘         │
│                     │                                       │
└─────────────────────┼───────────────────────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │  MySQL DB    │
              │  (terra_db)  │
              └──────────────┘
```

## Core Components

### 1. Entity Layer

#### Insight.java
```java
@Entity
@Table(name = "insights")
public class Insight {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    private String farmId;      // Farm identifier
    private String status;       // NORMAL or ANOMALY
    private String message;      // Human-readable insight
    private Instant timestamp;   // When insight was detected
    private Instant createdAt;   // Database insertion time
}
```

**Database Schema:**
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

### 2. Repository Layer

#### InsightRepository.java
Spring Data JPA repository with query methods:
- `findByFarmId(String farmId)` - Filter by farm
- `findByStatus(String status)` - Filter by status (NORMAL/ANOMALY)
- `findByTimestampBetween(start, end)` - Time-range queries
- `findAllByOrderByTimestampDesc()` - Latest insights first

### 3. Service Layer

#### KafkaConsumerService.java
Listens to `processed-insights` topic from terra-cortex:

**Kafka Message Format:**
```json
{
  "farmId": "sensor_temp_001",
  "status": "ANOMALY",
  "message": "Temperature exceeds threshold: 35.5°C > 30°C",
  "timestamp": "2025-01-23T10:30:45.123456Z"
}
```

**Processing Flow:**
1. Receive JSON message from Kafka
2. Deserialize to `InsightDto`
3. Map to `Insight` entity
4. Persist to MySQL via repository
5. Log success/failure

### 4. Controller Layer

#### DashboardController.java
REST API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/dashboard/insights` | GET | All insights (desc order) |
| `/api/v1/insights` | GET | All insights |
| `/api/v1/insights/farm/{farmId}` | GET | Filter by farm |
| `/api/v1/insights/status/{status}` | GET | Filter by status |
| `/api/v1/dashboard/summary` | GET | Statistics summary |

**Example Response:**
```json
GET /api/v1/dashboard/insights
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

## Configuration

### application.properties
```properties
# Server
spring.application.name=terra-ops
server.port=8080

# Kafka Consumer
spring.kafka.bootstrap-servers=kafka:9092
spring.kafka.consumer.group-id=terra-ops-group
spring.kafka.consumer.value-deserializer=JsonDeserializer
kafka.topic.processed-insights=processed-insights

# MySQL
spring.datasource.url=jdbc:mysql://mysql:3306/terra_db
spring.datasource.username=terra
spring.datasource.password=terra2025

# JPA
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=true
```

### Environment Variables (Docker)
```bash
SPRING_KAFKA_BOOTSTRAP_SERVERS=kafka:9092
SPRING_DATASOURCE_URL=jdbc:mysql://mysql:3306/terra_db
SPRING_DATASOURCE_USERNAME=terra
SPRING_DATASOURCE_PASSWORD=terra2025
```

## Build & Run

### Local Development
```bash
# Build
./gradlew build

# Run
./gradlew bootRun

# Test
./gradlew test
```

### Docker
```bash
# Build image
docker build -t terra-ops:1.0.0 .

# Run container
docker run -p 8080:8080 \
  -e SPRING_KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e SPRING_DATASOURCE_URL=jdbc:mysql://mysql:3306/terra_db \
  terra-ops:1.0.0
```

### Docker Compose
```yaml
terra-ops:
  build: ./services/terra-ops
  ports:
    - "8083:8080"
  environment:
    SPRING_KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/terra_db
  depends_on:
    - mysql
    - kafka
```

## API Testing

### 1. Check Health
```bash
curl http://localhost:8083/api/v1/health
```

### 2. Get All Insights
```bash
curl http://localhost:8083/api/v1/dashboard/insights
```

### 3. Filter by Farm
```bash
curl http://localhost:8083/api/v1/insights/farm/sensor_temp_001
```

### 4. Filter by Status
```bash
curl http://localhost:8083/api/v1/insights/status/ANOMALY
```

### 5. Get Dashboard Summary
```bash
curl http://localhost:8083/api/v1/dashboard/summary
```

**Expected Response:**
```json
{
  "totalInsights": 150,
  "normalInsights": 120,
  "anomalyInsights": 30,
  "timestamp": "2025-01-23T10:45:00.000Z"
}
```

## Integration Points

### Upstream Services
- **terra-cortex** (AI Analysis): Produces messages to `processed-insights` topic

### Downstream Services
- **MySQL**: Persists insights
- **Frontend Dashboard**: Consumes REST APIs

## Monitoring

### Actuator Endpoints
- `/actuator/health` - Service health
- `/actuator/info` - Service info
- `/actuator/prometheus` - Prometheus metrics

### Swagger UI
Access API documentation at:
```
http://localhost:8083/swagger-ui.html
```

## Error Handling

### Kafka Consumer Errors
- Invalid JSON → Logged, message skipped
- Database errors → Logged, retry handled by Kafka
- Deserialization errors → Logged with full stack trace

### REST API Errors
- Invalid farmId → Empty list returned
- Database connection loss → 500 Internal Server Error
- Invalid status value → Empty list returned

## Performance Considerations

1. **Database Indexes**: Created on `farm_id`, `status`, `timestamp`
2. **Kafka Consumer**: Auto-offset management, group coordination
3. **JPA Optimization**: `@GeneratedValue` for auto-increment IDs
4. **Connection Pooling**: HikariCP (Spring Boot default)

## Security Notes

⚠️ **Current Implementation**: No authentication/authorization
🔒 **Production Recommendations**:
- Add Spring Security
- Implement JWT authentication
- Use HTTPS/TLS
- Secure database credentials with secrets management

## Troubleshooting

### Issue: No insights in database
**Check:**
1. Is terra-cortex running and producing to Kafka?
2. Is Kafka consumer connected? (Check logs)
3. Is MySQL accessible? (Check connection string)

### Issue: Consumer lag increasing
**Check:**
1. Database write performance
2. Consumer group rebalancing
3. Network latency between services

### Issue: Duplicate insights
**Check:**
1. Consumer group ID configuration
2. Kafka offset management
3. Multiple consumer instances

## Data Flow Example

```
1. terra-cortex detects anomaly
   ↓
2. Publishes to processed-insights topic:
   {
     "farmId": "sensor_temp_001",
     "status": "ANOMALY",
     "message": "Temperature 35.5°C > 30°C",
     "timestamp": "2025-01-23T10:30:45.123456Z"
   }
   ↓
3. KafkaConsumerService receives message
   ↓
4. Maps to Insight entity and saves to MySQL
   ↓
5. Frontend calls GET /api/v1/dashboard/insights
   ↓
6. DashboardController returns persisted insights
```

## Development Checklist

- [x] Entity with id, farmId, status, message, timestamp
- [x] JPA Repository with query methods
- [x] Kafka Consumer listening to processed-insights
- [x] REST Controller with /api/v1/dashboard/insights
- [x] Docker containerization
- [x] Health endpoints
- [x] Swagger documentation
- [x] Comprehensive logging

## References

- **Spring Boot**: https://spring.io/projects/spring-boot
- **Spring Data JPA**: https://spring.io/projects/spring-data-jpa
- **Spring Kafka**: https://spring.io/projects/spring-kafka
- **MySQL Connector/J**: https://dev.mysql.com/doc/connector-j/en/
