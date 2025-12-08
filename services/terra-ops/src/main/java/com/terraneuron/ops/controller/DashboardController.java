package com.terraneuron.ops.controller;

import com.terraneuron.ops.entity.Insight;
import com.terraneuron.ops.entity.Sensor;
import com.terraneuron.ops.repository.InsightRepository;
import com.terraneuron.ops.repository.SensorRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Dashboard API Controller
 * 프론트엔드를 위한 REST API 제공
 */
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class DashboardController {

    private final InsightRepository insightRepository;
    private final SensorRepository sensorRepository;

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        return ResponseEntity.ok(Map.of(
                "service", "terra-ops",
                "status", "healthy",
                "timestamp", Instant.now()
        ));
    }

    @GetMapping("/sensors")
    public ResponseEntity<List<Sensor>> getAllSensors() {
        return ResponseEntity.ok(sensorRepository.findAll());
    }

    @GetMapping("/sensors/{farmId}")
    public ResponseEntity<List<Sensor>> getSensorsByFarm(@PathVariable Long farmId) {
        return ResponseEntity.ok(sensorRepository.findByFarmId(farmId));
    }

    @GetMapping("/insights")
    public ResponseEntity<List<Insight>> getAllInsights() {
        return ResponseEntity.ok(insightRepository.findAll());
    }

    @GetMapping("/insights/sensor/{sensorId}")
    public ResponseEntity<List<Insight>> getInsightsBySensor(@PathVariable Long sensorId) {
        return ResponseEntity.ok(insightRepository.findBySensorId(sensorId));
    }

    @GetMapping("/insights/severity/{severity}")
    public ResponseEntity<List<Insight>> getInsightsBySeverity(@PathVariable String severity) {
        return ResponseEntity.ok(insightRepository.findBySeverity(severity));
    }

    @GetMapping("/dashboard/summary")
    public ResponseEntity<?> getDashboardSummary() {
        long totalSensors = sensorRepository.count();
        long activeSensors = sensorRepository.findByStatus("ACTIVE").size();
        long totalInsights = insightRepository.count();
        long criticalInsights = insightRepository.findBySeverity("critical").size();
        long warningInsights = insightRepository.findBySeverity("warning").size();

        return ResponseEntity.ok(Map.of(
                "totalSensors", totalSensors,
                "activeSensors", activeSensors,
                "totalInsights", totalInsights,
                "criticalInsights", criticalInsights,
                "warningInsights", warningInsights,
                "timestamp", Instant.now()
        ));
    }
}
