package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.entity.CommandOutboxEvent;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.repository.CommandOutboxRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CommandOutboxServiceTest {

    @Mock
    private ActionPlanRepository actionPlanRepository;
    @Mock
    private CommandOutboxRepository commandOutboxRepository;

    private ObjectMapper objectMapper;
    private CommandOutboxService service;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper().findAndRegisterModules();
        service = new CommandOutboxService(
                actionPlanRepository,
                commandOutboxRepository,
                objectMapper);
        when(commandOutboxRepository.save(any(CommandOutboxEvent.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
    }

    @Test
    void approvedPlanAndCommandPayloadAreQueuedTogether() throws Exception {
        ActionPlan plan = approvedPlan("{\"duration_minutes\":30,\"speed_level\":\"high\"}");

        CommandOutboxEvent event = service.enqueue(plan);

        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.DISPATCHING);
        assertThat(plan.getCommandId()).startsWith("cmd-");
        assertThat(plan.getExecutionResult()).isEqualTo("COMMAND_OUTBOX_PENDING");
        assertThat(plan.getDispatchedAt()).isNull();
        assertThat(event.getCommandId()).isEqualTo(plan.getCommandId());
        assertThat(event.getStatus()).isEqualTo(CommandOutboxEvent.OutboxStatus.PENDING);
        assertThat(event.getTopic()).isEqualTo("terra.control.command");
        assertThat(event.getMessageKey()).isEqualTo("farm-1");

        @SuppressWarnings("unchecked")
        Map<String, Object> cloudEvent = objectMapper.readValue(event.getPayload(), Map.class);
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) cloudEvent.get("data");
        assertThat(cloudEvent).containsEntry("type", "terra.ops.command.execute");
        assertThat(data)
                .containsEntry("plan_id", "plan-1")
                .containsEntry("command_id", plan.getCommandId())
                .containsEntry("farm_id", "farm-1")
                .containsEntry("target_asset_id", "fan-01")
                .containsEntry("executed_by", "operator");
        assertThat(data.get("parameters")).isEqualTo(Map.of(
                "duration_minutes", 30,
                "speed_level", "high"));

        verify(actionPlanRepository).save(plan);
        verify(commandOutboxRepository).save(event);
    }

    @Test
    void malformedParametersAbortBeforeAnyDatabaseWrite() {
        ActionPlan plan = approvedPlan("{not-json}");

        assertThatThrownBy(() -> service.enqueue(plan))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Invalid command parameters JSON");

        verify(actionPlanRepository, never()).save(any());
        verify(commandOutboxRepository, never()).save(any());
        assertThat(plan.getStatus()).isEqualTo(ActionPlan.PlanStatus.APPROVED);
        assertThat(plan.getCommandId()).isNull();
    }

    private ActionPlan approvedPlan(String parameters) {
        return ActionPlan.builder()
                .planId("plan-1")
                .traceId("trace-1")
                .farmId("farm-1")
                .targetAssetId("fan-01")
                .actionCategory("ventilation")
                .actionType("turn_on")
                .parameters(parameters)
                .status(ActionPlan.PlanStatus.APPROVED)
                .priority(ActionPlan.ActionPriority.MEDIUM)
                .approvedBy("operator")
                .approvedAt(Instant.now())
                .generatedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(3600))
                .build();
    }
}
