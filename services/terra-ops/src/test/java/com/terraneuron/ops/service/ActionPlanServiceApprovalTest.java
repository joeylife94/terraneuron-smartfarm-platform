package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.service.safety.SafetyValidator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ActionPlanServiceApprovalTest {

    @Mock
    private ActionPlanRepository actionPlanRepository;
    @Mock
    private AuditService auditService;
    @Mock
    private ActionPlanEventValidator eventValidator;
    @Mock
    private CommandOutboxService commandOutboxService;

    private ActionPlanService service;

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        SafetyValidator safetyValidator = new SafetyValidator();
        service = new ActionPlanService(
                actionPlanRepository,
                safetyValidator,
                auditService,
                objectMapper,
                eventValidator,
                new ContractSchemaValidator(objectMapper),
                commandOutboxService);
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
    void validPendingPlanIsApprovedAndAtomicallyQueuedForDispatch() {
        ActionPlan plan = pendingPlanBuilder().build();
        when(actionPlanRepository.findByPlanId("plan-1")).thenReturn(Optional.of(plan));
        stubOutboxEnqueue();

        ActionPlan result = service.approvePlan("plan-1", "operator", "looks good");

        assertThat(result.getStatus()).isEqualTo(ActionPlan.PlanStatus.DISPATCHING);
        assertThat(result.getCommandId()).isEqualTo("cmd-outbox-1");
        assertThat(result.getDispatchedAt()).isNull();
        assertThat(result.getExecutedAt()).isNull();
        assertThat(result.getExecutionResult()).isEqualTo("COMMAND_OUTBOX_PENDING");
        assertThat(result.getApprovedBy()).isEqualTo("operator");
        assertThat(result.getApprovedAt()).isNotNull();

        verify(commandOutboxService).enqueue(plan);
        verify(auditService).logPlanApproved(eq(plan), eq("operator"), eq("looks good"));
        verify(auditService, never()).logCommandExecuted(eq(plan), eq(true), any(), any());
    }

    @Test
    void deliveredCommandWithoutDeviceAckBecomesAckTimeout() {
        ActionPlan plan = pendingPlanBuilder()
                .commandId("cmd-1a2b3c4d")
                .status(ActionPlan.PlanStatus.DELIVERED)
                .deliveredAt(Instant.now().minusSeconds(180))
                .ackDeadlineAt(Instant.now().minusSeconds(60))
                .build();
        when(actionPlanRepository.findByStatusAndAckDeadlineAtBefore(
                eq(ActionPlan.PlanStatus.DELIVERED), any(Instant.class)))
                .thenReturn(List.of(plan));

        service.timeoutMissingDeviceAcknowledgements();

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.ACK_TIMEOUT);
        assertThat(plan.getExecutionResult()).isEqualTo("DEVICE_ACK_TIMEOUT");
        assertThat(plan.getExecutionError()).contains("No device acknowledgement");
        assertThat(plan.getExecutedAt()).isNull();
        verify(actionPlanRepository).save(plan);
        verify(auditService).logCommandTimeout(plan);
    }

    @Test
    void invalidPlanIsRejectedAndNoCommandQueued() {
        ActionPlan plan = pendingPlanBuilder()
                .actionType(null)
                .build();
        when(actionPlanRepository.findByPlanId("plan-1")).thenReturn(Optional.of(plan));

        ActionPlan result = service.approvePlan("plan-1", "operator", "approve attempt");

        assertThat(result.getStatus()).isEqualTo(ActionPlan.PlanStatus.REJECTED);
        assertThat(result.getRejectionReason()).contains("LOGICAL");

        verify(commandOutboxService, never()).enqueue(any());
        verify(auditService).logPlanRejected(eq(plan), eq("system"), anyString());
        verify(auditService, never()).logPlanApproved(any(), anyString(), any());
    }

    @Test
    void validationOutcomeIsAlwaysAudited() {
        ActionPlan plan = pendingPlanBuilder().build();
        when(actionPlanRepository.findByPlanId("plan-1")).thenReturn(Optional.of(plan));
        stubOutboxEnqueue();

        service.approvePlan("plan-1", "operator", "ok");

        verify(auditService).logPlanValidated(eq(plan), anyBoolean(), any(), any());
    }

    private void stubOutboxEnqueue() {
        doAnswer(invocation -> {
            ActionPlan plan = invocation.getArgument(0);
            plan.setCommandId("cmd-outbox-1");
            plan.setStatus(ActionPlan.PlanStatus.DISPATCHING);
            plan.setExecutionResult("COMMAND_OUTBOX_PENDING");
            return null;
        }).when(commandOutboxService).enqueue(any(ActionPlan.class));
    }
}
