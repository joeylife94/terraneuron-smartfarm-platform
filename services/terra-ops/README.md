# Terra-Ops

🌾 **Management & Dashboard Microservice** for TerraNeuron Smart Farm Platform

**Status:** ✅ **Production-Validated** (December 9, 2025)  
**Phase 2.A:** ✅ **Action Loop Foundation** - COMPLETED (January 2026)  
**Phase 3:** ✅ **JWT Security** - COMPLETED (January 2026)

## Overview

Terra-Ops is a Java-based management service that consumes AI-processed insights from Kafka, stores them in MySQL, and provides REST APIs for dashboard visualization.

## Tech Stack

- **Language**: Java 17
- **Framework**: Spring Boot 3.2.0
- **Database**: MySQL 8.0
- **Message Broker**: Apache Kafka
- **Build Tool**: Gradle 8.5
- **ORM**: Spring Data JPA (Hibernate)

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Java 17+ (for local development)
- Running Kafka and MySQL (via docker-compose)

### Run with Docker Compose

```bash
# Start all services (from project root)
docker-compose up -d terra-ops

# Check logs
docker-compose logs -f terra-ops

# Check health
curl http://localhost:8083/api/v1/health
```

### Local Development

```bash
# Build
./gradlew build

# Run
./gradlew bootRun

# Test
./gradlew test
```

## Core Features

### 1. Kafka Consumer
- **Topic**: `processed-insights`
- **Group**: `terra-ops-group`
- Automatically consumes AI insights from terra-cortex
- Persists to MySQL with error handling

### 2. REST API Endpoints

#### Dashboard & Insights API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Service health check |
| `/api/v1/dashboard/insights` | GET | **Main dashboard endpoint** |
| `/api/v1/insights` | GET | All insights |
| `/api/v1/insights/farm/{farmId}` | GET | Filter by farm ID |
| `/api/v1/insights/status/{status}` | GET | Filter by status |
| `/api/v1/dashboard/summary` | GET | Statistics summary |

#### Action Protocol API (Phase 2.A) ✅ NEW

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/actions/pending` | GET | List pending action plans | VIEWER+ |
| `/api/actions/{id}` | GET | Get action plan details | VIEWER+ |
| `/api/actions/{id}/approve` | POST | Approve with safety validation | OPERATOR+ |
| `/api/actions/{id}/reject` | POST | Reject with reason | OPERATOR+ |
| `/api/actions/{id}/audit` | GET | Get audit trail for plan | VIEWER+ |
| `/api/actions/statistics` | GET | Dashboard statistics | VIEWER+ |

#### Authentication API (Phase 3) ✅ NEW

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login, returns JWT tokens |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/validate` | GET | Validate current token |

### 3. Database Schema

```sql
insights
├── id (BIGINT, PK, Auto-increment)
├── farm_id (VARCHAR, indexed)
├── status (VARCHAR, indexed) -- NORMAL or ANOMALY
├── message (TEXT)
├── timestamp (TIMESTAMP, indexed)
└── created_at (TIMESTAMP)
```

## API Examples

### Get Dashboard Insights
```bash
curl http://localhost:8083/api/v1/dashboard/insights
```

**Response:**
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

### Get Dashboard Summary
```bash
curl http://localhost:8083/api/v1/dashboard/summary
```

**Response:**
```json
{
  "totalInsights": 150,
  "normalInsights": 120,
  "anomalyInsights": 30,
  "timestamp": "2025-01-23T10:45:00.000Z"
}
```

### Filter by Status
```bash
curl http://localhost:8083/api/v1/insights/status/ANOMALY
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPRING_KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker address |
| `SPRING_DATASOURCE_URL` | `jdbc:mysql://localhost:3306/terra_ops` | MySQL connection string |
| `SPRING_DATASOURCE_USERNAME` | `terra` | Database username |
| `SPRING_DATASOURCE_PASSWORD` | `terra2025` | Database password |

### Docker Compose Setup

```yaml
terra-ops:
  build: ./services/terra-ops
  ports:
    - "8083:8080"
  environment:
    SPRING_KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/terra_db
    SPRING_DATASOURCE_USERNAME: terra
    SPRING_DATASOURCE_PASSWORD: terra2025
  depends_on:
    - mysql
    - kafka
```

## Monitoring

### Health Check
```bash
curl http://localhost:8083/actuator/health
```

### Prometheus Metrics
```bash
curl http://localhost:8083/actuator/prometheus
```

### Swagger UI
```
http://localhost:8083/swagger-ui.html
```

## Architecture

```
terra-cortex (AI) → Kafka (processed-insights) → terra-ops → MySQL
                                                      ↓
                                               REST API (Dashboard)
```

## Project Structure

```
terra-ops/
├── src/main/java/com/terraneuron/ops/
│   ├── TerraOpsApplication.java        # Main Spring Boot application
│   ├── entity/
│   │   └── Insight.java                 # JPA entity (id, farmId, status, message, timestamp)
│   ├── repository/
│   │   └── InsightRepository.java       # Spring Data JPA repository
│   ├── service/
│   │   └── KafkaConsumerService.java    # Kafka consumer logic
│   ├── controller/
│   │   └── DashboardController.java     # REST API endpoints
│   └── dto/
│       └── InsightDto.java              # Kafka message DTO
├── src/main/resources/
│   └── application.properties            # Configuration
├── build.gradle                          # Gradle dependencies
├── Dockerfile                            # Multi-stage Docker build
├── IMPLEMENTATION.md                     # Detailed implementation guide
└── README.md                             # This file
```

## Development Workflow

1. **Start Infrastructure**
   ```bash
   docker-compose up -d mysql kafka
   ```

2. **Run Service Locally**
   ```bash
   ./gradlew bootRun
   ```

3. **Produce Test Insights** (via terra-cortex or Kafka console)
   ```bash
   docker exec -it kafka kafka-console-producer \
     --bootstrap-server localhost:9092 \
     --topic processed-insights \
     --property "parse.key=true" \
     --property "key.separator=:"
   
   # Then paste:
   null:{"farmId":"sensor_temp_001","status":"ANOMALY","message":"Test anomaly","timestamp":"2025-01-23T10:30:45.123456Z"}
   ```

4. **Verify Database**
   ```bash
   docker exec -it mysql mysql -u terra -p terra_db
   SELECT * FROM insights;
   ```

5. **Test API**
   ```bash
   curl http://localhost:8083/api/v1/dashboard/insights
   ```

## Troubleshooting

### No data in database?
1. Check Kafka consumer is connected: `docker logs terra-ops | grep Kafka`
2. Verify terra-cortex is producing messages
3. Check MySQL connection: `docker logs terra-ops | grep MySQL`

### Consumer lag increasing?
1. Check database write performance
2. Verify network connectivity
3. Review consumer group configuration

### Swagger UI not loading?
Ensure SpringDoc OpenAPI dependency is in `build.gradle`

## Testing

### Unit Tests
```bash
./gradlew test
```

### Integration Tests
```bash
./gradlew integrationTest
```

### Manual API Test
```bash
# Health check
curl http://localhost:8083/api/v1/health

# Get insights
curl http://localhost:8083/api/v1/dashboard/insights

# Filter by farm
curl http://localhost:8083/api/v1/insights/farm/sensor_temp_001
```

## Performance

- **Database indexes**: Optimized for `farm_id`, `status`, `timestamp`
- **Connection pooling**: HikariCP (Spring Boot default)
- **Kafka consumer**: Auto-offset management
- **JPA batch inserts**: Configurable via `spring.jpa.properties.hibernate.jdbc.batch_size`

## Security Considerations

✅ **Implemented (Phase 3):**
- Spring Security with JWT Authentication
- Role-based access control (ADMIN, OPERATOR, VIEWER)
- BCrypt password hashing
- Stateless session management

**Authentication Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login with username/password, returns JWT tokens |
| `/api/auth/refresh` | POST | Refresh access token using refresh token |
| `/api/auth/validate` | GET | Validate current token |

**Default Test Users:**
- `admin` / `admin123` (ROLE_ADMIN)
- `operator` / `operator123` (ROLE_OPERATOR)
- `viewer` / `viewer123` (ROLE_VIEWER)

🔒 **Production Recommendations**:
- Configure SSL/TLS (HTTPS)
- Use strong JWT secret key (externalize to secrets manager)
- Enable CORS properly for frontend domains
- Secure database credentials with secrets management

## Contributing

1. Follow Spring Boot best practices
2. Maintain consistent code style (Lombok annotations)
3. Add meaningful log messages
4. Update tests for new features
5. Document API changes in IMPLEMENTATION.md

## Related Services

- **terra-sense**: IoT data ingestion (produces to `raw-sensor-data`)
- **terra-cortex**: AI analysis (consumes `raw-sensor-data`, produces to `processed-insights`)
- **terra-ops**: Dashboard management (consumes `processed-insights`)

## Documentation

- **IMPLEMENTATION.md**: Detailed implementation guide
- **QUICKREF.md**: Quick reference for developers
- **Swagger UI**: Interactive API documentation

## License

Part of the TerraNeuron Smart Farm Platform

---

**Made with 🌾 by TerraNeuron Team**
