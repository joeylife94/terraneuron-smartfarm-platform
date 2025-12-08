# RAG (Retrieval-Augmented Generation) Knowledge Base

This directory contains agricultural PDF documents that will be used to enhance AI recommendations with domain-specific expertise.

## 📂 Directory Structure

```
data/
├── knowledge_base/     # Place your PDF files here
│   ├── *.pdf          # Agricultural manuals, best practices, GlobalG.A.P., etc.
└── chroma_db/         # Vector database (auto-generated, DO NOT EDIT)
    └── agri_knowledge/
```

## 📚 Supported Documents

Add any agricultural PDF documents here, such as:

- **GlobalG.A.P. Manuals** - Certification standards for agricultural production
- **Crop Management Guides** - Best practices for specific crops (tomato, lettuce, etc.)
- **Pest & Disease Management** - IPM strategies, treatment protocols
- **Climate Control Guidelines** - Temperature, humidity, CO2 management
- **Irrigation Best Practices** - Water management, soil moisture optimization
- **Food Safety Standards** - HACCP, traceability, contamination prevention

## 🔄 How to Ingest PDFs

### Step 1: Add PDF Files
```bash
# Copy PDFs to knowledge_base directory
cp /path/to/your/agricultural_manual.pdf ./services/terra-cortex/data/knowledge_base/
```

### Step 2: Run Ingestion Script (Inside Container)
```bash
# Rebuild terra-cortex container (if Dockerfile/requirements changed)
docker-compose build terra-cortex

# Start terra-cortex
docker-compose up -d terra-cortex

# Run ingestion script inside container
docker exec -it terra-cortex python -m src.ingest_knowledge
```

You should see output like:
```
============================================================
🌾 Starting Knowledge Base Ingestion Pipeline
============================================================
📚 Found 3 PDF files
   📄 Loading: GlobalGAP_v5.pdf
      ✅ Loaded 45 pages
   📄 Loading: Tomato_Best_Practices.pdf
      ✅ Loaded 23 pages
✅ Total pages loaded: 68
🔄 Chunking 68 documents...
✅ Created 342 chunks (chunk_size=1000, overlap=200)
🔄 Creating ChromaDB vector database...
✅ ChromaDB vector database created and persisted
============================================================
✅ Knowledge Base Ingested: 68 documents processed
   📚 Total chunks: 342
   💾 Vector DB: /app/data/chroma_db
============================================================
```

### Step 3: Restart Terra-Cortex (Load RAG)
```bash
docker-compose restart terra-cortex
```

Check logs to verify RAG is enabled:
```bash
docker logs terra-cortex --tail 20
```

You should see:
```
✅ RAG Advisor enabled: 342 documents
✅ Cloud Advisor enabled with LOCAL LLM: llama3.1
```

## 🧪 Testing RAG Recommendations

Run simulation to generate anomalies and see RAG-enhanced recommendations:

```bash
python tests/simulation.py --mode mixed --count 10 --report
```

Open the generated HTML report and check the **AI Recommendation** column. You should see:
- **Without RAG**: Generic advice like "Check irrigation system"
- **With RAG**: Specific advice citing best practices, e.g., "According to GlobalG.A.P. standards, soil moisture below 20% requires immediate irrigation within 2 hours to prevent root stress..."

## 📊 RAG Statistics

Check RAG status via API:
```bash
curl http://localhost:8082/health
```

Response includes RAG stats:
```json
{
  "rag_advisor": {
    "enabled": true,
    "document_count": 342,
    "embedding_model": "all-MiniLM-L6-v2"
  }
}
```

## 🔧 Troubleshooting

### No PDFs Found
```
⚠️ No PDF files found in /app/data/knowledge_base
```
**Solution**: Add PDFs to `./services/terra-cortex/data/knowledge_base/` and re-run ingestion.

### ChromaDB Empty
```
⚠️ ChromaDB is empty (0 documents)
```
**Solution**: Run ingestion script first: `docker exec -it terra-cortex python -m src.ingest_knowledge`

### RAG Disabled
```
⚠️ RAG Advisor disabled (no knowledge base found)
```
**Solution**: Check if `chroma_db` directory exists and contains data. Re-run ingestion if empty.

### Slow Ingestion
Ingestion may take 1-5 minutes depending on PDF size and number of pages. This is normal - embeddings are computed locally on CPU.

## 📝 Sample Test PDF

For testing without real documents, create a simple text file and save as PDF:

**tomato_guide.txt** → Save as **tomato_guide.pdf**:
```
Tomato Temperature Management Best Practices

Optimal Temperature Range: 21-27°C (70-80°F)
Critical High: Above 32°C (90°F) - Risk of heat stress, blossom drop
Critical Low: Below 10°C (50°F) - Risk of chilling injury

Immediate Actions for High Temperature:
1. Increase ventilation and air circulation
2. Apply shade cloth (50% shade) during peak hours
3. Implement evaporative cooling (misting system)
4. Monitor soil moisture - increase irrigation frequency

Soil Moisture for Tomatoes:
Optimal: 60-80% field capacity
Critical Low: Below 40% - Risk of blossom-end rot
Action: Irrigate immediately, ensure consistent moisture

CO2 Enrichment:
Target: 800-1200 ppm during daylight hours
Critical High: Above 1500 ppm - Risk of toxicity
Action: Increase ventilation, reduce CO2 injection
```

## 🚀 Next Steps

1. **Add Domain PDFs** - Place agricultural manuals in `knowledge_base/`
2. **Run Ingestion** - Execute script inside container
3. **Verify RAG** - Check logs for "RAG Advisor enabled"
4. **Test Recommendations** - Run simulation and compare AI advice
5. **Iterate** - Add more PDFs, re-ingest, improve coverage

RAG transforms generic AI into an **Agri-Expert** with specialized knowledge! 🌾🧠
