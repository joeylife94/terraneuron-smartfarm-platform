package com.terraneuron.ops.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Insight Data Payload from terra-cortex
 * 
 * Maps to the 'data' field of CloudEvents message with type:
 * terra.cortex.insight.detected
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InsightDataPayload {
    
    @JsonProperty("trace_id")
    private String traceId;
    
    @JsonProperty("farm_id")
    private String farmId;
    
    @JsonProperty("asset_id")
    private String assetId;
    
    @JsonProperty("asset_type")
    private String assetType;
    
    @JsonProperty("sensor_type")
    private String sensorType;
    
    @JsonProperty("status")
    private String status;
    
    @JsonProperty("severity")
    private String severity;
    
    @JsonProperty("message")
    private String message;
    
    @JsonProperty("raw_value")
    private Double rawValue;
    
    @JsonProperty("confidence")
    private Double confidence;
    
    @JsonProperty("detected_at")
    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss", timezone = "UTC")
    private String detectedAt;
    
    @JsonProperty("llm_recommendation")
    private String llmRecommendation;
    
    @JsonProperty("rag_context")
    private String ragContext;
    
    /**
     * Validate required fields are present
     */
    public boolean isValid() {
        return farmId != null && !farmId.isBlank() &&
               sensorType != null && !sensorType.isBlank() &&
               status != null && !status.isBlank() &&
               severity != null && !severity.isBlank() &&
               message != null && !message.isBlank() &&
               rawValue != null &&
               confidence != null &&
               confidence >= 0 && confidence <= 1;
    }
}
