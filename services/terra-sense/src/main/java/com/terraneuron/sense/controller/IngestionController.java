package com.terraneuron.sense.controller;

import com.terraneuron.sense.model.SensorData;
import com.terraneuron.sense.service.InfluxDbWriterService;
import com.terraneuron.sense.service.KafkaProducerService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.Map;

/**
 * HTTP API를 통한 센서 데이터 수집
 * 1) InfluxDB에 시계열 저장 (추세 분석/이력)
 * 2) Kafka로 실시간 스트리밍 (AI 분석 파이프라인)
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/ingest")
@RequiredArgsConstructor
public class IngestionController {

    private final KafkaProducerService kafkaProducerService;
    private final InfluxDbWriterService influxDbWriterService;

    @PostMapping("/sensor-data")
    public ResponseEntity<?> ingestSensorData(@Valid @RequestBody SensorData sensorData) {
        log.info("📥 HTTP 센서 데이터 수신: {}", sensorData);

        if (sensorData.getTimestamp() == null) {
            sensorData.setTimestamp(Instant.now());
        }

        // 1) InfluxDB 시계열 저장 (실패해도 Kafka 전송에 영향 없음)
        influxDbWriterService.writeSensorData(sensorData);

        // 2) Kafka 실시간 스트리밍 → terra-cortex AI 분석
        kafkaProducerService.sendSensorData(sensorData);

        return ResponseEntity.ok(Map.of(
                "status", "accepted",
                "sensorId", sensorData.getSensorId(),
                "timestamp", sensorData.getTimestamp(),
                "persisted", true
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
