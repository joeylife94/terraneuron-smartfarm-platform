package com.terraneuron.sense.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.sense.model.DeviceCommand;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Map;

/**
 * Kafka → MQTT 제어 명령 브릿지
 *
 * 흐름:
 *   terra-ops (ActionPlanService.executePlan)
 *     → Kafka "terra.control.command"
 *       → 이 Consumer
 *         → MqttGatewayService.publishCommand()
 *           → MQTT "terra/devices/{farmId}/{assetId}/command"
 *             → 실제 IoT 디바이스
 *
 * 명령 실행 후 피드백 결과를 Kafka "terra.control.feedback" 토픽으로 보고
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DeviceCommandConsumer {

    private final MqttGatewayService mqttGateway;
    private final ObjectMapper objectMapper;
    private final KafkaTemplate<String, Object> kafkaTemplate;

    private static final String FEEDBACK_TOPIC = "terra.control.feedback";

    /**
     * Kafka에서 terra.control.command 메시지를 소비하여 MQTT로 전달
     */
    @KafkaListener(
            topics = "terra.control.command",
            groupId = "terra-sense-command-group",
            containerFactory = "commandListenerContainerFactory"
    )
    public void onCommand(Map<String, Object> commandEvent) {
        try {
            log.info("📥 제어 명령 수신 (Kafka → MQTT bridge)");

            // CloudEvents 포맷에서 data 추출
            @SuppressWarnings("unchecked")
            Map<String, Object> data = (Map<String, Object>) commandEvent.get("data");
            if (data == null) {
                log.error("❌ 잘못된 CloudEvent: 'data' 필드 누락");
                return;
            }

            String traceId = (String) data.get("trace_id");
            String commandId = (String) data.get("command_id");
            String planId = (String) data.get("plan_id");
            String targetAssetId = (String) data.get("target_asset_id");
            String actionType = (String) data.get("action_type");
            String executedBy = (String) data.get("executed_by");

            // parameters 파싱 (JSON 문자열 또는 Map)
            Map<String, Object> parameters = parseParameters(data.get("parameters"));

            // farmId 추출 — commandEvent 키 또는 data에서 가져오기
            String farmId = (String) data.getOrDefault("farm_id",
                    commandEvent.getOrDefault("key", "unknown"));

            DeviceCommand cmd = DeviceCommand.builder()
                    .commandId(commandId)
                    .traceId(traceId)
                    .planId(planId)
                    .targetAssetId(targetAssetId)
                    .actionType(actionType)
                    .parameters(parameters)
                    .executedBy(executedBy)
                    .farmId(farmId)
                    .issuedAt(Instant.now())
                    .build();

            // MQTT로 발행
            mqttGateway.publishCommand(cmd);

            // 피드백: 명령 전달 완료 보고
            sendFeedback(traceId, commandId, planId, farmId, targetAssetId, "DELIVERED", null);

            log.info("✅ 제어 명령 전달 완료: {} → {} ({})", commandId, targetAssetId, actionType);

        } catch (Exception e) {
            log.error("❌ 제어 명령 처리 실패: {}", e.getMessage(), e);

            // 실패 피드백
            try {
                @SuppressWarnings("unchecked")
                Map<String, Object> data = (Map<String, Object>) commandEvent.get("data");
                if (data != null) {
                    sendFeedback(
                            (String) data.get("trace_id"),
                            (String) data.get("command_id"),
                            (String) data.get("plan_id"),
                            (String) data.getOrDefault("farm_id", "unknown"),
                            (String) data.get("target_asset_id"),
                            "FAILED",
                            e.getMessage()
                    );
                }
            } catch (Exception ignored) {}
        }
    }

    /**
     * 피드백 메시지를 Kafka로 전송
     */
    private void sendFeedback(String traceId, String commandId, String planId,
                              String farmId, String assetId, String status, String error) {
        try {
            Map<String, Object> feedback = Map.of(
                    "specversion", "1.0",
                    "type", "terra.sense.command.feedback",
                    "source", "//terraneuron/terra-sense",
                    "id", java.util.UUID.randomUUID().toString(),
                    "time", Instant.now().toString(),
                    "datacontenttype", "application/json",
                    "data", Map.of(
                            "trace_id", traceId != null ? traceId : "",
                            "command_id", commandId != null ? commandId : "",
                            "plan_id", planId != null ? planId : "",
                            "farm_id", farmId,
                            "target_asset_id", assetId != null ? assetId : "",
                            "status", status,
                            "error", error != null ? error : "",
                            "timestamp", Instant.now().toString()
                    )
            );

            kafkaTemplate.send(FEEDBACK_TOPIC, farmId, feedback);
            log.info("📤 피드백 전송: {} → {} ({})", commandId, assetId, status);

        } catch (Exception e) {
            log.error("❌ 피드백 전송 실패: {}", e.getMessage());
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
                log.warn("⚠️ Failed to parse legacy string parameters as JSON; preserving raw value: {}",
                        e.getMessage());
                return Map.of("raw", params);
            }
        }
        return Map.of();
    }
}
