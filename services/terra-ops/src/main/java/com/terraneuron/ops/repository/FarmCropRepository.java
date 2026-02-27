package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.FarmCrop;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface FarmCropRepository extends JpaRepository<FarmCrop, Long> {

    List<FarmCrop> findByFarmId(String farmId);

    List<FarmCrop> findByFarmIdAndStatus(String farmId, String status);

    @Query("SELECT fc FROM FarmCrop fc JOIN FETCH fc.cropProfile cp LEFT JOIN FETCH cp.growthStages WHERE fc.farmId = :farmId AND fc.status = 'GROWING'")
    List<FarmCrop> findActiveCropsByFarmId(@Param("farmId") String farmId);

    @Query("SELECT fc FROM FarmCrop fc JOIN FETCH fc.cropProfile cp LEFT JOIN FETCH cp.growthStages WHERE fc.farmId = :farmId AND fc.zone = :zone AND fc.status = 'GROWING'")
    Optional<FarmCrop> findActiveCropByFarmIdAndZone(@Param("farmId") String farmId, @Param("zone") String zone);

    @Query("SELECT fc FROM FarmCrop fc JOIN FETCH fc.cropProfile WHERE fc.status = 'GROWING'")
    List<FarmCrop> findAllActiveCrops();

    List<FarmCrop> findByStatus(String status);
}
