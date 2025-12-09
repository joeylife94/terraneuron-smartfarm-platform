# 🦙 Ollama Local LLM Setup Guide

## Quick Start (5 Minutes)

### 1. Install Ollama on Host Machine

**Windows:**
```powershell
# Download from https://ollama.ai/download/windows
# Or use winget
winget install Ollama.Ollama
```

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Start Ollama Service

```bash
ollama serve
```

> **Note**: Keep this terminal running. Ollama runs on `http://localhost:11434`

### 3. Pull LLM Model

```bash
# Recommended: Llama 3.1 (4.7GB)
ollama pull llama3.1

# Alternative models:
# ollama pull mistral        # 4.1GB, faster
# ollama pull codellama      # 3.8GB, code-focused
# ollama pull llama3.1:13b   # 7.4GB, more accurate
```

### 4. Configure Terra-Cortex

**Option A: Use default .env.example (already configured)**
```bash
cp .env.example .env
```

**Option B: Manual configuration**
```bash
# Edit .env file
OPENAI_API_KEY=ollama
OPENAI_MODEL=llama3.1
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

### 5. Start Terra-Cortex

```bash
docker-compose up -d terra-cortex

# Check logs to confirm Ollama connection
docker logs terra-cortex --tail 20
```

**Expected output:**
```
✅ Cloud Advisor enabled with LOCAL LLM: llama3.1 (base_url: http://host.docker.internal:11434/v1)
🔄 Starting Kafka consumer loop with Hybrid AI...
```

---

## 🧪 Testing

### Test 1: Verify Ollama is Running
```bash
curl http://localhost:11434/v1/models
```

### Test 2: Generate Anomaly with AI Recommendation
```bash
python tests/simulation.py --mode anomaly --count 10 --report
```

**Expected HTML Report:**
- AI Status: 10 ANOMALY detections
- AI Recommendations: 10 LLM responses (in purple boxes)

### Test 3: Check Terra-Cortex Logs
```bash
docker logs terra-cortex -f

# You should see:
# 🤖 Triggering Cloud Advisor for ANOMALY...
# ✅ LLM recommendation received (XX chars)
```

---

## 🔧 Troubleshooting

### Issue: "AI Error: Check Local LLM connection"

**Cause**: Ollama is not running or not accessible from Docker.

**Solution:**
```bash
# 1. Check Ollama is running
curl http://localhost:11434/v1/models

# 2. Restart Ollama
ollama serve

# 3. Check Docker can reach host
docker exec terra-cortex curl http://host.docker.internal:11434/v1/models

# 4. Restart terra-cortex
docker-compose restart terra-cortex
```

### Issue: "Model 'llama3.1' not found"

**Solution:**
```bash
# Pull the model
ollama pull llama3.1

# List available models
ollama list
```

### Issue: Ollama responding slowly (>10 seconds)

**Solution:**
```bash
# Use a smaller/faster model
ollama pull mistral

# Update .env
OPENAI_MODEL=mistral

# Restart
docker-compose restart terra-cortex
```

---

## 🎯 Configuration Options

### Recommended Models by Use Case

| Use Case | Model | Size | Speed | Accuracy |
|----------|-------|------|-------|----------|
| **Development** | mistral | 4.1GB | ⚡⚡⚡ | ⭐⭐ |
| **Production** | llama3.1 | 4.7GB | ⚡⚡ | ⭐⭐⭐ |
| **High Accuracy** | llama3.1:13b | 7.4GB | ⚡ | ⭐⭐⭐⭐ |

### Environment Variables Reference

```bash
# Required
OPENAI_API_KEY=ollama  # Dummy key (required for compatibility)

# Model selection
OPENAI_MODEL=llama3.1  # Options: llama3.1, mistral, codellama, etc.

# Ollama endpoint
OPENAI_BASE_URL=http://host.docker.internal:11434/v1  # For Docker
# OR
OPENAI_BASE_URL=http://localhost:11434/v1  # For local development
```

---

## 📊 Performance Comparison

### Local Ollama vs OpenAI

| Metric | Ollama (Local) | OpenAI (Cloud) |
|--------|----------------|----------------|
| **Cost** | $0 (free) | ~$0.15 per 1M tokens |
| **Latency** | 1-5 seconds | 0.5-2 seconds |
| **Privacy** | 100% local | Cloud API |
| **Internet** | Not required | Required |
| **Setup** | 5 minutes | Instant |

### Hybrid AI Cost with Ollama

```
Daily sensor readings: 100,000
Anomaly rate: 10%
LLM calls: 10,000

Ollama cost: $0.00 (free)
OpenAI cost: $3.00/day

Savings: 100% 🎉
```

---

## 🚀 Production Deployment

### Option 1: Dedicated Ollama Container (Docker Compose)

```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    networks:
      - terraneuron-net

  terra-cortex:
    environment:
      OPENAI_BASE_URL: http://ollama:11434/v1  # Use container name
    depends_on:
      - ollama

volumes:
  ollama-data:
```

### Option 2: External Ollama Server

```bash
# On a dedicated GPU server
ollama serve --host 0.0.0.0:11434

# In terra-cortex .env
OPENAI_BASE_URL=http://192.168.1.100:11434/v1
```

---

## 📚 Additional Resources

- **Ollama Official Docs**: https://ollama.ai/docs
- **Model Library**: https://ollama.ai/library
- **Terra-Cortex README**: `services/terra-cortex/README.md`
- **Terra-Cortex RAG Guide**: `services/terra-cortex/RAG_QUICKSTART.md`
- **Test Reporter Guide**: `tests/TEST_REPORTER_README.md`

---

## 🎓 Advanced Topics

### Using Ollama with RAG System

Terra-Cortex now supports RAG (Retrieval-Augmented Generation) for enhanced recommendations:

```bash
# The RAG system works automatically with Ollama
# Knowledge base is stored in services/terra-cortex/data/knowledge_base/

# Test RAG with Ollama
curl http://localhost:8082/rag/query -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "Best temperature for tomato growth"}'
```

### GPU Acceleration (Optional)

For faster inference, use GPU-enabled Ollama:

**NVIDIA GPU:**
```bash
# Install NVIDIA Container Toolkit
# Then run Ollama with GPU support
docker run -d --gpus all \
  -v ollama:/root/.ollama \
  -p 11434:11434 \
  ollama/ollama
```

### Model Fine-tuning

You can create custom agricultural models:

```bash
# Create a Modelfile
cat > Modelfile << EOF
FROM llama3.1
SYSTEM You are an agricultural expert specializing in smart farming.
EOF

# Create custom model
ollama create agri-advisor -f Modelfile

# Use in terra-cortex
OPENAI_MODEL=agri-advisor
```

---

## ✅ Quick Verification Checklist

- [ ] Ollama installed and running (`ollama serve`)
- [ ] Model pulled (`ollama pull llama3.1`)
- [ ] `.env` file configured with Ollama settings
- [ ] Terra-cortex logs show "Cloud Advisor enabled with LOCAL LLM"
- [ ] Test simulation shows AI recommendations in HTML report

---

**Happy Smart Farming with Local AI! 🌾🤖**
