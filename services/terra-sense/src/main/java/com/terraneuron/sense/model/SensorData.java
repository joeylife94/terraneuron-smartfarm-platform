package com.terraneuron.sense.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * 센서 데이터 모델
 * IoT 센서에서 수집된 원시 데이터를 표현
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SensorData {
    
    private String sensorId;
    private String sensorType;  // temperature, humidity, co2, etc.
    private Double value;
    private String unit;
    private String farmId;
    
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss'Z'", timezone = "UTC")
    private Instant timestamp;
    
    public static SensorData createSample(String sensorId, String type, Double value) {
        return SensorData.builder()
                .sensorId(sensorId)
                .sensorType(type)
                .value(value)
                .unit(getUnitForType(type))
                .farmId("farm-A")
                .timestamp(Instant.now())
                .build();
    }
    
    private static String getUnitForType(String type) {
        return switch (type) {
            case "temperature" -> "°C";
            case "humidity" -> "%";
            case "co2" -> "ppm";
            default -> "unit";
        };
    }
}
