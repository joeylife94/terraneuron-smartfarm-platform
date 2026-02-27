package com.terraneuron.sense.controller;

import com.terraneuron.sense.model.DeviceStatus;
import com.terraneuron.sense.service.MqttGatewayService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 디바이스 상태 조회 REST API
 *
 * MQTT를 통해 수집된 디바이스 상태를 인메모리 캐시에서 제공
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/devices")
@RequiredArgsConstructor
public class DeviceController {

    private final MqttGatewayService mqttGateway;

    /**
     * 전체 디바이스 상태 목록
     */
    @GetMapping("/status")
    public ResponseEntity<?> getAllDeviceStatus() {
        Map<String, DeviceStatus> states = mqttGateway.getAllDeviceStates();
        return ResponseEntity.ok(Map.of(
                "count", states.size(),
                "devices", states
        ));
    }

    /**
     * 특정 디바이스 상태 조회
     */
    @GetMapping("/status/{farmId}/{assetId}")
    public ResponseEntity<?> getDeviceStatus(
            @PathVariable String farmId,
            @PathVariable String assetId) {
        DeviceStatus status = mqttGateway.getDeviceStatus(farmId, assetId);
        if (status == null) {
            return ResponseEntity.ok(Map.of(
                    "farmId", farmId,
                    "assetId", assetId,
                    "state", "unknown",
                    "message", "No status reported from device"
            ));
        }
        return ResponseEntity.ok(status);
    }

    /**
     * MQTT 게이트웨이 통계
     */
    @GetMapping("/mqtt/stats")
    public ResponseEntity<?> getMqttStats() {
        return ResponseEntity.ok(mqttGateway.getStats());
    }
}
