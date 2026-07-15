package com.terraneuron.sense.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** Kafka to MQTT command bridge with durable duplicate suppression. */
@Slf4j
@Service
public class DeviceCommandConsumer {

    private static final String FEEDBACK_TOPIC = "terra.control.feedback";

    private final MqttGatewayService mqttGateway;
    private final ObjectMapper objectMapper;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ContractSchemaValidator contractSchemaValidator;
    private final CommandRegistry commandRegistry;
    private final long feedbackTimeoutSeconds;

    public DeviceCommandConsumer(
            MqttGatewayService mqttGateway,
            ObjectMapper objectMapper,
            KafkaTemplate<String, Object> kafkaTemplate,
            ContractSchemaValidator contractSchemaValidator,
            CommandRegistry commandRegistry,
            @Value("${app.command.feedback-timeout-seconds:10}") long feedbackTimeoutSeconds) {
        this.mqttGateway = mqttGateway;
        this.objectMapper = objectMapper;
        this.kafkaTemplate = kafkaTemplate;
        this.contractSchemaValidator = contractSchemaValidator;
        this.commandRegistry = commandRegistry;
        this.feedbackTimeoutSeconds = feedbackTimeoutSeconds;
    }

    @KafkaListener(
            topics = "terra.control.command",
            groupId = "terra-sense-command-group",
            containerFactory = "commandListenerContainerFactory"
    )
    public void onCommand(Map<String, Object> commandEvent) {
        Map<String, Object> normalizedEvent = normalizeLegacyParameters(commandEvent);
        contractSchemaValidator.validate(ContractSchemaValidator.COMMAND_SCHEMA, normalizedEvent);

        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) normalizedEvent.get("data");
        if (data == null) {
            throw new IllegalArgumentException("Invalid CloudEvent: missing data field");
        }

        DeviceCommand command = toDeviceCommand(data, normalizedEvent);
        CommandRegistry.Registration registration = commandRegistry.register(command);

        if (registration.isCompletedDuplicate()) {
            log.info("Ignoring completed duplicate command: {}", command.getCommandId());
            return;
        }

        if (registration.isPendingDuplicate()) {
            // MQTT was already published. Re-emit broker-acknowledged delivery feedback
            // without physically publishing the command again.
            sendFeedback(command, "DELIVERED", null);
            log.info("Replayed delivery feedback for duplicate pending command: {}",
                    command.getCommandId());
            return;
        }

        try {
            mqttGateway.publishCommand(command);
        } catch (Exception publishError) {
            commandRegistry.releasePending(command.getCommandId());
            sendFeedback(command, "FAILED", rootCauseMessage(publishError));
            log.error("MQTT command delivery failed: command={} error={}",
                    command.getCommandId(), publishError.getMessage(), publishError);
            return;
        }

        // Await Kafka broker acknowledgement. If this fails, the listener throws and
        // Kafka redelivery follows the duplicate-pending path without MQTT republish.
        sendFeedback(command, "DELIVERED", null);
        log.info("Command delivered once: command={} asset={} action={}",
                command.getCommandId(), command.getTargetAssetId(), command.getActionType());
    }

    private DeviceCommand toDeviceCommand(
            Map<String, Object> data, Map<String, Object> normalizedEvent) {
        String farmId = (String) data.getOrDefault(
                "farm_id", normalizedEvent.getOrDefault("key", "unknown"));

        return DeviceCommand.builder()
                .commandId((String) data.get("command_id"))
                .traceId((String) data.get("trace_id"))
                .planId((String) data.get("plan_id"))
                .targetAssetId((String) data.get("target_asset_id"))
                .actionType((String) data.get("action_type"))
                .parameters(parseParameters(data.get("parameters")))
                .executedBy((String) data.get("executed_by"))
                .farmId(farmId)
                .issuedAt(Instant.now())
                .build();
    }

    private Map<String, Object> normalizeLegacyParameters(Map<String, Object> commandEvent) {
        if (commandEvent == null) {
            return null;
        }

        Object dataValue = commandEvent.get("data");
        if (!(dataValue instanceof Map<?, ?> data)) {
            return commandEvent;
        }

        Object parameters = data.get("parameters");
        if (!(parameters instanceof String)) {
            return commandEvent;
        }

        Map<String, Object> normalizedData = new LinkedHashMap<>();
        data.forEach((key, value) -> normalizedData.put(String.valueOf(key), value));
        normalizedData.put("parameters", parseParameters(parameters));

        Map<String, Object> normalizedEvent = new LinkedHashMap<>(commandEvent);
        normalizedEvent.put("data", normalizedData);
        return normalizedEvent;
    }

    private void sendFeedback(DeviceCommand command, String status, String error) {
        Map<String, Object> feedback = Map.of(
                "specversion", "1.0",
                "type", "terra.sense.command.feedback",
                "source", "//terraneuron/terra-sense",
                "id", java.util.UUID.randomUUID().toString(),
                "time", Instant.now().toString(),
                "datacontenttype", "application/json",
                "data", Map.of(
                        "trace_id", safe(command.getTraceId()),
                        "command_id", safe(command.getCommandId()),
                        "plan_id", safe(command.getPlanId()),
                        "farm_id", safe(command.getFarmId()),
                        "target_asset_id", safe(command.getTargetAssetId()),
                        "status", status,
                        "error", error != null ? error : "",
                        "timestamp", Instant.now().toString()
                )
        );

        try {
            kafkaTemplate.send(FEEDBACK_TOPIC, command.getFarmId(), feedback)
                    .get(feedbackTimeoutSeconds, TimeUnit.SECONDS);
            log.info("Feedback broker acknowledged: command={} status={}",
                    command.getCommandId(), status);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while publishing command feedback", e);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to publish command feedback", e);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseParameters(Object params) {
        if (params == null) return Map.of();
        if (params instanceof Map) return (Map<String, Object>) params;
        if (params instanceof String) {
            try {
                return objectMapper.readValue((String) params,
                        new TypeReference<Map<String, Object>>() {});
            } catch (Exception e) {
                log.warn("Failed to parse legacy string parameters; preserving raw value: {}",
                        e.getMessage());
                return Map.of("raw", params);
            }
        }
        return Map.of();
    }

    private String safe(String value) {
        return value != null ? value : "";
    }

    private String rootCauseMessage(Exception exception) {
        Throwable cause = exception;
        while (cause.getCause() != null) {
            cause = cause.getCause();
        }
        return cause.getMessage() != null ? cause.getMessage() : cause.getClass().getSimpleName();
    }
}
