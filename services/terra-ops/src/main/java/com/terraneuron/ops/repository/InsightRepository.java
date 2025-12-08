package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.Insight;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;

@Repository
public interface InsightRepository extends JpaRepository<Insight, Long> {
    
    List<Insight> findBySensorId(Long sensorId);
    
    List<Insight> findBySeverity(String severity);
    
    List<Insight> findByDetectedAtBetween(Instant start, Instant end);
    
    List<Insight> findBySensorIdAndSeverityOrderByDetectedAtDesc(Long sensorId, String severity);
}
