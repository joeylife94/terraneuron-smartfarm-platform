package com.terraneuron.ops.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * 작물 프로필 엔티티
 * 작물별 기본 정보와 생장 단계 목록을 관리
 */
@Entity
@Table(name = "crop_profiles", indexes = {
    @Index(name = "idx_crop_code", columnList = "crop_code"),
    @Index(name = "idx_crop_active", columnList = "is_active")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CropProfile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "crop_code", nullable = false, unique = true, length = 30)
    private String cropCode;

    @Column(name = "crop_name", nullable = false, length = 100)
    private String cropName;

    @Column(name = "crop_name_en", nullable = false, length = 100)
    private String cropNameEn;

    @Column(name = "crop_family", length = 50)
    private String cropFamily;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "total_growth_days")
    private Integer totalGrowthDays;

    @Column(name = "difficulty", length = 20)
    @Builder.Default
    private String difficulty = "MEDIUM";

    @Column(name = "is_active")
    @Builder.Default
    private Boolean isActive = true;

    @OneToMany(mappedBy = "cropProfile", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    @OrderBy("stageOrder ASC")
    @Builder.Default
    private List<GrowthStage> growthStages = new ArrayList<>();

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
}
