package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.service.safety.SafetyValidator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** Manages action-plan approval, safety gating, outbox dispatch, and terminal lifecycle. */
@Slf4j
@Service
@RequiredArgsConstructor
public class ActionPlanService {

    private final ActionPlanRepository actionPlanRepository;
    private final SafetyValidator safetyValidator;
    private final AuditService auditService;
    private final ObjectMapper objectMapper;
    private final ActionPlanEventValidator eventValidator;
    private final ContractSchemaValidator contractSchemaValidator;
    private final CommandOutboxService commandOutboxService;

    @KafkaListener(topics = "action-plans", groupId = "${spring.kafka.consumer.group-id}")
    @Transactional
    public void consumeActionPlan(Map<String, Object> planEvent) {
        try {
            contractSchemaValidator.validate(ContractSchemaValidator.ACTION_PLAN_SCHEMA, planEvent);
            Optional<Map<String, Object>> validatedData = eventValidator.validate(planEvent);
            if (validatedData.isEmpty()) {
                throw new IllegalArgumentException("Invalid action plan event payload");
            }

            Map<String, Object> data = validatedData.get();
            String traceId = (String) data.get("trace_id");
            String planId = (String) data.get("plan_id");
            if (actionPlanRepository.findByPlanId(planId).isPresent()) {
                log.warn("Plan already exists: {}", planId);
                return;
            }

            String parametersJson = data.get("parameters") == null
                    ? null : objectMapper.writeValueAsString(data.get("parameters"));
            String safetyConditionsJson = data.get("safety_conditions") == null
                    ? null : objectMapper.writeValueAsString(data.get("safety_conditions"));
            String priorityStr = (String) data.getOrDefault("priority", "medium");

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
                    .priority(ActionPlan.ActionPriority.valueOf(priorityStr.toUpperCase()))
                    .estimatedImpact((String) data.get("estimated_impact"))
                    .safetyConditions(safetyConditionsJson)
                    .requiresApproval((Boolean) data.getOrDefault("requires_approval", true))
                    .generatedAt(defaultInstant(parseInstant(data.get("generated_at"))))
                    .expiresAt(parseInstant(data.get("expires_at")))
                    .build();

            actionPlanRepository.save(plan);
            auditService.logPlanCreated(plan);
        } catch (Exception e) {
            log.error("Failed to process action plan: {}", e.getClass().getSimpleName(), e);
            throw new IllegalStateException("Failed to process action plan event", e);
        }
    }

    public List<ActionPlan> getPendingPlans() {
        return actionPlanRepository.findByStatusOrderByPriorityDescCreatedAtDesc(ActionPlan.PlanStatus.PENDING);
    }

    public List<ActionPlan> getSafetyBlockedPlans() {
        return actionPlanRepository.findByStatusOrderByPriorityDescCreatedAtDesc(
                ActionPlan.PlanStatus.SAFETY_BLOCKED);
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
        ActionPlan plan = lockedPlan(planId);
        if (!plan.canBeApproved()) {
            throw new IllegalStateException(
                    "Plan cannot be approved: status=" + plan.getStatus() + ", expired=" + plan.isExpired());
        }

        plan.setStatus(ActionPlan.PlanStatus.APPROVED);
        plan.setApprovedBy(approvedBy);
        plan.setApprovedAt(Instant.now());
        plan.setRejectionReason(null);
        actionPlanRepository.save(plan);
        auditService.logPlanApproved(plan, approvedBy, notes);

        SafetyValidator.ValidationResult validation = validateAndAudit(plan);
        if (!validation.isOverallPassed()) {
            return applyValidationFailure(plan, validation);
        }

        commandOutboxService.enqueue(plan);
        log.info("Plan approved and queued: {}", planId);
        return plan;
    }

    @Transactional
    public ActionPlan revalidateSafety(String planId) {
        ActionPlan plan = lockedPlan(planId);
        if (!plan.canBeSafetyRevalidated()) {
            throw new IllegalStateException(
                    "Plan cannot be safety-revalidated: status=" + plan.getStatus()
                            + ", expired=" + plan.isExpired()
                            + ", commandPresent=" + (plan.getCommandId() != null));
        }

        String previousReason = plan.getSafetyBlockReasonCode();
        plan.setStatus(ActionPlan.PlanStatus.APPROVED);
        SafetyValidator.ValidationResult validation = validateAndAudit(plan);
        if (!validation.isOverallPassed()) {
            return applyValidationFailure(plan, validation);
        }

        plan.setSafetyBlockReasonCode(null);
        plan.setSafetyBlockedAt(null);
        plan.setExecutionResult(null);
        plan.setExecutionError(null);
        actionPlanRepository.save(plan);
        commandOutboxService.enqueue(plan);
        auditService.logPlanSafetyCleared(plan, previousReason);
        log.info("Safety block cleared and command queued: plan={}", planId);
        return plan;
    }

    private ActionPlan lockedPlan(String planId) {
        return actionPlanRepository.findByPlanIdForUpdate(planId)
                .orElseThrow(() -> new IllegalArgumentException("Plan not found: " + planId));
    }

    private SafetyValidator.ValidationResult validateAndAudit(ActionPlan plan) {
        SafetyValidator.ValidationResult validation = safetyValidator.validate(plan);
        List<String> reasonCodes = validation.isOverallPassed()
                ? List.of()
                : List.of(defaultReason(validation.getFailureReasonCode()));
        auditService.logPlanValidated(
                plan,
                validation.isOverallPassed(),
                validation.getFailedLayer(),
                reasonCodes);
        return validation;
    }

    private ActionPlan applyValidationFailure(
            ActionPlan plan,
            SafetyValidator.ValidationResult validation) {
        String reasonCode = defaultReason(validation.getFailureReasonCode());
        if ("DEVICE_STATE".equals(validation.getFailedLayer())) {
            plan.setStatus(ActionPlan.PlanStatus.SAFETY_BLOCKED);
            plan.setSafetyBlockReasonCode(reasonCode);
            plan.setSafetyBlockedAt(Instant.now());
            plan.setExecutionResult("DEVICE_SAFETY_BLOCKED");
            plan.setExecutionError(null);
            plan.setRejectionReason(null);
            actionPlanRepository.save(plan);
            auditService.logPlanSafetyBlocked(plan, reasonCode);
            triggerSafetyAlert(plan, validation);
            return plan;
        }

        plan.setStatus(ActionPlan.PlanStatus.REJECTED);
        plan.setRejectionReason("Safety validation failed: " + reasonCode);
        actionPlanRepository.save(plan);
        auditService.logPlanRejected(plan, "system", plan.getRejectionReason());
        triggerSafetyAlert(plan, validation);
        return plan;
    }

    @Transactional
    public ActionPlan rejectPlan(String planId, String rejectedBy, String reason) {
        ActionPlan plan = lockedPlan(planId);
        if (plan.getStatus() != ActionPlan.PlanStatus.PENDING
                && plan.getStatus() != ActionPlan.PlanStatus.SAFETY_BLOCKED) {
            throw new IllegalStateException("Only PENDING or SAFETY_BLOCKED plans can be rejected");
        }
        plan.setStatus(ActionPlan.PlanStatus.REJECTED);
        plan.setRejectionReason(reason);
        actionPlanRepository.save(plan);
        auditService.logPlanRejected(plan, rejectedBy, reason);
        return plan;
    }

    private void triggerSafetyAlert(
            ActionPlan plan,
            SafetyValidator.ValidationResult validation) {
        try {
            String alertId = "alert-" + java.util.UUID.randomUUID().toString().substring(0, 8);
            auditService.logAlertTriggered(
                    plan.getTraceId(),
                    alertId,
                    plan.getFarmId(),
                    "warning",
                    "Safety validation blocked action plan. layer="
                            + validation.getFailedLayer()
                            + " reason=" + defaultReason(validation.getFailureReasonCode()));
        } catch (Exception e) {
            log.error("Failed to trigger safety alert: {}", e.getClass().getSimpleName());
        }
    }

    @Scheduled(fixedRate = 60000)
    @Transactional
    public void expireOldPlans() {
        Instant now = Instant.now();
        expire(actionPlanRepository.findExpiredPendingPlans(now));
        expire(actionPlanRepository.findExpiredApprovedPlans(now));
        expire(actionPlanRepository.findExpiredSafetyBlockedPlans(now));
    }

    private void expire(List<ActionPlan> plans) {
        for (ActionPlan plan : plans) {
            plan.setStatus(ActionPlan.PlanStatus.EXPIRED);
            actionPlanRepository.save(plan);
            log.info("Plan expired before dispatch: {}", plan.getPlanId());
        }
    }

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
                "safety_blocked", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.SAFETY_BLOCKED),
                "in_flight", inFlight,
                "rejected", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.REJECTED),
                "executed", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.EXECUTED),
                "failed", failed,
                "expired", actionPlanRepository.countByStatus(ActionPlan.PlanStatus.EXPIRED),
                "pending_critical", actionPlanRepository.countPendingByPriority(ActionPlan.ActionPriority.CRITICAL),
                "pending_high", actionPlanRepository.countPendingByPriority(ActionPlan.ActionPriority.HIGH));
    }

    private Instant parseInstant(Object value) {
        return value instanceof String text ? Instant.parse(text) : null;
    }

    private Instant defaultInstant(Instant value) {
        return value != null ? value : Instant.now();
    }

    private String defaultReason(String reason) {
        return reason == null || reason.isBlank() ? "SAFETY_VALIDATION_FAILED" : reason;
    }
}
