package com.terraneuron.ops.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * 생장 단계 엔티티
 * 작물별 생장 단계(파종→발아→영양생장→개화→착과→수확)에 따른
 * 최적 환경 조건(온도, 습도, CO2, 광량, 토양수분)을 정의
 */
@Entity
@Table(name = "growth_stages", indexes = {
    @Index(name = "idx_stage_crop", columnList = "crop_id"),
    @Index(name = "idx_stage_code", columnList = "stage_code")
}, uniqueConstraints = {
    @UniqueConstraint(name = "uk_crop_stage", columnNames = {"crop_id", "stage_order"})
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class GrowthStage {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "crop_id", nullable = false)
    @JsonIgnore
    private CropProfile cropProfile;

    @Column(name = "stage_order", nullable = false)
    private Integer stageOrder;

    @Column(name = "stage_code", nullable = false, length = 30)
    private String stageCode;

    @Column(name = "stage_name", nullable = false, length = 100)
    private String stageName;

    @Column(name = "duration_days", nullable = false)
    private Integer durationDays;

    // ========== 온도 범위 ==========
    @Column(name = "temp_min", nullable = false)
    private Double tempMin;

    @Column(name = "temp_optimal_low", nullable = false)
    private Double tempOptimalLow;

    @Column(name = "temp_optimal_high", nullable = false)
    private Double tempOptimalHigh;

    @Column(name = "temp_max", nullable = false)
    private Double tempMax;

    // ========== 습도 범위 ==========
    @Column(name = "humidity_min", nullable = false)
    private Double humidityMin;

    @Column(name = "humidity_optimal_low", nullable = false)
    private Double humidityOptimalLow;

    @Column(name = "humidity_optimal_high", nullable = false)
    private Double humidityOptimalHigh;

    @Column(name = "humidity_max", nullable = false)
    private Double humidityMax;

    // ========== CO2 범위 ==========
    @Column(name = "co2_min")
    @Builder.Default
    private Double co2Min = 300.0;

    @Column(name = "co2_optimal")
    @Builder.Default
    private Double co2Optimal = 800.0;

    @Column(name = "co2_max")
    @Builder.Default
    private Double co2Max = 1200.0;

    // ========== 광량 범위 ==========
    @Column(name = "light_min")
    @Builder.Default
    private Double lightMin = 200.0;

    @Column(name = "light_optimal")
    @Builder.Default
    private Double lightOptimal = 500.0;

    @Column(name = "light_max")
    @Builder.Default
    private Double lightMax = 1000.0;

    // ========== 토양 수분 범위 ==========
    @Column(name = "soil_moisture_min")
    @Builder.Default
    private Double soilMoistureMin = 30.0;

    @Column(name = "soil_moisture_optimal")
    @Builder.Default
    private Double soilMoistureOptimal = 60.0;

    @Column(name = "soil_moisture_max")
    @Builder.Default
    private Double soilMoistureMax = 80.0;

    // ========== 메모 ==========
    @Column(name = "notes", columnDefinition = "TEXT")
    private String notes;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }
}
