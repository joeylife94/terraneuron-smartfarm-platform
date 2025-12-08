package com.terraneuron.ops.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

/**
 * Kafka에서 수신하는 인사이트 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InsightDto {

    @JsonProperty("sensorId")
    private String sensorId;

    @JsonProperty("insightType")
    private String insightType;

    private String severity;

    private String message;

    @JsonProperty("confidenceScore")
    private Double confidenceScore;

    @JsonProperty("detectedAt")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'", timezone = "UTC")
    private Instant detectedAt;

    @JsonProperty("rawData")
    private Map<String, Object> rawData;
}
