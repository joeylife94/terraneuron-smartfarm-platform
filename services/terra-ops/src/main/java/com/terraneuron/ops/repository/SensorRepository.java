package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.Sensor;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface SensorRepository extends JpaRepository<Sensor, Long> {
    
    List<Sensor> findByFarmId(Long farmId);
    
    List<Sensor> findBySensorType(String sensorType);
    
    List<Sensor> findByStatus(String status);
}
