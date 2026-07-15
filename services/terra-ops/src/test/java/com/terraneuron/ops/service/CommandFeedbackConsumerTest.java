package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.repository.ActionPlanRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CommandFeedbackConsumerTest {

    @Mock
    private ActionPlanRepository actionPlanRepository;
    @Mock
    private AuditService auditService;

    private CommandFeedbackConsumer consumer;

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
        consumer = new CommandFeedbackConsumer(
                actionPlanRepository,
                auditService,
                new ContractSchemaValidator(objectMapper),
                120);
    }

    @Test
    void deliveredFeedbackStartsDeviceAckDeadlineWithoutMarkingExecution() {
        ActionPlan plan = plan(ActionPlan.PlanStatus.DISPATCHED);
        when(actionPlanRepository.findByCommandId("cmd-1a2b3c4d")).thenReturn(Optional.of(plan));

        consumer.onFeedback(feedback("DELIVERED", "", "plan-123", "farm-001", "fan-01"));

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DELIVERED);
        assertThat(plan.getDeliveredAt()).isNotNull();
        assertThat(plan.getAckDeadlineAt()).isAfter(plan.getDeliveredAt());
        assertThat(plan.getExecutedAt()).isNull();
        assertThat(plan.getExecutionResult()).isEqualTo("MQTT_PUBLISH_CONFIRMED");
        verify(actionPlanRepository).save(plan);
        verify(auditService, never()).logCommandFeedback(
                anyString(), anyString(), anyString(), anyString(), anyString(), anyString(), anyString());
    }

    @Test
    void executedFeedbackMarksOnlyTheCorrelatedCommandComplete() {
        ActionPlan plan = plan(ActionPlan.PlanStatus.DELIVERED);
        plan.setAckDeadlineAt(Instant.now().plusSeconds(120));
        when(actionPlanRepository.findByCommandId("cmd-1a2b3c4d")).thenReturn(Optional.of(plan));

        consumer.onFeedback(feedback("EXECUTED", "", "plan-123", "farm-001", "fan-01"));

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.EXECUTED);
        assertThat(plan.getExecutedAt()).isNotNull();
        assertThat(plan.getAckDeadlineAt()).isNull();
        assertThat(plan.getExecutionResult()).isEqualTo("DEVICE_CONFIRMED");
        verify(auditService).logCommandFeedback(
                eq("trace-123"), eq("cmd-1a2b3c4d"), eq("plan-123"),
                eq("farm-001"), eq("fan-01"), eq("EXECUTED"), eq(""));
    }

    @Test
    void lateExecutionAckResolvesPreviousTimeoutTruthfully() {
        ActionPlan plan = plan(ActionPlan.PlanStatus.ACK_TIMEOUT);
        plan.setExecutionResult("DEVICE_ACK_TIMEOUT");
        plan.setExecutionError("No device acknowledgement received before deadline");
        when(actionPlanRepository.findByCommandId("cmd-1a2b3c4d")).thenReturn(Optional.of(plan));

        consumer.onFeedback(feedback("EXECUTED", "", "plan-123", "farm-001", "fan-01"));

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.EXECUTED);
        assertThat(plan.getExecutionResult()).isEqualTo("DEVICE_CONFIRMED_LATE");
        assertThat(plan.getExecutionError()).isNull();
        assertThat(plan.getExecutedAt()).isNotNull();
    }

    @Test
    void failedBridgeFeedbackBecomesDeliveryFailure() {
        ActionPlan plan = plan(ActionPlan.PlanStatus.DISPATCHED);
        when(actionPlanRepository.findByCommandId("cmd-1a2b3c4d")).thenReturn(Optional.of(plan));

        consumer.onFeedback(feedback(
                "FAILED", "broker unavailable", "plan-123", "farm-001", "fan-01"));

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DELIVERY_FAILED);
        assertThat(plan.getExecutedAt()).isNull();
        assertThat(plan.getExecutionResult()).isEqualTo("MQTT_DELIVERY_FAILED");
        assertThat(plan.getExecutionError()).isEqualTo("broker unavailable");
        verify(auditService).logCommandFeedback(
                eq("trace-123"), eq("cmd-1a2b3c4d"), eq("plan-123"),
                eq("farm-001"), eq("fan-01"), eq("FAILED"), eq("broker unavailable"));
    }

    @Test
    void deviceFailureAfterDeliveryBecomesExecutionFailure() {
        ActionPlan plan = plan(ActionPlan.PlanStatus.DELIVERED);
        plan.setAckDeadlineAt(Instant.now().plusSeconds(120));
        when(actionPlanRepository.findByCommandId("cmd-1a2b3c4d")).thenReturn(Optional.of(plan));

        consumer.onFeedback(feedback(
                "FAILED", "motor blocked", "plan-123", "farm-001", "fan-01"));

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.EXECUTION_FAILED);
        assertThat(plan.getAckDeadlineAt()).isNull();
        assertThat(plan.getExecutionResult()).isEqualTo("DEVICE_EXECUTION_FAILED");
        assertThat(plan.getExecutionError()).isEqualTo("motor blocked");
    }

    @Test
    void mismatchedPlanIdentityCannotAcknowledgeCommand() {
        ActionPlan plan = plan(ActionPlan.PlanStatus.DELIVERED);
        when(actionPlanRepository.findByCommandId("cmd-1a2b3c4d")).thenReturn(Optional.of(plan));

        assertThatThrownBy(() -> consumer.onFeedback(
                feedback("EXECUTED", "", "plan-other", "farm-001", "fan-01")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Failed to process command feedback event")
                .hasRootCauseMessage("Feedback plan_id does not match command owner");

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DELIVERED);
        verify(actionPlanRepository, never()).save(plan);
        verify(auditService, never()).logCommandFeedback(
                anyString(), anyString(), anyString(), anyString(), anyString(), anyString(), anyString());
    }

    private ActionPlan plan(ActionPlan.PlanStatus status) {
        return ActionPlan.builder()
                .planId("plan-123")
                .traceId("trace-123")
                .commandId("cmd-1a2b3c4d")
                .farmId("farm-001")
                .targetAssetId("fan-01")
                .actionCategory("ventilation")
                .actionType("turn_on")
                .status(status)
                .priority(ActionPlan.ActionPriority.MEDIUM)
                .generatedAt(Instant.now())
                .build();
    }

    private Map<String, Object> feedback(
            String status, String error, String planId, String farmId, String assetId) {
        return Map.of(
                "specversion", "1.0",
                "type", "terra.sense.command.feedback",
                "source", "//terraneuron/terra-sense",
                "id", "e5f6a7b8-c9d0-4e12-9fab-34567890abcd",
                "time", "2025-12-09T10:35:01Z",
                "datacontenttype", "application/json",
                "data", Map.of(
                        "trace_id", "trace-123",
                        "command_id", "cmd-1a2b3c4d",
                        "plan_id", planId,
                        "farm_id", farmId,
                        "target_asset_id", assetId,
                        "status", status,
                        "error", error,
                        "timestamp", "2025-12-09T10:35:01Z"));
    }
}
