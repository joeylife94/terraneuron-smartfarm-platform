package com.terraneuron.sense.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
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

    private static final long MAX_FUTURE_SKEW_SECONDS = 300;

    @NotBlank(message = "sensorId is required")
    @Size(max = 100, message = "sensorId must be at most 100 characters")
    private String sensorId;

    @NotBlank(message = "sensorType is required")
    @Pattern(
            regexp = "temperature|humidity|co2|soilMoisture|light",
            message = "sensorType must be one of temperature, humidity, co2, soilMoisture, light"
    )
    private String sensorType;

    @NotNull(message = "value is required")
    private Double value;

    @NotBlank(message = "unit is required")
    @Size(max = 20, message = "unit must be at most 20 characters")
    private String unit;

    @NotBlank(message = "farmId is required")
    @Size(max = 100, message = "farmId must be at most 100 characters")
    private String farmId;

    @JsonFormat(shape = JsonFormat.Shape.STRING)
    private Instant timestamp;

    @AssertTrue(message = "value is outside the physical range for sensorType")
    @JsonIgnore
    public boolean isValueWithinPhysicalRange() {
        if (value == null || sensorType == null || !Double.isFinite(value)) {
            return value == null || Double.isFinite(value == null ? 0.0 : value);
        }

        return switch (sensorType) {
            case "temperature" -> value >= -50.0 && value <= 80.0;
            case "humidity", "soilMoisture" -> value >= 0.0 && value <= 100.0;
            case "co2" -> value >= 0.0 && value <= 10_000.0;
            case "light" -> value >= 0.0 && value <= 200_000.0;
            default -> true; // @Pattern reports unsupported sensor types.
        };
    }

    @AssertTrue(message = "timestamp cannot be more than 5 minutes in the future")
    @JsonIgnore
    public boolean isTimestampWithinAllowedClockSkew() {
        return timestamp == null || !timestamp.isAfter(Instant.now().plusSeconds(MAX_FUTURE_SKEW_SECONDS));
    }

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
            case "humidity", "soilMoisture" -> "%";
            case "co2" -> "ppm";
            case "light" -> "lux";
            default -> "unit";
        };
    }
}
