package com.terraneuron.sense.controller;

import com.terraneuron.sense.model.SensorData;
import com.terraneuron.sense.service.KafkaProducerService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.Map;

/**
 * HTTP API를 통한 센서 데이터 수집
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/ingest")
@RequiredArgsConstructor
public class IngestionController {

    private final KafkaProducerService kafkaProducerService;

    @PostMapping("/sensor-data")
    public ResponseEntity<?> ingestSensorData(@RequestBody SensorData sensorData) {
        log.info("📥 HTTP 센서 데이터 수신: {}", sensorData);
        
        if (sensorData.getTimestamp() == null) {
            sensorData.setTimestamp(Instant.now());
        }
        
        kafkaProducerService.sendSensorData(sensorData);
        
        return ResponseEntity.ok(Map.of(
                "status", "accepted",
                "sensorId", sensorData.getSensorId(),
                "timestamp", sensorData.getTimestamp()
        ));
    }

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        return ResponseEntity.ok(Map.of(
                "service", "terra-sense",
                "status", "healthy",
                "timestamp", Instant.now()
        ));
    }
}
