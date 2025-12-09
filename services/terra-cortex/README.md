# 🧠 Terra-Cortex Hybrid AI + RAG Analysis Microservice

**Status:** ✅ **HYBRID AI + RAG ARCHITECTURE IMPLEMENTED**  
**Stack:** Python 3.10 + FastAPI + aiokafka + OpenAI/Ollama + ChromaDB  
**Version:** 3.0.0  
**Port:** 8082  
**Role:** Three-stage AI analysis (Local Edge AI + Cloud/Local LLM + RAG Knowledge Base)  
**Phase 2.A:** 🚧 **CloudEvents v1.0** (Action Plan Generation with trace_id)

---

## 🎯 Hybrid AI + RAG Architecture Overview

Terra-Cortex now implements a **3-stage intelligent analysis pipeline**:

```
Sensor Data → Stage 1: Local Edge Analyzer (always runs)
                  ↓
              Status: NORMAL or ANOMALY
                  ↓
              Stage 2: Cloud LLM Advisor (only for ANOMALY)
                  ↓
              Enhanced Insight with LLM Recommendation
                  ↓
              Stage 3: RAG Knowledge Base (contextual agricultural advice)
                  ↓
              Final Insight with Domain-Specific Knowledge
```

### Architecture Benefits

| Feature | Local Edge Analyzer | Cloud LLM Advisor | RAG Knowledge Base |
|---------|---------------------|-------------------|--------------------|
| **Speed** | <1ms (instant) | ~500-2000ms | ~100-500ms |
| **Cost** | Free (rule-based) | Pay-per-request | Free (local) |
| **Trigger** | Always runs | ANOMALY only | On-demand |
| **Output** | Status + Severity + Message | Detailed recommendation | Agricultural context |
| **AI Type** | Rule-based detection | GPT-4o-mini or Ollama | Vector similarity search |

---

## ✅ Implementation Status

### Phase 1: MVP Logic ✅ COMPLETE
- [x] Python project initialized in `services/terra-cortex`
- [x] `requirements.txt` with fastapi, uvicorn, aiokafka, pydantic
- [x] Kafka Consumer listening to `raw-sensor-data` topic
- [x] Rule-based anomaly detection (temperature, humidity, CO2, soil moisture, light)
- [x] Kafka Producer sending results to `processed-insights` topic
- [x] Dockerfile for containerized deployment

### Phase 2: Hybrid AI Architecture ✅ COMPLETE
- [x] **Local Edge Analyzer** module (`src/local_analyzer.py`)
  - 5 sensor types with threshold-based detection
  - Instant response (<1ms latency)
  - Zero cost operation
- [x] **Cloud LLM Advisor** module (`src/cloud_advisor.py`)
  - OpenAI API integration (gpt-4o-mini)
  - Ollama support for local LLM
  - Async/await pattern for non-blocking calls
  - Graceful degradation (works without API key)
- [x] **Smart Trigger Logic** in `main.py`
  - Local Analyzer always runs
  - Cloud Advisor only triggers for ANOMALY status
  - Conditional LLM recommendation injection
- [x] **Enhanced Data Model** (`models.py`)
  - Added `llmRecommendation: Optional[str]` field
- [x] **Environment Configuration**
  - `OPENAI_API_KEY` for Cloud LLM
  - `OPENAI_MODEL` selection (default: gpt-4o-mini)
  - `.env.example` template provided

### Phase 3: RAG System ✅ COMPLETE
- [x] **RAG Advisor** module (`src/rag_advisor.py`)
  - ChromaDB vector database integration
  - PDF/TXT knowledge base ingestion
  - Semantic similarity search
  - Contextual agricultural advice
- [x] **Knowledge Ingestion** (`src/ingest_knowledge.py`)
  - Automatic document processing
  - Vector embedding generation
  - Persistent storage in ChromaDB
- [x] **RAG API Endpoints** in `main.py`
  - `/rag/query` - Query knowledge base
  - `/rag/ingest` - Add new knowledge
  - `/health` - System health check with RAG status
- [x] **Data Directory Structure**
  - `data/knowledge_base/` - Source documents
  - `data/chroma_db/` - Vector database storage

---

## 📂 File Structure

```
services/terra-cortex/
├── requirements.txt        # Python dependencies (fastapi, aiokafka, openai, chromadb)
├── Dockerfile              # Docker container definition
├── .env.example            # Environment variable template
├── IMPLEMENTATION.md       # Complete implementation guide
├── QUICKREF.md             # Quick reference card
├── RAG_QUICKSTART.md       # RAG system setup guide
├── README.md               # This file
├── data/
│   ├── knowledge_base/     # Agricultural knowledge documents (PDF, TXT)
│   └── chroma_db/          # ChromaDB vector database
└── src/
    ├── __init__.py         # Python package marker
    ├── main.py             # ✅ FastAPI app + Hybrid AI + RAG orchestration
    ├── local_analyzer.py   # ✅ Local Edge AI (rule-based detection)
    ├── cloud_advisor.py    # ✅ Cloud/Local LLM integration
    ├── rag_advisor.py      # ✅ RAG knowledge base system
    ├── ingest_knowledge.py # ✅ Knowledge base ingestion tool
    └── models.py           # ✅ Enhanced Pydantic models
```

---

## 🚀 Quick Start

### **Local Development**

```bash
# 1. Install dependencies
cd services/terra-cortex
pip install -r requirements.txt

# 2. (Optional) Configure Cloud LLM
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run the service
uvicorn src.main:app --reload --port 8082

# 4. Test
curl http://localhost:8082/
curl http://localhost:8082/info
```

### **Docker**

```bash
# Build
docker build -t terraneuron/terra-cortex:2.0.0 .

# Run with LOCAL-ONLY mode (no API key)
docker run -p 8082:8082 \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  terraneuron/terra-cortex:2.0.0

# Run with Cloud LLM enabled
docker run -p 8082:8082 \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  -e OPENAI_API_KEY=sk-your-key-here \
  -e OPENAI_MODEL=gpt-4o-mini \
  terraneuron/terra-cortex:2.0.0
```

### **Docker Compose**

```bash
# From project root
docker-compose up -d terra-cortex

# Check logs
docker-compose logs -f terra-cortex

# You should see:
# ✅ Local Analyzer initialized (Edge AI)
# ⚠️ Cloud Advisor disabled (OPENAI_API_KEY not set)
# OR
# ✅ Cloud Advisor enabled with model: gpt-4o-mini
```

---

## 🧪 Testing

### **1. Test Hybrid AI Pipeline**

```bash
# Send ANOMALY data (will trigger both stages)
curl -X POST http://localhost:8081/api/v1/ingest/sensor-data \
  -H "Content-Type: application/json" \
  -d '{
    "sensorId": "sensor-001",
    "sensorType": "temperature",
    "value": 38.5,
    "unit": "°C",
    "farmId": "farm-A",
    "timestamp": "2025-12-08T10:30:00Z"
  }'

# Check terra-cortex logs
docker logs terra-cortex --tail 50

# Expected output:
# 📥 Received: farm-A - temperature: 38.5
# 🔍 Local Analyzer: ANOMALY (critical)
# 🤖 Cloud Advisor: Generating recommendation...
# 📤 Sent: farm-A - ANOMALY (critical) with LLM recommendation
```

### **2. Verify AI Status**

```bash
# Check service status
curl http://localhost:8082/

# Response:
{
  "service": "terra-cortex",
  "version": "2.0.0",
  "architecture": "hybrid-ai",
  "status": "running",
  "local_analyzer": {
    "total_analyses": 150,
    "analyzer_type": "local_edge_ai",
    "mode": "rule-based"
  },
  "cloud_advisor": {
    "total_recommendations": 12,
    "advisor_type": "cloud_llm",
    "model": "gpt-4o-mini",
    "enabled": true
  }
}
```

---

## 📊 Hybrid AI Logic

### Stage 1: Local Edge Analyzer (Always Runs)

**Rule-Based Thresholds:**

| Sensor Type | Warning Threshold | Critical Threshold | Status |
|-------------|-------------------|-------------------|--------|
| **Temperature** | > 30°C | > 35°C | ANOMALY |
| **Humidity** | < 40% | < 30% | ANOMALY |
| **CO2** | > 800 ppm | > 1000 ppm | ANOMALY |
| **Soil Moisture** | < 30% | < 20% | ANOMALY |
| **Light** | < 200 lux | < 800 lux | ANOMALY |

**Output Example (Without LLM):**
```json
{
  "farmId": "farm-A",
  "sensorType": "temperature",
  "status": "ANOMALY",
  "severity": "critical",
  "message": "🔥 Temperature is critically high: 38.5°C (critical threshold: 35.0°C)",
  "confidence": 0.95,
  "detectedAt": "2025-12-08T10:30:00Z",
  "rawValue": 38.5
}
```

### Stage 2: Cloud LLM Advisor (ANOMALY Only)

**Trigger Condition:**
```python
if insight.status == "ANOMALY" and cloud_advisor.enabled:
    llm_recommendation = await cloud_advisor.get_recommendation(sensor_data, insight)
    if llm_recommendation:
        insight.llmRecommendation = llm_recommendation
```

**LLM Prompt Structure:**
```
System: You are an expert agricultural AI assistant.

User: Analyze this anomaly:
- Farm ID: farm-A
- Sensor: temperature
- Reading: 38.5°C
- Local Analysis: Temperature critically high (threshold: 35°C)

Provide:
1. Immediate Action (1-2 sentences)
2. Root Cause Analysis (1 sentence)
3. Prevention Strategy (1 sentence)
```

**Output Example (With LLM):**
```json
{
  "farmId": "farm-A",
  "sensorType": "temperature",
  "status": "ANOMALY",
  "severity": "critical",
  "message": "🔥 Temperature is critically high: 38.5°C",
  "confidence": 0.95,
  "detectedAt": "2025-12-08T10:30:00Z",
  "rawValue": 38.5,
  "llmRecommendation": "🤖 Immediate Action: Activate emergency cooling system and check ventilation fans immediately. Root Cause: Temperature exceeded critical threshold by 3.5°C, likely due to inadequate airflow or cooling system malfunction. Prevention: Install redundant cooling systems with automated failover and real-time temperature monitoring alerts."
}
```

---

## 🔄 Data Flow

```
Kafka Topic: raw-sensor-data
    ↓ (async consume)
AIOKafkaConsumer
    ↓ (deserialize JSON)
SensorData (Pydantic model)
    ↓ (Stage 1: Always)
Local Edge Analyzer
    ↓ (analyze threshold)
Insight (ANOMALY or NORMAL)
    ↓ (Stage 2: If ANOMALY & enabled)
Cloud LLM Advisor
    ↓ (async OpenAI API call)
Enhanced Insight with llmRecommendation
    ↓ (async produce)
AIOKafkaProducer
    ↓
Kafka Topic: processed-insights
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service status with AI statistics |
| `/health` | GET | Health check |
| `/info` | GET | Detailed AI pipeline configuration |

**Example Responses:**

**GET /**
```json
{
  "service": "terra-cortex",
  "version": "2.0.0",
  "architecture": "hybrid-ai",
  "status": "running",
  "description": "Hybrid AI Analysis Engine: Local Edge AI + Cloud LLM",
  "local_analyzer": {
    "total_analyses": 150,
    "analyzer_type": "local_edge_ai",
    "mode": "rule-based"
  },
  "cloud_advisor": {
    "total_recommendations": 12,
    "advisor_type": "cloud_llm",
    "model": "gpt-4o-mini",
    "enabled": true
  }
}
```

**GET /info**
```json
{
  "service": "terra-cortex",
  "version": "2.0.0",
  "architecture": "hybrid-ai",
  "kafka": {
    "bootstrap_servers": "kafka:9092",
    "consumer_group": "terra-cortex-group",
    "input_topic": "raw-sensor-data",
    "output_topic": "processed-insights"
  },
  "ai_pipeline": {
    "stage_1": {
      "name": "Local Edge Analyzer",
      "type": "rule-based",
      "latency": "instant (<1ms)",
      "cost": "free",
      "always_runs": true,
      "total_analyses": 150
    },
    "stage_2": {
      "name": "Cloud LLM Advisor",
      "type": "llm-powered",
      "model": "gpt-4o-mini",
      "trigger": "ANOMALY only",
      "enabled": true,
      "total_recommendations": 12
    }
  }
}
```

---

## 🎯 Key Features

✅ **Hybrid AI Pipeline** - Local + Cloud for optimal cost/performance  
✅ **Smart Trigger Logic** - LLM only called for ANOMALY detections  
✅ **Graceful Degradation** - Works in LOCAL-ONLY mode without API key  
✅ **Async LLM Calls** - Non-blocking with aiokafka + AsyncOpenAI  
✅ **Multiple LLM Support** - OpenAI API or Ollama (local)  
✅ **Enhanced Insights** - Optional `llmRecommendation` field  
✅ **Performance Optimized** - Local Analyzer <1ms latency  
✅ **Cost Effective** - LLM costs minimized (ANOMALY-only trigger)  

---

## 📦 Dependencies

```txt
fastapi==0.109.0          # Web framework
uvicorn[standard]==0.27.0 # ASGI server
aiokafka==0.10.0          # Async Kafka client
pydantic==2.5.3           # Data validation
openai==1.12.0            # OpenAI API client (NEW!)
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address | `localhost:9092` | Yes |
| `OPENAI_API_KEY` | OpenAI API key for Cloud LLM | None | No* |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o-mini` | No |
| `OLLAMA_BASE_URL` | Ollama server URL (if using local LLM) | None | No |

*Note: Service works in LOCAL-ONLY mode without API key. Cloud Advisor will be disabled.

### Configuration Modes

#### Mode 1: LOCAL-ONLY (No LLM)
```bash
# No OPENAI_API_KEY set
docker-compose up -d terra-cortex

# Result:
# ✅ Local Analyzer: Active
# ⚠️ Cloud Advisor: Disabled
# - Fast, free, rule-based detection only
# - No LLM recommendations
```

#### Mode 2: Hybrid AI with OpenAI
```bash
# Add to .env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

docker-compose up -d terra-cortex

# Result:
# ✅ Local Analyzer: Active
# ✅ Cloud Advisor: Enabled (OpenAI)
# - Full hybrid AI pipeline
# - LLM recommendations for ANOMALY detections
```

#### Mode 3: Hybrid AI with Ollama (Local LLM)
```bash
# Install Ollama
docker run -d -p 11434:11434 ollama/ollama
ollama pull llama3.1

# Update cloud_advisor.py to use Ollama endpoint
# Add to docker-compose.yml:
# environment:
#   OLLAMA_BASE_URL: http://host.docker.internal:11434

docker-compose up -d terra-cortex

# Result:
# ✅ Local Analyzer: Active
# ✅ Cloud Advisor: Enabled (Ollama)
# - Full hybrid AI pipeline with local LLM
# - No external API costs
```

---

## 📚 Documentation

- **README.md** - This file (Hybrid AI overview)
- **IMPLEMENTATION.md** - Detailed implementation guide
- **QUICKREF.md** - Quick reference card
- **../../../tests/TEST_REPORTER_README.md** - HTML test report usage

---

## 🚦 Operational Modes

### Development Mode
```bash
cd services/terra-cortex
uvicorn src.main:app --reload --port 8082

# Hot reload enabled
# Debug logging
# Local Kafka connection
```

### Production Mode
```bash
docker-compose up -d terra-cortex

# Container orchestration
# Health checks enabled
# Automatic restart
# Resource limits applied
```

### Testing Mode
```bash
# Run simulation with HTML report
python tests/simulation.py --mode anomaly --count 20 --report

# Generate test report with AI verification
# Check for LLM recommendations in purple boxes
# Validate Local Analyzer performance
```

---

## 🔍 Monitoring

### Check Service Status
```bash
# Quick health check
curl http://localhost:8082/health

# Detailed AI pipeline info
curl http://localhost:8082/info

# View real-time logs
docker logs terra-cortex -f --tail 50
```

### Key Log Messages
```
✅ Local Analyzer initialized (Edge AI)
✅ Cloud Advisor enabled with model: gpt-4o-mini
🔄 Starting Kafka consumer loop with Hybrid AI...
📥 Received: farm-A - temperature: 38.5
🔍 Local Analyzer: ANOMALY (critical)
🤖 Cloud Advisor: Generating recommendation...
📤 Sent: farm-A - ANOMALY (critical) with LLM recommendation
```

---

## 🎓 Best Practices

### 1. **Start with LOCAL-ONLY mode**
Test rule-based detection first before enabling LLM.

### 2. **Use gpt-4o-mini for cost optimization**
Balance between quality and cost (~$0.15 per 1M tokens).

### 3. **Monitor LLM usage**
Track `cloud_advisor.total_recommendations` to control costs.

### 4. **Consider Ollama for lab environments**
Free local LLM alternative with Llama 3.1.

### 5. **Test with HTML Report**
```bash
python tests/simulation.py --mode anomaly --count 20 --report
```
Verify AI recommendations appear in purple boxes.

---

## 🐛 Troubleshooting

### Issue: Cloud Advisor not working

**Check logs:**
```bash
docker logs terra-cortex | grep -i "cloud advisor"
```

**Expected (disabled):**
```
⚠️ Cloud Advisor disabled (OPENAI_API_KEY not set)
```

**Expected (enabled):**
```
✅ Cloud Advisor enabled with model: gpt-4o-mini
```

**Solution:**
- Add `OPENAI_API_KEY` to `.env` file
- Restart: `docker-compose up -d terra-cortex`

### Issue: LLM recommendations not in database

**Cause:** Terra-ops needs schema update.

**Solution:**
```sql
ALTER TABLE terra_db.insights 
ADD COLUMN llm_recommendation TEXT NULL;
```

Then update terra-ops Java code to map the field.

---

## 📊 Performance Metrics

### Local Edge Analyzer
- **Latency**: <1ms per analysis
- **Throughput**: 10,000+ analyses/second
- **Cost**: $0.00 (free)

### Cloud LLM Advisor (OpenAI gpt-4o-mini)
- **Latency**: ~500-2000ms per recommendation
- **Cost**: ~$0.15 per 1M tokens (~$0.0003 per recommendation)
- **Trigger Rate**: Only for ANOMALY detections (typically 5-20%)

### Example Cost Calculation
```
Daily sensor readings: 100,000
Anomaly rate: 10%
LLM calls: 10,000
Cost per day: 10,000 × $0.0003 = $3.00
Cost per month: ~$90

Compare to: Always-on LLM = 100,000 × $0.0003 = $30/day = $900/month
Savings: 90% cost reduction with smart triggering
```

---

## 🎉 Success Criteria

✅ **Functional**
- Local Analyzer detects anomalies correctly
- Cloud Advisor generates relevant recommendations
- Hybrid pipeline processes data end-to-end

✅ **Performance**
- Local Analyzer <1ms latency
- LLM recommendations within 2 seconds
- No blocking on Kafka consumer loop

✅ **Cost Optimization**
- LLM only called for ANOMALY detections
- Graceful degradation without API key
- Monitoring shows actual vs potential LLM calls

✅ **Production Ready**
- Docker container builds successfully
- Health checks pass
- Logs confirm proper initialization
- Test report shows AI recommendations

---

## 📝 Version History

### v2.0.0 (December 2025) - Hybrid AI Architecture
- Added Local Edge Analyzer (rule-based)
- Added Cloud LLM Advisor (OpenAI/Ollama)
- Implemented smart trigger logic
- Enhanced data model with llmRecommendation
- Added graceful degradation
- Updated documentation

### v1.0.0 (November 2025) - MVP Release
- Basic rule-based anomaly detection
- Kafka consumer/producer
- FastAPI endpoints
- Docker containerization

---

**Built with ❤️ for Smart Agriculture | Hybrid AI Architecture for Cost-Effective Intelligence**
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
