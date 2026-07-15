package com.terraneuron.ops.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.service.safety.SafetyValidator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

/**
 * Action Plan Service
 * Manages the complete lifecycle of action plans with safety validation.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ActionPlanService {

    private final ActionPlanRepository actionPlanRepository;
    private final SafetyValidator safetyValidator;
    private final AuditService auditService;
    private final ObjectMapper objectMapper;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ActionPlanEventValidator eventValidator;
    private final ContractSchemaValidator contractSchemaValidator;

    private static final String COMMAND_TOPIC = "terra.control.command";
    private static final long COMMAND_DISPATCH_TIMEOUT_SECONDS = 10;

    /**
     * Kafka consumer for action-plans topic
     * Receives plans from terra-cortex and stores them for approval
     */
    @KafkaListener(topics = "action-plans", groupId = "${spring.kafka.consumer.group-id}")
    @Transactional
    public void consumeActionPlan(Map<String, Object> planEvent) {
        try {
            log.info("📥 Received action plan event from terra-cortex");

            contractSchemaValidator.validate(
                    ContractSchemaValidator.ACTION_PLAN_SCHEMA, planEvent);
            Optional<Map<String, Object>> validatedData = eventValidator.validate(planEvent);
            if (validatedData.isEmpty()) {
                throw new IllegalArgumentException("Invalid action plan event payload");
            }

            Map<String, Object> data = validatedData.get();
            String traceId = (String) data.get("trace_id");
            String planId = (String) data.get("plan_id");

            if (actionPlanRepository.findByPlanId(planId).isPresent()) {
                log.warn("⚠️ Plan already exists: {}", planId);
                return;
            }

            String parametersJson = null;
            Object params = data.get("parameters");
            if (params != null) {
                parametersJson = objectMapper.writeValueAsString(params);
            }

            String safetyConditionsJson = null;
            Object safetyConditions = data.get("safety_conditions");
            if (safetyConditions != null) {
                safetyConditionsJson = objectMapper.writeValueAsString(safetyConditions);
            }

            String priorityStr = (String) data.getOrDefault("priority", "medium");
            ActionPlan.ActionPriority priority = ActionPlan.ActionPriority.valueOf(priorityStr.toUpperCase());

            Instant generatedAt = parseInstant(data.get("generated_at"));
            Instant expiresAt = parseInstant(data.get("expires_at"));

            ActionPlan plan = ActionPlan.builder()
                    .planId(planId)
                    .traceId(traceId)
                    .farmId((String) data.get("farm_id"))
                    .planType((String) data.getOrDefault("plan_type", "input"))
                    .targetAssetId((String) data.get("target_asset_id"))
                    .targetAssetType((String) data.getOrDefault("target_asset_type", "device"))
                    .actionCategory((String) data.get("action_category"))
                    .actionType((String) data.get("action_type"))
                    .parameters(parametersJson)
                    .reasoning((String) data.get("reasoning"))
                    .status(ActionPlan.PlanStatus.PENDING)
                    .priority(priority)
                    .estimatedImpact((String) data.get("estimated_impact"))
                    .safetyConditions(safetyConditionsJson)
                    .requiresApproval((Boolean) data.getOrDefault("requires_approval", true))
                    .generatedAt(generatedAt != null ? generatedAt : Instant.now())
                    .expiresAt(expiresAt)
                    .build();

            actionPlanRepository.save(plan);
            log.info("✅ Action plan saved: {} ({})", planId, plan.getActionCategory());
            auditService.logPlanCreated(plan);

        } catch (Exception e) {
            log.error("❌ Failed to process action plan: {}", e.getMessage(), e);
            throw new IllegalStateException("Failed to process action plan event", e);
        }
    }

    public List<ActionPlan> getPendingPlans() {
        return actionPlanRepository.findByStatusOrderByPriorityDescCreatedAtDesc(ActionPlan.PlanStatus.PENDING);
    }

    public List<ActionPlan> getPendingPlansByFarm(String farmId) {
        return actionPlanRepository.findByStatusAndFarmId(ActionPlan.PlanStatus.PENDING, farmId);
    }

    public Page<ActionPlan> getPendingPlans(Pageable pageable) {
        return actionPlanRepository.findByStatus(ActionPlan.PlanStatus.PENDING, pageable);
    }

    public Optional<ActionPlan> getPlanById(String planId) {
        return actionPlanRepository.findByPlanId(planId);
    }

    @Transactional
    public ActionPlan approvePlan(String planId, String approvedBy, String notes) {
        ActionPlan plan = actionPlanRepository.findByPlanId(planId)
                .orElseThrow(() -> new IllegalArgumentException("Plan not found: " + planId));

        if (!plan.canBeApproved()) {
            throw new IllegalStateException("Plan cannot be approved: status=" + plan.getStatus() + ", expired=" + plan.isExpired());
        }

        plan.setStatus(ActionPlan.PlanStatus.APPROVED);
        plan.setApprovedBy(approvedBy);
        plan.setApprovedAt(Instant.now());

        SafetyValidator.ValidationResult validationResult = safetyValidator.validate(plan);
        auditService.logPlanValidated(plan, validationResult.isOverallPassed(),
                validationResult.getFailedLayer(), validationResult.getAllErrors());

        if (!validationResult.isOverallPassed()) {
            log.warn("⚠️ Safety validation failed for plan {}. Defaulting to ALERT_ONLY.", planId);
            plan.setStatus(ActionPlan.PlanStatus.REJECTED);
            plan.setRejectionReason("Safety validation failed at layer: " + validationResult.getFailedLayer() +
                    ". Errors: " + String.join("; ", validationResult.getAllErrors()));
            actionPlanRepository.save(plan);

            auditService.logPlanRejected(plan, "system", plan.getRejectionReason());
            triggerSafetyAlert(plan, validationResult);
            return plan;
        }

        actionPlanRepository.save(plan);
        log.info("✅ Plan approved: {} by {}", planId, approvedBy);
        auditService.logPlanApproved(plan, approvedBy, notes);

        dispatchPlan(plan);
        return plan;
    }

    @Transactional
    public ActionPlan rejectPlan(String planId, String rejectedBy, String reason) {
        ActionPlan plan = actionPlanRepository.findByPlanId(planId)
                .orElseThrow(() -> new IllegalArgumentException("Plan not found: " + planId));

        if (plan.getStatus() != ActionPlan.PlanStatus.PENDING) {
            throw new IllegalStateException("Only PENDING plans can be rejected");
        }

        plan.setStatus(ActionPlan.PlanStatus.REJECTED);
        plan.setRejectionReason(reason);
        actionPlanRepository.save(plan);

        log.info("❌ Plan rejected: {} by {} - Reason: {}", planId, rejectedBy, reason);
        auditService.logPlanRejected(plan, rejectedBy, reason);
        return plan;
    }

    /**
     * Dispatch an approved plan to Kafka.
     * Kafka acknowledgement proves transport acceptance, not physical execution.
     */
    @Transactional
    public void dispatchPlan(ActionPlan plan) {
        if (!plan.canBeDispatched()) {
            log.warn("⚠️ Plan cannot be dispatched: {} (status={})", plan.getPlanId(), plan.getStatus());
            return;
        }

        String commandId = "cmd-" + java.util.UUID.randomUUID();

        try {
            Map<String, Object> parameters = parseCommandParameters(plan.getParameters());

            Map<String, Object> commandEvent = Map.of(
                    "specversion", "1.0",
                    "type", "terra.ops.command.execute",
                    "source", "//terraneuron/terra-ops",
                    "id", java.util.UUID.randomUUID().toString(),
                    "time", Instant.now().toString(),
                    "datacontenttype", "application/json",
                    "data", Map.of(
                            "trace_id", plan.getTraceId(),
                            "plan_id", plan.getPlanId(),
                            "command_id", commandId,
                            "farm_id", plan.getFarmId(),
                            "target_asset_id", plan.getTargetAssetId(),
                            "action_type", plan.getActionType(),
                            "parameters", parameters,
                            "executed_by", plan.getApprovedBy()
                    )
            );

            plan.setCommandId(commandId);
            plan.setStatus(ActionPlan.PlanStatus.DISPATCHING);
            plan.setExecutionResult("PUBLISHING_TO_KAFKA");
            plan.setExecutionError(null);
            plan.setDispatchedAt(null);
            plan.setDeliveredAt(null);
            plan.setAckDeadlineAt(null);
            plan.setExecutedAt(null);
            actionPlanRepository.save(plan);

            kafkaTemplate.send(COMMAND_TOPIC, plan.getFarmId(), commandEvent)
                    .get(COMMAND_DISPATCH_TIMEOUT_SECONDS, TimeUnit.SECONDS);

            plan.setStatus(ActionPlan.PlanStatus.DISPATCHED);
            plan.setDispatchedAt(Instant.now());
            plan.setExecutionResult("KAFKA_ACKNOWLEDGED");
            actionPlanRepository.save(plan);

            log.info("📤 Command dispatched: plan={} command={} asset={} action={}",
                    plan.getPlanId(), commandId, plan.getTargetAssetId(), plan.getActionType());

        } catch (Exception e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }

            String error = rootCauseMessage(e);
            log.error("❌ Failed to dispatch plan {}: {}", plan.getPlanId(), error, e);
            plan.setStatus(ActionPlan.PlanStatus.DISPATCH_FAILED);
            plan.setExecutionResult("DISPATCH_FAILED");
            plan.setExecutionError(error);
            actionPlanRepository.save(plan);

            auditService.logCommandExecuted(plan, false, null, error);
        }
    }

    private void triggerSafetyAlert(ActionPlan plan, SafetyValidator.ValidationResult validationResult) {
        try {
            String alertId = "alert-" + java.util.UUID.randomUUID().toString().substring(0, 8);

            auditService.logAlertTriggered(
                    plan.getTraceId(),
                    alertId,
                    plan.getFarmId(),
                    "warning",
                    "Safety validation failed for action plan. Manual intervention required. " +
                            "Failed layer: " + validationResult.getFailedLayer()
            );

            log.info("🚨 Safety alert triggered for plan: {}", plan.getPlanId());
        } catch (Exception e) {
            log.error("Failed to trigger safety alert: {}", e.getMessage());
        }
    }

    @Scheduled(fixedRate = 60000)
    @Transactional
    public void expireOldPlans() {
        Instant now = Instant.now();

        List<ActionPlan> expiredPending = actionPlanRepository.findExpiredPendingPlans(now);
        for (ActionPlan plan : expiredPending) {
            plan.setStatus(ActionPlan.PlanStatus.EXPIRED);
            actionPlanRepository.save(plan);
            log.info("⏰ Plan expired: {}", plan.getPlanId());
        }

        List<ActionPlan> expiredApproved = actionPlanRepository.findExpiredApprovedPlans(now);
        for (ActionPlan plan : expiredApproved) {
            plan.setStatus(ActionPlan.PlanStatus.EXPIRED);
            actionPlanRepository.save(plan);
            log.info("⏰ Approved plan expired without dispatch: {}", plan.getPlanId());
        }
    }

    /**
     * Mark MQTT-delivered commands as timed out when no device acknowledgement arrives.
     */
    @Scheduled(fixedRateString = "${app.command.ack-timeout-scan-ms:30000}")
    @Transactional
    public void timeoutMissingDeviceAcknowledgements() {
        Instant now = Instant.now();
        List<ActionPlan> timedOut = actionPlanRepository.findByStatusAndAckDeadlineAtBefore(
                ActionPlan.PlanStatus.DELIVERED, now);

        for (ActionPlan plan : timedOut) {
            plan.setStatus(ActionPlan.PlanStatus.ACK_TIMEOUT);
            plan.setExecutionResult("DEVICE_ACK_TIMEOUT");
            plan.setExecutionError("No device acknowledgement received before " + plan.getAckDeadlineAt());
            actionPlanRepository.save(plan);
            auditService.logCommandTimeout(plan);
            log.warn("⏰ Device ACK timeout: plan={} command={}", plan.getPlanId(), plan.getCommandId());
        }
    }

    public Map<String, Long> getPlanStatistics() {
        long inFlight = actionPlanRepository.countByStatus(ActionPlan.PlanStatus.DISPATCHING)
                + actionPlanRepository.countByStatus(ActionPlan.PlanStatus.DISPATCHED)
                + actionPlanRepository.countByStatus(ActionPlan.PlanStatus.DELIVERED);
        long failed = actionPlanRepository.countByStatus(ActionPlan.PlanStatus.DISPATCH_FAILED)
                + actionPlanRepository.countByStatus(ActionPlan.PlanStatus.DELIVERY_FAILED)
                + actionPlanRepository.countByStatus(ActionPlan.PlanStatus.EXECUTION_FAILED)
                + actionPlanRepository.countByStatus(ActionPlan.PlanStatus.ACK_TIMEOUT)
                + actionPlanRepository.countByStatus(ActionPlan.PlanStatus.FAILED);

        return Map.of(
                "pending", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.PENDING),
                "approved", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.APPROVED),
                "in_flight", inFlight,
                "rejected", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.REJECTED),
                "executed", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.EXECUTED),
                "failed", failed,
                "expired", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.EXPIRED),
                "pending_critical", actionPlanRepository.countPendingByPriority(ActionPlan.ActionPriority.CRITICAL),
                "pending_high", actionPlanRepository.countPendingByPriority(ActionPlan.ActionPriority.HIGH)
        );
    }

    private Map<String, Object> parseCommandParameters(String parametersJson)
            throws JsonProcessingException {
        if (parametersJson == null || parametersJson.isBlank()) {
            return Map.of();
        }
        return objectMapper.readValue(
                parametersJson, new TypeReference<Map<String, Object>>() {});
    }

    private Instant parseInstant(Object value) {
        if (value == null) return null;
        if (value instanceof String) {
            return Instant.parse((String) value);
        }
        return null;
    }

    private String rootCauseMessage(Exception exception) {
        Throwable cause = exception;
        while (cause.getCause() != null) {
            cause = cause.getCause();
        }
        return cause.getMessage() != null ? cause.getMessage() : cause.getClass().getSimpleName();
    }
}
