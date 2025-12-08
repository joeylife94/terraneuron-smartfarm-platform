# 📋 Simulation Script Implementation Summary

## ✅ What Was Created

### 1. **tests/simulation.py** (Main Testing Tool)
- **435 lines** of production-ready Python code
- Comprehensive sensor data simulator with 3 modes:
  - `normal` - Realistic sensor values within expected ranges
  - `anomaly` - Out-of-range values to test AI detection
  - `mixed` - 80% normal + 20% anomaly (realistic scenario)
- Full command-line interface with argparse
- Real-time statistics tracking
- Color-coded console output with status indicators
- Error handling and timeout management

### 2. **tests/README.md** (Updated)
- Complete testing documentation in Korean
- Step-by-step setup instructions
- 5 different testing scenarios with examples
- Troubleshooting guide with Kafka debugging commands
- Performance expectations and metrics
- Full stack management commands

### 3. **tests/QUICKSTART.md** (New)
- 5-minute quick start guide in Korean
- Essential commands only
- Service URLs reference table
- Quick troubleshooting tips

---

## 🎯 Key Features

### Simulation Script Capabilities

1. **Sensor Data Generation**
   - Temperature (15-30°C normal, 35-45°C anomaly)
   - Humidity (40-80% normal, 10-30% anomaly)
   - Soil Moisture (30-70% normal, 5-20% anomaly)
   - CO2 (300-1000 ppm normal, 1500-2500 ppm anomaly)
   - Light (100-800 lux normal, 50-90 lux anomaly)

2. **HTTP Request Management**
   - Automatic health check before testing
   - Configurable request interval (default: 1 second)
   - Configurable request count (default: 10)
   - Timeout handling (5 seconds)
   - Custom terra-sense URL support

3. **Statistics & Reporting**
   - Total requests sent
   - Success/failure counts
   - HTTP status code distribution
   - Percentage calculations
   - Color-coded output (✅ success, ❌ failure, ⏱️ timeout)

4. **Command-Line Interface**
   ```bash
   python tests/simulation.py [options]
   
   Options:
     --mode {normal|anomaly|mixed}  # Data generation mode
     --count N                      # Number of requests
     --interval SECONDS             # Time between requests
     --url URL                      # Target service URL
     --verbose                      # Show full request/response
     --help                         # Show help message
   ```

---

## 📊 Usage Examples

### Example 1: Basic Test
```bash
python tests/simulation.py
```
**Output:**
```
╔═══════════════════════════════════════════════════════════╗
║   🌾 TerraNeuron Pipeline Simulation Tool 🧠              ║
╚═══════════════════════════════════════════════════════════╝

✅ terra-sense is healthy (Status: 200)
✅ [1/10] temperature      =   25.34 °C    | HTTP 200
✅ [2/10] humidity         =   65.22 %     | HTTP 200
...
============================================================
📊 TEST STATISTICS
Total Requests:   10
✅ Success:        10 (100.00%)
============================================================
```

### Example 2: Anomaly Detection Test
```bash
python tests/simulation.py --mode anomaly --count 15
```
**What it tests:**
- Sends only out-of-range sensor values
- Verifies terra-cortex AI detects anomalies
- Checks if ANOMALY status appears in terra-ops

### Example 3: Load Test
```bash
python tests/simulation.py --count 100 --interval 0.1
```
**What it tests:**
- System throughput (10 requests/second)
- Kafka consumer lag
- Database write performance
- Overall system stability

---

## 🔄 Complete Data Flow Verification

The simulation script tests the entire pipeline:

```
Simulation Script
    ↓ HTTP POST /api/v1/ingest
terra-sense (Port 8081)
    ↓ Kafka topic: raw-sensor-data
terra-cortex (Port 8082)
    ↓ AI Analysis (MVP logic: temp > 30°C or humidity < 40% = ANOMALY)
    ↓ Kafka topic: processed-insights
terra-ops (Port 8083)
    ↓ JPA Repository save
MySQL (terra_db.insights table)
    ↓ REST API
Dashboard API
```

**Verification commands:**
```bash
# 1. Check terra-sense logs
docker-compose logs -f terra-sense

# 2. Check terra-cortex logs
docker-compose logs -f terra-cortex

# 3. Check terra-ops logs
docker-compose logs -f terra-ops

# 4. Query MySQL database
docker exec -it mysql mysql -u terra -pterra2025 -e \
  "SELECT * FROM terra_db.insights ORDER BY timestamp DESC LIMIT 5"

# 5. Query Dashboard API
curl http://localhost:8083/api/v1/dashboard/insights | jq
```

---

## 📈 Testing Scenarios

### Scenario 1: Normal Operations (Baseline)
```bash
python tests/simulation.py --mode normal --count 20
```
**Expected:**
- 100% HTTP 200 responses
- Most insights have status = "NORMAL"
- Low anomaly count in dashboard summary

### Scenario 2: Anomaly Detection (AI Validation)
```bash
python tests/simulation.py --mode anomaly --count 15
```
**Expected:**
- 100% HTTP 200 responses
- All insights have status = "ANOMALY"
- Messages show "exceeds threshold" or "below threshold"
- High anomaly count in dashboard summary

### Scenario 3: Mixed Workload (Realistic)
```bash
python tests/simulation.py --mode mixed --count 50
```
**Expected:**
- ~80% NORMAL, ~20% ANOMALY insights
- Validates AI correctly classifies both types
- Realistic production-like scenario

### Scenario 4: Load Test (Performance)
```bash
python tests/simulation.py --count 100 --interval 0.1
```
**Expected:**
- No timeouts or errors
- Consistent response times
- All messages eventually processed
- Kafka consumer lag stays low

### Scenario 5: Stress Test (Long-Running)
```bash
python tests/simulation.py --count 300 --interval 1
```
**Expected:**
- 5 minutes of continuous load
- No memory leaks or performance degradation
- All services remain healthy

---

## 🛠️ How to Run the Full Stack

### Step 1: Start Docker Compose
```bash
cd terraneuron-smartfarm-platform
docker-compose up -d
```

**Services started (13 total):**
- Infrastructure: Kafka, Zookeeper, MySQL, Redis, InfluxDB, Mosquitto
- Monitoring: Prometheus, Grafana, kafka-exporter, mysql-exporter
- Application: terra-gateway, terra-sense, terra-cortex, terra-ops

### Step 2: Wait for Stability (~30 seconds)
```bash
# Check all services are up
docker-compose ps

# Verify health endpoints
curl http://localhost:8081/api/v1/health  # terra-sense
curl http://localhost:8082/health         # terra-cortex
curl http://localhost:8083/api/v1/health  # terra-ops
```

### Step 3: Install Python Dependencies
```bash
pip install requests
```

### Step 4: Run Simulation
```bash
# Basic test
python tests/simulation.py

# With custom options
python tests/simulation.py --mode mixed --count 30 --verbose
```

### Step 5: Verify Results
```bash
# Check dashboard API
curl http://localhost:8083/api/v1/dashboard/insights | jq

# Check MySQL database
docker exec -it mysql mysql -u terra -pterra2025 -e \
  "SELECT COUNT(*) as total, status, COUNT(*) FROM terra_db.insights GROUP BY status"

# View service logs
docker-compose logs -f terra-cortex
```

---

## 🎓 What You Learned

1. **How to simulate IoT sensor data** with realistic and anomaly values
2. **How to test microservices** with HTTP requests and validate responses
3. **How to verify Kafka message flow** through the entire pipeline
4. **How to check database persistence** in MySQL
5. **How to use command-line tools** for system testing
6. **How to read Docker logs** for debugging
7. **How to monitor system performance** during load testing

---

## 📚 Documentation Files

| File | Purpose | Lines |
|------|---------|-------|
| `tests/simulation.py` | Main simulation script | 435 |
| `tests/README.md` | Complete testing guide (Korean) | 247 |
| `tests/QUICKSTART.md` | 5-minute quick start (Korean) | 82 |

---

## 🚦 Next Steps

### For QA Engineers:
1. Run all 5 testing scenarios
2. Document any failures or unexpected behavior
3. Create additional test cases for edge cases
4. Set up CI/CD integration for automated testing

### For Developers:
1. Review simulation script code quality
2. Add unit tests for the simulator classes
3. Extend with more sensor types if needed
4. Add performance benchmarking features

### For DevOps:
1. Integrate simulation into CI/CD pipeline
2. Add scheduled load tests (nightly)
3. Set up alerting for test failures
4. Create Grafana dashboards for test metrics

---

## 🎉 Success Criteria

The simulation is successful when:

- ✅ All HTTP requests return status 200
- ✅ terra-sense logs show "Published to Kafka"
- ✅ terra-cortex logs show "📥 Received" and "📤 Sent"
- ✅ terra-ops logs show "✅ Insight saved"
- ✅ MySQL database contains insights with correct status
- ✅ Dashboard API returns the saved insights
- ✅ Statistics show 100% success rate

---

## 📞 Support

**For issues or questions:**
1. Check `tests/README.md` for troubleshooting
2. Review service logs: `docker-compose logs <service-name>`
3. Verify Kafka topics: `docker exec -it kafka kafka-topics --list`
4. Check service documentation in `services/*/IMPLEMENTATION.md`

---

**Created:** December 8, 2025  
**Author:** QA Engineer Role  
**Version:** 1.0.0  

**Happy Testing! 🌾🧠**
