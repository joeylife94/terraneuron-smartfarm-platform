"""
CloudEvents v1.0 Compliant Models for TerraNeuron
Following ACTION_PROTOCOL.md specification
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


# ============ Enums ============

class InsightStatus(str, Enum):
    NORMAL = "NORMAL"
    ANOMALY = "ANOMALY"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ActionCategory(str, Enum):
    VENTILATION = "ventilation"
    IRRIGATION = "irrigation"
    LIGHTING = "lighting"
    HEATING = "heating"
    COOLING = "cooling"
    ALERT = "alert"


class ActionType(str, Enum):
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    ADJUST = "adjust"
    ALERT_ONLY = "alert_only"


class PlanStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============ CloudEvents Base ============

class CloudEventBase(BaseModel):
    """CloudEvents v1.0 Base Schema"""
    specversion: str = Field(default="1.0", description="CloudEvents spec version")
    type: str = Field(..., description="Event type: terra.<service>.<category>.<action>")
    source: str = Field(..., description="Event source URI")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event ID")
    time: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="RFC3339 timestamp"
    )
    datacontenttype: str = Field(default="application/json")


# ============ Insight Detection Event ============

class InsightDetectedData(BaseModel):
    """Data payload for terra.cortex.insight.detected"""
    trace_id: str = Field(..., description="Distributed tracing ID")
    farm_id: str
    asset_id: Optional[str] = None
    asset_type: str = "sensor"
    sensor_type: str
    status: InsightStatus
    severity: Severity
    message: str
    raw_value: float
    confidence: float = Field(ge=0, le=1)
    detected_at: str
    llm_recommendation: Optional[str] = None
    rag_context: Optional[str] = None


class InsightDetectedEvent(CloudEventBase):
    """CloudEvents compliant Insight Detection Event"""
    type: str = "terra.cortex.insight.detected"
    source: str = "//terraneuron/terra-cortex"
    data: InsightDetectedData


# ============ Action Plan Generation Event ============

class ActionPlanParameters(BaseModel):
    """Parameters for action execution"""
    duration_minutes: Optional[int] = None
    speed_level: Optional[str] = None
    target_value: Optional[float] = None
    intensity: Optional[int] = None


class ActionPlanData(BaseModel):
    """Data payload for terra.cortex.plan.generated"""
    trace_id: str
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    plan_type: str = "input"  # FarmOS compatible: input, harvest, maintenance
    farm_id: str
    target_asset_id: str
    target_asset_type: str = "device"
    action_category: ActionCategory
    action_type: ActionType
    parameters: ActionPlanParameters = Field(default_factory=ActionPlanParameters)
    reasoning: str
    requires_approval: bool = True
    priority: Priority = Priority.MEDIUM
    estimated_impact: Optional[str] = None
    safety_conditions: List[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: Optional[str] = None


class ActionPlanGeneratedEvent(CloudEventBase):
    """CloudEvents compliant Action Plan Generation Event"""
    type: str = "terra.cortex.plan.generated"
    source: str = "//terraneuron/terra-cortex"
    data: ActionPlanData


# ============ Plan Approval/Rejection Events ============

class PlanApprovalData(BaseModel):
    """Data payload for terra.ops.plan.approved/rejected"""
    trace_id: str
    plan_id: str
    approved_by: str
    approved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: Optional[str] = None


class PlanApprovedEvent(CloudEventBase):
    """CloudEvents compliant Plan Approval Event"""
    type: str = "terra.ops.plan.approved"
    source: str = "//terraneuron/terra-ops"
    data: PlanApprovalData


class PlanRejectedEvent(CloudEventBase):
    """CloudEvents compliant Plan Rejection Event"""
    type: str = "terra.ops.plan.rejected"
    source: str = "//terraneuron/terra-ops"
    data: PlanApprovalData


# ============ Command Execution Events ============

class CommandExecutedData(BaseModel):
    """Data payload for terra.ops.command.executed"""
    trace_id: str
    plan_id: str
    command_id: str = Field(default_factory=lambda: f"cmd-{uuid.uuid4().hex[:8]}")
    target_asset_id: str
    action_type: ActionType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    executed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    execution_result: str = "SUCCESS"
    execution_duration_ms: Optional[int] = None


class CommandExecutedEvent(CloudEventBase):
    """CloudEvents compliant Command Execution Event"""
    type: str = "terra.ops.command.executed"
    source: str = "//terraneuron/terra-ops"
    data: CommandExecutedData


# ============ Alert Events ============

class AlertTriggeredData(BaseModel):
    """Data payload for terra.ops.alert.triggered"""
    trace_id: str
    alert_id: str = Field(default_factory=lambda: f"alert-{uuid.uuid4().hex[:8]}")
    farm_id: str
    severity: Severity
    alert_type: str
    message: str
    source_insight_id: Optional[str] = None
    triggered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    requires_acknowledgment: bool = True


class AlertTriggeredEvent(CloudEventBase):
    """CloudEvents compliant Alert Event"""
    type: str = "terra.ops.alert.triggered"
    source: str = "//terraneuron/terra-ops"
    data: AlertTriggeredData


# ============ Audit Log Entry ============

class AuditLogEntry(BaseModel):
    """FarmOS compatible audit log entry (maps to Log type: activity)"""
    trace_id: str
    log_id: str = Field(default_factory=lambda: f"log-{uuid.uuid4().hex[:8]}")
    log_type: str = "activity"  # FarmOS standard
    event_type: str  # CREATE, VALIDATE, APPROVE, EXECUTE, REJECT, FAIL
    entity_type: str  # plan, command, alert
    entity_id: str
    actor: str  # user_id or "system"
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    success: bool = True
    error_message: Optional[str] = None


# ============ Factory Functions ============

def generate_trace_id() -> str:
    """Generate a new trace_id for distributed tracing"""
    return f"trace-{uuid.uuid4()}"


def create_insight_event(
    trace_id: str,
    farm_id: str,
    sensor_type: str,
    status: InsightStatus,
    severity: Severity,
    message: str,
    raw_value: float,
    confidence: float,
    llm_recommendation: Optional[str] = None,
    rag_context: Optional[str] = None
) -> InsightDetectedEvent:
    """Factory function to create InsightDetectedEvent"""
    return InsightDetectedEvent(
        data=InsightDetectedData(
            trace_id=trace_id,
            farm_id=farm_id,
            asset_id=f"sensor-{sensor_type}-01",
            sensor_type=sensor_type,
            status=status,
            severity=severity,
            message=message,
            raw_value=raw_value,
            confidence=confidence,
            detected_at=datetime.now(timezone.utc).isoformat(),
            llm_recommendation=llm_recommendation,
            rag_context=rag_context
        )
    )


def create_action_plan_event(
    trace_id: str,
    farm_id: str,
    target_asset_id: str,
    action_category: ActionCategory,
    action_type: ActionType,
    reasoning: str,
    priority: Priority = Priority.MEDIUM,
    parameters: Optional[Dict[str, Any]] = None,
    safety_conditions: Optional[List[str]] = None,
    expires_minutes: int = 30
) -> ActionPlanGeneratedEvent:
    """Factory function to create ActionPlanGeneratedEvent"""
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(
        now.timestamp() + expires_minutes * 60, 
        tz=timezone.utc
    ).isoformat()
    
    return ActionPlanGeneratedEvent(
        data=ActionPlanData(
            trace_id=trace_id,
            farm_id=farm_id,
            target_asset_id=target_asset_id,
            action_category=action_category,
            action_type=action_type,
            parameters=ActionPlanParameters(**(parameters or {})),
            reasoning=reasoning,
            priority=priority,
            safety_conditions=safety_conditions or [],
            expires_at=expires_at
        )
    )
