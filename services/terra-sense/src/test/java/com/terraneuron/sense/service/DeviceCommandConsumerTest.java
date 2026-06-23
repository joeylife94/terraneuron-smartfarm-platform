package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class DeviceCommandConsumerTest {

    @Mock
    private MqttGatewayService mqttGateway;
    @Mock
    private KafkaTemplate<String, Object> kafkaTemplate;

    private DeviceCommandConsumer consumer;

    @BeforeEach
    void setUp() {
        consumer = new DeviceCommandConsumer(mqttGateway, new ObjectMapper(), kafkaTemplate);
    }

    @Test
    void consumesObjectParametersAndPublishesContractFeedback() {
        Map<String, Object> commandEvent = commandEvent(Map.of(
                "duration_minutes", 30,
                "speed_level", "high"));

        consumer.onCommand(commandEvent);

        ArgumentCaptor<DeviceCommand> commandCaptor = ArgumentCaptor.forClass(DeviceCommand.class);
        verify(mqttGateway).publishCommand(commandCaptor.capture());
        assertThat(commandCaptor.getValue().getFarmId()).isEqualTo("farm-001");
        assertThat(commandCaptor.getValue().getParameters()).containsEntry("duration_minutes", 30);

        ArgumentCaptor<Object> feedbackCaptor = ArgumentCaptor.forClass(Object.class);
        verify(kafkaTemplate).send(
                eq("terra.control.feedback"), eq("farm-001"), feedbackCaptor.capture());

        @SuppressWarnings("unchecked")
        Map<String, Object> feedback = (Map<String, Object>) feedbackCaptor.getValue();
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) feedback.get("data");
        assertThat(feedback).containsEntry("type", "terra.sense.command.feedback")
                .containsEntry("source", "//terraneuron/terra-sense");
        assertThat(data).containsEntry("trace_id", "trace-123")
                .containsEntry("command_id", "cmd-1a2b3c4d")
                .containsEntry("plan_id", "plan-123")
                .containsEntry("farm_id", "farm-001")
                .containsEntry("target_asset_id", "fan-01")
                .containsEntry("status", "DELIVERED")
                .containsEntry("error", "");
        assertThat(data.get("timestamp")).isInstanceOf(String.class);
    }

    @Test
    void continuesToAcceptLegacyJsonStringParameters() {
        consumer.onCommand(commandEvent("{\"duration_minutes\":15}"));

        ArgumentCaptor<DeviceCommand> commandCaptor = ArgumentCaptor.forClass(DeviceCommand.class);
        verify(mqttGateway).publishCommand(commandCaptor.capture());
        assertThat(commandCaptor.getValue().getParameters())
                .containsEntry("duration_minutes", 15);
    }

    private Map<String, Object> commandEvent(Object parameters) {
        return Map.of(
                "specversion", "1.0",
                "type", "terra.ops.command.execute",
                "source", "//terraneuron/terra-ops",
                "id", "d4e5f6a7-b8c9-4d01-8efa-234567890abc",
                "time", "2025-12-09T10:35:00Z",
                "datacontenttype", "application/json",
                "data", Map.of(
                        "trace_id", "trace-123",
                        "plan_id", "plan-123",
                        "command_id", "cmd-1a2b3c4d",
                        "farm_id", "farm-001",
                        "target_asset_id", "fan-01",
                        "action_type", "turn_on",
                        "parameters", parameters,
                        "executed_by", "operator-01"));
    }
}
