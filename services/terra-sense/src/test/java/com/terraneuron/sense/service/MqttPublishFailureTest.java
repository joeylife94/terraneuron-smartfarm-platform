package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceSafetyDecision;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.MqttMessage;
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class MqttPublishFailureTest {

    @Mock private MqttClient mqttClient;
    @Mock private KafkaProducerService kafkaProducerService;
    @Mock private MqttGatewayService mqttGatewayService;
    @Mock private KafkaTemplate<String, Object> kafkaTemplate;
    @Mock private CommandRegistry commandRegistry;
    @Mock private DeviceStateRegistry deviceStateRegistry;
    @Mock private DeviceSafetyPolicy deviceSafetyPolicy;

    private final Clock clock = Clock.fixed(
            Instant.parse("2026-07-18T03:00:00Z"), ZoneOffset.UTC);

    @Test
    void gatewayPropagatesBrokerPublishFailure() throws Exception {
        doThrow(new MqttException(MqttException.REASON_CODE_BROKER_UNAVAILABLE))
                .when(mqttClient).publish(anyString(), any(MqttMessage.class));
        when(commandRegistry.pendingCount()).thenReturn(0L);
        when(deviceStateRegistry.status()).thenReturn(
                new DeviceStateRegistry.RegistryStatus("redis", true, clock.instant(), 0));

        MqttGatewayService gateway = new MqttGatewayService(
                mqttClient,
                runtimeObjectMapper(),
                kafkaProducerService,
                kafkaTemplate,
                commandRegistry,
                deviceStateRegistry,
                clock,
                10);

        assertThatThrownBy(() -> gateway.publishCommand(deviceCommand()))
                .isInstanceOf(MqttPublishException.class)
                .hasMessageContaining("fan-01")
                .hasCauseInstanceOf(MqttException.class);
        assertThat(gateway.getStats())
                .containsEntry("commands_sent", 0L)
                .containsEntry("pending_command_acks", 0L)
                .containsEntry("error_count", 1L);
    }

    @Test
    void commandConsumerReleasesClaimAndPublishesFailedFeedback() {
        ObjectMapper objectMapper = runtimeObjectMapper();
        DeviceCommandConsumer consumer = new DeviceCommandConsumer(
                mqttGatewayService,
                objectMapper,
                kafkaTemplate,
                new ContractSchemaValidator(objectMapper),
                commandRegistry,
                deviceSafetyPolicy,
                new SimpleMeterRegistry(),
                clock,
                10);

        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(new CommandRegistry.Registration(
                        CommandRegistry.RegistrationState.SHOULD_PUBLISH));
        when(deviceSafetyPolicy.evaluate(any()))
                .thenReturn(DeviceSafetyDecision.allowed(clock.instant(), 1, 1));
        doThrow(new MqttPublishException(
                "Failed to publish MQTT command for asset fan-01",
                new RuntimeException("broker unavailable")))
                .when(mqttGatewayService).publishCommand(any(DeviceCommand.class));
        when(kafkaTemplate.send(eq("terra.control.feedback"), eq("farm-001"), any()))
                .thenReturn(CompletableFuture.<SendResult<String, Object>>completedFuture(null));

        consumer.onCommand(commandEvent());

        verify(commandRegistry).releasePending("cmd-1a2b3c4d");
        verify(commandRegistry, never()).markPublished("cmd-1a2b3c4d");
        ArgumentCaptor<Object> feedbackCaptor = ArgumentCaptor.forClass(Object.class);
        verify(kafkaTemplate).send(
                eq("terra.control.feedback"), eq("farm-001"), feedbackCaptor.capture());
        @SuppressWarnings("unchecked")
        Map<String, Object> feedback = (Map<String, Object>) feedbackCaptor.getValue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) feedback.get("data");
        assertThat(data).containsEntry("command_id", "cmd-1a2b3c4d")
                .containsEntry("status", "FAILED");
        assertThat(data.get("error").toString()).contains("broker unavailable");
    }

    private ObjectMapper runtimeObjectMapper() {
        return new ObjectMapper().findAndRegisterModules();
    }

    private DeviceCommand deviceCommand() {
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
                .issuedAt(clock.instant())
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
