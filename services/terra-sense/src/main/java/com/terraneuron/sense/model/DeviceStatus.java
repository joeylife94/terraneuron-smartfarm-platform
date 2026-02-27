package com.terraneuron.sense.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

/**
 * 디바이스 상태 모델
 * MQTT를 통해 디바이스에서 보고된 현재 상태
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DeviceStatus {

    /** 디바이스/자산 ID */
    private String assetId;

    /** 농장 ID */
    private String farmId;

    /** 디바이스 유형 (fan, heater, humidifier, dehumidifier, vent, led) */
    private String deviceType;

    /** 현재 상태 (online, offline, running, idle, error) */
    private String state;

    /** 마지막 명령 ID (실행 중인 경우) */
    private String lastCommandId;

    /** 확장 속성 (speed_level, power_percentage 등) */
    private Map<String, Object> attributes;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", timezone = "UTC")
    private Instant reportedAt;

    /** 디바이스 온라인 여부 */
    public boolean isOnline() {
        return "online".equals(state) || "running".equals(state) || "idle".equals(state);
    }
}
