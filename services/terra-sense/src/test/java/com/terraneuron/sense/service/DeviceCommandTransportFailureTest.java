package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceSafetyDecision;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DeviceCommandTransportFailureTest {

    @Mock private MqttGatewayService mqttGateway;
    @Mock private KafkaTemplate<String, Object> kafkaTemplate;
    @Mock private CommandRegistry commandRegistry;
    @Mock private DeviceSafetyPolicy deviceSafetyPolicy;

    private DeviceCommandConsumer consumer;

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        when(deviceSafetyPolicy.evaluate(any()))
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
    void mqttPublishFailureUsesStableTransportPrefix() {
        when(commandRegistry.register(any(DeviceCommand.class)))
                .thenReturn(new CommandRegistry.Registration(
                        CommandRegistry.RegistrationState.SHOULD_PUBLISH));
        doThrow(new IllegalStateException("broker unavailable"))
                .when(mqttGateway).publishCommand(any(DeviceCommand.class));
        CompletableFuture<SendResult<String, Object>> feedback =
                CompletableFuture.completedFuture(null);
        when(kafkaTemplate.send(eq("terra.control.feedback"), eq("farm-001"), any()))
                .thenReturn(feedback);

        consumer.onCommand(commandEvent());

        verify(commandRegistry).releasePending("cmd-1a2b3c4d");
        verify(commandRegistry, never()).markPublished("cmd-1a2b3c4d");
        ArgumentCaptor<Object> captor = ArgumentCaptor.forClass(Object.class);
        verify(kafkaTemplate).send(eq("terra.control.feedback"), eq("farm-001"), captor.capture());

        @SuppressWarnings("unchecked")
        Map<String, Object> event = (Map<String, Object>) captor.getValue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) event.get("data");
        assertThat(data).containsEntry("status", "FAILED")
                .containsEntry("error", "MQTT_PUBLISH_FAILED:broker unavailable");
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
