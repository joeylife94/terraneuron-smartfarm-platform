package com.terraneuron.ops.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.entity.AuditLog;
import com.terraneuron.ops.repository.AuditLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Audit Logging Service
 * Records all significant events for compliance, debugging, and analytics.
 * FarmOS Compatible: Maps to Log entity (type: activity)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditService {

    private final AuditLogRepository auditLogRepository;
    private final ObjectMapper objectMapper;

    @Transactional
    public AuditLog logPlanCreated(ActionPlan plan) {
        Map<String, Object> details = new HashMap<>();
        details.put("action_category", plan.getActionCategory());
        details.put("action_type", plan.getActionType());
        details.put("target_asset", plan.getTargetAssetId());
        details.put("priority", plan.getPriority().name());
        details.put("requires_approval", plan.getRequiresApproval());

        return createLog(
                plan.getTraceId(),
                AuditLog.EventType.PLAN_CREATED,
                "plan",
                plan.getPlanId(),
                "system",
                "AI generated action plan: " + plan.getActionCategory() + " - " + plan.getActionType(),
                details,
                true,
                null
        );
    }

    @Transactional
    public AuditLog logPlanValidated(ActionPlan plan, boolean passed, String failedLayer, List<String> errors) {
        Map<String, Object> details = new HashMap<>();
        details.put("validation_passed", passed);
        details.put("failed_layer", failedLayer);
        details.put("errors", errors);

        return createLog(
                plan.getTraceId(),
                AuditLog.EventType.PLAN_VALIDATED,
                "plan",
                plan.getPlanId(),
                "system",
                passed ? "Safety validation passed all 4 layers" : "Safety validation failed at layer: " + failedLayer,
                details,
                passed,
                passed ? null : String.join("; ", errors)
        );
    }

    @Transactional
    public AuditLog logPlanApproved(ActionPlan plan, String approvedBy, String notes) {
        Map<String, Object> details = new HashMap<>();
        details.put("approved_by", approvedBy);
        details.put("approval_notes", notes);
        details.put("previous_status", "PENDING");

        return createLog(
                plan.getTraceId(),
                AuditLog.EventType.PLAN_APPROVED,
                "plan",
                plan.getPlanId(),
                approvedBy,
                "Plan approved by " + approvedBy,
                details,
                true,
                null
        );
    }

    @Transactional
    public AuditLog logPlanRejected(ActionPlan plan, String rejectedBy, String reason) {
        Map<String, Object> details = new HashMap<>();
        details.put("rejected_by", rejectedBy);
        details.put("rejection_reason", reason);
        details.put("previous_status", plan.getStatus().name());

        return createLog(
                plan.getTraceId(),
                AuditLog.EventType.PLAN_REJECTED,
                "plan",
                plan.getPlanId(),
                rejectedBy,
                "Plan rejected: " + reason,
                details,
                true,
                null
        );
    }

    @Transactional
    public AuditLog logCommandExecuted(ActionPlan plan, boolean success, String result, String error) {
        Map<String, Object> details = new HashMap<>();
        details.put("command_id", plan.getCommandId());
        details.put("target_asset", plan.getTargetAssetId());
        details.put("action_type", plan.getActionType());
        details.put("execution_result", result);
        details.put("executed_by", plan.getApprovedBy());

        return createLog(
                plan.getTraceId(),
                success ? AuditLog.EventType.COMMAND_EXECUTED : AuditLog.EventType.COMMAND_FAILED,
                "command",
                plan.getCommandId() != null ? plan.getCommandId() : plan.getPlanId(),
                "system",
                success ? "Command executed successfully" : "Command execution failed",
                details,
                success,
                error
        );
    }

    @Transactional
    public AuditLog logCommandTimeout(ActionPlan plan) {
        Map<String, Object> details = new HashMap<>();
        details.put("command_id", plan.getCommandId());
        details.put("plan_id", plan.getPlanId());
        details.put("farm_id", plan.getFarmId());
        details.put("target_asset", plan.getTargetAssetId());
        details.put("ack_deadline_at", plan.getAckDeadlineAt());

        return createLog(
                plan.getTraceId(),
                AuditLog.EventType.COMMAND_TIMEOUT,
                "command",
                plan.getCommandId() != null ? plan.getCommandId() : plan.getPlanId(),
                "system",
                "Device acknowledgement timeout for asset " + plan.getTargetAssetId(),
                details,
                false,
                plan.getExecutionError()
        );
    }

    @Transactional
    public AuditLog logAlertTriggered(String traceId, String alertId, String farmId, String severity, String message) {
        Map<String, Object> details = new HashMap<>();
        details.put("farm_id", farmId);
        details.put("severity", severity);
        details.put("alert_message", message);

        return createLog(
                traceId,
                AuditLog.EventType.ALERT_TRIGGERED,
                "alert",
                alertId,
                "system",
                "Alert triggered: " + severity + " - " + message,
                details,
                true,
                null
        );
    }

    @Transactional
    public AuditLog logInsightDetected(String traceId, String insightId, String farmId, String status, String message) {
        Map<String, Object> details = new HashMap<>();
        details.put("farm_id", farmId);
        details.put("status", status);
        details.put("insight_message", message);

        return createLog(
                traceId,
                AuditLog.EventType.INSIGHT_DETECTED,
                "insight",
                insightId,
                "system",
                "Insight detected: " + status + " - " + message,
                details,
                true,
                null
        );
    }

    public List<AuditLog> getAuditTrail(String traceId) {
        return auditLogRepository.findByTraceIdOrderByTimestampAsc(traceId);
    }

    public List<AuditLog> getEntityHistory(String entityType, String entityId) {
        return auditLogRepository.findByEntityTypeAndEntityIdOrderByTimestampAsc(entityType, entityId);
    }

    public List<AuditLog> getPlanHistory(String planId) {
        return auditLogRepository.findPlanHistory(planId);
    }

    private String tracePrefix(String traceId) {
        if (traceId == null || traceId.isBlank()) {
            return "no-trace";
        }
        return traceId.length() <= 20 ? traceId : traceId.substring(0, 20);
    }

    private AuditLog createLog(
            String traceId,
            AuditLog.EventType eventType,
            String entityType,
            String entityId,
            String actor,
            String action,
            Map<String, Object> details,
            boolean success,
            String errorMessage) {

        String detailsJson = null;
        try {
            detailsJson = objectMapper.writeValueAsString(details);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize audit log details: {}", e.getMessage());
        }

        AuditLog auditLog = AuditLog.builder()
                .traceId(traceId)
                .eventType(eventType)
                .entityType(entityType)
                .entityId(entityId)
                .actor(actor)
                .action(action)
                .details(detailsJson)
                .timestamp(Instant.now())
                .success(success)
                .errorMessage(errorMessage)
                .build();

        AuditLog saved = auditLogRepository.save(auditLog);
        log.info("📝 Audit: [{}] {} - {} - {}", tracePrefix(traceId), eventType, entityType, action);
        return saved;
    }

    /**
     * Log terminal command feedback from the device path.
     */
    @Transactional
    public AuditLog logCommandFeedback(String traceId, String commandId, String planId,
                                       String farmId, String assetId, String status, String error) {
        Map<String, Object> details = new HashMap<>();
        details.put("command_id", commandId);
        details.put("plan_id", planId);
        details.put("farm_id", farmId);
        details.put("target_asset", assetId);
        details.put("feedback_status", status);
        if (error != null && !error.isEmpty()) {
            details.put("error", error);
        }

        boolean success = "EXECUTED".equals(status);
        return createLog(
                traceId != null && !traceId.isEmpty() ? traceId : "feedback-" + commandId,
                success ? AuditLog.EventType.COMMAND_EXECUTED : AuditLog.EventType.COMMAND_FAILED,
                "command",
                commandId != null ? commandId : planId,
                "terra-sense",
                "Device feedback: " + status + " for asset " + assetId,
                details,
                success,
                success ? null : error
        );
    }
}
