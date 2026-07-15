package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.entity.CommandOutboxEvent;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.repository.CommandOutboxRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CommandOutboxStateServiceTest {

    @Mock
    private CommandOutboxRepository commandOutboxRepository;
    @Mock
    private ActionPlanRepository actionPlanRepository;
    @Mock
    private AuditService auditService;

    private CommandOutboxStateService service;

    @BeforeEach
    void setUp() {
        service = new CommandOutboxStateService(
                commandOutboxRepository,
                actionPlanRepository,
                auditService);
    }

    @Test
    void kafkaAcknowledgementMarksOutboxAndDispatchesPlan() {
        Instant publishedAt = Instant.parse("2026-07-16T01:00:00Z");
        CommandOutboxEvent event = event(0);
        ActionPlan plan = plan(ActionPlan.PlanStatus.DISPATCHING);
        when(commandOutboxRepository.findById(1L)).thenReturn(Optional.of(event));
        when(actionPlanRepository.findByCommandId("cmd-1")).thenReturn(Optional.of(plan));

        service.markPublished(1L, publishedAt);

        assertThat(event.getStatus()).isEqualTo(CommandOutboxEvent.OutboxStatus.PUBLISHED);
        assertThat(event.getPublishedAt()).isEqualTo(publishedAt);
        assertThat(event.getLockedAt()).isNull();
        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DISPATCHED);
        assertThat(plan.getDispatchedAt()).isEqualTo(publishedAt);
        assertThat(plan.getExecutionResult()).isEqualTo("KAFKA_ACKNOWLEDGED");
        verify(commandOutboxRepository).save(event);
        verify(actionPlanRepository).save(plan);
    }

    @Test
    void lateOutboxCommitNeverRegressesDeliveredPlan() {
        Instant publishedAt = Instant.parse("2026-07-16T01:00:00Z");
        CommandOutboxEvent event = event(0);
        ActionPlan plan = plan(ActionPlan.PlanStatus.DELIVERED);
        plan.setExecutionResult("MQTT_PUBLISH_CONFIRMED");
        when(commandOutboxRepository.findById(1L)).thenReturn(Optional.of(event));
        when(actionPlanRepository.findByCommandId("cmd-1")).thenReturn(Optional.of(plan));

        service.markPublished(1L, publishedAt);

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DELIVERED);
        assertThat(plan.getExecutionResult()).isEqualTo("MQTT_PUBLISH_CONFIRMED");
        assertThat(plan.getDispatchedAt()).isEqualTo(publishedAt);
    }

    @Test
    void transientFailureReturnsEventToPendingWithBackoff() {
        Instant failedAt = Instant.parse("2026-07-16T01:00:00Z");
        CommandOutboxEvent event = event(0);
        ActionPlan plan = plan(ActionPlan.PlanStatus.DISPATCHING);
        when(commandOutboxRepository.findById(1L)).thenReturn(Optional.of(event));
        when(actionPlanRepository.findByCommandId("cmd-1")).thenReturn(Optional.of(plan));

        service.markFailed(1L, "broker unavailable", failedAt, 3, Duration.ofSeconds(2));

        assertThat(event.getStatus()).isEqualTo(CommandOutboxEvent.OutboxStatus.PENDING);
        assertThat(event.getAttempts()).isEqualTo(1);
        assertThat(event.getNextAttemptAt()).isEqualTo(failedAt.plusSeconds(2));
        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DISPATCHING);
        assertThat(plan.getExecutionResult()).isEqualTo("KAFKA_RETRY_PENDING");
        assertThat(plan.getExecutionError()).isEqualTo("broker unavailable");
        verify(auditService, never()).logCommandExecuted(plan, false, null, "broker unavailable");
    }

    @Test
    void finalFailureMovesOutboxToDeadAndPlanToDispatchFailed() {
        Instant failedAt = Instant.parse("2026-07-16T01:00:00Z");
        CommandOutboxEvent event = event(2);
        ActionPlan plan = plan(ActionPlan.PlanStatus.DISPATCHING);
        when(commandOutboxRepository.findById(1L)).thenReturn(Optional.of(event));
        when(actionPlanRepository.findByCommandId("cmd-1")).thenReturn(Optional.of(plan));

        service.markFailed(1L, "broker unavailable", failedAt, 3, Duration.ofSeconds(2));

        assertThat(event.getStatus()).isEqualTo(CommandOutboxEvent.OutboxStatus.DEAD);
        assertThat(event.getAttempts()).isEqualTo(3);
        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DISPATCH_FAILED);
        assertThat(plan.getExecutionResult()).isEqualTo("OUTBOX_DEAD_LETTER");
        verify(auditService).logCommandExecuted(plan, false, null, "broker unavailable");
    }

    private CommandOutboxEvent event(int attempts) {
        return CommandOutboxEvent.builder()
                .id(1L)
                .eventId("event-1")
                .planId("plan-1")
                .commandId("cmd-1")
                .topic("terra.control.command")
                .messageKey("farm-1")
                .payload("{}")
                .status(CommandOutboxEvent.OutboxStatus.PROCESSING)
                .attempts(attempts)
                .nextAttemptAt(Instant.now())
                .lockedAt(Instant.now())
                .build();
    }

    private ActionPlan plan(ActionPlan.PlanStatus status) {
        return ActionPlan.builder()
                .planId("plan-1")
                .traceId("trace-1")
                .farmId("farm-1")
                .targetAssetId("fan-01")
                .actionCategory("ventilation")
                .actionType("turn_on")
                .commandId("cmd-1")
                .status(status)
                .priority(ActionPlan.ActionPriority.MEDIUM)
                .generatedAt(Instant.now())
                .build();
    }
}
