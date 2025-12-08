package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * AI 분석 인사이트 엔티티
 */
@Entity
@Table(name = "insights")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Insight {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "insight_id")
    private Long insightId;

    @Column(name = "sensor_id", nullable = false)
    private Long sensorId;

    @Column(name = "insight_type", nullable = false, length = 50)
    private String insightType;

    @Column(name = "severity", length = 20)
    private String severity;

    @Column(name = "message", columnDefinition = "TEXT")
    private String message;

    @Column(name = "confidence_score", precision = 5, scale = 2)
    private Double confidenceScore;

    @Column(name = "detected_at", nullable = false)
    private Instant detectedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
