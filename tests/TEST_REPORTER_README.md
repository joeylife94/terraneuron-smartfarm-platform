# 🧪 TerraNeuron Test Reporter - User Guide

## Overview

The upgraded `simulation.py` now includes a professional **HTML Test Reporter** that generates comprehensive test reports with AI verification capabilities. This tool is designed for QA engineers to validate the Hybrid AI Architecture and prove Local AI (Ollama) integration.

---

## ✨ Key Features

### 1. **Professional HTML Report Generation**
- Beautiful, responsive HTML design with gradient styling
- Summary dashboard with 7 key metrics
- Detailed test results table with color-coded rows
- AI recommendation highlighting in purple gradient boxes

### 2. **AI Integration Verification**
- Queries terra-ops API for insights after simulation
- Matches insights to sent sensor data
- Extracts `llmRecommendation` field (from Cloud/Local LLM)
- Tracks AI-triggered anomaly count vs total tests

### 3. **Performance Metrics**
- Per-request latency measurement (milliseconds)
- Average latency calculation
- Success rate percentage
- Test duration tracking

### 4. **Enhanced CLI Arguments**
```bash
--report                    # Generate HTML test report
--wait-for-insights <sec>   # Wait time before querying insights (default: 3s)
--verbose                   # Show full request/response details
```

---

## 🚀 Quick Start

### Basic Usage (No Report)
```bash
python tests/simulation.py --mode anomaly --count 10
```

### Generate HTML Report
```bash
python tests/simulation.py --mode anomaly --count 20 --report
```

### With Verbose Output
```bash
python tests/simulation.py --mode anomaly --count 10 --report --verbose
```

### Custom Wait Time for Insights
```bash
python tests/simulation.py --mode anomaly --count 50 --report --wait-for-insights 5
```

---

## 📊 Understanding the HTML Report

### Summary Dashboard Metrics

| Metric | Description |
|--------|-------------|
| **Total Tests** | Number of sensor data points sent |
| **Success Rate** | Percentage of successful HTTP 200 responses |
| **AI Triggered** | Number of anomalies detected by Local Analyzer |
| **AI Recommendations** | Number of LLM-generated recommendations |
| **Passed** | Number of successful test cases |
| **Failed** | Number of failed test cases |
| **Avg Latency** | Average response time in milliseconds |

### Test Results Table Columns

| Column | Description |
|--------|-------------|
| **#** | Test sequence number |
| **Timestamp** | Test execution time (HH:MM:SS.mmm) |
| **Farm ID** | Farm identifier (farm-A, farm-B, etc.) |
| **Sensor Type** | Type of sensor (temperature, humidity, etc.) |
| **Value** | Sensor reading with unit |
| **AI Status** | Local Analyzer result (NORMAL/ANOMALY) |
| **🤖 AI Recommendation** | LLM-generated recommendation (highlighted in purple) |
| **Latency** | Response time in milliseconds |
| **Result** | Test result (PASS/FAIL) |

### Color Coding

- 🟢 **Green rows**: NORMAL sensor readings (no action needed)
- 🔴 **Red rows**: ANOMALY detections (AI triggered)
- 🟣 **Purple boxes**: AI-generated recommendations (LLM responses)

---

## 🤖 AI Verification Workflow

### Current State (LOCAL-ONLY Mode)

```
Sensor Data → terra-sense → Kafka → terra-cortex (Local Analyzer) → Kafka → terra-ops → MySQL
                                            ↓
                                    Status: NORMAL/ANOMALY
                                    llmRecommendation: null
```

**Test Report Shows:**
- ✅ AI Status: NORMAL or ANOMALY (from Local Edge Analyzer)
- ❌ AI Recommendation: Empty (Cloud Advisor disabled)

### With Cloud/Local LLM Enabled

```
Sensor Data → terra-sense → Kafka → terra-cortex (Hybrid AI) → Kafka → terra-ops → MySQL
                                            ↓
                              Stage 1: Local Analyzer → ANOMALY detected
                              Stage 2: Cloud Advisor → LLM Recommendation
                                            ↓
                                    llmRecommendation: "🤖 Immediate Action: ..."
```

**Test Report Shows:**
- ✅ AI Status: ANOMALY (from Local Edge Analyzer)
- ✅ AI Recommendation: Detailed LLM response (highlighted in purple)

---

## 🔧 Setup for Full AI Verification

### Option 1: OpenAI Cloud LLM

1. **Add API Key to .env**
   ```bash
   echo "OPENAI_API_KEY=sk-your-key-here" >> .env
   echo "OPENAI_MODEL=gpt-4o-mini" >> .env
   ```

2. **Restart terra-cortex**
   ```bash
   docker-compose up -d terra-cortex
   ```

3. **Verify Cloud Advisor is enabled**
   ```bash
   docker logs terra-cortex --tail 20
   # Should see: "✅ Cloud Advisor enabled with model: gpt-4o-mini"
   ```

### Option 2: Ollama Local LLM (Recommended for Lab)

1. **Install Ollama**
   ```bash
   # Download from https://ollama.ai
   # Or use Docker: docker run -d -p 11434:11434 ollama/ollama
   ```

2. **Pull Llama 3.1 Model**
   ```bash
   ollama pull llama3.1
   ```

3. **Configure terra-cortex for Ollama**
   ```yaml
   # docker-compose.yml
   terra-cortex:
     environment:
       OLLAMA_BASE_URL: http://host.docker.internal:11434
       OLLAMA_MODEL: llama3.1
   ```

4. **Update terra-cortex code to use Ollama**
   - Modify `src/cloud_advisor.py` to use Ollama API instead of OpenAI
   - Example: `openai.base_url = "http://localhost:11434/v1"`

---

## 📈 Example Test Report

**File**: `test_report_20251208_224817.html`

**Summary:**
- Total Tests: 10
- Success Rate: 100%
- AI Triggered: 10 anomalies
- AI Recommendations: 0 (Cloud Advisor disabled)
- Avg Latency: 19ms

**Sample Row (ANOMALY Detection):**

| # | Timestamp | Farm ID | Sensor Type | Value | AI Status | 🤖 AI Recommendation | Latency | Result |
|---|-----------|---------|-------------|-------|-----------|---------------------|---------|--------|
| 4 | 22:48:20.254 | farm-B | temperature | 35.74 °C | <span style="background:#fed7d7;padding:5px 12px;border-radius:20px;color:#742a2a">ANOMALY</span> | — | 25ms | PASS |

**Note**: When Cloud/Local LLM is enabled, the "AI Recommendation" column will show:
```
🤖 Immediate Action: Check cooling system and ventilation fans.
   Root Cause: Temperature exceeded critical threshold (35°C).
   Prevention: Install automated cooling controls with temp sensors.
```

---

## 🔍 Troubleshooting

### Issue: "No insights retrieved from terra-ops"

**Cause**: Terra-ops service is not responding or insights are not yet processed.

**Solution**:
```bash
# Check terra-ops logs
docker-compose logs terra-ops

# Verify service is running
docker ps | grep terra-ops

# Check MySQL for insights
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 \
  -e "SELECT COUNT(*) FROM terra_db.insights WHERE timestamp > NOW() - INTERVAL 5 MINUTE"

# Increase wait time
python tests/simulation.py --mode anomaly --count 10 --report --wait-for-insights 10
```

### Issue: "AI Recommendations found: 0/10"

**Cause**: Cloud Advisor is disabled (no OPENAI_API_KEY or Ollama configuration).

**Solution**:
```bash
# Check terra-cortex logs
docker logs terra-cortex --tail 50 | grep -i "cloud advisor"

# Should see either:
# ✅ "Cloud Advisor enabled with model: gpt-4o-mini"  (good)
# ⚠️  "Cloud Advisor disabled (no API key)"          (need to configure)

# Configure API key (see "Setup for Full AI Verification" above)
```

### Issue: "llmRecommendation field not in MySQL"

**Cause**: Terra-ops (Java service) database schema doesn't have `llm_recommendation` column yet.

**Solution**:
```bash
# Add column to insights table
docker exec -it terraneuron-mysql mysql -u terra -pterra2025 \
  -e "ALTER TABLE terra_db.insights ADD COLUMN llm_recommendation TEXT NULL"

# Update terra-ops Java code to map the field
# Update Insight.java entity with @Column(name = "llm_recommendation")
```

---

## 🎯 Testing Strategies

### Strategy 1: Validate Local Analyzer Only
**Goal**: Verify rule-based anomaly detection works correctly.

```bash
python tests/simulation.py --mode anomaly --count 30 --report
```

**Expected Result**:
- AI Status: 30 ANOMALY detections (100%)
- AI Recommendations: 0 (Cloud Advisor disabled)
- All rows should be red (ANOMALY)

### Strategy 2: Validate Hybrid AI Pipeline
**Goal**: Prove LLM generates recommendations for anomalies.

```bash
# Enable OpenAI or Ollama first (see setup section)
python tests/simulation.py --mode anomaly --count 20 --report --wait-for-insights 5
```

**Expected Result**:
- AI Status: 20 ANOMALY detections (100%)
- AI Recommendations: 20 LLM responses (100%)
- Purple recommendation boxes should appear in all rows

### Strategy 3: Mixed Mode Stress Test
**Goal**: Test system under mixed workload (normal + anomaly).

```bash
python tests/simulation.py --mode mixed --count 100 --interval 0.5 --report
```

**Expected Result**:
- AI Status: ~20 ANOMALY, ~80 NORMAL (mixed)
- AI Recommendations: ~20 (only for anomalies)
- Green and red rows mixed in report

---

## 📝 Report File Naming

Reports are automatically named with timestamp:
```
test_report_YYYYMMDD_HHMMSS.html
```

**Example**: `test_report_20251208_224817.html`
- Date: December 8, 2025
- Time: 22:48:17 (10:48:17 PM)

---

## 🌐 Opening the Report

### Option 1: Auto-open (Windows)
```bash
python tests/simulation.py --mode anomaly --count 10 --report
# Report will open automatically in default browser
```

### Option 2: Manual open
```bash
# Get the file path from output
# Open in browser:
# - Windows: Start-Process test_report_YYYYMMDD_HHMMSS.html
# - Mac: open test_report_YYYYMMDD_HHMMSS.html
# - Linux: xdg-open test_report_YYYYMMDD_HHMMSS.html
```

### Option 3: Direct file path
```
file:///C:/Users/YourName/workspace/terraneuron-smartfarm-platform/test_report_YYYYMMDD_HHMMSS.html
```

---

## 📦 Report Archive

### Organizing Test Reports
```bash
# Create reports directory
mkdir -p tests/reports

# Move report to archive
mv test_report_*.html tests/reports/

# Run with custom output path
# (Future enhancement: add --output flag)
```

---

## 🎓 Best Practices

### 1. **Always use --report for AI verification**
```bash
# Good ✅
python tests/simulation.py --mode anomaly --count 20 --report

# Limited ❌ (no AI verification)
python tests/simulation.py --mode anomaly --count 20
```

### 2. **Use --verbose for debugging**
```bash
python tests/simulation.py --mode anomaly --count 5 --report --verbose
```

### 3. **Adjust wait time based on system load**
```bash
# Fast system: 3s wait (default)
python tests/simulation.py --mode anomaly --count 10 --report

# Slow system: 10s wait
python tests/simulation.py --mode anomaly --count 10 --report --wait-for-insights 10
```

### 4. **Archive reports after major milestones**
```bash
# After implementing new feature
python tests/simulation.py --mode anomaly --count 50 --report
mv test_report_*.html tests/reports/feature_X_validation.html
```

---

## 🚀 Future Enhancements

### Planned Features
- [ ] Export to PDF
- [ ] JSON report format
- [ ] Email notifications
- [ ] Grafana dashboard integration
- [ ] Custom output path (`--output` flag)
- [ ] Compare multiple test runs
- [ ] Performance regression detection

---

## 📞 Support

**Issues**: Check docker-compose logs for all services
```bash
docker-compose logs -f
```

**Questions**: Refer to main project README.md

**Version**: Test Reporter v2.0.0 (December 2025)

---

## 📜 License

Same as main TerraNeuron project.

---

**Happy Testing! 🌾🤖**
