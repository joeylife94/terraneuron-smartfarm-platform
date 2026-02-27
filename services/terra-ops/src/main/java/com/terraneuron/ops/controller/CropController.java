package com.terraneuron.ops.controller;

import com.terraneuron.ops.entity.CropProfile;
import com.terraneuron.ops.entity.FarmCrop;
import com.terraneuron.ops.entity.GrowthStage;
import com.terraneuron.ops.service.CropService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * 작물 관리 REST API
 * - 작물 프로필 조회
 * - 농장-작물 매핑 관리
 * - 최적 환경 조건 조회 (terra-cortex 연동 핵심 API)
 */
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Crop Management", description = "작물 프로필 및 생장 단계 관리 API")
public class CropController {

    private final CropService cropService;

    // ========== 작물 프로필 ==========

    @GetMapping("/crops")
    @Operation(summary = "활성 작물 목록 조회", description = "등록된 모든 활성 작물 프로필을 반환합니다.")
    public ResponseEntity<List<CropProfile>> getAllCrops() {
        return ResponseEntity.ok(cropService.getAllActiveCrops());
    }

    @GetMapping("/crops/{cropCode}")
    @Operation(summary = "작물 프로필 상세 조회", description = "작물 코드로 프로필 및 생장 단계 정보를 반환합니다.")
    public ResponseEntity<CropProfile> getCropByCode(@PathVariable String cropCode) {
        return cropService.getCropByCode(cropCode)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/crops/{cropCode}/stages")
    @Operation(summary = "생장 단계 목록 조회", description = "특정 작물의 모든 생장 단계별 환경 조건을 반환합니다.")
    public ResponseEntity<List<GrowthStage>> getGrowthStages(@PathVariable String cropCode) {
        List<GrowthStage> stages = cropService.getGrowthStages(cropCode);
        return stages.isEmpty()
                ? ResponseEntity.notFound().build()
                : ResponseEntity.ok(stages);
    }

    // ========== 농장-작물 매핑 ==========

    @GetMapping("/farms/{farmId}/crops")
    @Operation(summary = "농장 재배 작물 조회", description = "특정 농장에서 현재 재배 중인 작물 목록을 반환합니다.")
    public ResponseEntity<List<FarmCrop>> getFarmCrops(@PathVariable String farmId) {
        return ResponseEntity.ok(cropService.getFarmCrops(farmId));
    }

    @PostMapping("/farms/{farmId}/crops")
    @Operation(summary = "작물 배정", description = "농장에 새 작물을 배정합니다.")
    public ResponseEntity<FarmCrop> assignCrop(
            @PathVariable String farmId,
            @RequestBody AssignCropRequest request) {
        FarmCrop result = cropService.assignCropToFarm(
                farmId,
                request.cropCode(),
                request.zone(),
                request.plantedAt() != null ? request.plantedAt() : LocalDate.now()
        );
        return ResponseEntity.ok(result);
    }

    @PutMapping("/farms/{farmId}/crops/{id}/advance-stage")
    @Operation(summary = "생장 단계 수동 진행", description = "해당 작물의 생장 단계를 다음 단계로 진행합니다.")
    public ResponseEntity<FarmCrop> advanceStage(
            @PathVariable String farmId,
            @PathVariable Long id) {
        FarmCrop result = cropService.advanceStage(id);
        return ResponseEntity.ok(result);
    }

    // ========== terra-cortex 연동 핵심 API ==========

    @GetMapping("/farms/{farmId}/optimal-conditions")
    @Operation(summary = "최적 환경 조건 조회",
            description = "현재 작물/생장 단계에 맞는 최적 환경 조건을 반환합니다. terra-cortex가 분석 시 호출합니다.")
    public ResponseEntity<Map<String, Object>> getOptimalConditions(@PathVariable String farmId) {
        return ResponseEntity.ok(cropService.getOptimalConditions(farmId));
    }

    // ========== DTO ==========

    record AssignCropRequest(
            String cropCode,
            String zone,
            LocalDate plantedAt
    ) {}
}
