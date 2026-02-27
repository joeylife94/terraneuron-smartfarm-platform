package com.terraneuron.sense.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

/**
 * 디바이스 제어 명령 모델
 * terra-ops에서 Kafka를 통해 전달받은 명령 → MQTT로 디바이스에 전송
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DeviceCommand {

    /** 명령 고유 ID */
    private String commandId;

    /** 실행 추적 ID (distributed tracing) */
    private String traceId;

    /** 원본 액션 플랜 ID */
    private String planId;

    /** 대상 디바이스/자산 ID (e.g. fan-01, vent-01) */
    private String targetAssetId;

    /** 제어 유형 (TURN_ON, TURN_OFF, SET_LEVEL, ...) */
    private String actionType;

    /** 디바이스 실행 파라미터 (duration_minutes, speed_level 등) */
    private Map<String, Object> parameters;

    /** 명령 실행자 */
    private String executedBy;

    /** 대상 농장 ID */
    private String farmId;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", timezone = "UTC")
    private Instant issuedAt;

    /**
     * MQTT 토픽 생성
     * 패턴: terra/devices/{farmId}/{targetAssetId}/command
     */
    public String toMqttTopic() {
        return String.format("terra/devices/%s/%s/command",
                farmId != null ? farmId : "unknown",
                targetAssetId != null ? targetAssetId : "unknown"
        );
    }

    /**
     * 피드백용 MQTT 토픽
     * 패턴: terra/devices/{farmId}/{targetAssetId}/status
     */
    public String toFeedbackTopic() {
        return String.format("terra/devices/%s/%s/status",
                farmId != null ? farmId : "unknown",
                targetAssetId != null ? targetAssetId : "unknown"
        );
    }
}
