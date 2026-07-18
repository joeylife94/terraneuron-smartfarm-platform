package com.terraneuron.sense.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyRequest;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** Kafka to MQTT command bridge with durable duplicate suppression and a final safety recheck. */
@Slf4j
@Service
public class DeviceCommandConsumer {

    private static final String FEEDBACK_TOPIC = "terra.control.feedback";
    private static final String SAFETY_BLOCK_PREFIX = "DEVICE_SAFETY_BLOCKED:";

    private final MqttGatewayService mqttGateway;
    private final ObjectMapper objectMapper;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ContractSchemaValidator contractSchemaValidator;
    private final CommandRegistry commandRegistry;
    private final DeviceSafetyPolicy deviceSafetyPolicy;
    private final MeterRegistry meterRegistry;
    private final Clock clock;
    private final long feedbackTimeoutSeconds;

    public DeviceCommandConsumer(
            MqttGatewayService mqttGateway,
            ObjectMapper objectMapper,
            KafkaTemplate<String, Object> kafkaTemplate,
            ContractSchemaValidator contractSchemaValidator,
            CommandRegistry commandRegistry,
            DeviceSafetyPolicy deviceSafetyPolicy,
            MeterRegistry meterRegistry,
            Clock clock,
            @Value("${app.command.feedback-timeout-seconds:10}") long feedbackTimeoutSeconds) {
        this.mqttGateway = mqttGateway;
        this.objectMapper = objectMapper;
        this.kafkaTemplate = kafkaTemplate;
        this.contractSchemaValidator = contractSchemaValidator;
        this.commandRegistry = commandRegistry;
        this.deviceSafetyPolicy = deviceSafetyPolicy;
        this.meterRegistry = meterRegistry;
        this.clock = clock;
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

        if (registration.isPublishedDuplicate()) {
            sendFeedback(command, "DELIVERED", null);
            log.info("Replayed delivery feedback for published command: {}",
                    command.getCommandId());
            return;
        }

        if (registration.isPublishInProgress()) {
            throw new IllegalStateException(
                    "MQTT publish lease is already held for command " + command.getCommandId());
        }

        if (!registration.shouldPublish()) {
            throw new IllegalStateException(
                    "Unsupported command registration state: " + registration.state());
        }

        DeviceSafetyDecision safetyDecision = deviceSafetyPolicy.evaluate(new DeviceSafetyRequest(
                command.getFarmId(),
                command.getTargetAssetId(),
                command.getActionCategory(),
                command.getActionType(),
                command.getParameters()));
        if (!safetyDecision.allowed()) {
            handleSafetyBlock(command, safetyDecision);
            return;
        }

        try {
            mqttGateway.publishCommand(command);
        } catch (Exception publishError) {
            commandRegistry.releasePending(command.getCommandId());
            sendFeedback(command, "FAILED", rootCauseMessage(publishError));
            log.error("MQTT command delivery failed: command={} error={}",
                    command.getCommandId(), publishError.getClass().getSimpleName(), publishError);
            return;
        }

        // Persist PUBLISHED before delivery feedback. Kafka redelivery can then replay
        // feedback without repeating the physical MQTT command.
        commandRegistry.markPublished(command.getCommandId());

        // Await Kafka broker acknowledgement. If this fails, the listener throws and
        // Kafka redelivery follows the PUBLISHED path without MQTT republish.
        sendFeedback(command, "DELIVERED", null);
        log.info("Command delivered once: command={} asset={} action={}",
                command.getCommandId(), command.getTargetAssetId(), command.getActionType());
    }

    private void handleSafetyBlock(DeviceCommand command, DeviceSafetyDecision decision) {
        String reason = decision.reasonCode().name();
        Counter.builder("terra_device_safety_predispatch_blocks_total")
                .description("Commands blocked by the final device safety recheck")
                .tag("reason", reason.toLowerCase(Locale.ROOT))
                .register(meterRegistry)
                .increment();

        if (!commandRegistry.claimCompletion(
                command.getCommandId(), "FAILED", SAFETY_BLOCK_PREFIX + reason)) {
            log.info("Ignoring duplicate pre-dispatch safety block: command={}", command.getCommandId());
            return;
        }

        try {
            sendFeedback(command, "FAILED", SAFETY_BLOCK_PREFIX + reason);
            commandRegistry.finishCompletion(command.getCommandId());
            log.warn("Command blocked before MQTT dispatch: command={} reason={}",
                    command.getCommandId(), reason);
        } catch (RuntimeException feedbackError) {
            commandRegistry.rollbackCompletion(command.getCommandId());
            commandRegistry.releasePending(command.getCommandId());
            throw feedbackError;
        }
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
                .targetAssetType((String) data.get("target_asset_type"))
                .actionCategory((String) data.get("action_category"))
                .actionType((String) data.get("action_type"))
                .parameters(parseParameters(data.get("parameters")))
                .executedBy((String) data.get("executed_by"))
                .farmId(farmId)
                .issuedAt(clock.instant())
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
        Instant now = clock.instant();
        Map<String, Object> feedback = Map.of(
                "specversion", "1.0",
                "type", "terra.sense.command.feedback",
                "source", "//terraneuron/terra-sense",
                "id", java.util.UUID.randomUUID().toString(),
                "time", now.toString(),
                "datacontenttype", "application/json",
                "data", Map.of(
                        "trace_id", safe(command.getTraceId()),
                        "command_id", safe(command.getCommandId()),
                        "plan_id", safe(command.getPlanId()),
                        "farm_id", safe(command.getFarmId()),
                        "target_asset_id", safe(command.getTargetAssetId()),
                        "status", status,
                        "error", error != null ? error : "",
                        "timestamp", now.toString()
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
                log.warn("Failed to parse legacy string parameters; preserving raw value");
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