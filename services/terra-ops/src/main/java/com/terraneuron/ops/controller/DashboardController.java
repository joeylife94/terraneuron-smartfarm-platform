package com.terraneuron.ops.controller;

import com.terraneuron.ops.entity.Insight;
import com.terraneuron.ops.repository.InsightRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Dashboard API Controller
 * Provides REST API for frontend consumption
 */
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class DashboardController {

    private final InsightRepository insightRepository;

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        return ResponseEntity.ok(Map.of(
                "service", "terra-ops",
                "status", "healthy",
                "timestamp", Instant.now()
        ));
    }

    /**
     * GET /api/v1/dashboard/insights
     * Returns all insights ordered by timestamp descending
     */
    @GetMapping("/dashboard/insights")
    public ResponseEntity<List<Insight>> getDashboardInsights() {
        return ResponseEntity.ok(insightRepository.findAllByOrderByTimestampDesc());
    }

    /**
     * GET /api/v1/insights
     * Returns all insights
     */
    @GetMapping("/insights")
    public ResponseEntity<List<Insight>> getAllInsights() {
        return ResponseEntity.ok(insightRepository.findAll());
    }

    /**
     * GET /api/v1/insights/farm/{farmId}
     * Returns insights for a specific farm
     */
    @GetMapping("/insights/farm/{farmId}")
    public ResponseEntity<List<Insight>> getInsightsByFarm(@PathVariable String farmId) {
        return ResponseEntity.ok(insightRepository.findByFarmId(farmId));
    }

    /**
     * GET /api/v1/insights/status/{status}
     * Returns insights filtered by status
     */
    @GetMapping("/insights/status/{status}")
    public ResponseEntity<List<Insight>> getInsightsByStatus(@PathVariable String status) {
        return ResponseEntity.ok(insightRepository.findByStatus(status));
    }

    /**
     * GET /api/v1/dashboard/summary
     * Returns dashboard summary statistics
     */
    @GetMapping("/dashboard/summary")
    public ResponseEntity<?> getDashboardSummary() {
        long totalInsights = insightRepository.count();
        long normalInsights = insightRepository.findByStatus("NORMAL").size();
        long anomalyInsights = insightRepository.findByStatus("ANOMALY").size();

        return ResponseEntity.ok(Map.of(
                "totalInsights", totalInsights,
                "normalInsights", normalInsights,
                "anomalyInsights", anomalyInsights,
                "timestamp", Instant.now()
        ));
    }
}
