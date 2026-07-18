package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyReason;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeviceCommandConsumerTest {

    @Mock private MqttGatewayService mqttGateway;
    @Mock private KafkaTemplate<String, Object> kafkaTemplate;
    @Mock private CommandRegistry commandRegistry;
    @Mock private DeviceSafetyPolicy deviceSafetyPolicy;

    private DeviceCommandConsumer consumer;

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        lenient().when(deviceSafetyPolicy.evaluate(any()))
                .thenReturn(DeviceSafetyDecision.allowed(
                        Instant.parse("2026-07-18T03:00:00Z"), 1, 1));
        consumer = new DeviceCommandConsumer(
                mqttGateway,
                objectMapper,
                kafkaTemplate,
                new ContractSchemaValidator(objectMapper),
                commandRegistry,
                deviceSafetyPolicy,
                new SimpleMeterRegistry(),
                Clock.fixed(Instant.parse("2026-07-18T03:00:00Z"), ZoneOffset.UTC),
                10);
    }

    @Test
    void freshDevicePublishesOnceAndCorrelatesFeedback() {
        stubPublishableCommandAndFeedback();

        consumer.onCommand(commandEvent(Map.of(
                "duration_minutes", 30,
                "speed_level", "high")));

        ArgumentCaptor<DeviceCommand> commandCaptor = ArgumentCaptor.forClass(DeviceCommand.class);
        verify(mqttGateway).publishCommand(commandCaptor.capture());
        verify(commandRegistry).markPublished("cmd-1a2b3c4d");
        assertThat(commandCaptor.getValue().getFarmId()).isEqualTo("farm-001");
        assertThat(commandCaptor.getValue().getActionCategory()).isEqualTo("ventilation");
        assertThat(commandCaptor.getValue().getParameters()).containsEntry("duration_minutes", 30);

        Map<String, Object> data = capturedFeedbackData();
        assertThat(data).containsEntry("command_id", "cmd-1a2b3c4d")
                .containsEntry("plan_id", "plan-123")
                .containsEntry("status", "DELIVERED")
                .containsEntry("error", "");
    }

    @Test
    void safetyChangeAfterApprovalBlocksMqttAndCompletesIdempotently() {
        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(new CommandRegistry.Registration(
                        CommandRegistry.RegistrationState.SHOULD_PUBLISH));
        when(deviceSafetyPolicy.evaluate(any()))
                .thenReturn(DeviceSafetyDecision.blocked(
                        DeviceSafetyReason.STATE_OFFLINE,
                        Instant.parse("2026-07-18T03:00:00Z"),
                        1L,
                        1L));
        when(commandRegistry.claimCompletion(
                "cmd-1a2b3c4d", "FAILED", "DEVICE_SAFETY_BLOCKED:STATE_OFFLINE"))
                .thenReturn(true);
        stubFeedbackSuccess();

        consumer.onCommand(commandEvent(Map.of("duration_minutes", 30)));

        verify(mqttGateway, never()).publishCommand(any());
        verify(commandRegistry).finishCompletion("cmd-1a2b3c4d");
        Map<String, Object> data = capturedFeedbackData();
        assertThat(data).containsEntry("command_id", "cmd-1a2b3c4d")
                .containsEntry("status", "FAILED")
                .containsEntry("error", "DEVICE_SAFETY_BLOCKED:STATE_OFFLINE");
    }

    @Test
    void publishedDuplicateReplaysFeedbackWithoutMqttRepublish() {
        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(new CommandRegistry.Registration(
                        CommandRegistry.RegistrationState.PUBLISHED));
        stubFeedbackSuccess();

        consumer.onCommand(commandEvent(Map.of("duration_minutes", 30)));

        verify(mqttGateway, never()).publishCommand(any());
        verify(commandRegistry, never()).markPublished("cmd-1a2b3c4d");
        verify(kafkaTemplate).send(eq("terra.control.feedback"), eq("farm-001"), any());
    }

    @Test
    void activePublishLeaseDoesNotClaimFalseDelivery() {
        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(new CommandRegistry.Registration(
                        CommandRegistry.RegistrationState.PUBLISH_IN_PROGRESS));

        assertThatThrownBy(() -> consumer.onCommand(commandEvent(Map.of("duration_minutes", 30))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("publish lease");
        verify(mqttGateway, never()).publishCommand(any());
        verifyNoInteractions(kafkaTemplate);
    }

    @Test
    void completedDuplicateIsFullySuppressed() {
        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(new CommandRegistry.Registration(
                        CommandRegistry.RegistrationState.COMPLETED));

        consumer.onCommand(commandEvent(Map.of("duration_minutes", 30)));

        verify(mqttGateway, never()).publishCommand(any());
        verifyNoInteractions(kafkaTemplate);
    }

    @Test
    void rejectsInvalidCommandBeforePublishing() {
        Map<String, Object> invalidEvent = Map.of(
                "specversion", "1.0",
                "type", "terra.ops.command.execute",
                "data", Map.of());

        assertThatThrownBy(() -> consumer.onCommand(invalidEvent))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("command.schema.json");
        verifyNoInteractions(mqttGateway, kafkaTemplate, commandRegistry);
    }

    private void stubPublishableCommandAndFeedback() {
        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(new CommandRegistry.Registration(
                        CommandRegistry.RegistrationState.SHOULD_PUBLISH));
        stubFeedbackSuccess();
    }

    private void stubFeedbackSuccess() {
        CompletableFuture<SendResult<String, Object>> future = CompletableFuture.completedFuture(null);
        when(kafkaTemplate.send(eq("terra.control.feedback"), eq("farm-001"), any()))
                .thenReturn(future);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> capturedFeedbackData() {
        ArgumentCaptor<Object> captor = ArgumentCaptor.forClass(Object.class);
        verify(kafkaTemplate).send(eq("terra.control.feedback"), eq("farm-001"), captor.capture());
        Map<String, Object> event = (Map<String, Object>) captor.getValue();
        return (Map<String, Object>) event.get("data");
    }

    private Map<String, Object> commandEvent(Object parameters) {
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
                        Map.entry("parameters", parameters),
                        Map.entry("executed_by", "operator-01")));
    }
}
