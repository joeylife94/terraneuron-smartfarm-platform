# Event Contract Documentation

**Version:** 1.0  
**Date:** 2025-12-09  
**Status:** ✅ Aligned  

## Overview

This document describes the canonical CloudEvents v1.0 contracts for cross-service event communication in TerraNeuron. All events follow the CloudEvents specification with a standardized envelope wrapping domain-specific payloads.

## Architecture

```
Producer (terra-cortex)
        ↓
   CloudEvents v1.0 Envelope
        ↓
Kafka Topic (processed-insights / action-plans)
        ↓
   Consumer (terra-ops)
        ↓
Parse Envelope → Extract Data → Map to Entity → Persist
```

## Event Types

### 1. Insight Detection Event

**Topic:** `processed-insights`  
**Type:** `terra.cortex.insight.detected`  
**Producer:** terra-cortex  
**Consumer:** terra-ops  

#### Purpose
Communicates AI-detected insights (anomalies, status changes) from terra-cortex to terra-ops for persistent storage and action planning.

#### Schema Location
- JSON Schema: [`processed-insight.schema.json`](./processed-insight.schema.json)
- Pydantic Model: [`terra-cortex/src/cloudevents_models.py`](../../services/terra-cortex/src/cloudevents_models.py) (`InsightDetectedEvent`)
- Java Model: [`terra-ops/src/main/java/.../dto/InsightDataPayload.java`](../../services/terra-ops/src/main/java/com/terraneuron/ops/dto/InsightDataPayload.java)

#### CloudEvents Envelope
```json
{
  "specversion": "1.0",
  "type": "terra.cortex.insight.detected",
  "source": "//terraneuron/terra-cortex",
  "id": "<UUID>",
  "time": "<RFC3339>",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-<UUID>",
    "farm_id": "farm-001",
    "asset_id": "sensor-temp-01",
    "asset_type": "sensor",
    "sensor_type": "temperature",
    "status": "ANOMALY",
    "severity": "critical",
    "message": "Temperature 42.5°C exceeds threshold",
    "raw_value": 42.5,
    "confidence": 0.95,
    "detected_at": "2025-12-09T10:30:00Z",
    "llm_recommendation": "...",
    "rag_context": "..."
  }
}
```

#### Data Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trace_id` | string | ✅ | Distributed tracing ID |
| `farm_id` | string | ✅ | Farm identifier |
| `asset_id` | string | ❌ | Asset/sensor identifier |
| `asset_type` | string | ✅ (default: "sensor") | Type of asset |
| `sensor_type` | string | ✅ | Sensor type (temperature, humidity, co2, etc.) |
| `status` | string | ✅ | Status: NORMAL or ANOMALY |
| `severity` | string | ✅ | Severity: info, warning, or critical |
| `message` | string | ✅ | Human-readable message |
| `raw_value` | number | ✅ | Raw sensor value |
| `confidence` | number | ✅ | Confidence score (0-1) |
| `detected_at` | string | ✅ | Detection timestamp (RFC3339) |
| `llm_recommendation` | string | ❌ | LLM recommendation (ANOMALY only) |
| `rag_context` | string | ❌ | RAG context used in analysis |

### 2. Action Plan Generation Event

**Topic:** `action-plans`  
**Type:** `terra.cortex.plan.generated`  
**Producer:** terra-cortex  
**Consumer:** terra-ops  

#### Purpose
Communicates AI-generated action plans from terra-cortex to terra-ops for approval workflow and execution.

#### Schema Location
- JSON Schema: [`action-plan.schema.json`](./action-plan.schema.json)
- Pydantic Model: [`terra-cortex/src/cloudevents_models.py`](../../services/terra-cortex/src/cloudevents_models.py) (`ActionPlanGeneratedEvent`)
- Java Model: [`terra-ops/src/main/java/.../dto/ActionPlanDto.java`](../../services/terra-ops/src/main/java/com/terraneuron/ops/dto/ActionPlanDto.java)

#### CloudEvents Envelope
```json
{
  "specversion": "1.0",
  "type": "terra.cortex.plan.generated",
  "source": "//terraneuron/terra-cortex",
  "id": "<UUID>",
  "time": "<RFC3339>",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-<UUID>",
    "plan_id": "plan-abc12345",
    "plan_type": "input",
    "farm_id": "farm-001",
    "target_asset_id": "fan-01",
    "target_asset_type": "device",
    "action_category": "ventilation",
    "action_type": "turn_on",
    "parameters": {
      "duration_minutes": 30,
      "speed_level": "high"
    },
    "reasoning": "...",
    "requires_approval": true,
    "priority": "high",
    "safety_conditions": ["fan-01_device_online", "no_maintenance_mode"],
    "generated_at": "2025-12-09T10:30:05Z",
    "expires_at": "2025-12-09T11:00:05Z"
  }
}
```

#### Data Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trace_id` | string | ✅ | Links to source insight |
| `plan_id` | string | ✅ | Unique plan identifier |
| `plan_type` | string | ✅ (default: "input") | FarmOS type: input, harvest, maintenance |
| `farm_id` | string | ✅ | Farm identifier |
| `target_asset_id` | string | ✅ | Target device ID |
| `target_asset_type` | string | ✅ (default: "device") | Asset type |
| `action_category` | string | ✅ | ventilation, irrigation, lighting, heating, cooling, alert |
| `action_type` | string | ✅ | turn_on, turn_off, adjust, alert_only |
| `parameters` | object | ❌ | Action parameters (duration_minutes, speed_level, etc.) |
| `reasoning` | string | ✅ | Why this action was recommended |
| `requires_approval` | boolean | ✅ (default: true) | Whether approval needed |
| `priority` | string | ✅ (default: "medium") | low, medium, high, critical |
| `estimated_impact` | string | ❌ | Expected outcome |
| `safety_conditions` | array | ✅ | Conditions to verify before execution |
| `generated_at` | string | ✅ | Generation timestamp |
| `expires_at` | string | ❌ | Expiration timestamp |

## Consumer Implementation

### terra-ops Kafka Consumer

**Location:** [`KafkaConsumerService.java`](../../services/terra-ops/src/main/java/com/terraneuron/ops/service/KafkaConsumerService.java)

The consumer parses CloudEvents messages using the `InsightEventParser`:

```java
// Parse CloudEvents envelope
Optional<Insight> insightOpt = insightEventParser.parse(messageData);

// Save to database
Insight saved = insightRepository.save(insightOpt.get());
```

**Error Handling:**
- Missing `data` field → Log error, skip message
- Invalid field types → Log error, skip message
- Missing required fields → Log error, skip message
- Malformed JSON → Log error, skip message

**Backward Compatibility:**
- Also supports legacy flat format (camelCase fields) for graceful migration
- Logs warning when legacy format is used

### Event Parsing Logic

```
Message received
    ↓
Is CloudEvents format? (check specversion + type)
    ├─ YES → Parse envelope, extract data, validate payload
    ├─ NO  → Is legacy flat format? (check for farmId)
    │       ├─ YES → Parse flat structure, warn about deprecated format
    │       └─ NO  → Log malformed event error, skip
    ↓
Validation success?
    ├─ YES → Create entity, persist to database
    └─ NO  → Log validation error, skip
```

## Field Naming Convention

**CloudEvents `data` payload:** snake_case
```json
{
  "farm_id": "...",
  "sensor_type": "...",
  "raw_value": 25.5,
  "detected_at": "...",
  "llm_recommendation": "..."
}
```

**Java Entities:** camelCase via `@JsonProperty` annotation
```java
@JsonProperty("farm_id")
private String farmId;

@JsonProperty("sensor_type")
private String sensorType;
```

## Testing

### Unit Tests

Location: [`InsightEventParserTest.java`](../../services/terra-ops/src/test/java/com/terraneuron/ops/service/InsightEventParserTest.java)

Run with:
```bash
mvn test -Dtest=InsightEventParserTest
```

**Coverage:**
- ✅ Valid CloudEvents insight parsing
- ✅ Missing required fields detection
- ✅ Invalid field values rejection
- ✅ Legacy flat format parsing
- ✅ Null/malformed message handling
- ✅ Timestamp parsing
- ✅ Optional fields handling

### Integration Tests

To test against running Kafka:

```bash
# Start Kafka
docker-compose up -d kafka

# Run terra-ops
mvn spring-boot:run

# Publish test message to processed-insights topic
# Message should be consumed and stored in database
```

## Migration Guide

### For New Consumers (Recommended)

Implement CloudEvents parsing using the [`CloudEventsEnvelope`](../../services/terra-ops/src/main/java/com/terraneuron/ops/dto/CloudEventsEnvelope.java) generic wrapper:

```java
@KafkaListener(topics = "processed-insights")
public void consume(Map<String, Object> messageData) {
    Optional<Insight> insight = insightEventParser.parse(messageData);
    // Handle result
}
```

### For Existing Flat Format Consumers

The parser provides backward compatibility:
1. Consumes support both CloudEvents and legacy flat formats
2. Legacy format triggers warning log (search for `LEGACY format`)
3. No code changes required, but migration to CloudEvents is encouraged

## Troubleshooting

### Messages not being consumed

**Check:**
1. Event type matches consumer topic (e.g., `terra.cortex.insight.detected` for `processed-insights`)
2. `data` field is present and not empty
3. Required fields are populated and valid
4. Check consumer logs for parsing errors

**Example error logs:**
```
❌ CloudEvents message missing 'data' field
❌ Invalid insight data payload - missing or invalid required fields: farmId=null
⚠️ Parsed LEGACY format insight (deprecated)
```

### Validation failures

Common causes:
- `confidence` outside 0-1 range
- `farm_id` is empty or blank
- `sensor_type` is missing
- `status` is not NORMAL or ANOMALY
- `severity` is not info/warning/critical

Fix by checking producer logs and validating input data.

## Related Documentation

- [ACTION_PROTOCOL.md](../ACTION_PROTOCOL.md) - Complete action protocol specification
- [API_REFERENCE.md](../API_REFERENCE.md) - Service APIs
- [DEVELOPMENT_GUIDE.md](../DEVELOPMENT_GUIDE.md) - Development setup

## Future Enhancements

- [ ] Support for other event types (commands, alerts, audit logs)
- [ ] Schema validation library
- [ ] Event replay from dead-letter queue
- [ ] Multi-tenancy support in trace_id
