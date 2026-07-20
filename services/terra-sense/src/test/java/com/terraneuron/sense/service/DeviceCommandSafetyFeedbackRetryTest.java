package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyReason;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeviceCommandSafetyFeedbackRetryTest {

    private static final Instant NOW = Instant.parse("2026-07-18T03:00:00Z");

    @Mock private MqttGatewayService mqttGateway;
    @Mock private KafkaTemplate<String, Object> kafkaTemplate;
    @Mock private CommandRegistry commandRegistry;
    @Mock private DeviceSafetyPolicy deviceSafetyPolicy;

    private DeviceCommandConsumer consumer;

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        consumer = new DeviceCommandConsumer(
                mqttGateway,
                objectMapper,
                kafkaTemplate,
                new ContractSchemaValidator(objectMapper),
                commandRegistry,
                deviceSafetyPolicy,
                new SimpleMeterRegistry(),
                Clock.fixed(NOW, ZoneOffset.UTC),
                10);
    }

    @Test
    void failedSafetyFeedbackKeepsTerminalMarkerAndRedeliveryOnlyReplaysFeedback() {
        DeviceCommand command = command();
        CommandRegistry.CommandCompletion completion = new CommandRegistry.CommandCompletion(
                command,
                "FAILED",
                "DEVICE_SAFETY_BLOCKED:STATE_OFFLINE",
                NOW);

        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(
                        new CommandRegistry.Registration(
                                CommandRegistry.RegistrationState.SHOULD_PUBLISH),
                        new CommandRegistry.Registration(
                                CommandRegistry.RegistrationState.COMPLETED));
        when(deviceSafetyPolicy.evaluate(any()))
                .thenReturn(DeviceSafetyDecision.blocked(
                        DeviceSafetyReason.STATE_OFFLINE,
                        NOW,
                        1L,
                        1L));
        when(commandRegistry.claimCompletion(
                "cmd-1a2b3c4d", "FAILED", "DEVICE_SAFETY_BLOCKED:STATE_OFFLINE"))
                .thenReturn(true);
        when(commandRegistry.findCompletion("cmd-1a2b3c4d"))
                .thenReturn(Optional.of(completion));

        CompletableFuture<SendResult<String, Object>> failedFeedback =
                CompletableFuture.failedFuture(new IllegalStateException("feedback broker unavailable"));
        CompletableFuture<SendResult<String, Object>> replayedFeedback =
                CompletableFuture.completedFuture(null);
        when(kafkaTemplate.send(eq("terra.control.feedback"), eq("farm-001"), any()))
                .thenReturn(failedFeedback, replayedFeedback);

        assertThatThrownBy(() -> consumer.onCommand(commandEvent()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Failed to publish command feedback");

        verify(commandRegistry, never()).rollbackCompletion("cmd-1a2b3c4d");
        verify(commandRegistry, never()).releasePending("cmd-1a2b3c4d");
        verify(mqttGateway, never()).publishCommand(any());

        consumer.onCommand(commandEvent());

        verify(commandRegistry).findCompletion("cmd-1a2b3c4d");
        verify(commandRegistry).finishCompletion("cmd-1a2b3c4d");
        verify(deviceSafetyPolicy, times(1)).evaluate(any());
        verify(kafkaTemplate, times(2))
                .send(eq("terra.control.feedback"), eq("farm-001"), any());
        verify(mqttGateway, never()).publishCommand(any());
    }

    private DeviceCommand command() {
        return DeviceCommand.builder()
                .commandId("cmd-1a2b3c4d")
                .traceId("trace-123")
                .planId("plan-123")
                .farmId("farm-001")
                .targetAssetId("fan-01")
                .targetAssetType("device")
                .actionCategory("ventilation")
                .actionType("turn_on")
                .parameters(Map.of("duration_minutes", 30))
                .executedBy("operator-01")
                .issuedAt(NOW)
                .build();
    }

    private Map<String, Object> commandEvent() {
        return Map.of(
                "specversion", "1.0",
                "type", "terra.ops.command.execute",
                "source", "//terraneuron/terra-ops",
                "id", "d4e5f6a7-b8c9-4d01-8efa-234567890abc",
                "time", "2025-12-09T10:35:00Z",
                "datacontenttype", "application/json",
                "data", Map.ofEntries(
                        Map.entry("trace_id", "trace-123"),
                        Map.entry("plan_id", "plan-123"),
                        Map.entry("command_id", "cmd-1a2b3c4d"),
                        Map.entry("farm_id", "farm-001"),
                        Map.entry("target_asset_id", "fan-01"),
                        Map.entry("target_asset_type", "device"),
                        Map.entry("action_category", "ventilation"),
                        Map.entry("action_type", "turn_on"),
                        Map.entry("parameters", Map.of("duration_minutes", 30)),
                        Map.entry("executed_by", "operator-01")));
    }
}
