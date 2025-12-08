# 🧠 Terra-Cortex AI Analysis Microservice

**Status:** ✅ **FULLY IMPLEMENTED**  
**Stack:** Python 3.10 + FastAPI + aiokafka  
**Port:** 8082  
**Role:** AI-powered sensor data analysis and anomaly detection

---

## ✅ Implementation Complete

All requirements have been successfully implemented:

- [x] Python project initialized in `services/terra-cortex`
- [x] `requirements.txt` with fastapi, uvicorn, aiokafka, pydantic
- [x] Kafka Consumer listening to `raw-sensor-data` topic
- [x] MVP Dummy Logic:
  - Temperature > 30 → ANOMALY
  - Humidity < 40 → ANOMALY
  - Otherwise → NORMAL
- [x] Kafka Producer sending results to `processed-insights` topic
- [x] Dockerfile for containerized deployment

---

## 📂 File Structure

```
services/terra-cortex/
├── requirements.txt        # Python dependencies (fastapi, aiokafka, etc.)
├── Dockerfile              # Docker container definition
├── IMPLEMENTATION.md       # Complete implementation guide
├── QUICKREF.md             # Quick reference card
├── README.md               # This file
└── src/
    ├── __init__.py         # Python package marker
    ├── main.py             # ✅ FastAPI app + async Kafka loop
    ├── logic.py            # ✅ MVP anomaly detection logic
    └── models.py           # ✅ Pydantic models (SensorData, Insight)
```

---

## 🚀 Quick Start

### **Local Development**

```bash
# 1. Install dependencies
cd services/terra-cortex
pip install -r requirements.txt

# 2. Run the service
uvicorn src.main:app --reload --port 8082

# 3. Test
curl http://localhost:8082/health
```

### **Docker**

```bash
# Build
docker build -t terraneuron/terra-cortex:1.0.0 .

# Run
docker run -p 8082:8082 \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  terraneuron/terra-cortex:1.0.0
```

### **Docker Compose**

```bash
# From project root
docker-compose up -d terra-cortex
```

---

## 🧪 Testing

### **1. Send Test Data to Kafka**

```bash
# Temperature ANOMALY (> 30)
echo '{"farmId":"farm-A","sensorType":"temperature","value":35.5}' | \
  kafka-console-producer --bootstrap-server localhost:9092 --topic raw-sensor-data

# Humidity ANOMALY (< 40)
echo '{"farmId":"farm-B","sensorType":"humidity","value":25.0}' | \
  kafka-console-producer --bootstrap-server localhost:9092 --topic raw-sensor-data

# NORMAL
echo '{"farmId":"farm-C","sensorType":"temperature","value":25.0}' | \
  kafka-console-producer --bootstrap-server localhost:9092 --topic raw-sensor-data
```

### **2. View Results**

```bash
# Consume from output topic
kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic processed-insights \
  --from-beginning

# Or check service logs
docker-compose logs -f terra-cortex
```

---

## 📊 MVP Logic

**Rule-Based Anomaly Detection:**

| Sensor Type | Condition | Status | Severity |
|-------------|-----------|--------|----------|
| Temperature | > 30°C | ANOMALY | warning/critical |
| Humidity | < 40% | ANOMALY | warning/critical |
| Others | - | NORMAL | info |

---

## 🔄 Data Flow

```
Kafka Topic: raw-sensor-data
    ↓ (async consume)
AIOKafkaConsumer
    ↓ (deserialize JSON)
SensorData (Pydantic model)
    ↓ (apply MVP logic)
analyze_sensor_data()
    ↓ (create insight)
Insight (ANOMALY or NORMAL)
    ↓ (async produce)
AIOKafkaProducer
    ↓
Kafka Topic: processed-insights
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint |
| `/health` | GET | Health check |
| `/info` | GET | Service information |

**Example:**
```bash
curl http://localhost:8082/health

{
  "status": "healthy",
  "kafka_consumer_running": true,
  "kafka_producer_running": true,
  "input_topic": "raw-sensor-data",
  "output_topic": "processed-insights"
}
```

---

## 🎯 Key Features

✅ **Async Kafka Client** - Non-blocking I/O with aiokafka  
✅ **FastAPI Framework** - Modern Python web framework  
✅ **MVP Logic** - Simple rule-based anomaly detection  
✅ **Type Safety** - Pydantic models for data validation  
✅ **Docker Ready** - Containerized for easy deployment  
✅ **Health Checks** - HTTP and Docker health endpoints  
✅ **Graceful Shutdown** - Proper cleanup on exit  

---

## 📦 Dependencies

```txt
fastapi==0.109.0          # Web framework
uvicorn[standard]==0.27.0 # ASGI server
aiokafka==0.10.0          # Async Kafka client
pydantic==2.5.3           # Data validation
pydantic-settings==2.1.0  # Settings management
```

---

## 📚 Documentation

- **IMPLEMENTATION.md** - Complete implementation guide with code examples
- **QUICKREF.md** - Quick reference card
- **README.md** - This file

---

## 🔧 Configuration

**Environment Variables:**
```bash
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
INPUT_TOPIC=raw-sensor-data
OUTPUT_TOPIC=processed-insights
CONSUMER_GROUP=terra-cortex-group
```

---

## 🎓 Code Highlights

**Async Kafka Consumer:**
```python
consumer = AIOKafkaConsumer(
    'raw-sensor-data',
    bootstrap_servers='localhost:9092',
    group_id='terra-cortex-group',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

async for message in consumer:
    sensor_data = SensorData(**message.value)
    insight = analyze_sensor_data(sensor_data)
    await send_insight(insight)
```

**MVP Logic:**
```python
def analyze_sensor_data(sensor_data: SensorData) -> Insight:
    if sensor_type == "temperature" and value > 30:
        status = "ANOMALY"
        severity = "warning" if value <= 35 else "critical"
    elif sensor_type == "humidity" and value < 40:
        status = "ANOMALY"
        severity = "warning" if value >= 30 else "critical"
    else:
        status = "NORMAL"
        severity = "info"
    
    return Insight(
        farmId=sensor_data.farmId,
        status=status,
        severity=severity,
        confidence=0.90,
        detectedAt=datetime.utcnow()
    )
```

---

## 🔮 Future Enhancements

1. **Replace MVP Logic** with real ML models:
   - LSTM for time-series anomaly detection
   - Isolation Forest for multivariate analysis
   - PyTorch-based deep learning models

2. **Add Features**:
   - Prometheus metrics
   - Error retry logic
   - Dead letter queue

3. **Scalability**:
   - Multiple consumer instances
   - Kafka partition management

---

**Implementation Status:** ✅ **COMPLETE AND READY**  
**Implemented by:** AI Engineer & Python Backend Developer  
**Date:** December 8, 2025  
**Version:** 1.0.0
