package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * AI Analysis Insight Entity
 * Stores processed insights from terra-cortex AI analysis
 */
@Entity
@Table(name = "insights", indexes = {
    @Index(name = "idx_farm_id", columnList = "farm_id"),
    @Index(name = "idx_status", columnList = "status"),
    @Index(name = "idx_timestamp", columnList = "timestamp")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Insight {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "trace_id", length = 100)
    private String traceId;

    @Column(name = "farm_id", nullable = false)
    private String farmId;

    @Column(name = "asset_id", length = 100)
    private String assetId;

    @Column(name = "asset_type", length = 50)
    private String assetType;

    @Column(name = "sensor_type", length = 50)
    private String sensorType;

    @Column(name = "status", nullable = false, length = 50)
    private String status;

    @Column(name = "severity", length = 50)
    private String severity;

    @Column(name = "message", columnDefinition = "TEXT")
    private String message;

    @Column(name = "raw_value")
    private Double rawValue;

    @Column(name = "confidence")
    private Double confidence;
    
    @Column(name = "llm_recommendation", columnDefinition = "TEXT")
    private String llmRecommendation;

    @Column(name = "rag_context", columnDefinition = "TEXT")
    private String ragContext;

    @Column(name = "timestamp", nullable = false)
    private Instant timestamp;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
