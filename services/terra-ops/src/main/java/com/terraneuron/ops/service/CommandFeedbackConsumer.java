package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.repository.ActionPlanRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Map;

/**
 * Consumes transport and device feedback for a dispatched command.
 * A plan reaches EXECUTED only when feedback is correlated to its persisted command ID.
 */
@Slf4j
@Service
public class CommandFeedbackConsumer {

    private final ActionPlanRepository actionPlanRepository;
    private final AuditService auditService;
    private final ContractSchemaValidator contractSchemaValidator;
    private final long ackTimeoutSeconds;

    public CommandFeedbackConsumer(
            ActionPlanRepository actionPlanRepository,
            AuditService auditService,
            ContractSchemaValidator contractSchemaValidator,
            @Value("${app.command.ack-timeout-seconds:120}") long ackTimeoutSeconds) {
        this.actionPlanRepository = actionPlanRepository;
        this.auditService = auditService;
        this.contractSchemaValidator = contractSchemaValidator;
        this.ackTimeoutSeconds = ackTimeoutSeconds;
    }

    @KafkaListener(
            topics = "terra.control.feedback",
            groupId = "${spring.kafka.consumer.group-id}"
    )
    @Transactional
    public void onFeedback(Map<String, Object> feedbackEvent) {
        try {
            contractSchemaValidator.validate(
                    ContractSchemaValidator.FEEDBACK_SCHEMA, feedbackEvent);

            @SuppressWarnings("unchecked")
            Map<String, Object> data = (Map<String, Object>) feedbackEvent.get("data");
            if (data == null) {
                throw new IllegalArgumentException("Invalid command feedback event: missing data field");
            }

            String traceId = requiredString(data, "trace_id");
            String commandId = requiredString(data, "command_id");
            String planId = requiredString(data, "plan_id");
            String status = requiredString(data, "status");
            String error = (String) data.getOrDefault("error", "");
            String farmId = requiredString(data, "farm_id");
            String assetId = requiredString(data, "target_asset_id");

            log.info("📥 Command feedback: plan={} command={} status={}", planId, commandId, status);

            ActionPlan plan = actionPlanRepository.findByCommandId(commandId)
                    .orElseThrow(() -> new IllegalArgumentException(
                            "No action plan found for command_id=" + commandId));

            validateCorrelation(plan, planId, farmId, assetId);
            boolean changed = updatePlanFromFeedback(plan, status, error);

            if (changed && ("EXECUTED".equals(status) || "FAILED".equals(status))) {
                auditService.logCommandFeedback(
                        traceId, commandId, planId, farmId, assetId, status, error);
            }

        } catch (Exception e) {
            log.error("❌ Failed to process command feedback: {}", e.getMessage(), e);
            throw new IllegalStateException("Failed to process command feedback event", e);
        }
    }

    private boolean updatePlanFromFeedback(ActionPlan plan, String status, String error) {
        ActionPlan.PlanStatus current = plan.getStatus();
        Instant now = Instant.now();

        switch (status) {
            case "DELIVERED":
                if (current == ActionPlan.PlanStatus.DISPATCHED) {
                    plan.setStatus(ActionPlan.PlanStatus.DELIVERED);
                    plan.setDeliveredAt(now);
                    plan.setAckDeadlineAt(now.plusSeconds(ackTimeoutSeconds));
                    plan.setExecutionResult("MQTT_PUBLISH_CONFIRMED");
                    plan.setExecutionError(null);
                    actionPlanRepository.save(plan);
                    log.info("   📡 MQTT delivery confirmed: plan={} command={} deadline={}",
                            plan.getPlanId(), plan.getCommandId(), plan.getAckDeadlineAt());
                    return true;
                }
                if (current == ActionPlan.PlanStatus.DELIVERED || current == ActionPlan.PlanStatus.EXECUTED) {
                    log.info("   ℹ️ Ignoring duplicate or late DELIVERED feedback: plan={} status={}",
                            plan.getPlanId(), current);
                    return false;
                }
                throw invalidTransition(plan, status);

            case "EXECUTED":
                if (current == ActionPlan.PlanStatus.DISPATCHED
                        || current == ActionPlan.PlanStatus.DELIVERED
                        || current == ActionPlan.PlanStatus.ACK_TIMEOUT) {
                    boolean late = current == ActionPlan.PlanStatus.ACK_TIMEOUT;
                    plan.setStatus(ActionPlan.PlanStatus.EXECUTED);
                    plan.setExecutedAt(now);
                    plan.setAckDeadlineAt(null);
                    plan.setExecutionResult(late ? "DEVICE_CONFIRMED_LATE" : "DEVICE_CONFIRMED");
                    plan.setExecutionError(null);
                    actionPlanRepository.save(plan);
                    log.info("   ✅ Device execution confirmed: plan={} command={} late={}",
                            plan.getPlanId(), plan.getCommandId(), late);
                    return true;
                }
                if (current == ActionPlan.PlanStatus.EXECUTED) {
                    log.info("   ℹ️ Ignoring duplicate EXECUTED feedback: plan={}", plan.getPlanId());
                    return false;
                }
                throw invalidTransition(plan, status);

            case "FAILED":
                if (current == ActionPlan.PlanStatus.DISPATCHED) {
                    plan.setStatus(ActionPlan.PlanStatus.DELIVERY_FAILED);
                    plan.setExecutionResult("MQTT_DELIVERY_FAILED");
                } else if (current == ActionPlan.PlanStatus.DELIVERED
                        || current == ActionPlan.PlanStatus.ACK_TIMEOUT) {
                    plan.setStatus(ActionPlan.PlanStatus.EXECUTION_FAILED);
                    plan.setExecutionResult("DEVICE_EXECUTION_FAILED");
                    plan.setAckDeadlineAt(null);
                } else if (current == ActionPlan.PlanStatus.DELIVERY_FAILED
                        || current == ActionPlan.PlanStatus.EXECUTION_FAILED) {
                    log.info("   ℹ️ Ignoring duplicate FAILED feedback: plan={} status={}",
                            plan.getPlanId(), current);
                    return false;
                } else {
                    throw invalidTransition(plan, status);
                }

                plan.setExecutionError(error);
                actionPlanRepository.save(plan);
                log.warn("   ❌ Command failure: plan={} command={} state={} error={}",
                        plan.getPlanId(), plan.getCommandId(), plan.getStatus(), error);
                return true;

            default:
                throw new IllegalArgumentException("Unsupported feedback status: " + status);
        }
    }

    private void validateCorrelation(ActionPlan plan, String planId, String farmId, String assetId) {
        if (!plan.getPlanId().equals(planId)) {
            throw new IllegalArgumentException("Feedback plan_id does not match command owner");
        }
        if (!plan.getFarmId().equals(farmId)) {
            throw new IllegalArgumentException("Feedback farm_id does not match command owner");
        }
        if (!plan.getTargetAssetId().equals(assetId)) {
            throw new IllegalArgumentException("Feedback target_asset_id does not match command owner");
        }
    }

    private String requiredString(Map<String, Object> data, String field) {
        Object value = data.get(field);
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalArgumentException("Invalid command feedback event: missing " + field);
        }
        return text;
    }

    private IllegalStateException invalidTransition(ActionPlan plan, String feedbackStatus) {
        return new IllegalStateException(
                "Cannot apply " + feedbackStatus + " feedback to plan " + plan.getPlanId()
                        + " in status " + plan.getStatus());
    }
}
