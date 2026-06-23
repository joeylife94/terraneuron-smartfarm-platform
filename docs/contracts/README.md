# Event Contract Documentation

**Version:** 1.1<br>
**Date:** 2026-06-23<br>
**Status:** ✅ Aligned

## Overview

This document describes the canonical CloudEvents v1.0 contracts for cross-service event communication in TerraNeuron. All events follow the CloudEvents specification with a standardized envelope wrapping domain-specific payloads.

## Architecture

```
Producer (terra-cortex / terra-ops / terra-sense)
        ↓
   CloudEvents v1.0 Envelope
        ↓
Kafka Topic
        ↓
   Consumer service
        ↓
Extract Data → Process or forward → Record outcome
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
- Java runtime path: terra-ops does **not** bind action-plan events to a typed DTO. The
  envelope is validated by [`ActionPlanEventValidator.java`](../../services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanEventValidator.java)
  and the `data` payload is consumed as a raw `Map<String, Object>` in
  [`ActionPlanService.consumeActionPlan`](../../services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanService.java),
  which maps fields directly onto the `ActionPlan` JPA entity.

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

### 3. Control Command Event

**Topic:** `terra.control.command`<br>
**Type:** `terra.ops.command.execute`<br>
**Producer:** terra-ops (`ActionPlanService.executePlan`)<br>
**Consumer:** terra-sense (`DeviceCommandConsumer.onCommand`)

#### Purpose

Requests that terra-sense deliver an approved action-plan command to the target device over
MQTT. The JSON Schema is [`command.schema.json`](./command.schema.json).

#### CloudEvents Envelope

```json
{
  "specversion": "1.0",
  "type": "terra.ops.command.execute",
  "source": "//terraneuron/terra-ops",
  "id": "d4e5f6a7-b8c9-4d01-8efa-234567890abc",
  "time": "2025-12-09T10:35:00Z",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "plan_id": "plan-abc12345",
    "command_id": "cmd-1a2b3c4d",
    "farm_id": "farm-001",
    "target_asset_id": "fan-01",
    "action_type": "turn_on",
    "parameters": {
      "duration_minutes": 30,
      "speed_level": "high"
    },
    "executed_by": "operator-01"
  }
}
```

#### Data Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trace_id` | string | ✅ | Trace inherited from the action plan |
| `plan_id` | string | ✅ | Approved action plan identifier |
| `command_id` | string | ✅ | Command identifier generated by terra-ops |
| `farm_id` | string | ✅ | Farm used for device routing and Kafka partitioning |
| `target_asset_id` | string | ✅ | Target device identifier |
| `action_type` | string | ✅ | `turn_on`, `turn_off`, `adjust`, or `alert_only` |
| `parameters` | object | ✅ | Action-specific command parameters |
| `executed_by` | string | ✅ | User who approved the plan for execution |

`ActionPlan.parameters` remains stored as JSON text in MySQL, but terra-ops parses it back to
an object before publishing this event. For compatibility with already-published or external
messages, terra-sense continues to accept either an object or a JSON-encoded string.

The `CommandExecutedEvent` model in `terra-cortex/src/cloudevents_models.py` uses the distinct
type `terra.ops.command.executed`. It is a historical notification-style model and is not the
request consumed from `terra.control.command`; the runtime request type remains
`terra.ops.command.execute`.

### 4. Command Feedback Event

**Topic:** `terra.control.feedback`<br>
**Type:** `terra.sense.command.feedback`<br>
**Producer:** terra-sense (`DeviceCommandConsumer.sendFeedback`)<br>
**Consumer:** terra-ops (`CommandFeedbackConsumer.onFeedback`)

#### Purpose

Reports command delivery or execution status to terra-ops so it can update the action plan and
write an audit record. The JSON Schema is [`feedback.schema.json`](./feedback.schema.json).

#### CloudEvents Envelope

```json
{
  "specversion": "1.0",
  "type": "terra.sense.command.feedback",
  "source": "//terraneuron/terra-sense",
  "id": "e5f6a7b8-c9d0-4e12-9fab-34567890abcd",
  "time": "2025-12-09T10:35:01Z",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "command_id": "cmd-1a2b3c4d",
    "plan_id": "plan-abc12345",
    "farm_id": "farm-001",
    "target_asset_id": "fan-01",
    "status": "DELIVERED",
    "error": "",
    "timestamp": "2025-12-09T10:35:01Z"
  }
}
```

#### Data Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trace_id` | string | ✅ | Trace inherited from the command request |
| `command_id` | string | ✅ | Command being reported |
| `plan_id` | string | ✅ | Associated action plan |
| `farm_id` | string | ✅ | Farm identifier |
| `target_asset_id` | string | ✅ | Target device identifier |
| `status` | string | ✅ | `DELIVERED`, `EXECUTED`, or `FAILED` |
| `error` | string | ✅ | Failure detail, or an empty string when successful |
| `timestamp` | string | ✅ | Feedback generation time (RFC3339) |

The current terra-sense bridge emits `DELIVERED` after MQTT publication and `FAILED` when
command handling fails. terra-ops also understands `EXECUTED` for device-confirmed completion.

## Consumer Implementation

### terra-ops Kafka Consumer - Insight Events

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

### terra-ops Kafka Consumer - Action Plan Events

**Location:** [`ActionPlanService.java`](../../services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanService.java)
**Validator:** [`ActionPlanEventValidator.java`](../../services/terra-ops/src/main/java/com/terraneuron/ops/service/ActionPlanEventValidator.java)

The consumer validates CloudEvents envelopes and parses action plans:

```java
// Validate CloudEvents v1.0 envelope
Optional<Map<String, Object>> validatedData = eventValidator.validate(planEvent);

if (validatedData.isEmpty()) {
    log.warn("Skipping malformed or wrong-type action plan event");
    return;
}

// Extract and persist plan data
Map<String, Object> data = validatedData.get();
ActionPlan plan = ActionPlan.builder()
    .planId((String) data.get("plan_id"))
    .traceId((String) data.get("trace_id"))
    // ... map remaining fields
    .build();

actionPlanRepository.save(plan);
```

**Envelope Validation Rules:**
- `specversion` must equal `"1.0"`
- `type` must equal `"terra.cortex.plan.generated"`
- `data` field must exist and be a non-empty object/map

**Error Handling:**
- Missing or invalid `specversion` → Log error, skip event
- Wrong `type` → Log warn, skip event (graceful rejection)
- Missing `data` field → Log error, skip event
- Empty `data` or non-map type → Log error, skip event
- All validation failures are non-fatal and do not crash the consumer

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

**Insight Parser Tests**

Location: [`InsightEventParserTest.java`](../../services/terra-ops/src/test/java/com/terraneuron/ops/service/InsightEventParserTest.java)

Run with:
```bash
cd services/terra-ops
gradle test --tests "*InsightEventParserTest"
```

**Coverage:**
- ✅ Valid CloudEvents insight parsing
- ✅ Missing required fields detection
- ✅ Invalid field values rejection
- ✅ Legacy flat format parsing
- ✅ Null/malformed message handling
- ✅ Timestamp parsing
- ✅ Optional fields handling

**Action Plan Validator Tests**

Location: [`ActionPlanEventValidatorTest.java`](../../services/terra-ops/src/test/java/com/terraneuron/ops/service/ActionPlanEventValidatorTest.java)

Run with:
```bash
cd services/terra-ops
gradle test --tests "*ActionPlanEventValidatorTest"
```

**Coverage:**
- ✅ Valid CloudEvents v1.0 action plan envelope validation
- ✅ Wrong or non-string `specversion` rejection
- ✅ Wrong or non-string `type` rejection
- ✅ Missing `data` field detection
- ✅ Empty `data` field detection
- ✅ Non-map `data` type rejection
- ✅ Null event handling
- ✅ trace_id extraction
- ✅ Data field preservation (all fields intact after validation)

**Contract Schema Example Tests**

Location: [`ContractSchemaExamplesTest.java`](../../services/terra-ops/src/test/java/com/terraneuron/ops/contracts/ContractSchemaExamplesTest.java)

The test loads every `docs/contracts/*.schema.json` file and validates every embedded example
against its Draft 7 schema. Gradle also packages these same files as runtime resources for
terra-ops and terra-sense. Their ingress consumers validate canonical CloudEvents before domain
parsing or processing, and validation failures propagate to the listener container. Legacy flat
insights remain supported without schema validation; legacy JSON-string command parameters are
normalized to objects before command validation.

### Integration Tests

To test against running Kafka:

```bash
# Start Kafka
docker-compose up -d kafka

# Run terra-ops
cd services/terra-ops
gradle bootRun

# Publish test message to processed-insights topic
# Message should be consumed and stored in database
```

## Migration Guide

### For New Consumers (Recommended)

terra-ops consumes CloudEvents as raw `Map<String, Object>` messages and validates each event
with `ContractSchemaValidator` before mapping the `data` payload. There is intentionally **no
generic typed envelope wrapper**; the ingress consumers, `ActionPlanEventValidator`, and
`InsightEventParser` remain the canonical entry points:

```java
@KafkaListener(topics = "processed-insights")
public void consume(Map<String, Object> messageData) {
    contractSchemaValidator.validate(
        ContractSchemaValidator.PROCESSED_INSIGHT_SCHEMA, messageData);
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

- [ ] Support for other event types (alerts, audit logs)
- [ ] Event replay from dead-letter queue
- [ ] Multi-tenancy support in trace_id
