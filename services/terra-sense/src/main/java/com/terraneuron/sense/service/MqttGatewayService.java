package com.terraneuron.sense.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceStatus;
import lombok.extern.slf4j.Slf4j;
import org.eclipse.paho.client.mqttv3.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * MQTT gateway for outbound commands, inbound sensor data and device feedback.
 */
@Slf4j
@Service
public class MqttGatewayService implements MqttCallback {

    private static final String FEEDBACK_TOPIC = "terra.control.feedback";

    private final MqttClient mqttClient;
    private final ObjectMapper objectMapper;
    private final KafkaProducerService kafkaProducer;
    private final KafkaTemplate<String, Object> kafkaTemplate;

    @Value("${mqtt.topic.device-status:terra/devices/+/+/status}")
    private String deviceStatusTopicPattern;

    @Value("${mqtt.topic.sensor-data:terra/sensors/+/+/data}")
    private String sensorDataTopicPattern;

    @Value("${mqtt.qos:1}")
    private int defaultQos;

    @Value("${mqtt.sensor-ingest.enabled:true}")
    private boolean sensorIngestEnabled;

    private final ConcurrentHashMap<String, DeviceStatus> deviceStates = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, DeviceCommand> pendingCommands = new ConcurrentHashMap<>();

    private final AtomicLong commandsSent = new AtomicLong();
    private final AtomicLong statusReceived = new AtomicLong();
    private final AtomicLong sensorMsgReceived = new AtomicLong();
    private final AtomicLong errorCount = new AtomicLong();

    public MqttGatewayService(MqttClient mqttClient, ObjectMapper objectMapper,
                              KafkaProducerService kafkaProducer,
                              KafkaTemplate<String, Object> kafkaTemplate) {
        this.mqttClient = mqttClient;
        this.objectMapper = objectMapper;
        this.kafkaProducer = kafkaProducer;
        this.kafkaTemplate = kafkaTemplate;
    }

    @PostConstruct
    public void init() {
        mqttClient.setCallback(this);
        subscribeTopics();
        log.info("✅ MQTT Gateway initialized — listening for device status & sensor data");
    }

    /**
     * Publish a command and retain its correlation metadata until a physical device ACK arrives.
     */
    public void publishCommand(DeviceCommand cmd) {
        if (cmd == null || cmd.getCommandId() == null || cmd.getCommandId().isBlank()) {
            throw new IllegalArgumentException("Device command must contain commandId");
        }

        pendingCommands.put(cmd.getCommandId(), cmd);
        try {
            String topic = cmd.toMqttTopic();
            String payload = objectMapper.writeValueAsString(cmd);
            MqttMessage msg = new MqttMessage(payload.getBytes(StandardCharsets.UTF_8));
            msg.setQos(defaultQos);
            msg.setRetained(false);

            mqttClient.publish(topic, msg);
            commandsSent.incrementAndGet();

            log.info("📤 MQTT command published: topic={} command={} asset={} action={}",
                    topic, cmd.getCommandId(), cmd.getTargetAssetId(), cmd.getActionType());

        } catch (MqttException | JsonProcessingException e) {
            pendingCommands.remove(cmd.getCommandId(), cmd);
            errorCount.incrementAndGet();
            String assetId = cmd.getTargetAssetId() != null ? cmd.getTargetAssetId() : "unknown";
            log.error("❌ MQTT command publish failed: asset={} command={} error={}",
                    assetId, cmd.getCommandId(), e.getMessage(), e);
            throw new MqttPublishException(
                    "Failed to publish MQTT command for asset " + assetId,
                    e
            );
        }
    }

    public DeviceStatus getDeviceStatus(String farmId, String assetId) {
        return deviceStates.get(farmId + "/" + assetId);
    }

    public Map<String, DeviceStatus> getAllDeviceStates() {
        return Map.copyOf(deviceStates);
    }

    public Map<String, Object> getStats() {
        return Map.of(
                "commands_sent", commandsSent.get(),
                "pending_command_acks", pendingCommands.size(),
                "status_received", statusReceived.get(),
                "sensor_messages", sensorMsgReceived.get(),
                "error_count", errorCount.get(),
                "tracked_devices", deviceStates.size(),
                "mqtt_connected", mqttClient.isConnected()
        );
    }

    @Override
    public void connectionLost(Throwable cause) {
        log.warn("⚠️ MQTT connection lost: {}. Waiting for automatic reconnect...", cause.getMessage());
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
            log.error("❌ MQTT message processing failed: topic={} error={}", topic, e.getMessage(), e);
        }
    }

    @Override
    public void deliveryComplete(IMqttDeliveryToken token) {
        // QoS delivery confirms broker transport only; it is not a device execution ACK.
    }

    private void subscribeTopics() {
        try {
            mqttClient.subscribe(deviceStatusTopicPattern, defaultQos);
            log.info("📡 MQTT subscription: {}", deviceStatusTopicPattern);

            if (sensorIngestEnabled) {
                mqttClient.subscribe(sensorDataTopicPattern, defaultQos);
                log.info("📡 MQTT subscription: {}", sensorDataTopicPattern);
            }

        } catch (MqttException e) {
            log.error("❌ MQTT subscription failed: {}", e.getMessage());
        }
    }

    /**
     * Process status from terra/devices/{farmId}/{assetId}/status.
     */
    private void handleDeviceStatus(String topic, String payload) {
        try {
            DeviceStatus status = objectMapper.readValue(payload, DeviceStatus.class);

            String[] parts = topic.split("/");
            if (parts.length >= 4) {
                if (status.getFarmId() == null) status.setFarmId(parts[2]);
                if (status.getAssetId() == null) status.setAssetId(parts[3]);
            }
            if (status.getReportedAt() == null) status.setReportedAt(Instant.now());

            String key = status.getFarmId() + "/" + status.getAssetId();
            deviceStates.put(key, status);
            statusReceived.incrementAndGet();

            log.info("📥 Device status: {} → {} ({})", key, status.getState(),
                    status.getLastCommandId() != null ? "command:" + status.getLastCommandId() : "idle");

            if (status.hasTerminalCommandAcknowledgement()) {
                publishDeviceAcknowledgement(status);
            }

        } catch (JsonProcessingException e) {
            errorCount.incrementAndGet();
            log.warn("⚠️ Device status parsing failed: topic={}", topic);
        }
    }

    private void publishDeviceAcknowledgement(DeviceStatus status) {
        String commandId = status.getLastCommandId();
        DeviceCommand command = pendingCommands.get(commandId);
        if (command == null) {
            log.warn("⚠️ Ignoring unknown or duplicate device ACK: command={} asset={}",
                    commandId, status.getAssetId());
            return;
        }

        if (!command.getFarmId().equals(status.getFarmId())
                || !command.getTargetAssetId().equals(status.getAssetId())) {
            errorCount.incrementAndGet();
            log.error("❌ Device ACK identity mismatch: command={} expected={}/{} actual={}/{}",
                    commandId,
                    command.getFarmId(), command.getTargetAssetId(),
                    status.getFarmId(), status.getAssetId());
            return;
        }

        String feedbackStatus = status.getLastCommandStatus().toUpperCase();
        String error = "FAILED".equals(feedbackStatus)
                ? (status.getLastCommandError() != null ? status.getLastCommandError() : "Device reported failure")
                : "";

        Map<String, Object> feedback = Map.of(
                "specversion", "1.0",
                "type", "terra.sense.command.feedback",
                "source", "//terraneuron/terra-sense",
                "id", java.util.UUID.randomUUID().toString(),
                "time", status.getReportedAt().toString(),
                "datacontenttype", "application/json",
                "data", Map.of(
                        "trace_id", safe(command.getTraceId()),
                        "command_id", commandId,
                        "plan_id", safe(command.getPlanId()),
                        "farm_id", command.getFarmId(),
                        "target_asset_id", command.getTargetAssetId(),
                        "status", feedbackStatus,
                        "error", error,
                        "timestamp", status.getReportedAt().toString()
                )
        );

        kafkaTemplate.send(FEEDBACK_TOPIC, command.getFarmId(), feedback);
        pendingCommands.remove(commandId, command);
        log.info("📤 Device ACK forwarded: command={} asset={} status={}",
                commandId, command.getTargetAssetId(), feedbackStatus);
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
            if (data.getTimestamp() == null) data.setTimestamp(Instant.now());

            kafkaProducer.sendSensorData(data);
            sensorMsgReceived.incrementAndGet();

            log.debug("📡→📤 MQTT sensor → Kafka: {}/{} = {}",
                    data.getFarmId(), data.getSensorType(), data.getValue());

        } catch (JsonProcessingException e) {
            errorCount.incrementAndGet();
            log.warn("⚠️ MQTT sensor data parsing failed: topic={}", topic);
        }
    }

    private String safe(String value) {
        return value != null ? value : "";
    }
}
