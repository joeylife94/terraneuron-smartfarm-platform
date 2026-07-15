package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class MqttDeviceAckCorrelationTest {

    @Mock
    private MqttClient mqttClient;
    @Mock
    private KafkaProducerService kafkaProducerService;
    @Mock
    private KafkaTemplate<String, Object> kafkaTemplate;

    private MqttGatewayService gateway;

    @BeforeEach
    void setUp() {
        gateway = new MqttGatewayService(
                mqttClient,
                new ObjectMapper().findAndRegisterModules(),
                kafkaProducerService,
                kafkaTemplate);
    }

    @Test
    void explicitDeviceExecutionAckIsForwardedWithOriginalPlanContext() throws Exception {
        gateway.publishCommand(command());

        gateway.messageArrived(
                "terra/devices/farm-001/fan-01/status",
                mqttMessage(statusJson("farm-001", "fan-01", "EXECUTED", null)));

        ArgumentCaptor<Object> feedbackCaptor = ArgumentCaptor.forClass(Object.class);
        verify(kafkaTemplate).send(
                eq("terra.control.feedback"), eq("farm-001"), feedbackCaptor.capture());

        @SuppressWarnings("unchecked")
        Map<String, Object> event = (Map<String, Object>) feedbackCaptor.getValue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) event.get("data");

        assertThat(data)
                .containsEntry("trace_id", "trace-123")
                .containsEntry("plan_id", "plan-123")
                .containsEntry("command_id", "cmd-1a2b3c4d")
                .containsEntry("farm_id", "farm-001")
                .containsEntry("target_asset_id", "fan-01")
                .containsEntry("status", "EXECUTED")
                .containsEntry("error", "");
        assertThat(gateway.getStats()).containsEntry("pending_command_acks", 0);
    }

    @Test
    void mismatchedDeviceIdentityCannotAcknowledgeAnotherAssetCommand() throws Exception {
        gateway.publishCommand(command());

        gateway.messageArrived(
                "terra/devices/farm-001/heater-01/status",
                mqttMessage(statusJson("farm-001", "heater-01", "EXECUTED", null)));

        verify(kafkaTemplate, never()).send(
                eq("terra.control.feedback"), eq("farm-001"), org.mockito.ArgumentMatchers.any());
        assertThat(gateway.getStats())
                .containsEntry("pending_command_acks", 1)
                .containsEntry("error_count", 1L);
    }

    @Test
    void genericRunningStatusIsNotTreatedAsExecutionAck() throws Exception {
        gateway.publishCommand(command());
        String payload = """
                {
                  "farmId":"farm-001",
                  "assetId":"fan-01",
                  "state":"running",
                  "lastCommandId":"cmd-1a2b3c4d",
                  "reportedAt":"2026-07-15T12:00:00.000Z"
                }
                """;

        gateway.messageArrived(
                "terra/devices/farm-001/fan-01/status",
                mqttMessage(payload));

        verify(kafkaTemplate, never()).send(
                eq("terra.control.feedback"), eq("farm-001"), org.mockito.ArgumentMatchers.any());
        assertThat(gateway.getStats()).containsEntry("pending_command_acks", 1);
    }

    private DeviceCommand command() {
        return DeviceCommand.builder()
                .commandId("cmd-1a2b3c4d")
                .traceId("trace-123")
                .planId("plan-123")
                .farmId("farm-001")
                .targetAssetId("fan-01")
                .actionType("turn_on")
                .parameters(Map.of("duration_minutes", 30))
                .executedBy("operator-01")
                .issuedAt(Instant.parse("2026-07-15T11:59:00Z"))
                .build();
    }

    private MqttMessage mqttMessage(String payload) {
        return new MqttMessage(payload.getBytes(StandardCharsets.UTF_8));
    }

    private String statusJson(String farmId, String assetId, String status, String error) {
        String errorField = error == null ? "null" : "\"" + error + "\"";
        return """
                {
                  "farmId":"%s",
                  "assetId":"%s",
                  "state":"idle",
                  "lastCommandId":"cmd-1a2b3c4d",
                  "lastCommandStatus":"%s",
                  "lastCommandError":%s,
                  "reportedAt":"2026-07-15T12:00:00.000Z"
                }
                """.formatted(farmId, assetId, status, errorField);
    }
}
