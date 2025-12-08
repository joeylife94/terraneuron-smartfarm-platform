package com.terraneuron.ops.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * DTO for Insight data received from Kafka
 * Maps to processed-insights topic from terra-cortex
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InsightDto {

    @JsonProperty("farmId")
    private String farmId;
    
    @JsonProperty("sensorType")
    private String sensorType;

    @JsonProperty("status")
    private String status;
    
    @JsonProperty("severity")
    private String severity;

    @JsonProperty("message")
    private String message;
    
    @JsonProperty("confidence")
    private Double confidence;
    
    @JsonProperty("rawValue")
    private Double rawValue;

    @JsonProperty("detectedAt")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS", timezone = "UTC")
    private Instant timestamp;
}
