package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.service.safety.SafetyValidator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Focused unit tests for {@link ActionPlanService#approvePlan}.
 */
@ExtendWith(MockitoExtension.class)
class ActionPlanServiceApprovalTest {

    @Mock
    private ActionPlanRepository actionPlanRepository;
    @Mock
    private AuditService auditService;
    @Mock
    private KafkaTemplate<String, Object> kafkaTemplate;
    @Mock
    private ActionPlanEventValidator eventValidator;

    private ActionPlanService service;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        SafetyValidator safetyValidator = new SafetyValidator();
        service = new ActionPlanService(
                actionPlanRepository,
                safetyValidator,
                auditService,
                objectMapper,
                kafkaTemplate,
                eventValidator,
                new ContractSchemaValidator(objectMapper));
    }

    private ActionPlan.ActionPlanBuilder pendingPlanBuilder() {
        return ActionPlan.builder()
                .planId("plan-1")
                .traceId("trace-0000000000000001")
                .farmId("farm-1")
                .targetAssetId("fan-01")
                .actionCategory("ventilation")
                .actionType("turn_on")
                .parameters("{\"duration_minutes\":30,\"speed_level\":\"high\"}")
                .reasoning("Temperature exceeds threshold")
                .status(ActionPlan.PlanStatus.PENDING)
                .priority(ActionPlan.ActionPriority.MEDIUM)
                .requiresApproval(true)
                .generatedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(3600));
    }

    @Test
    void validPendingPlanIsApprovedAndDispatchedButNotExecuted() {
        ActionPlan plan = pendingPlanBuilder().build();
        when(actionPlanRepository.findByPlanId("plan-1")).thenReturn(Optional.of(plan));
        stubSuccessfulDispatch();

        ActionPlan result = service.approvePlan("plan-1", "operator", "looks good");

        assertThat(result.getStatus()).isEqualTo(ActionPlan.PlanStatus.DISPATCHED);
        assertThat(result.getExecutedAt()).isNull();
        assertThat(result.getExecutionResult()).startsWith("KAFKA_ACKNOWLEDGED:cmd-");
        assertThat(result.getApprovedBy()).isEqualTo("operator");
        assertThat(result.getApprovedAt()).isNotNull();

        ArgumentCaptor<Object> eventCaptor = ArgumentCaptor.forClass(Object.class);
        verify(kafkaTemplate, times(1)).send(
                eq("terra.control.command"), eq("farm-1"), eventCaptor.capture());
        @SuppressWarnings("unchecked")
        Map<String, Object> commandEvent = (Map<String, Object>) eventCaptor.getValue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) commandEvent.get("data");
        assertThat(commandEvent.get("type")).isEqualTo("terra.ops.command.execute");
        assertThat(data.get("farm_id")).isEqualTo("farm-1");
        assertThat(data.get("parameters")).isEqualTo(Map.of(
                "duration_minutes", 30,
                "speed_level", "high"));
        verify(auditService).logPlanApproved(eq(plan), eq("operator"), eq("looks good"));
        verify(auditService, never()).logCommandExecuted(eq(plan), eq(true), any(), any());
    }

    @Test
    void kafkaPublishFailureEndsInDispatchFailedNotExecuted() {
        ActionPlan plan = pendingPlanBuilder().build();
        when(actionPlanRepository.findByPlanId("plan-1")).thenReturn(Optional.of(plan));
        stubFailedDispatch("broker unavailable");

        ActionPlan result = service.approvePlan("plan-1", "operator", "looks good");

        assertThat(result.getStatus()).isEqualTo(ActionPlan.PlanStatus.DISPATCH_FAILED);
        assertThat(result.getExecutedAt()).isNull();
        assertThat(result.getExecutionResult()).startsWith("DISPATCH_FAILED:cmd-");
        assertThat(result.getExecutionError()).contains("broker unavailable");
        verify(auditService).logCommandExecuted(eq(plan), eq(false), eq(null), anyString());
    }

    @Test
    void invalidPlanIsRejectedAndNoCommandPublished() {
        ActionPlan plan = pendingPlanBuilder()
                .actionType(null)
                .build();
        when(actionPlanRepository.findByPlanId("plan-1")).thenReturn(Optional.of(plan));

        ActionPlan result = service.approvePlan("plan-1", "operator", "approve attempt");

        assertThat(result.getStatus()).isEqualTo(ActionPlan.PlanStatus.REJECTED);
        assertThat(result.getRejectionReason()).contains("LOGICAL");

        verify(kafkaTemplate, never()).send(anyString(), anyString(), any());
        verify(auditService).logPlanRejected(eq(plan), eq("system"), anyString());
        verify(auditService, never()).logPlanApproved(any(), anyString(), any());
    }

    @Test
    void validationOutcomeIsAlwaysAudited() {
        ActionPlan plan = pendingPlanBuilder().build();
        when(actionPlanRepository.findByPlanId("plan-1")).thenReturn(Optional.of(plan));
        stubSuccessfulDispatch();

        service.approvePlan("plan-1", "operator", "ok");

        verify(auditService).logPlanValidated(eq(plan), anyBoolean(), any(), any());
    }

    private void stubSuccessfulDispatch() {
        CompletableFuture<SendResult<String, Object>> result =
                CompletableFuture.completedFuture(null);
        when(kafkaTemplate.send(eq("terra.control.command"), eq("farm-1"), any()))
                .thenReturn(result);
    }

    private void stubFailedDispatch(String message) {
        CompletableFuture<SendResult<String, Object>> result = new CompletableFuture<>();
        result.completeExceptionally(new RuntimeException(message));
        when(kafkaTemplate.send(eq("terra.control.command"), eq("farm-1"), any()))
                .thenReturn(result);
    }
}
