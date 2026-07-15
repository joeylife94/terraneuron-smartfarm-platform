package com.terraneuron.sense.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import com.terraneuron.sense.model.DeviceStatus;
import lombok.extern.slf4j.Slf4j;
import org.eclipse.paho.client.mqttv3.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

/**
 * MQTT 게이트웨이 서비스
 *
 * 양방향 MQTT 브릿지:
 * 1) Outbound: Kafka terra.control.command → MQTT 디바이스 제어
 * 2) Inbound : MQTT 센서 데이터 → Kafka raw-sensor-data (선택)
 * 3) Feedback: MQTT 디바이스 상태 → 인메모리 상태 캐시 + Kafka 보고
 *
 * MQTT 토픽 규칙:
 *   terra/devices/{farmId}/{assetId}/command  — 제어 명령 (publish)
 *   terra/devices/{farmId}/{assetId}/status   — 디바이스 피드백 (subscribe)
 *   terra/sensors/{farmId}/+/data             — 센서 raw data (subscribe)
 */
@Slf4j
@Service
public class MqttGatewayService implements MqttCallback {

    private final MqttClient mqttClient;
    private final ObjectMapper objectMapper;
    private final KafkaProducerService kafkaProducer;

    @Value("${mqtt.topic.device-status:terra/devices/+/+/status}")
    private String deviceStatusTopicPattern;

    @Value("${mqtt.topic.sensor-data:terra/sensors/+/+/data}")
    private String sensorDataTopicPattern;

    @Value("${mqtt.qos:1}")
    private int defaultQos;

    @Value("${mqtt.sensor-ingest.enabled:true}")
    private boolean sensorIngestEnabled;

    // — 디바이스 상태 인메모리 캐시 —
    private final ConcurrentHashMap<String, DeviceStatus> deviceStates = new ConcurrentHashMap<>();

    // — 통계 —
    private final AtomicLong commandsSent = new AtomicLong();
    private final AtomicLong statusReceived = new AtomicLong();
    private final AtomicLong sensorMsgReceived = new AtomicLong();
    private final AtomicLong errorCount = new AtomicLong();

    public MqttGatewayService(MqttClient mqttClient, ObjectMapper objectMapper,
                              KafkaProducerService kafkaProducer) {
        this.mqttClient = mqttClient;
        this.objectMapper = objectMapper;
        this.kafkaProducer = kafkaProducer;
    }

    @PostConstruct
    public void init() {
        mqttClient.setCallback(this);
        subscribeTopics();
        log.info("✅ MQTT Gateway initialized — listening for device status & sensor data");
    }

    /**
     * 디바이스 제어 명령을 MQTT로 발행
     */
    public void publishCommand(DeviceCommand cmd) {
        try {
            String topic = cmd.toMqttTopic();
            String payload = objectMapper.writeValueAsString(cmd);
            MqttMessage msg = new MqttMessage(payload.getBytes(StandardCharsets.UTF_8));
            msg.setQos(defaultQos);
            msg.setRetained(false);

            mqttClient.publish(topic, msg);
            commandsSent.incrementAndGet();

            log.info("📤 MQTT 명령 발행: topic={}, asset={}, action={}",
                    topic, cmd.getTargetAssetId(), cmd.getActionType());

        } catch (MqttException | JsonProcessingException e) {
            errorCount.incrementAndGet();
            String assetId = cmd != null ? cmd.getTargetAssetId() : "unknown";
            log.error("❌ MQTT 명령 발행 실패: asset={}, err={}", assetId, e.getMessage(), e);
            throw new MqttPublishException(
                    "Failed to publish MQTT command for asset " + assetId,
                    e
            );
        }
    }

    /**
     * 디바이스 상태 조회 (인메모리 캐시)
     */
    public DeviceStatus getDeviceStatus(String farmId, String assetId) {
        return deviceStates.get(farmId + "/" + assetId);
    }

    /**
     * 전체 디바이스 상태 조회
     */
    public Map<String, DeviceStatus> getAllDeviceStates() {
        return Map.copyOf(deviceStates);
    }

    /**
     * 통계
     */
    public Map<String, Object> getStats() {
        return Map.of(
                "commands_sent", commandsSent.get(),
                "status_received", statusReceived.get(),
                "sensor_messages", sensorMsgReceived.get(),
                "error_count", errorCount.get(),
                "tracked_devices", deviceStates.size(),
                "mqtt_connected", mqttClient.isConnected()
        );
    }

    // ========== MQTT Callback ==========

    @Override
    public void connectionLost(Throwable cause) {
        log.warn("⚠️ MQTT 연결 끊김: {}. 자동 재연결 대기...", cause.getMessage());
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
                log.debug("무시된 MQTT 메시지: topic={}", topic);
            }

        } catch (Exception e) {
            errorCount.incrementAndGet();
            log.error("❌ MQTT 메시지 처리 실패: topic={}, err={}", topic, e.getMessage());
        }
    }

    @Override
    public void deliveryComplete(IMqttDeliveryToken token) {
        // QoS 1/2 전송 완료 확인
    }

    // ========== 내부 메서드 ==========

    private void subscribeTopics() {
        try {
            // 디바이스 상태 피드백 구독
            mqttClient.subscribe(deviceStatusTopicPattern, defaultQos);
            log.info("📡 MQTT 구독: {}", deviceStatusTopicPattern);

            // 센서 데이터 구독 (옵션)
            if (sensorIngestEnabled) {
                mqttClient.subscribe(sensorDataTopicPattern, defaultQos);
                log.info("📡 MQTT 구독: {}", sensorDataTopicPattern);
            }

        } catch (MqttException e) {
            log.error("❌ MQTT 토픽 구독 실패: {}", e.getMessage());
        }
    }

    /**
     * 디바이스 상태 메시지 처리
     * 토픽: terra/devices/{farmId}/{assetId}/status
     */
    private void handleDeviceStatus(String topic, String payload) {
        try {
            DeviceStatus status = objectMapper.readValue(payload, DeviceStatus.class);

            // 토픽에서 farmId/assetId 추출 (fallback)
            String[] parts = topic.split("/");
            if (parts.length >= 4) {
                if (status.getFarmId() == null) status.setFarmId(parts[2]);
                if (status.getAssetId() == null) status.setAssetId(parts[3]);
            }
            if (status.getReportedAt() == null) status.setReportedAt(Instant.now());

            // 인메모리 캐시 갱신
            String key = status.getFarmId() + "/" + status.getAssetId();
            deviceStates.put(key, status);
            statusReceived.incrementAndGet();

            log.info("📥 디바이스 상태: {} → {} ({})", key, status.getState(),
                    status.getLastCommandId() != null ? "cmd:" + status.getLastCommandId() : "idle");

        } catch (JsonProcessingException e) {
            errorCount.incrementAndGet();
            log.warn("⚠️ 디바이스 상태 파싱 실패: topic={}", topic);
        }
    }

    /**
     * MQTT 센서 데이터 → Kafka 포워딩
     * 토픽: terra/sensors/{farmId}/{sensorId}/data
     */
    private void handleSensorData(String topic, String payload) {
        try {
            com.terraneuron.sense.model.SensorData data =
                    objectMapper.readValue(payload, com.terraneuron.sense.model.SensorData.class);

            // 토픽에서 farmId/sensorId 추출 (fallback)
            String[] parts = topic.split("/");
            if (parts.length >= 4) {
                if (data.getFarmId() == null) data.setFarmId(parts[2]);
                if (data.getSensorId() == null) data.setSensorId(parts[3]);
            }
            if (data.getTimestamp() == null) data.setTimestamp(Instant.now());

            // Kafka로 포워딩
            kafkaProducer.sendSensorData(data);
            sensorMsgReceived.incrementAndGet();

            log.debug("📡→📤 MQTT 센서 → Kafka: {}/{} = {}",
                    data.getFarmId(), data.getSensorType(), data.getValue());

        } catch (JsonProcessingException e) {
            errorCount.incrementAndGet();
            log.warn("⚠️ MQTT 센서 데이터 파싱 실패: topic={}", topic);
        }
    }
}
