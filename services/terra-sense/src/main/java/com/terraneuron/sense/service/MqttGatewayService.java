package com.terraneuron.sense.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceStateRecord;
import com.terraneuron.sense.model.DeviceStatus;
import lombok.extern.slf4j.Slf4j;
import org.eclipse.paho.client.mqttv3.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/** MQTT gateway for outbound commands, inbound sensor data and device feedback. */
@Slf4j
@Service
public class MqttGatewayService implements MqttCallback {

    private static final String FEEDBACK_TOPIC = "terra.control.feedback";

    private final MqttClient mqttClient;
    private final ObjectMapper objectMapper;
    private final KafkaProducerService kafkaProducer;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final CommandRegistry commandRegistry;
    private final DeviceStateRegistry deviceStateRegistry;
    private final Clock clock;
    private final long feedbackTimeoutSeconds;

    @Value("${mqtt.topic.device-status:terra/devices/+/+/status}")
    private String deviceStatusTopicPattern;

    @Value("${mqtt.topic.sensor-data:terra/sensors/+/+/data}")
    private String sensorDataTopicPattern;

    @Value("${mqtt.qos:1}")
    private int defaultQos;

    @Value("${mqtt.sensor-ingest.enabled:true}")
    private boolean sensorIngestEnabled;

    private final AtomicLong commandsSent = new AtomicLong();
    private final AtomicLong statusReceived = new AtomicLong();
    private final AtomicLong sensorMsgReceived = new AtomicLong();
    private final AtomicLong errorCount = new AtomicLong();

    public MqttGatewayService(
            MqttClient mqttClient,
            ObjectMapper objectMapper,
            KafkaProducerService kafkaProducer,
            KafkaTemplate<String, Object> kafkaTemplate,
            CommandRegistry commandRegistry,
            DeviceStateRegistry deviceStateRegistry,
            Clock clock,
            @Value("${app.command.feedback-timeout-seconds:10}") long feedbackTimeoutSeconds) {
        this.mqttClient = mqttClient;
        this.objectMapper = objectMapper;
        this.kafkaProducer = kafkaProducer;
        this.kafkaTemplate = kafkaTemplate;
        this.commandRegistry = commandRegistry;
        this.deviceStateRegistry = deviceStateRegistry;
        this.clock = clock;
        this.feedbackTimeoutSeconds = feedbackTimeoutSeconds;
    }

    @PostConstruct
    public void init() {
        mqttClient.setCallback(this);
        subscribeTopics();
        log.info("MQTT Gateway initialized — listening for device status & sensor data");
    }

    /** Publish a command already claimed by the durable command registry. */
    public void publishCommand(DeviceCommand command) {
        if (command == null || command.getCommandId() == null || command.getCommandId().isBlank()) {
            throw new IllegalArgumentException("Device command must contain commandId");
        }

        try {
            String topic = command.toMqttTopic();
            String payload = objectMapper.writeValueAsString(command);
            MqttMessage message = new MqttMessage(payload.getBytes(StandardCharsets.UTF_8));
            message.setQos(defaultQos);
            message.setRetained(false);

            mqttClient.publish(topic, message);
            commandsSent.incrementAndGet();

            log.info("MQTT command published: topic={} command={} asset={} action={}",
                    topic,
                    command.getCommandId(),
                    command.getTargetAssetId(),
                    command.getActionType());
        } catch (MqttException | JsonProcessingException e) {
            errorCount.incrementAndGet();
            String assetId = command.getTargetAssetId() != null
                    ? command.getTargetAssetId() : "unknown";
            log.error("MQTT command publish failed: asset={} command={} error={}",
                    assetId, command.getCommandId(), e.getMessage(), e);
            throw new MqttPublishException(
                    "Failed to publish MQTT command for asset " + assetId,
                    e);
        }
    }

    public DeviceStatus getDeviceStatus(String farmId, String assetId) {
        return deviceStateRegistry.find(farmId, assetId)
                .map(this::toDeviceStatus)
                .orElse(null);
    }

    public Map<String, DeviceStatus> getAllDeviceStates() {
        Map<String, DeviceStatus> states = new LinkedHashMap<>();
        deviceStateRegistry.findAll().forEach((key, value) -> states.put(key, toDeviceStatus(value)));
        return Map.copyOf(states);
    }

    public Map<String, Object> getStats() {
        DeviceStateRegistry.RegistryStatus registryStatus = deviceStateRegistry.status();
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("commands_sent", commandsSent.get());
        stats.put("pending_command_acks", commandRegistry.pendingCount());
        stats.put("status_received", statusReceived.get());
        stats.put("sensor_messages", sensorMsgReceived.get());
        stats.put("error_count", errorCount.get());
        stats.put("tracked_devices", registryStatus.trackedDevices());
        stats.put("mqtt_connected", mqttClient.isConnected());
        stats.put("device_state_registry_backend", registryStatus.backend());
        stats.put("device_state_registry_available", registryStatus.available());
        if (registryStatus.lastSuccessfulReadAt() != null) {
            stats.put("device_state_registry_last_success_at", registryStatus.lastSuccessfulReadAt().toString());
        }
        return Map.copyOf(stats);
    }

    @Override
    public void connectionLost(Throwable cause) {
        log.warn("MQTT connection lost: {}. Waiting for automatic reconnect...", cause.getMessage());
    }

    @Override
    public void messageArrived(String topic, MqttMessage message) {
        try {
            String payload = new String(message.getPayload(), StandardCharsets.UTF_8);

            if (topic.contains("/status")) {
                handleDeviceStatus(topic, payload);
            } else if (topic.contains("/data")) {
                handleSensorData(topic, payload);
            } else {
                log.debug("Ignored MQTT message: topic={}", topic);
            }
        } catch (Exception e) {
            errorCount.incrementAndGet();
            log.error("MQTT message processing failed: topic={} error={}",
                    topic, e.getClass().getSimpleName(), e);
        }
    }

    @Override
    public void deliveryComplete(IMqttDeliveryToken token) {
        // QoS delivery confirms broker transport only; it is not a device execution ACK.
    }

    private void subscribeTopics() {
        try {
            mqttClient.subscribe(deviceStatusTopicPattern, defaultQos);
            log.info("MQTT subscription: {}", deviceStatusTopicPattern);

            if (sensorIngestEnabled) {
                mqttClient.subscribe(sensorDataTopicPattern, defaultQos);
                log.info("MQTT subscription: {}", sensorDataTopicPattern);
            }
        } catch (MqttException e) {
            log.error("MQTT subscription failed: {}", e.getMessage());
        }
    }

    private void handleDeviceStatus(String topic, String payload) {
        try {
            DeviceStatus status = objectMapper.readValue(payload, DeviceStatus.class);
            String[] parts = topic.split("/");
            if (parts.length < 5) {
                throw new IllegalArgumentException("Invalid device status topic");
            }

            String topicFarmId = parts[2];
            String topicAssetId = parts[3];
            if (status.getFarmId() != null && !topicFarmId.equals(status.getFarmId())) {
                throw new IllegalArgumentException("Device status farm identity mismatch");
            }
            if (status.getAssetId() != null && !topicAssetId.equals(status.getAssetId())) {
                throw new IllegalArgumentException("Device status asset identity mismatch");
            }

            Instant observedAt = clock.instant();
            status.setFarmId(topicFarmId);
            status.setAssetId(topicAssetId);

            // Never synthesize reportedAt from broker observation time. The safety policy
            // must be able to distinguish a device timestamp from Terra-Sense receipt time.
            deviceStateRegistry.save(DeviceStateRecord.from(status, observedAt));
            statusReceived.incrementAndGet();

            log.info("Device status accepted: state={} ack_present={}",
                    status.getState(), status.getLastCommandId() != null);

            if (status.hasTerminalCommandAcknowledgement()) {
                publishDeviceAcknowledgement(status);
            }
        } catch (JsonProcessingException e) {
            errorCount.incrementAndGet();
            log.warn("Device status parsing failed: topic={}", topic);
        }
    }

    private void publishDeviceAcknowledgement(DeviceStatus status) {
        String commandId = status.getLastCommandId();
        Optional<DeviceCommand> pending = commandRegistry.findPending(commandId);
        if (pending.isEmpty()) {
            log.warn("Ignoring unknown or duplicate device ACK: command={} asset={}",
                    commandId, status.getAssetId());
            return;
        }

        DeviceCommand command = pending.get();
        if (!command.getFarmId().equals(status.getFarmId())
                || !command.getTargetAssetId().equals(status.getAssetId())) {
            errorCount.incrementAndGet();
            log.error("Device ACK identity mismatch: command={} expected={}/{} actual={}/{}",
                    commandId,
                    command.getFarmId(), command.getTargetAssetId(),
                    status.getFarmId(), status.getAssetId());
            return;
        }

        String feedbackStatus = status.getLastCommandStatus().toUpperCase();
        String error = "FAILED".equals(feedbackStatus)
                ? (status.getLastCommandError() != null
                        ? status.getLastCommandError() : "Device reported failure")
                : "";

        if (!commandRegistry.claimCompletion(commandId, feedbackStatus, error)) {
            log.info("Ignoring duplicate terminal device ACK: command={} status={}",
                    commandId, feedbackStatus);
            return;
        }

        // Feedback transport still needs a timestamp even when the device omitted
        // reportedAt. This fallback does not alter the stored state used by safety checks.
        Instant acknowledgedAt = status.getReportedAt() != null
                ? status.getReportedAt()
                : clock.instant();

        Map<String, Object> feedback = Map.of(
                "specversion", "1.0",
                "type", "terra.sense.command.feedback",
                "source", "//terraneuron/terra-sense",
                "id", java.util.UUID.randomUUID().toString(),
                "time", acknowledgedAt.toString(),
                "datacontenttype", "application/json",
                "data", Map.of(
                        "trace_id", safe(command.getTraceId()),
                        "command_id", commandId,
                        "plan_id", safe(command.getPlanId()),
                        "farm_id", command.getFarmId(),
                        "target_asset_id", command.getTargetAssetId(),
                        "status", feedbackStatus,
                        "error", error,
                        "timestamp", acknowledgedAt.toString()
                )
        );

        try {
            kafkaTemplate.send(FEEDBACK_TOPIC, command.getFarmId(), feedback)
                    .get(feedbackTimeoutSeconds, TimeUnit.SECONDS);
            commandRegistry.finishCompletion(commandId);
            log.info("Device ACK broker acknowledged: command={} asset={} status={}",
                    commandId, command.getTargetAssetId(), feedbackStatus);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            commandRegistry.rollbackCompletion(commandId);
            throw new IllegalStateException("Interrupted while forwarding device ACK", e);
        } catch (Exception e) {
            commandRegistry.rollbackCompletion(commandId);
            throw new IllegalStateException("Failed to forward device ACK", e);
        }
    }

    private void handleSensorData(String topic, String payload) {
        try {
            com.terraneuron.sense.model.SensorData data =
                    objectMapper.readValue(payload, com.terraneuron.sense.model.SensorData.class);

            String[] parts = topic.split("/");
            if (parts.length >= 4) {
                if (data.getFarmId() == null) data.setFarmId(parts[2]);
                if (data.getSensorId() == null) data.setSensorId(parts[3]);
            }
            if (data.getTimestamp() == null) data.setTimestamp(clock.instant());

            kafkaProducer.sendSensorData(data);
            sensorMsgReceived.incrementAndGet();

            log.debug("MQTT sensor to Kafka: {}/{} = {}",
                    data.getFarmId(), data.getSensorType(), data.getValue());
        } catch (JsonProcessingException e) {
            errorCount.incrementAndGet();
            log.warn("MQTT sensor data parsing failed: topic={}", topic);
        }
    }

    private DeviceStatus toDeviceStatus(DeviceStateRecord state) {
        return DeviceStatus.builder()
                .farmId(state.getFarmId())
                .assetId(state.getAssetId())
                .deviceType(state.getDeviceType())
                .state(state.getState())
                .maintenanceMode(state.isMaintenanceMode())
                .capabilities(state.getCapabilities())
                .lastCommandId(state.getLastCommandId())
                .lastCommandStatus(state.getLastCommandStatus())
                .lastCommandError(state.getLastCommandError())
                .attributes(state.getAttributes())
                .reportedAt(state.getReportedAt())
                .build();
    }

    private String safe(String value) {
        return value != null ? value : "";
    }
}
