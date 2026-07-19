package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceStateRecord;
import com.terraneuron.sense.model.DeviceStatus;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class MqttDeviceAckCorrelationTest {

    private static final Instant REPORTED_AT = Instant.parse("2026-07-15T12:00:00Z");

    @Mock private MqttClient mqttClient;
    @Mock private KafkaProducerService kafkaProducerService;
    @Mock private KafkaTemplate<String, Object> kafkaTemplate;
    @Mock private CommandRegistry commandRegistry;
    @Mock private DeviceStateRegistry deviceStateRegistry;

    private MqttGatewayService gateway;
    private Clock clock;

    @BeforeEach
    void setUp() {
        clock = Clock.fixed(REPORTED_AT, ZoneOffset.UTC);
        lenient().when(deviceStateRegistry.status()).thenReturn(
                new DeviceStateRegistry.RegistryStatus("redis", true, clock.instant(), 1));
        gateway = new MqttGatewayService(
                mqttClient,
                new ObjectMapper().findAndRegisterModules(),
                kafkaProducerService,
                kafkaTemplate,
                commandRegistry,
                deviceStateRegistry,
                clock,
                10);
    }

    @Test
    void explicitDeviceExecutionAckIsForwardedAndPersistedWithOriginalPlanContext() throws Exception {
        stubPendingCommandAndFeedback();

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
        assertThat(data).containsEntry("trace_id", "trace-123")
                .containsEntry("plan_id", "plan-123")
                .containsEntry("command_id", "cmd-1a2b3c4d")
                .containsEntry("status", "EXECUTED");

        ArgumentCaptor<DeviceStateRecord> stateCaptor =
                ArgumentCaptor.forClass(DeviceStateRecord.class);
        verify(deviceStateRegistry).save(stateCaptor.capture());
        assertThat(stateCaptor.getValue().getLastCommandId()).isEqualTo("cmd-1a2b3c4d");
        assertThat(stateCaptor.getValue().getLastCommandStatus()).isEqualTo("EXECUTED");
        assertThat(stateCaptor.getValue().getLastCommandError()).isNull();
        verify(commandRegistry).finishCompletion("cmd-1a2b3c4d");
    }

    @Test
    void terminalAckIsForwardedAndPreviousStateInvalidatedWhenSharedWriteFails() throws Exception {
        stubPendingCommandAndFeedback();
        doThrow(new DeviceStateRegistryUnavailableException(
                "state registry unavailable", new RuntimeException("redis unavailable")))
                .when(deviceStateRegistry)
                .save(any(DeviceStateRecord.class));

        gateway.messageArrived(
                "terra/devices/farm-001/fan-01/status",
                mqttMessage(statusJson("farm-001", "fan-01", "EXECUTED", null)));

        verify(deviceStateRegistry).invalidate("farm-001", "fan-01");
        verify(kafkaTemplate).send(eq("terra.control.feedback"), eq("farm-001"), any());
        verify(commandRegistry).finishCompletion("cmd-1a2b3c4d");
        assertThat(gateway.getStats())
                .containsEntry("status_received", 1L)
                .containsEntry("error_count", 1L);
    }

    @Test
    void deviceStatusQueriesPreserveAckFieldsFromSharedRegistry() {
        DeviceStateRecord stored = DeviceStateRecord.builder()
                .farmId("farm-001")
                .assetId("fan-01")
                .deviceType("fan")
                .state("error")
                .lastCommandId("cmd-1a2b3c4d")
                .lastCommandStatus("FAILED")
                .lastCommandError("motor overload")
                .reportedAt(REPORTED_AT)
                .observedAt(REPORTED_AT)
                .build();
        when(deviceStateRegistry.find("farm-001", "fan-01"))
                .thenReturn(Optional.of(stored));
        when(deviceStateRegistry.findAll())
                .thenReturn(Map.of("farm-001/fan-01", stored));

        DeviceStatus single = gateway.getDeviceStatus("farm-001", "fan-01");
        DeviceStatus listed = gateway.getAllDeviceStates().get("farm-001/fan-01");

        assertThat(single.getLastCommandId()).isEqualTo("cmd-1a2b3c4d");
        assertThat(single.getLastCommandStatus()).isEqualTo("FAILED");
        assertThat(single.getLastCommandError()).isEqualTo("motor overload");
        assertThat(listed.getLastCommandId()).isEqualTo("cmd-1a2b3c4d");
        assertThat(listed.getLastCommandStatus()).isEqualTo("FAILED");
        assertThat(listed.getLastCommandError()).isEqualTo("motor overload");
    }

    @Test
    void duplicateTerminalAckIsSuppressed() throws Exception {
        when(commandRegistry.findPending("cmd-1a2b3c4d")).thenReturn(Optional.of(command()));
        when(commandRegistry.claimCompletion("cmd-1a2b3c4d", "EXECUTED", "")).thenReturn(false);

        gateway.messageArrived(
                "terra/devices/farm-001/fan-01/status",
                mqttMessage(statusJson("farm-001", "fan-01", "EXECUTED", null)));

        verify(kafkaTemplate, never()).send(
                eq("terra.control.feedback"), eq("farm-001"), any());
        verify(commandRegistry, never()).finishCompletion("cmd-1a2b3c4d");
    }

    @Test
    void mismatchedDeviceIdentityCannotAcknowledgeAnotherAssetCommand() throws Exception {
        when(commandRegistry.findPending("cmd-1a2b3c4d")).thenReturn(Optional.of(command()));
        when(commandRegistry.pendingCount()).thenReturn(1L);

        gateway.messageArrived(
                "terra/devices/farm-001/heater-01/status",
                mqttMessage(statusJson("farm-001", "heater-01", "EXECUTED", null)));

        verify(kafkaTemplate, never()).send(eq("terra.control.feedback"), eq("farm-001"), any());
        verify(commandRegistry, never()).claimCompletion("cmd-1a2b3c4d", "EXECUTED", "");
        assertThat(gateway.getStats())
                .containsEntry("pending_command_acks", 1L)
                .containsEntry("error_count", 1L);
    }

    @Test
    void genericRunningStatusIsStoredButNotTreatedAsExecutionAck() throws Exception {
        when(commandRegistry.pendingCount()).thenReturn(1L);
        String payload = """
                {
                  "farmId":"farm-001",
                  "assetId":"fan-01",
                  "deviceType":"fan",
                  "state":"running",
                  "lastCommandId":"cmd-1a2b3c4d",
                  "reportedAt":"2026-07-15T12:00:00.000Z"
                }
                """;

        gateway.messageArrived(
                "terra/devices/farm-001/fan-01/status",
                mqttMessage(payload));

        verify(kafkaTemplate, never()).send(eq("terra.control.feedback"), eq("farm-001"), any());
        verify(commandRegistry, never()).findPending("cmd-1a2b3c4d");
        verify(deviceStateRegistry).save(any(DeviceStateRecord.class));
        assertThat(gateway.getStats()).containsEntry("pending_command_acks", 1L);
    }

    @Test
    void malformedStatusPayloadInvalidatesTopicState() throws Exception {
        gateway.messageArrived(
                "terra/devices/farm-001/fan-01/status",
                mqttMessage("{not-json"));

        verify(deviceStateRegistry).invalidate("farm-001", "fan-01");
        verify(deviceStateRegistry, never()).save(any());
        verify(kafkaTemplate, never()).send(any(), any(), any());
        assertThat(gateway.getStats()).containsEntry("error_count", 1L);
    }

    @ParameterizedTest
    @CsvSource({
            "other-farm, fan-01",
            "farm-001, heater-01"
    })
    void topicPayloadIdentityMismatchInvalidatesTopicState(
            String payloadFarmId,
            String payloadAssetId) throws Exception {
        gateway.messageArrived(
                "terra/devices/farm-001/fan-01/status",
                mqttMessage(statusJson(payloadFarmId, payloadAssetId, "EXECUTED", null)));

        verify(deviceStateRegistry).invalidate("farm-001", "fan-01");
        verify(deviceStateRegistry, never()).save(any());
        verify(kafkaTemplate, never()).send(any(), any(), any());
        assertThat(gateway.getStats()).containsEntry("error_count", 1L);
    }

    private void stubPendingCommandAndFeedback() {
        when(commandRegistry.findPending("cmd-1a2b3c4d")).thenReturn(Optional.of(command()));
        when(commandRegistry.claimCompletion("cmd-1a2b3c4d", "EXECUTED", "")).thenReturn(true);
        when(kafkaTemplate.send(eq("terra.control.feedback"), eq("farm-001"), any()))
                .thenReturn(CompletableFuture.<SendResult<String, Object>>completedFuture(null));
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
                .issuedAt(clock.instant().minusSeconds(60))
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
                  "deviceType":"fan",
                  "state":"idle",
                  "lastCommandId":"cmd-1a2b3c4d",
                  "lastCommandStatus":"%s",
                  "lastCommandError":%s,
                  "reportedAt":"2026-07-15T12:00:00.000Z"
                }
                """.formatted(farmId, assetId, status, errorField);
    }
}
