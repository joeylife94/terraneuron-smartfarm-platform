package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.CropProfile;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface CropProfileRepository extends JpaRepository<CropProfile, Long> {

    Optional<CropProfile> findByCropCode(String cropCode);

    List<CropProfile> findByIsActiveTrue();

    List<CropProfile> findByDifficulty(String difficulty);

    boolean existsByCropCode(String cropCode);
}
