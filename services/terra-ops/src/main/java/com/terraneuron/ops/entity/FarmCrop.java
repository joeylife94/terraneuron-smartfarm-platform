package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.time.LocalDate;

/**
 * 농장-작물 매핑 엔티티
 * 어떤 농장(farmId)에서 어떤 작물을 재배 중이며, 현재 어떤 생장 단계인지를 추적
 */
@Entity
@Table(name = "farm_crops", indexes = {
    @Index(name = "idx_fc_farm", columnList = "farm_id"),
    @Index(name = "idx_fc_status", columnList = "status"),
    @Index(name = "idx_fc_crop", columnList = "crop_id")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FarmCrop {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "farm_id", nullable = false, length = 50)
    private String farmId;

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "crop_id", nullable = false)
    private CropProfile cropProfile;

    @Column(name = "zone", length = 50)
    private String zone;

    @Column(name = "planted_at", nullable = false)
    private LocalDate plantedAt;

    @Column(name = "current_stage_order")
    @Builder.Default
    private Integer currentStageOrder = 1;

    @Column(name = "expected_harvest")
    private LocalDate expectedHarvest;

    @Column(name = "status", length = 20)
    @Builder.Default
    private String status = "GROWING";

    @Column(name = "notes", columnDefinition = "TEXT")
    private String notes;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at")
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
        updatedAt = Instant.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }

    /**
     * 현재 생장 단계의 GrowthStage 객체 반환
     */
    @Transient
    public GrowthStage getCurrentGrowthStage() {
        if (cropProfile == null || cropProfile.getGrowthStages() == null) return null;
        return cropProfile.getGrowthStages().stream()
                .filter(gs -> gs.getStageOrder().equals(this.currentStageOrder))
                .findFirst()
                .orElse(null);
    }
}
