package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.Insight;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

@Repository
public interface InsightRepository extends JpaRepository<Insight, Long> {
    
    List<Insight> findByFarmId(String farmId);
    
    List<Insight> findByStatus(String status);
    
    List<Insight> findByTimestampBetween(Instant start, Instant end);
    
    List<Insight> findByFarmIdAndStatusOrderByTimestampDesc(String farmId, String status);
    
    List<Insight> findAllByOrderByTimestampDesc();
}
