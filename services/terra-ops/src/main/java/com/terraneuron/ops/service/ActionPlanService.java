package com.terraneuron.ops.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.dto.ActionPlanDto;
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

    private static final String COMMAND_TOPIC = "terra.control.command";

    /**
     * Kafka consumer for action-plans topic
     * Receives plans from terra-cortex and stores them for approval
     */
    @KafkaListener(topics = "action-plans", groupId = "${spring.kafka.consumer.group-id}")
    @Transactional
    public void consumeActionPlan(Map<String, Object> planEvent) {
        try {
            log.info("📥 Received action plan from terra-cortex");
            
            // Extract data from CloudEvents format
            @SuppressWarnings("unchecked")
            Map<String, Object> data = (Map<String, Object>) planEvent.get("data");
            if (data == null) {
                log.error("❌ Invalid CloudEvent: missing 'data' field");
                return;
            }

            String traceId = (String) data.get("trace_id");
            String planId = (String) data.get("plan_id");

            // Check if plan already exists
            if (actionPlanRepository.findByPlanId(planId).isPresent()) {
                log.warn("⚠️ Plan already exists: {}", planId);
                return;
            }

            // Convert parameters to JSON string
            String parametersJson = null;
            Object params = data.get("parameters");
            if (params != null) {
                parametersJson = objectMapper.writeValueAsString(params);
            }

            // Convert safety conditions to JSON string
            String safetyConditionsJson = null;
            Object safetyConditions = data.get("safety_conditions");
            if (safetyConditions != null) {
                safetyConditionsJson = objectMapper.writeValueAsString(safetyConditions);
            }

            // Parse priority
            String priorityStr = (String) data.getOrDefault("priority", "medium");
            ActionPlan.ActionPriority priority = ActionPlan.ActionPriority.valueOf(priorityStr.toUpperCase());

            // Parse timestamps
            Instant generatedAt = parseInstant(data.get("generated_at"));
            Instant expiresAt = parseInstant(data.get("expires_at"));

            // Create ActionPlan entity
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

            // Audit log
            auditService.logPlanCreated(plan);

        } catch (Exception e) {
            log.error("❌ Failed to process action plan: {}", e.getMessage(), e);
        }
    }

    /**
     * Get all pending action plans
     */
    public List<ActionPlan> getPendingPlans() {
        return actionPlanRepository.findByStatusOrderByPriorityDescCreatedAtDesc(ActionPlan.PlanStatus.PENDING);
    }

    /**
     * Get pending plans by farm
     */
    public List<ActionPlan> getPendingPlansByFarm(String farmId) {
        return actionPlanRepository.findByStatusAndFarmId(ActionPlan.PlanStatus.PENDING, farmId);
    }

    /**
     * Get pending plans with pagination
     */
    public Page<ActionPlan> getPendingPlans(Pageable pageable) {
        return actionPlanRepository.findByStatus(ActionPlan.PlanStatus.PENDING, pageable);
    }

    /**
     * Get plan by ID
     */
    public Optional<ActionPlan> getPlanById(String planId) {
        return actionPlanRepository.findByPlanId(planId);
    }

    /**
     * Approve an action plan
     */
    @Transactional
    public ActionPlan approvePlan(String planId, String approvedBy, String notes) {
        ActionPlan plan = actionPlanRepository.findByPlanId(planId)
                .orElseThrow(() -> new IllegalArgumentException("Plan not found: " + planId));

        if (!plan.canBeApproved()) {
            throw new IllegalStateException("Plan cannot be approved: status=" + plan.getStatus() + ", expired=" + plan.isExpired());
        }

        // Run safety validation
        SafetyValidator.ValidationResult validationResult = safetyValidator.validate(plan);
        auditService.logPlanValidated(plan, validationResult.isOverallPassed(), 
                validationResult.getFailedLayer(), validationResult.getAllErrors());

        if (!validationResult.isOverallPassed()) {
            // Fail-safe: Default to ALERT_ONLY instead of execution
            log.warn("⚠️ Safety validation failed for plan {}. Defaulting to ALERT_ONLY.", planId);
            plan.setStatus(ActionPlan.PlanStatus.REJECTED);
            plan.setRejectionReason("Safety validation failed at layer: " + validationResult.getFailedLayer() + 
                    ". Errors: " + String.join("; ", validationResult.getAllErrors()));
            actionPlanRepository.save(plan);
            
            auditService.logPlanRejected(plan, "system", plan.getRejectionReason());
            
            // Trigger alert instead
            triggerSafetyAlert(plan, validationResult);
            
            return plan;
        }

        // Update plan status
        plan.setStatus(ActionPlan.PlanStatus.APPROVED);
        plan.setApprovedBy(approvedBy);
        plan.setApprovedAt(Instant.now());
        actionPlanRepository.save(plan);

        log.info("✅ Plan approved: {} by {}", planId, approvedBy);
        auditService.logPlanApproved(plan, approvedBy, notes);

        // Execute the approved plan
        executePlan(plan);

        return plan;
    }

    /**
     * Reject an action plan
     */
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
     * Execute an approved plan by sending command to control topic
     */
    @Transactional
    public void executePlan(ActionPlan plan) {
        if (!plan.canBeExecuted()) {
            log.warn("⚠️ Plan cannot be executed: {}", plan.getPlanId());
            return;
        }

        try {
            // Build command event
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
                            "command_id", "cmd-" + java.util.UUID.randomUUID().toString().substring(0, 8),
                            "target_asset_id", plan.getTargetAssetId(),
                            "action_type", plan.getActionType(),
                            "parameters", plan.getParameters() != null ? plan.getParameters() : "{}",
                            "executed_by", plan.getApprovedBy()
                    )
            );

            // Send to control topic
            kafkaTemplate.send(COMMAND_TOPIC, plan.getFarmId(), commandEvent);
            
            // Update plan status
            plan.setStatus(ActionPlan.PlanStatus.EXECUTED);
            plan.setExecutedAt(Instant.now());
            plan.setExecutionResult("SENT_TO_DEVICE");
            actionPlanRepository.save(plan);

            log.info("📤 Command sent: {} -> {} ({})", plan.getPlanId(), plan.getTargetAssetId(), plan.getActionType());
            auditService.logCommandExecuted(plan, true, "SENT_TO_DEVICE", null);

        } catch (Exception e) {
            log.error("❌ Failed to execute plan {}: {}", plan.getPlanId(), e.getMessage());
            plan.setStatus(ActionPlan.PlanStatus.FAILED);
            plan.setExecutionError(e.getMessage());
            actionPlanRepository.save(plan);
            
            auditService.logCommandExecuted(plan, false, null, e.getMessage());
        }
    }

    /**
     * Trigger safety alert when validation fails
     */
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

    /**
     * Scheduled task to expire old pending plans
     */
    @Scheduled(fixedRate = 60000) // Every minute
    @Transactional
    public void expireOldPlans() {
        Instant now = Instant.now();
        
        // Expire pending plans
        List<ActionPlan> expiredPending = actionPlanRepository.findExpiredPendingPlans(now);
        for (ActionPlan plan : expiredPending) {
            plan.setStatus(ActionPlan.PlanStatus.EXPIRED);
            actionPlanRepository.save(plan);
            log.info("⏰ Plan expired: {}", plan.getPlanId());
        }

        // Expire approved but not executed plans
        List<ActionPlan> expiredApproved = actionPlanRepository.findExpiredApprovedPlans(now);
        for (ActionPlan plan : expiredApproved) {
            plan.setStatus(ActionPlan.PlanStatus.EXPIRED);
            actionPlanRepository.save(plan);
            log.info("⏰ Approved plan expired without execution: {}", plan.getPlanId());
        }
    }

    /**
     * Get plan statistics
     */
    public Map<String, Long> getPlanStatistics() {
        return Map.of(
                "pending", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.PENDING),
                "approved", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.APPROVED),
                "rejected", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.REJECTED),
                "executed", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.EXECUTED),
                "failed", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.FAILED),
                "expired", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.EXPIRED),
                "pending_critical", actionPlanRepository.countPendingByPriority(ActionPlan.ActionPriority.CRITICAL),
                "pending_high", actionPlanRepository.countPendingByPriority(ActionPlan.ActionPriority.HIGH)
        );
    }

    // ========== Helper Methods ==========

    private Instant parseInstant(Object value) {
        if (value == null) return null;
        if (value instanceof String) {
            return Instant.parse((String) value);
        }
        return null;
    }
}
