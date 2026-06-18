package com.terraneuron.ops.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.dto.InsightDataPayload;
import com.terraneuron.ops.entity.Insight;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.time.temporal.TemporalAccessor;
import java.util.Map;
import java.util.Optional;

/**
 * Parser for Insight Events from Kafka
 * 
 * Handles both:
 * - CloudEvents v1.0 format (canonical): {"specversion": "1.0", "type": "terra.cortex.insight.detected", "data": {...}}
 * - Legacy flat format (deprecated): {"farmId": "...", "status": "..."}
 * 
 * Provides safe parsing with clear error logging.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class InsightEventParser {
    
    private final ObjectMapper objectMapper;
    
    /**
     * Parse a Kafka message into an Insight entity
     * 
     * @param messageData Raw message from Kafka (can be CloudEvents or legacy flat format)
     * @return Optional containing Insight if parsing succeeds, empty if validation fails
     */
    public Optional<Insight> parse(Map<String, Object> messageData) {
        if (messageData == null) {
            log.warn("Cannot parse null message");
            return Optional.empty();
        }
        
        // Try CloudEvents format first (v1.0 envelope + data)
        if (messageData.containsKey("specversion") && messageData.containsKey("type")) {
            return parseCloudEventsFormat(messageData);
        }
        
        // Fall back to legacy flat format
        if (messageData.containsKey("farmId")) {
            return parseLegacyFormat(messageData);
        }
        
        // Neither format matched - malformed event
        log.error("Malformed event - neither CloudEvents nor legacy format: keys={}", messageData.keySet());
        return Optional.empty();
    }
    
    /**
     * Parse CloudEvents v1.0 format
     * Expected structure:
     * {
     *   "specversion": "1.0",
     *   "type": "terra.cortex.insight.detected",
     *   "source": "//terraneuron/terra-cortex",
     *   "id": "uuid",
     *   "time": "RFC3339",
     *   "datacontenttype": "application/json",
     *   "data": { "farm_id": "...", "sensor_type": "...", ... }
     * }
     */
    private Optional<Insight> parseCloudEventsFormat(Map<String, Object> messageData) {
        try {
            String type = (String) messageData.get("type");
            if (type == null || !type.equals("terra.cortex.insight.detected")) {
                log.warn("Unexpected event type for insight: {}", type);
                return Optional.empty();
            }
            
            @SuppressWarnings("unchecked")
            Map<String, Object> dataMap = (Map<String, Object>) messageData.get("data");
            if (dataMap == null || dataMap.isEmpty()) {
                log.error("CloudEvents message missing 'data' field");
                return Optional.empty();
            }
            
            // Parse data payload
            InsightDataPayload payload = objectMapper.convertValue(dataMap, InsightDataPayload.class);
            
            if (!payload.isValid()) {
                log.error("Invalid insight data payload - missing or invalid required fields: farmId={}, sensorType={}, status={}, severity={}, confidence={}",
                        payload.getFarmId(), payload.getSensorType(), payload.getStatus(), payload.getSeverity(), payload.getConfidence());
                return Optional.empty();
            }
            
            // Convert to Insight entity
            Instant timestamp = parseTimestamp(payload.getDetectedAt());
            
            Insight insight = Insight.builder()
                    .farmId(payload.getFarmId())
                    .status(payload.getStatus())
                    .message(payload.getMessage())
                    .llmRecommendation(payload.getLlmRecommendation())
                    .timestamp(timestamp)
                    .build();
            
            log.info("✅ Parsed CloudEvents insight: farmId={}, status={}, severity={}", 
                    payload.getFarmId(), payload.getStatus(), payload.getSeverity());
            
            return Optional.of(insight);
            
        } catch (Exception e) {
            log.error("Failed to parse CloudEvents format insight: {}", e.getMessage(), e);
            return Optional.empty();
        }
    }
    
    /**
     * Parse legacy flat format (deprecated but supported for backward compatibility)
     * Expected structure:
     * {
     *   "farmId": "...",
     *   "sensorType": "...",
     *   "status": "...",
     *   "severity": "...",
     *   "message": "...",
     *   "confidence": 0.95,
     *   "rawValue": 25.5,
     *   "detectedAt": "...",
     *   "llmRecommendation": "..."
     * }
     */
    private Optional<Insight> parseLegacyFormat(Map<String, Object> messageData) {
        try {
            String farmId = (String) messageData.get("farmId");
            String status = (String) messageData.get("status");
            String message = (String) messageData.get("message");
            String llmRec = (String) messageData.get("llmRecommendation");
            Object timestampObj = messageData.get("detectedAt");
            
            if (farmId == null || farmId.isBlank() || status == null || status.isBlank()) {
                log.warn("Legacy format missing required fields: farmId={}, status={}", farmId, status);
                return Optional.empty();
            }
            
            Instant timestamp = parseTimestamp(timestampObj);
            
            Insight insight = Insight.builder()
                    .farmId(farmId)
                    .status(status)
                    .message(message != null ? message : "")
                    .llmRecommendation(llmRec)
                    .timestamp(timestamp)
                    .build();
            
            log.info("⚠️ Parsed LEGACY format insight (deprecated): farmId={}, status={}", farmId, status);
            
            return Optional.of(insight);
            
        } catch (Exception e) {
            log.error("Failed to parse legacy format insight: {}", e.getMessage(), e);
            return Optional.empty();
        }
    }
    
    /**
     * Parse timestamp from various formats
     */
    private Instant parseTimestamp(Object timestampObj) {
        if (timestampObj == null) {
            return Instant.now();
        }
        
        if (timestampObj instanceof Instant) {
            return (Instant) timestampObj;
        }
        
        if (timestampObj instanceof String) {
            try {
                String timestampStr = (String) timestampObj;
                // Try parsing as RFC3339/ISO-8601
                TemporalAccessor ta = DateTimeFormatter.ISO_INSTANT.parse(timestampStr);
                return Instant.from(ta);
            } catch (Exception e) {
                log.warn("Could not parse timestamp string, using now(): {}", timestampObj);
                return Instant.now();
            }
        }
        
        log.warn("Unexpected timestamp type: {}, using now()", timestampObj.getClass().getSimpleName());
        return Instant.now();
    }
}
