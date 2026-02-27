package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.CropProfile;
import com.terraneuron.ops.entity.FarmCrop;
import com.terraneuron.ops.entity.GrowthStage;
import com.terraneuron.ops.repository.CropProfileRepository;
import com.terraneuron.ops.repository.FarmCropRepository;
import com.terraneuron.ops.repository.GrowthStageRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;

/**
 * 작물 관리 서비스
 * - 작물 프로필 CRUD
 * - 농장-작물 매핑 관리
 * - 생장 단계 자동 진행
 * - 작물별 현재 최적 환경 조건 조회 (terra-cortex 연동용)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CropService {

    private final CropProfileRepository cropProfileRepository;
    private final GrowthStageRepository growthStageRepository;
    private final FarmCropRepository farmCropRepository;

    // ========== 작물 프로필 ==========

    public List<CropProfile> getAllActiveCrops() {
        return cropProfileRepository.findByIsActiveTrue();
    }

    public Optional<CropProfile> getCropByCode(String cropCode) {
        return cropProfileRepository.findByCropCode(cropCode);
    }

    public List<GrowthStage> getGrowthStages(String cropCode) {
        return growthStageRepository.findAllByCropCode(cropCode);
    }

    // ========== 농장-작물 매핑 ==========

    public List<FarmCrop> getFarmCrops(String farmId) {
        return farmCropRepository.findActiveCropsByFarmId(farmId);
    }

    public Optional<FarmCrop> getFarmCropByZone(String farmId, String zone) {
        return farmCropRepository.findActiveCropByFarmIdAndZone(farmId, zone);
    }

    @Transactional
    public FarmCrop assignCropToFarm(String farmId, String cropCode, String zone, LocalDate plantedAt) {
        CropProfile crop = cropProfileRepository.findByCropCode(cropCode)
                .orElseThrow(() -> new IllegalArgumentException("작물을 찾을 수 없습니다: " + cropCode));

        LocalDate expectedHarvest = plantedAt.plusDays(crop.getTotalGrowthDays());

        FarmCrop farmCrop = FarmCrop.builder()
                .farmId(farmId)
                .cropProfile(crop)
                .zone(zone)
                .plantedAt(plantedAt)
                .currentStageOrder(1)
                .expectedHarvest(expectedHarvest)
                .status("GROWING")
                .build();

        FarmCrop saved = farmCropRepository.save(farmCrop);
        log.info("🌱 작물 배정: farmId={}, crop={}, zone={}, planted={}", farmId, cropCode, zone, plantedAt);
        return saved;
    }

    @Transactional
    public FarmCrop advanceStage(Long farmCropId) {
        FarmCrop fc = farmCropRepository.findById(farmCropId)
                .orElseThrow(() -> new IllegalArgumentException("Farm crop not found: " + farmCropId));

        List<GrowthStage> stages = growthStageRepository
                .findByCropProfileIdOrderByStageOrderAsc(fc.getCropProfile().getId());

        int maxStage = stages.stream().mapToInt(GrowthStage::getStageOrder).max().orElse(1);

        if (fc.getCurrentStageOrder() >= maxStage) {
            fc.setStatus("HARVESTED");
            log.info("🎉 수확 완료: farmCropId={}", farmCropId);
        } else {
            fc.setCurrentStageOrder(fc.getCurrentStageOrder() + 1);
            GrowthStage newStage = stages.stream()
                    .filter(s -> s.getStageOrder().equals(fc.getCurrentStageOrder()))
                    .findFirst().orElse(null);
            log.info("📈 생장 단계 진행: farmCropId={}, newStage={} ({})",
                    farmCropId, fc.getCurrentStageOrder(),
                    newStage != null ? newStage.getStageName() : "unknown");
        }

        return farmCropRepository.save(fc);
    }

    // ========== terra-cortex 연동: 최적 환경 조건 조회 ==========

    /**
     * 특정 농장의 현재 작물/단계 기반 최적 환경 조건 반환
     * terra-cortex가 HTTP로 호출하여 분석에 활용
     */
    public Map<String, Object> getOptimalConditions(String farmId) {
        List<FarmCrop> activeCrops = farmCropRepository.findActiveCropsByFarmId(farmId);

        if (activeCrops.isEmpty()) {
            return Map.of(
                    "farmId", farmId,
                    "hasCropProfile", false,
                    "message", "등록된 재배 작물이 없습니다. 기본 임계값을 사용합니다."
            );
        }

        List<Map<String, Object>> cropConditions = new ArrayList<>();
        for (FarmCrop fc : activeCrops) {
            GrowthStage stage = getCurrentStageForFarmCrop(fc);
            if (stage == null) continue;

            Map<String, Object> condition = new LinkedHashMap<>();
            condition.put("cropCode", fc.getCropProfile().getCropCode());
            condition.put("cropName", fc.getCropProfile().getCropName());
            condition.put("zone", fc.getZone());
            condition.put("currentStage", stage.getStageName());
            condition.put("stageCode", stage.getStageCode());
            condition.put("stageOrder", stage.getStageOrder());
            condition.put("plantedAt", fc.getPlantedAt().toString());
            condition.put("daysSincePlanting", ChronoUnit.DAYS.between(fc.getPlantedAt(), LocalDate.now()));

            // 센서별 최적 범위
            condition.put("temperature", Map.of(
                    "min", stage.getTempMin(),
                    "optimalLow", stage.getTempOptimalLow(),
                    "optimalHigh", stage.getTempOptimalHigh(),
                    "max", stage.getTempMax()
            ));
            condition.put("humidity", Map.of(
                    "min", stage.getHumidityMin(),
                    "optimalLow", stage.getHumidityOptimalLow(),
                    "optimalHigh", stage.getHumidityOptimalHigh(),
                    "max", stage.getHumidityMax()
            ));
            condition.put("co2", Map.of(
                    "min", stage.getCo2Min(),
                    "optimal", stage.getCo2Optimal(),
                    "max", stage.getCo2Max()
            ));
            condition.put("light", Map.of(
                    "min", stage.getLightMin(),
                    "optimal", stage.getLightOptimal(),
                    "max", stage.getLightMax()
            ));
            condition.put("soilMoisture", Map.of(
                    "min", stage.getSoilMoistureMin(),
                    "optimal", stage.getSoilMoistureOptimal(),
                    "max", stage.getSoilMoistureMax()
            ));

            if (stage.getNotes() != null) {
                condition.put("notes", stage.getNotes());
            }

            cropConditions.add(condition);
        }

        return Map.of(
                "farmId", farmId,
                "hasCropProfile", true,
                "crops", cropConditions,
                "updatedAt", java.time.Instant.now().toString()
        );
    }

    /**
     * 파종일 기반으로 현재 어떤 생장 단계인지 자동 계산
     */
    private GrowthStage getCurrentStageForFarmCrop(FarmCrop fc) {
        List<GrowthStage> stages = fc.getCropProfile().getGrowthStages();
        if (stages == null || stages.isEmpty()) return null;

        long daysSincePlanting = ChronoUnit.DAYS.between(fc.getPlantedAt(), LocalDate.now());
        int cumulativeDays = 0;
        GrowthStage currentStage = stages.get(0);

        for (GrowthStage stage : stages) {
            cumulativeDays += stage.getDurationDays();
            if (daysSincePlanting <= cumulativeDays) {
                currentStage = stage;
                break;
            }
            currentStage = stage; // 마지막 단계 유지 (수확기 이후)
        }

        // DB의 currentStageOrder도 자동 업데이트
        if (!fc.getCurrentStageOrder().equals(currentStage.getStageOrder())) {
            fc.setCurrentStageOrder(currentStage.getStageOrder());
            farmCropRepository.save(fc);
            log.info("📈 자동 단계 진행: farmId={}, crop={}, stage={} ({})",
                    fc.getFarmId(), fc.getCropProfile().getCropCode(),
                    currentStage.getStageOrder(), currentStage.getStageName());
        }

        return currentStage;
    }
}
