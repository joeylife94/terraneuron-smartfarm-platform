package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.GrowthStage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface GrowthStageRepository extends JpaRepository<GrowthStage, Long> {

    List<GrowthStage> findByCropProfileIdOrderByStageOrderAsc(Long cropId);

    Optional<GrowthStage> findByCropProfileIdAndStageOrder(Long cropId, Integer stageOrder);

    @Query("SELECT gs FROM GrowthStage gs JOIN gs.cropProfile cp WHERE cp.cropCode = :cropCode AND gs.stageOrder = :stageOrder")
    Optional<GrowthStage> findByCropCodeAndStageOrder(@Param("cropCode") String cropCode, @Param("stageOrder") Integer stageOrder);

    @Query("SELECT gs FROM GrowthStage gs JOIN gs.cropProfile cp WHERE cp.cropCode = :cropCode ORDER BY gs.stageOrder ASC")
    List<GrowthStage> findAllByCropCode(@Param("cropCode") String cropCode);
}
