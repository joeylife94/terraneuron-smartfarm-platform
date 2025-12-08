# 🧠 Terra-Cortex Quick Reference

## MVP Logic Summary

```python
# If temperature > 30 → ANOMALY
# If humidity < 40 → ANOMALY
# Otherwise → NORMAL

def analyze_sensor_data(sensor_data: SensorData) -> Insight:
    if sensor_type == "temperature" and value > 30:
        return ANOMALY
    elif sensor_type == "humidity" and value < 40:
        return ANOMALY
    else:
        return NORMAL
```

---

## File Structure

```
services/terra-cortex/
├── requirements.txt        ✅ fastapi, uvicorn, aiokafka, pydantic
├── Dockerfile              ✅ Python 3.10-slim
└── src/
    ├── main.py             ✅ FastAPI + async Kafka loop
    ├── logic.py            ✅ MVP anomaly detection
    └── models.py           ✅ SensorData, Insight
```

---

## Core Files

### **main.py** (FastAPI + Kafka)
```python
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from src.logic import analyze_sensor_data

# Async consumer loop
async for message in consumer:
    sensor_data = SensorData(**message.value)
    insight = analyze_sensor_data(sensor_data)
    await producer.send_and_wait(OUTPUT_TOPIC, insight)
```

### **logic.py** (MVP Logic)
```python
def analyze_sensor_data(sensor_data: SensorData) -> Insight:
    if sensor_type == "temperature" and value > 30:
        status = "ANOMALY"
    elif sensor_type == "humidity" and value < 40:
        status = "ANOMALY"
    else:
        status = "NORMAL"
    
    return Insight(...)
```

### **models.py** (Pydantic Models)
```python
class SensorData(BaseModel):
    farmId: str
    sensorType: str
    value: float

class Insight(BaseModel):
    farmId: str
    status: str  # NORMAL or ANOMALY
    severity: str
    confidence: float
```

---

## Quick Commands

```bash
# Install
pip install -r requirements.txt

# Run
uvicorn src.main:app --reload --port 8082

# Docker build
docker build -t terra-cortex .

# Docker run
docker run -p 8082:8082 terra-cortex

# Test
curl http://localhost:8082/health
```

---

## Data Flow

```
raw-sensor-data (Kafka)
    ↓
AIOKafkaConsumer (async)
    ↓
analyze_sensor_data()
    ↓
Insight (ANOMALY/NORMAL)
    ↓
AIOKafkaProducer (async)
    ↓
processed-insights (Kafka)
```

---

## Test Examples

**Temperature ANOMALY:**
```json
{"farmId":"farm-A","sensorType":"temperature","value":35.5}
→ ANOMALY (critical)
```

**Humidity ANOMALY:**
```json
{"farmId":"farm-B","sensorType":"humidity","value":25.0}
→ ANOMALY (warning)
```

**NORMAL:**
```json
{"farmId":"farm-C","sensorType":"temperature","value":25.0}
→ NORMAL (info)
```

---

**Status: ✅ COMPLETE**
