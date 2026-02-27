# 🎯 TerraNeuron Action Protocol Specification

**Version:** 1.1.0  
**Status:** ✅ Implemented in Production  
**Date:** December 9, 2025  
**Last Updated:** February 2026 (Project Status Reviewed)  
**Standard:** CloudEvents v1.0 Compliant

> **📖 관련 문서:** [PROJECT_STATUS.md](PROJECT_STATUS.md) | [API_REFERENCE.md](API_REFERENCE.md) | [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [CloudEvents Schema](#cloudevents-schema)
3. [Type Naming Convention](#type-naming-convention)
4. [Action Command Schema](#action-command-schema)
5. [Safety Validation Rules](#safety-validation-rules)
6. [Event Flow](#event-flow)
7. [Examples](#examples)
8. [Implementation Guidelines](#implementation-guidelines)

---

## 🎯 Overview

### Purpose
This protocol defines the **standardized format for all Action Commands** in the TerraNeuron platform, ensuring:
- **Interoperability:** CloudEvents v1.0 compliance for cross-service communication
- **Traceability:** Mandatory `trace_id` for distributed tracing
- **Safety:** Built-in validation rules to prevent unsafe actions
- **FarmOS Compatibility:** Aligned with FarmOS/AgStack terminology

### Key Principles
1. **Safety First:** All actions must pass 4-layer validation before execution
2. **Standards Compliance:** Strict adherence to CloudEvents v1.0 and FarmOS naming
3. **Auditability:** Full traceability via `trace_id` propagation
4. **Fail-Safe:** Default to `ALERT_ONLY` mode on validation failures

---

## 📦 CloudEvents Schema

All Action Commands **MUST** conform to CloudEvents v1.0 specification.

### Required Fields

```json
{
  "specversion": "1.0",
  "type": "terra.<service>.<category>.<action>",
  "source": "//terraneuron/<service>",
  "id": "<UUID>",
  "time": "<RFC3339 timestamp>",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "<UUID>",
    "...": "..."
  }
}
```

### Field Definitions

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `specversion` | string | ✅ Yes | CloudEvents version | `"1.0"` |
| `type` | string | ✅ Yes | Event type (strict naming) | `"terra.cortex.plan.generated"` |
| `source` | URI-reference | ✅ Yes | Event producer | `"//terraneuron/terra-cortex"` |
| `id` | string | ✅ Yes | Unique event ID (UUID v4) | `"a1b2c3d4-..."` |
| `time` | timestamp | ✅ Yes | Event creation time (RFC3339) | `"2025-12-09T10:30:00Z"` |
| `datacontenttype` | string | ✅ Yes | Content type of data | `"application/json"` |
| `data` | object | ✅ Yes | Payload (includes trace_id) | See schemas below |

---

## 🏷️ Type Naming Convention

### Strict Standard: `terra.<service>.<category>.<action>`

#### Service Names
- `terra.cortex` - AI Analysis Service
- `terra.ops` - Operations Management Service
- `terra.sense` - IoT Ingestion Service
- `terra.gateway` - API Gateway Service

#### Category Names
- `insight` - AI detection/analysis results
- `plan` - Action recommendations/plans
- `command` - Device control commands
- `event` - General farm events
- `alert` - Critical notifications

#### Action Names
- `detected` - AI detection completed
- `generated` - Plan/recommendation created
- `approved` - Human approval granted
- `rejected` - Human rejection
- `executed` - Action completed
- `failed` - Action failed

### Valid Type Examples
```
✅ terra.cortex.insight.detected
✅ terra.cortex.plan.generated
✅ terra.ops.plan.approved
✅ terra.ops.plan.rejected
✅ terra.ops.command.executed
✅ terra.sense.event.received
✅ terra.ops.alert.triggered
```

### Invalid Type Examples
```
❌ terraneuron.cortex.insight (missing service prefix)
❌ terra.cortex.anomaly (missing action)
❌ terra.ai.plan.created (wrong service name)
❌ terra-cortex.plan.generated (hyphen instead of dot)
```

---

## 📋 Action Command Schema

### 1. AI Insight Detection Event

**Type:** `terra.cortex.insight.detected`

```json
{
  "specversion": "1.0",
  "type": "terra.cortex.insight.detected",
  "source": "//terraneuron/terra-cortex",
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "time": "2025-12-09T10:30:00Z",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "farm_id": "farm-001",
    "asset_id": "sensor-temp-01",
    "asset_type": "sensor",
    "sensor_type": "temperature",
    "status": "ANOMALY",
    "severity": "critical",
    "message": "Temperature 42.5°C exceeds threshold 35°C",
    "raw_value": 42.5,
    "confidence": 0.95,
    "detected_at": "2025-12-09T10:30:00Z",
    "llm_recommendation": "Immediate ventilation required. Recommend activating fan for 30 minutes."
  }
}
```

### 2. AI Action Plan Generation Event

**Type:** `terra.cortex.plan.generated`

```json
{
  "specversion": "1.0",
  "type": "terra.cortex.plan.generated",
  "source": "//terraneuron/terra-cortex",
  "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "time": "2025-12-09T10:30:05Z",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "plan_id": "plan-12345",
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
    "reasoning": "Temperature anomaly detected at 42.5°C. Ventilation required to reduce temperature to safe range (20-30°C).",
    "requires_approval": true,
    "priority": "high",
    "estimated_impact": "Expected temperature reduction: 5-10°C within 30 minutes",
    "safety_conditions": [
      "fan_device_online",
      "no_maintenance_mode",
      "temperature_above_threshold"
    ],
    "generated_at": "2025-12-09T10:30:05Z",
    "expires_at": "2025-12-09T11:00:05Z"
  }
}
```

### 3. Human Approval Event

**Type:** `terra.ops.plan.approved`

```json
{
  "specversion": "1.0",
  "type": "terra.ops.plan.approved",
  "source": "//terraneuron/terra-ops",
  "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "time": "2025-12-09T10:31:00Z",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "plan_id": "plan-12345",
    "approval_status": "approved",
    "approved_by": "user-admin-01",
    "approved_at": "2025-12-09T10:31:00Z",
    "approval_note": "Confirmed. Temperature is critical. Proceed with ventilation.",
    "modified_parameters": null
  }
}
```

### 4. Device Command Execution Event

**Type:** `terra.ops.command.executed`

```json
{
  "specversion": "1.0",
  "type": "terra.ops.command.executed",
  "source": "//terraneuron/terra-ops",
  "id": "d4e5f6a7-b8c9-0123-def0-1234567890ab",
  "time": "2025-12-09T10:31:05Z",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "plan_id": "plan-12345",
    "command_id": "cmd-98765",
    "farm_id": "farm-001",
    "asset_id": "fan-01",
    "asset_type": "device",
    "action_type": "turn_on",
    "parameters": {
      "duration_minutes": 30,
      "speed_level": "high"
    },
    "execution_status": "success",
    "executed_at": "2025-12-09T10:31:05Z",
    "log_type": "activity",
    "log_message": "Fan activated successfully. Speed: high, Duration: 30min"
  }
}
```

### 5. Rejection Event

**Type:** `terra.ops.plan.rejected`

```json
{
  "specversion": "1.0",
  "type": "terra.ops.plan.rejected",
  "source": "//terraneuron/terra-ops",
  "id": "e5f6a7b8-c9d0-1234-ef01-234567890abc",
  "time": "2025-12-09T10:31:00Z",
  "datacontenttype": "application/json",
  "data": {
    "trace_id": "trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "plan_id": "plan-12345",
    "rejection_reason": "safety_validation_failed",
    "rejection_detail": "Device fan-01 is currently in maintenance mode",
    "rejected_by": "system",
    "rejected_at": "2025-12-09T10:31:00Z",
    "fallback_action": "ALERT_ONLY"
  }
}
```

---

## 🛡️ Safety Validation Rules

### 4-Layer Validation Pipeline

All Action Plans **MUST** pass through these validators before execution:

#### 1. Logical Validator
**Purpose:** Validate parameter logic and constraints

**Rules:**
- `duration_minutes > 0 AND duration_minutes <= 1440` (24 hours max)
- `speed_level IN ["low", "medium", "high"]`
- `temperature_threshold >= -50 AND <= 100`
- `humidity_level >= 0 AND <= 100`

**Failure Action:** Reject with `rejection_reason: "invalid_parameters"`

#### 2. Context Validator
**Purpose:** Validate environmental safety conditions

**Rules:**
- ❌ **DON'T** turn OFF cooling if `current_temperature > 40°C`
- ❌ **DON'T** turn OFF heating if `current_temperature < 5°C`
- ❌ **DON'T** activate irrigation if `current_humidity > 90%`
- ✅ **DO** check weather forecast for outdoor actions

**Failure Action:** Reject with `rejection_reason: "unsafe_environmental_condition"`

#### 3. Permission Validator
**Purpose:** Enforce approval requirements

**Rules:**
- If `requires_approval: true` -> Wait for human approval
- If `priority: "critical"` -> Fast-track approval process
- If plan expired (`time > expires_at`) -> Reject automatically

**Failure Action:** Set status to `PENDING_APPROVAL` or `EXPIRED`

#### 4. Device State Validator
**Purpose:** Verify device availability

**Rules:**
- Device status = `online` (not `offline`, `maintenance`, `error`)
- Device last heartbeat within 5 minutes
- Device capability matches action type
- No conflicting commands in queue

**Failure Action:** Reject with `rejection_reason: "device_unavailable"`

### Validation Response Schema

```json
{
  "validation_result": "success|failed",
  "validators_passed": ["logical", "context", "permission", "device"],
  "validators_failed": [],
  "failure_details": {
    "validator": "context",
    "reason": "unsafe_environmental_condition",
    "detail": "Cannot turn off cooling. Current temperature 42°C exceeds safe limit."
  },
  "fallback_action": "ALERT_ONLY",
  "validated_at": "2025-12-09T10:30:10Z"
}
```

---

## 🔄 Event Flow

### Complete Action Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. SENSOR DATA INGESTION (terra-sense)                         │
│    Topic: terra.sensor.raw                                      │
│    trace_id: generated                                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. AI ANALYSIS (terra-cortex)                                   │
│    Event: terra.cortex.insight.detected                         │
│    Topic: terra.ai.insight                                      │
│    trace_id: propagated                                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. PLAN GENERATION (terra-cortex)                               │
│    Event: terra.cortex.plan.generated                           │
│    Topic: terra.control.plan                                    │
│    trace_id: propagated                                         │
│    requires_approval: true                                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SAFETY VALIDATION (terra-ops)                                │
│    Validators: [Logical, Context, Permission, Device]           │
│    trace_id: propagated                                         │
│                                                                  │
│    ┌──────────────────────────┐                                │
│    │ PASS ALL VALIDATORS?     │                                │
│    └──────┬───────────┬────────┘                                │
│           │ YES       │ NO                                      │
└───────────┼───────────┼──────────────────────────────────────────┘
            │           │
            │           ▼
            │     ┌─────────────────────────────────────────────┐
            │     │ 4.B REJECTION                               │
            │     │ Event: terra.ops.plan.rejected              │
            │     │ fallback_action: ALERT_ONLY                 │
            │     │ trace_id: propagated                        │
            │     └─────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. APPROVAL REQUIRED (terra-ops)                                │
│    Status: PENDING_APPROVAL                                     │
│    Notification sent to operator                                │
│    trace_id: propagated                                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. HUMAN DECISION                                               │
│    Event: terra.ops.plan.approved OR rejected                   │
│    trace_id: propagated                                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. COMMAND EXECUTION (terra-ops)                                │
│    Event: terra.ops.command.executed                            │
│    Topic: terra.control.command                                 │
│    Log Type: activity                                           │
│    trace_id: propagated                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 Examples

### Example 1: Complete Success Flow

```json
// Step 1: Sensor Data
{
  "specversion": "1.0",
  "type": "terra.sense.event.received",
  "source": "//terraneuron/terra-sense",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "time": "2025-12-09T10:30:00Z",
  "data": {
    "trace_id": "trace-001",
    "farm_id": "farm-001",
    "sensor_id": "temp-sensor-01",
    "sensor_type": "temperature",
    "value": 42.5,
    "unit": "celsius"
  }
}

// Step 2: AI Detection
{
  "specversion": "1.0",
  "type": "terra.cortex.insight.detected",
  "source": "//terraneuron/terra-cortex",
  "id": "650e8400-e29b-41d4-a716-446655440001",
  "time": "2025-12-09T10:30:05Z",
  "data": {
    "trace_id": "trace-001",
    "status": "ANOMALY",
    "severity": "critical",
    "message": "Critical temperature anomaly"
  }
}

// Step 3: Plan Generation
{
  "specversion": "1.0",
  "type": "terra.cortex.plan.generated",
  "source": "//terraneuron/terra-cortex",
  "id": "750e8400-e29b-41d4-a716-446655440002",
  "time": "2025-12-09T10:30:10Z",
  "data": {
    "trace_id": "trace-001",
    "plan_id": "plan-001",
    "action_type": "turn_on",
    "target_asset_id": "fan-01",
    "requires_approval": true
  }
}

// Step 4: Approval
{
  "specversion": "1.0",
  "type": "terra.ops.plan.approved",
  "source": "//terraneuron/terra-ops",
  "id": "850e8400-e29b-41d4-a716-446655440003",
  "time": "2025-12-09T10:31:00Z",
  "data": {
    "trace_id": "trace-001",
    "plan_id": "plan-001",
    "approved_by": "admin-01"
  }
}

// Step 5: Execution
{
  "specversion": "1.0",
  "type": "terra.ops.command.executed",
  "source": "//terraneuron/terra-ops",
  "id": "950e8400-e29b-41d4-a716-446655440004",
  "time": "2025-12-09T10:31:05Z",
  "data": {
    "trace_id": "trace-001",
    "command_id": "cmd-001",
    "execution_status": "success"
  }
}
```

### Example 2: Safety Rejection Flow

```json
// Plan Generated
{
  "specversion": "1.0",
  "type": "terra.cortex.plan.generated",
  "source": "//terraneuron/terra-cortex",
  "id": "a50e8400-e29b-41d4-a716-446655440005",
  "time": "2025-12-09T11:00:00Z",
  "data": {
    "trace_id": "trace-002",
    "plan_id": "plan-002",
    "action_type": "turn_off",
    "target_asset_id": "heater-01",
    "parameters": {
      "reason": "temperature_normalized"
    }
  }
}

// Rejected by Context Validator
{
  "specversion": "1.0",
  "type": "terra.ops.plan.rejected",
  "source": "//terraneuron/terra-ops",
  "id": "b50e8400-e29b-41d4-a716-446655440006",
  "time": "2025-12-09T11:00:05Z",
  "data": {
    "trace_id": "trace-002",
    "plan_id": "plan-002",
    "rejection_reason": "unsafe_environmental_condition",
    "rejection_detail": "Cannot turn off heater. Current temperature 3°C is below safe minimum 5°C.",
    "validator_failed": "context",
    "fallback_action": "ALERT_ONLY"
  }
}
```

---

## 🛠️ Implementation Guidelines

### For Service Developers

#### 1. Generating Events

**Java (Spring Boot):**
```java
@Service
public class CloudEventService {
    
    public CloudEvent createInsightEvent(Insight insight, String traceId) {
        return CloudEventBuilder.v1()
            .withId(UUID.randomUUID().toString())
            .withType("terra.cortex.insight.detected")
            .withSource(URI.create("//terraneuron/terra-cortex"))
            .withTime(OffsetDateTime.now())
            .withDataContentType("application/json")
            .withData(createInsightData(insight, traceId))
            .build();
    }
    
    private Map<String, Object> createInsightData(Insight insight, String traceId) {
        Map<String, Object> data = new HashMap<>();
        data.put("trace_id", traceId);
        data.put("farm_id", insight.getFarmId());
        data.put("status", insight.getStatus());
        // ... add all required fields
        return data;
    }
}
```

**Python (FastAPI):**
```python
from cloudevents.http import CloudEvent
from datetime import datetime
import uuid

def create_plan_event(plan_data: dict, trace_id: str) -> CloudEvent:
    attributes = {
        "specversion": "1.0",
        "type": "terra.cortex.plan.generated",
        "source": "//terraneuron/terra-cortex",
        "id": str(uuid.uuid4()),
        "time": datetime.utcnow().isoformat() + "Z",
        "datacontenttype": "application/json"
    }
    
    data = {
        "trace_id": trace_id,
        **plan_data
    }
    
    return CloudEvent(attributes, data)
```

#### 2. Propagating trace_id

**HTTP Headers:**
```http
X-Trace-Id: trace-a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Kafka Message Headers:**
```java
ProducerRecord<String, String> record = new ProducerRecord<>("topic", key, value);
record.headers().add("trace_id", traceId.getBytes(StandardCharsets.UTF_8));
```

**Logging:**
```java
// Structured Logging with trace_id
MDC.put("trace_id", traceId);
log.info("Processing action plan", 
    kv("plan_id", planId),
    kv("trace_id", traceId));
MDC.clear();
```

#### 3. Validation Implementation

**Java Validator Example:**
```java
@Component
public class ContextValidator implements SafetyValidator {
    
    @Override
    public ValidationResult validate(ActionPlan plan, FarmContext context) {
        // Rule: Don't turn OFF cooling if temp > 40°C
        if (plan.getActionType().equals("turn_off") 
            && plan.getTargetAssetId().contains("cooling")
            && context.getCurrentTemperature() > 40.0) {
            
            return ValidationResult.builder()
                .result("failed")
                .validator("context")
                .reason("unsafe_environmental_condition")
                .detail("Cannot turn off cooling. Current temperature exceeds safe limit.")
                .fallbackAction("ALERT_ONLY")
                .build();
        }
        
        return ValidationResult.success("context");
    }
}
```

---

## 📚 Related Documents

- [CloudEvents v1.0 Specification](https://github.com/cloudevents/spec/blob/v1.0/spec.md)
- [FarmOS Documentation](https://farmos.org/development/api/)
- [PROJECT_SUMMARY.md](../PROJECT_SUMMARY.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-09 | Initial protocol definition with CloudEvents v1.0 compliance |
| 1.1.0 | 2026-01 | Implementation complete: CloudEvents models, SafetyValidator, AuditService, ActionPlanService |

---

## ✅ Implementation Status (January 2026)

| Component | File | Status |
|-----------|------|--------|
| CloudEvents Models | `terra-cortex/src/cloudevents_models.py` | ✅ Implemented |
| 4-Layer Safety Validator | `terra-ops/src/.../SafetyValidator.java` | ✅ Implemented |
| Action Plan Entity | `terra-ops/src/.../ActionPlan.java` | ✅ Implemented |
| Audit Logging | `terra-ops/src/.../AuditService.java` | ✅ Implemented |
| Action API Controller | `terra-ops/src/.../ActionController.java` | ✅ Implemented |
| Kafka Consumer | `terra-ops/src/.../ActionPlanService.java` | ✅ Implemented |

---

**🛡️ Safety First. Standards Always.**
